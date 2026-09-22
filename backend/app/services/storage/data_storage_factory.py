"""
Data Storage Factory.

Instantiates and returns the appropriate BaseDataStorage implementation
based on environment configuration (DATA_STORAGE_BACKEND) or explicit selection.

Default is 'mongodb' to preserve existing behavior and guarantee zero regression.
When switching to 'base', BaseApiStorageService is used.

DEFERRED IMPORTS: MongoDataStorage is imported lazily inside get_data_storage()
so that importing data_storage_factory does not initialize MongoDB when BASE is used.
"""

from typing import Optional
from app.config.base_config import get_base_config
from app.services.storage.base_data_storage import BaseDataStorage
from app.services.storage.base_api_storage_service import BaseApiStorageService


def get_data_storage(storage_backend: Optional[str] = None) -> BaseDataStorage:
    """
    Return the configured BaseDataStorage provider.

    Args:
        storage_backend: Optional override ("mongodb" or "base").
                         If None, uses DATA_STORAGE_BACKEND from configuration.

    Returns:
        Instance implementing BaseDataStorage.
    """
    config = get_base_config()
    backend = (storage_backend or config.storage_backend).lower().strip()

    if backend == "mongodb":
        # Lazy import preserves total isolation for BASE operations and prevents import-time side effects
        from app.services.storage.mongo_data_storage import MongoDataStorage
        return MongoDataStorage()
    elif backend == "base":
        return BaseApiStorageService(config=config)
    else:
        raise ValueError(
            f"Unsupported data storage backend: '{backend}'. "
            f"Supported backends are 'mongodb' and 'base'."
        )
