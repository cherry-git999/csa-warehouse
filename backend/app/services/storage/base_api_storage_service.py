"""
BaseApiStorageService.

Warehouse-side adapter responsible for calling the BASE (Backend As Storage Engine) API.
Implements the BaseDataStorage interface with isolated transport, configurable endpoints,
and bounded network timeouts.

ARCHITECTURAL RULES:
1. Do not hardcode an invented endpoint contract.
2. Transport, authentication, and endpoint routes are fully configurable.
3. Do not silently fall back to direct MongoDB when BASE fails.
4. Failures are immediately visible to callers so pipeline execution is marked as failed.
5. Checkpoints are only advanced when persistence is explicitly successful.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union
import requests

from app.config.base_config import BaseStorageConfig, get_base_config
from app.schemas.base_schema import (
    SaveDatasetRequest,
    FetchDatasetRequest,
    MergeDatasetRequest,
    StorageResponse,
)
from app.services.storage.base_data_storage import (
    BaseDataStorage,
    BaseStorageError,
    BaseConnectionError,
    BaseTimeoutError,
    BaseAuthenticationError,
    BaseDataValidationError,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# TRANSPORT CLIENT ABSTRACTION
# ==============================================================================

class BaseTransportClient(ABC):
    """
    Abstract transport client for interacting with the BASE API.
    Isolates protocol (HTTP, internal in-process, mock) from storage logic.
    """

    @abstractmethod
    def execute_request(
        self,
        method: str,
        endpoint_template: str,
        path_params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute a request against BASE API.

        Raises:
            BaseStorageError (or subclass) on failure.
        """
        pass


class HttpBaseTransportClient(BaseTransportClient):
    """
    HTTP implementation of BaseTransportClient using bounded requests.Session.
    """

    def __init__(self, config: BaseStorageConfig):
        self.config = config
        self.base_url = config.base_api_url.rstrip("/")
        self.session = requests.Session()
        self._setup_auth()

    def _setup_auth(self) -> None:
        """Configure authentication headers on the session."""
        if self.config.auth_type == "bearer" and self.config.auth_token:
            token = self.config.auth_token.get_secret_value()
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif self.config.auth_type == "api_key" and self.config.api_key:
            key = self.config.api_key.get_secret_value()
            self.session.headers[self.config.api_key_header] = key
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["Accept"] = "application/json"

    def execute_request(
        self,
        method: str,
        endpoint_template: str,
        path_params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        path = endpoint_template.format(**(path_params or {}))
        url = f"{self.base_url}/{path.lstrip('/')}"
        effective_timeout = timeout or self.config.timeout_seconds

        logger.debug(f"[BASE Client] {method.upper()} {url}")

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                json=payload if payload is not None else None,
                params=params,
                timeout=(self.config.connect_timeout_seconds, effective_timeout),
            )
        except requests.exceptions.Timeout as e:
            msg = f"BASE API request timed out after {effective_timeout}s: {e}"
            logger.error(msg)
            raise BaseTimeoutError(msg) from e
        except requests.exceptions.ConnectionError as e:
            msg = f"Failed to connect to BASE API at '{url}': {e}"
            logger.error(msg)
            raise BaseConnectionError(msg) from e
        except requests.exceptions.RequestException as e:
            msg = f"BASE API network error at '{url}': {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

        # Handle HTTP status codes
        if response.status_code in (401, 403):
            msg = f"BASE API authentication failed ({response.status_code}): {response.text}"
            logger.error(msg)
            raise BaseAuthenticationError(msg)

        if response.status_code in (400, 422):
            msg = f"BASE API payload validation error ({response.status_code}): {response.text}"
            logger.error(msg)
            raise BaseDataValidationError(msg)

        if response.status_code >= 400:
            msg = f"BASE API returned error status {response.status_code}: {response.text}"
            logger.error(msg)
            raise BaseStorageError(msg)

        # Parse JSON response
        try:
            return response.json() if response.content else {}
        except Exception as e:
            msg = f"Failed to parse BASE API JSON response from '{url}': {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e


