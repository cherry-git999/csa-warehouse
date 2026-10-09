"""
Storage Router for CSA Warehouse.

Routes dataset persistence and retrieval operations to the appropriate
BaseDataStorage implementation (MongoDataStorage or BaseApiStorageService)
based on pipeline configuration in PIPELINE_CONFIG.

ARCHITECTURAL RULES:
1. Canonical identifier is pipeline_id.
2. stock_inventory is excluded from the current BASE migration scope and ALWAYS routes to MongoDataStorage.
3. Unknown pipeline_id raises an explicit configuration error.
4. Missing storage_backend in PIPELINE_CONFIG defaults safely to 'mongodb'.
5. Unsupported storage_backend (e.g. 'postgres', 'redis') raises an explicit configuration error.
6. Lazy instantiation ensures importing this module causes zero database or network side effects.
"""

import logging
from typing import Optional

from app.config.pipeline_mapping import PIPELINE_CONFIG
from app.services.storage.base_data_storage import BaseDataStorage

logger = logging.getLogger(__name__)


class StorageRouterError(ValueError):
    """Base exception for StorageRouter resolution errors."""
    pass


class UnknownPipelineError(StorageRouterError, KeyError):
    """Raised when a pipeline_id is not registered in PIPELINE_CONFIG."""
    pass


class UnsupportedStorageBackendError(StorageRouterError):
    """Raised when an explicit storage_backend is not supported."""
    pass


class StorageRouter:
    """
    Dataset-aware storage router directing persistence and retrieval calls
    to either MongoDataStorage or BaseApiStorageService based on pipeline configuration.
    """

    SUPPORTED_BACKENDS = {"mongodb", "base"}

    def __init__(self):
        self._mongo_storage: Optional[BaseDataStorage] = None
        self._base_storage: Optional[BaseDataStorage] = None

    def _get_mongo(self) -> BaseDataStorage:
        """Lazily instantiate MongoDataStorage to prevent import-time side effects."""
        if self._mongo_storage is None:
            from app.services.storage.mongo_data_storage import MongoDataStorage
            self._mongo_storage = MongoDataStorage()
        return self._mongo_storage

    def _get_base(self) -> BaseDataStorage:
        """Lazily instantiate BaseApiStorageService to prevent network side effects."""
        if self._base_storage is None:
            from app.services.storage.base_api_storage_service import BaseApiStorageService
            self._base_storage = BaseApiStorageService()
        return self._base_storage

    def get_storage(self, pipeline_id: str) -> BaseDataStorage:
        """
        Resolve the storage backend for a given pipeline_id.

        Args:
            pipeline_id: Canonical pipeline identifier.

        Returns:
            An instance conforming to BaseDataStorage (MongoDataStorage or BaseApiStorageService).

        Raises:
            UnknownPipelineError: If pipeline_id is not registered in PIPELINE_CONFIG.
            UnsupportedStorageBackendError: If storage_backend is invalid/unsupported.
        """
        if not pipeline_id or pipeline_id not in PIPELINE_CONFIG:
            raise UnknownPipelineError(
                f"Unknown pipeline_id '{pipeline_id}'. "
                f"Pipeline is not registered in PIPELINE_CONFIG."
            )

        # STRICT GUARDRAIL: stock_inventory is excluded from the current BASE migration scope
        if pipeline_id == "stock_inventory":
            return self._get_mongo()

        cfg = PIPELINE_CONFIG[pipeline_id]
        backend_raw = cfg.get("storage_backend")

        # Missing storage_backend defaults to 'mongodb' for backward compatibility
        if backend_raw is None or str(backend_raw).strip() == "":
            return self._get_mongo()

        backend = str(backend_raw).lower().strip()

        if backend == "mongodb":
            return self._get_mongo()
        elif backend == "base":
            return self._get_base()
        else:
            raise UnsupportedStorageBackendError(
                f"Unsupported storage backend '{backend_raw}' configured for pipeline '{pipeline_id}'. "
                f"Supported backends are 'mongodb' and 'base'."
            )


# Module-level singleton accessor
_router_instance: Optional[StorageRouter] = None


def get_storage_router() -> StorageRouter:
    """
    Get the singleton StorageRouter instance.
    Lazy initialization ensures zero database or network side effects at import time.
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = StorageRouter()
    return _router_instance
