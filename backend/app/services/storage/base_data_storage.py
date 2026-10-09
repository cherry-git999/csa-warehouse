"""
BaseDataStorage Contract.

Application-facing abstract interface for dataset storage operations in CSA Warehouse.
Establishes the minimal contract for:
- save_dataset(pipeline_id, records, mode="upsert", identity_key=None) -> StorageResult
- fetch_dataset(pipeline_id, filters=None, columns=None, limit=None, offset=None) -> List[Dict[str, Any]]

All concrete implementations (MongoDB adapter, BASE API service) must implement this contract.
Checkpoints, ETL joins, and data-frame conversions are intentionally excluded from this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from app.schemas.base_schema import StorageResult


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


# ==============================================================================
# BASE DATA STORAGE CONTRACT
# ==============================================================================

class BaseDataStorage(ABC):
    """
    Minimal abstract contract for dataset persistence and retrieval.
    Implementations must enforce strict failure visibility (never swallow errors).
    """

    @abstractmethod
    def save_dataset(
        self,
        pipeline_id: str,
        records: List[Dict[str, Any]],
        mode: str = "upsert",
        identity_key: Optional[str] = None,
    ) -> StorageResult:
        """
        Persist a dataset's records into storage.

        Args:
            pipeline_id: Canonical identifier of the pipeline / dataset.
            records: List of dictionaries representing mapped records.
            mode: Storage mode, either 'upsert' (incremental merge) or 'replace' (snapshot overwrite).
            identity_key: Field used for record matching when mode='upsert'.

        Returns:
            StorageResult detailing operation outcome, record count, and mode.

        Raises:
            BaseStorageError (or subclass): On ANY persistence failure.
        """
        pass

    @abstractmethod
    def fetch_dataset(
        self,
        pipeline_id: str,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch records for a dataset from storage.

        Args:
            pipeline_id: Canonical identifier of the pipeline / dataset.
            filters: Optional key-value equality filters.
            columns: Optional list of column names to project.
            limit: Maximum number of records to return.
            offset: Record offset for pagination.

        Returns:
            List of dictionaries representing dataset records (empty list if not found).

        Raises:
            BaseStorageError (or subclass): On ANY retrieval failure.
        """
        pass
