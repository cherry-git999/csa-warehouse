"""
Data Storage Factory (Compatibility Shim).

DEPRECATION NOTICE:
This module is retained for backward compatibility. New code should use
StorageRouter (app.services.storage.storage_router) for dataset/pipeline-aware
storage backend resolution.

Instantiates and returns the appropriate BaseDataStorage implementation
based on environment configuration (DATA_STORAGE_BACKEND), explicit backend selection,
or delegation to StorageRouter via pipeline_id.
"""

from typing import Optional
from app.config.base_config import get_base_config
from app.services.storage.base_data_storage import BaseDataStorage
from app.services.storage.base_api_storage_service import BaseApiStorageService


def get_data_storage(
    storage_backend: Optional[str] = None,
    pipeline_id: Optional[str] = None,
) -> BaseDataStorage:
    """
    Return the configured BaseDataStorage provider.

    Args:
        storage_backend: Optional override ("mongodb" or "base").
                         If None and pipeline_id is provided, delegates to StorageRouter.
                         If None and pipeline_id is None, uses DATA_STORAGE_BACKEND from configuration.
        pipeline_id: Optional canonical pipeline identifier to route via StorageRouter.

    Returns:
        Instance implementing BaseDataStorage.
    """
    if pipeline_id is not None:
        from app.services.storage.storage_router import get_storage_router
        return get_storage_router().get_storage(pipeline_id)

    config = get_base_config()
    backend = (storage_backend or config.storage_backend).lower().strip()

    if backend == "mongodb":
        from app.services.storage.mongo_data_storage import MongoDataStorage
        return MongoDataStorage()
    elif backend == "base":
        return BaseApiStorageService(config=config)
    else:
        raise ValueError(
            f"Unsupported data storage backend: '{backend}'. "
            f"Supported backends are 'mongodb' and 'base'."
        )
