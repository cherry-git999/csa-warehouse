"""
BaseApiStorageService.

Warehouse-side adapter responsible for calling the BASE (Backend As Storage Engine) API.
Implements the BaseDataStorage interface with isolated transport, configurable connection settings,
and bounded network timeouts.

ARCHITECTURAL RULES:
1. Do not hardcode or invent an unconfirmed endpoint contract.
2. The real HTTP contract will be bound when the official BASE specification is published.
3. Strict failure visibility: Never fall back silently to MongoDB when BASE fails.
4. Failures are immediately raised as BaseStorageError or its subclasses.
5. Mock transport client is retained for offline validation and testing.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import requests

from app.config.base_config import BaseStorageConfig, get_base_config
from app.schemas.base_schema import StorageResult
from app.services.storage.base_data_storage import (
    BaseDataStorage,
    BaseStorageError,
    BaseConnectionError,
    BaseTimeoutError,
    BaseAuthenticationError,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# TRANSPORT CLIENT ABSTRACTION
# ==============================================================================

class BaseTransportClient(ABC):
    """
    Abstract transport client for interacting with the BASE API.
    Isolates protocol (HTTP, mock) from storage logic.
    """

    @abstractmethod
    def execute_request(
        self,
        method: str,
        path: str,
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
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
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

        if response.status_code in (401, 403):
            msg = f"BASE API authentication failed ({response.status_code}): {response.text}"
            logger.error(msg)
            raise BaseAuthenticationError(msg)

        if response.status_code >= 400:
            msg = f"BASE API returned error status {response.status_code}: {response.text}"
            logger.error(msg)
            raise BaseStorageError(msg)

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

    def __init__(self, config: Optional[BaseStorageConfig] = None):
        self.config = config or get_base_config()
        self.datasets: Dict[str, List[Dict[str, Any]]] = {}
        self.call_history: List[Dict[str, Any]] = []

    def execute_request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        self.call_history.append({
            "method": method,
            "path": path,
            "payload": payload,
            "params": params,
        })

        # Save Dataset Simulation
        if method.upper() in ("POST", "PUT") and "save" in path:
            req = payload or {}
            pipeline_id = req.get("pipeline_id", "default")
            records = req.get("records", [])
            mode = req.get("mode", "upsert")
            identity_key = req.get("identity_key")

            if mode == "replace" or not identity_key:
                self.datasets[pipeline_id] = list(records)
            else:
                # In-memory identity upsert
                existing = list(self.datasets.get(pipeline_id, []))
                key_to_idx = {
                    r[identity_key]: idx for idx, r in enumerate(existing)
                    if isinstance(r, dict) and identity_key in r
                }
                for inc in records:
                    if isinstance(inc, dict) and identity_key in inc and inc[identity_key] in key_to_idx:
                        existing[key_to_idx[inc[identity_key]]] = inc
                    else:
                        existing.append(inc)
                self.datasets[pipeline_id] = existing

            return {
                "success": True,
                "pipeline_id": pipeline_id,
                "record_count": len(self.datasets[pipeline_id]),
                "message": "Saved to Mock BASE",
            }

        # Fetch Dataset Simulation
        if method.upper() == "GET" or "fetch" in path:
            pipeline_id = (params or {}).get("pipeline_id") or path.split("/")[-1]
            data = self.datasets.get(pipeline_id, [])
            return {
                "success": True,
                "pipeline_id": pipeline_id,
                "record_count": len(data),
                "records": data,
            }

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
        pipeline_id: str,
        records: List[Dict[str, Any]],
        mode: str = "upsert",
        identity_key: Optional[str] = None,
    ) -> StorageResult:
        """
        Persist dataset records via BASE API.
        Enforces strict failure visibility: never falls back to MongoDB.

        Args:
            pipeline_id: Canonical pipeline identifier.
            records: List of normalized records to save.
            mode: 'upsert' or 'replace'.
            identity_key: Optional merge key for upsert mode.

        Returns:
            StorageResult on successful persistence.

        Raises:
            BaseStorageError: On ANY failure.
        """
        payload = {
            "pipeline_id": pipeline_id,
            "records": records,
            "mode": mode,
            "identity_key": identity_key,
        }

        logger.info(
            f"[BASE Adapter] Saving dataset '{pipeline_id}' "
            f"({len(records)} records, mode='{mode}') via BASE API..."
        )

        # Transport dispatch; failure will raise BaseStorageError and NOT fall back to MongoDB
        res_data = self.transport.execute_request(
            method="POST",
            path="datasets/save",
            payload=payload,
        )

        return StorageResult(
            pipeline_id=pipeline_id,
            record_count=res_data.get("record_count", len(records)),
            mode=mode,
            message=res_data.get("message", "Dataset successfully saved in BASE"),
        )

    def fetch_dataset(
        self,
        pipeline_id: str,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch dataset records from BASE API.

        Args:
            pipeline_id: Canonical pipeline identifier.
            filters: Optional key-value equality filters.
            columns: Optional list of projected column names.
            limit: Maximum records to return.
            offset: Record offset for pagination.

        Returns:
            List of record dictionaries.

        Raises:
            BaseStorageError: On ANY retrieval failure.
        """
        logger.info(f"[BASE Adapter] Fetching dataset '{pipeline_id}' via BASE API...")

        params = {"pipeline_id": pipeline_id}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        res_data = self.transport.execute_request(
            method="GET",
            path=f"datasets/fetch/{pipeline_id}",
            params=params,
        )

        records = res_data.get("records") or res_data.get("data") or []

        # Client-side filtering and projection if returned from mock/generic endpoint
        if filters:
            records = [
                r for r in records
                if all(r.get(k) == v for k, v in filters.items())
            ]
        if columns:
            records = [
                {k: r.get(k) for k in columns if k in r}
                for r in records
            ]

        return records
