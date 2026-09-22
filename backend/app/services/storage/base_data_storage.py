"""
BaseDataStorage Contract.

Application-facing abstract interface for dataset storage operations in CSA Warehouse.
Establishes the contract for:
- save_dataset
- fetch_dataset
- merge_dataset
- get_checkpoint
- update_checkpoint

All concrete implementations (BASE client service, MongoDB compatibility adapter)
must implement this contract.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union
import pandas as pd

from app.schemas.base_schema import (
    SaveDatasetRequest,
    FetchDatasetRequest,
    MergeDatasetRequest,
    StorageResponse,
)


# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class BaseStorageError(Exception):
    """Base exception for all storage service failures."""
    pass


class BaseConnectionError(BaseStorageError):
    """Raised when connection to the storage service cannot be established."""
    pass


class BaseTimeoutError(BaseStorageError):
    """Raised when a storage operation exceeds the configured timeout."""
    pass


class BaseAuthenticationError(BaseStorageError):
    """Raised when authentication or authorization to storage service fails."""
    pass


class BaseDataValidationError(BaseStorageError):
    """Raised when payload or schema validation fails."""
    pass


# ==============================================================================
# BASE DATA STORAGE INTERFACE
# ==============================================================================

class BaseDataStorage(ABC):
    """
    Abstract contract for dataset persistence, retrieval, merging,
    and checkpoint management.
    """

    @abstractmethod
    def save_dataset(
        self,
        request: Union[SaveDatasetRequest, Dict[str, Any]],
        **kwargs: Any
    ) -> StorageResponse:
        """
        Persist a dataset's records into storage.

        Args:
            request: SaveDatasetRequest model or equivalent dictionary containing:
                     dataset_id, dataset_name, records, mode ("upsert" or "replace"),
                     identity_key, pipeline_id, user_id, optional schema metadata.

        Returns:
            StorageResponse indicating success, record counts, and operation details.

        Raises:
            BaseStorageError: On persistence failure (must never fail silently).
        """
        pass

    @abstractmethod
    def fetch_dataset(
        self,
        request: Union[FetchDatasetRequest, Dict[str, Any], str],
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Fetch records for a dataset from storage.

        Args:
            request: FetchDatasetRequest model, dictionary, or dataset_id / name string.

        Returns:
            List of dictionaries representing dataset records (empty list if not found).

        Raises:
            BaseStorageError: On fetch failure.
        """
        pass

    @abstractmethod
    def merge_dataset(
        self,
        request: Union[MergeDatasetRequest, Dict[str, Any]],
        **kwargs: Any
    ) -> StorageResponse:
        """
        Merge records or another dataset into a target dataset based on identity
        or spatial/temporal resolution rules.

        Args:
            request: MergeDatasetRequest model or equivalent dictionary.

        Returns:
            StorageResponse indicating success, record counts, and operation details.

        Raises:
            BaseStorageError: On merge failure.
        """
        pass

    @abstractmethod
    def get_checkpoint(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest synchronization checkpoint for a pipeline.

        Args:
            pipeline_id: Identifier of the pipeline/dataset.

        Returns:
            Dictionary with checkpoint details (last_sync_timestamp, execution_id, etc.)
            or None if no checkpoint exists.
        """
        pass

    @abstractmethod
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
        Update the synchronization checkpoint for a pipeline.
        Must only be invoked after successful datastore persistence.

        Args:
            pipeline_id: Identifier of the pipeline/dataset.
            last_sync_timestamp: Latest timestamp watermark from source records.
            execution_id: UUID of the current execution.
            record_count: Number of records processed.
            status: Status of the sync operation ("success" or "error").
            source_type: Source system identifier (e.g. "erpnext").

        Returns:
            Dictionary representing the updated checkpoint document.
        """
        pass

    def fetch_dataset_df(
        self,
        request: Union[FetchDatasetRequest, Dict[str, Any], str],
        **kwargs: Any
    ) -> pd.DataFrame:
        """
        Convenience method to retrieve dataset records directly as a pandas DataFrame.
        Useful for dashboards and analytic operations without coupling the interface.
        """
        records = self.fetch_dataset(request, **kwargs)
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)