class MockBaseTransportClient(BaseTransportClient):
    """
    In-memory mock transport client for testing BASE architecture
    without an active external BASE service.
    """

    def __init__(self, config: BaseStorageConfig):
        self.config = config
        self.datasets: Dict[str, List[Dict[str, Any]]] = {}
        self.checkpoints: Dict[str, Dict[str, Any]] = {}
        self.call_history: List[Dict[str, Any]] = []

    def execute_request(
        self,
        method: str,
        endpoint_template: str,
        path_params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        self.call_history.append({
            "method": method,
            "endpoint": endpoint_template,
            "path_params": path_params,
            "payload": payload,
            "params": params,
        })

        # Save Dataset
        if "save" in endpoint_template:
            req = payload or {}
            ds_id = req.get("dataset_id", "default")
            records = req.get("records", [])
            self.datasets[ds_id] = list(records)
            return {
                "success": True,
                "dataset_id": ds_id,
                "dataset_name": req.get("dataset_name"),
                "record_count": len(records),
                "updated": True,
                "inserted": False,
                "message": "Saved to Mock BASE",
            }

        # Fetch Dataset
        if "fetch" in endpoint_template:
            req = payload or {}
            ds_id = req.get("dataset_id") or (params.get("dataset_id") if params else None)
            data = self.datasets.get(ds_id, [])
            return {
                "success": True,
                "dataset_id": ds_id,
                "record_count": len(data),
                "data": data,
            }

        # Merge Dataset
        if "merge" in endpoint_template:
            req = payload or {}
            target_id = req.get("target_dataset_id", "default")
            incoming = req.get("source_records", [])
            existing = self.datasets.get(target_id, [])
            # Simple identity merge
            merged = list(existing) + list(incoming)
            self.datasets[target_id] = merged
            return {
                "success": True,
                "dataset_id": target_id,
                "record_count": len(merged),
                "updated": True,
                "message": "Merged in Mock BASE",
            }

        # Checkpoints
        if "checkpoint" in endpoint_template:
            pid = (path_params or {}).get("pipeline_id", "default")
            if method.upper() == "GET":
                return self.checkpoints.get(pid, {})
            elif method.upper() in ("POST", "PUT"):
                self.checkpoints[pid] = payload or {}
                return self.checkpoints[pid]

        return {"success": True}


# ==============================================================================
# BASE API STORAGE SERVICE
# ==============================================================================

class BaseApiStorageService(BaseDataStorage):
    """
    Warehouse-side adapter for BASE (Backend As Storage Engine).
    Implements BaseDataStorage by dispatching to the configured transport client.
    """

    def __init__(
        self,
        config: Optional[BaseStorageConfig] = None,
        transport: Optional[BaseTransportClient] = None,
    ):
        self.config = config or get_base_config()
        if transport is not None:
            self.transport = transport
        elif self.config.transport == "mock":
            self.transport = MockBaseTransportClient(self.config)
        else:
            self.transport = HttpBaseTransportClient(self.config)

    def save_dataset(
        self,
        request: Union[SaveDatasetRequest, Dict[str, Any]],
        **kwargs: Any
    ) -> StorageResponse:
        """
        Persist dataset records by calling BASE API save endpoint.
        Never falls back silently to MongoDB.
        """
        if isinstance(request, dict):
            req_model = SaveDatasetRequest(**request)
        else:
            req_model = request

        payload = req_model.model_dump(exclude_none=True)

        logger.info(
            f"[BASE Adapter] Saving dataset '{req_model.dataset_id}' "
            f"({len(req_model.records)} records) via BASE API..."
        )

        try:
            res_data = self.transport.execute_request(
                method="POST",
                endpoint_template=self.config.endpoint_save,
                payload=payload,
            )
            return StorageResponse(
                success=res_data.get("success", True),
                dataset_id=res_data.get("dataset_id", req_model.dataset_id),
                dataset_name=res_data.get("dataset_name", req_model.dataset_name),
                record_count=res_data.get("record_count", len(req_model.records)),
                updated=res_data.get("updated", False),
                inserted=res_data.get("inserted", False),
                message=res_data.get("message", "Dataset saved successfully in BASE"),
                details=res_data.get("details", {}),
            )
        except BaseStorageError:
            # Re-raise directly to maintain strict failure visibility
            raise
        except Exception as e:
            msg = f"Unexpected failure saving dataset '{req_model.dataset_id}' in BASE: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def fetch_dataset(
        self,
        request: Union[FetchDatasetRequest, Dict[str, Any], str],
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Fetch dataset records from BASE API.
        """
        if isinstance(request, str):
            req_model = FetchDatasetRequest(dataset_id=request)
        elif isinstance(request, dict):
            req_model = FetchDatasetRequest(**request)
        else:
            req_model = request

        payload = req_model.model_dump(exclude_none=True)

        logger.info(f"[BASE Adapter] Fetching dataset '{req_model.dataset_id or req_model.dataset_name}' from BASE...")

        try:
            res_data = self.transport.execute_request(
                method="POST",
                endpoint_template=self.config.endpoint_fetch,
                payload=payload,
            )

            # Support common payload response structures ("data", "records", or root list)
            if isinstance(res_data, list):
                return res_data
            elif "data" in res_data and isinstance(res_data["data"], list):
                return res_data["data"]
            elif "records" in res_data and isinstance(res_data["records"], list):
                return res_data["records"]
            return []
        except BaseStorageError:
            raise
        except Exception as e:
            msg = f"Unexpected failure fetching dataset from BASE: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def merge_dataset(
        self,
        request: Union[MergeDatasetRequest, Dict[str, Any]],
        **kwargs: Any
    ) -> StorageResponse:
        """
        Merge records or datasets in BASE API.
        """
        if isinstance(request, dict):
            req_model = MergeDatasetRequest(**request)
        else:
            req_model = request

        payload = req_model.model_dump(exclude_none=True)

        logger.info(f"[BASE Adapter] Merging into dataset '{req_model.target_dataset_id}' via BASE API...")

        try:
            res_data = self.transport.execute_request(
                method="POST",
                endpoint_template=self.config.endpoint_merge,
                payload=payload,
            )
            return StorageResponse(
                success=res_data.get("success", True),
                dataset_id=res_data.get("dataset_id", req_model.target_dataset_id),
                record_count=res_data.get("record_count", 0),
                updated=res_data.get("updated", True),
                message=res_data.get("message", "Datasets merged successfully in BASE"),
                details=res_data.get("details", {}),
            )
        except BaseStorageError:
            raise
        except Exception as e:
            msg = f"Unexpected failure merging datasets in BASE: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def get_checkpoint(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve synchronization checkpoint from BASE API.
        """
        try:
            res = self.transport.execute_request(
                method="GET",
                endpoint_template=self.config.endpoint_checkpoint_get,
                path_params={"pipeline_id": pipeline_id},
            )
            return res if res else None
        except BaseStorageError:
            raise
        except Exception as e:
            msg = f"Failed to retrieve checkpoint for pipeline '{pipeline_id}' from BASE: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def update_checkpoint(
        self,
        pipeline_id: str,
        last_sync_timestamp: Optional[str] = None,
        execution_id: Optional[str] = None,
        record_count: int = 0,
        status: str = "success",
        source_type: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Update synchronization checkpoint via BASE API.
        """
        payload = {
            "pipeline_id": pipeline_id,
            "last_sync_timestamp": last_sync_timestamp,
            "execution_id": execution_id,
            "record_count": record_count,
            "status": status,
            "source_type": source_type,
            **kwargs,
        }
        try:
            return self.transport.execute_request(
                method="POST",
                endpoint_template=self.config.endpoint_checkpoint_update,
                path_params={"pipeline_id": pipeline_id},
                payload=payload,
            )
        except BaseStorageError:
            raise
        except Exception as e:
            msg = f"Failed to update checkpoint for pipeline '{pipeline_id}' in BASE: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e
