"""
BASE Configuration.

Defines connection, authentication, transport, timeouts, and endpoint templates
for the BASE API without hardcoding unconfirmed endpoint assumptions.
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class BaseStorageConfig(BaseSettings):
    """
    Configuration settings for BASE (Backend As Storage Engine) integration.
    All properties can be overridden using environment variables.
    """
    # Active storage backend: "mongodb" (default compatibility mode) or "base"
    storage_backend: str = Field(default="mongodb", env="DATA_STORAGE_BACKEND")

    # BASE API Root URL (e.g. "http://localhost:8080" or "http://base.internal")
    base_api_url: str = Field(default="http://localhost:8080", env="BASE_API_URL")

    # Transport mechanism: "http", "internal", or "mock"
    transport: str = Field(default="http", env="BASE_TRANSPORT")

    # Authentication type: "none", "bearer", or "api_key"
    auth_type: str = Field(default="none", env="BASE_AUTH_TYPE")
    auth_token: Optional[SecretStr] = Field(default=None, env="BASE_AUTH_TOKEN")
    api_key: Optional[SecretStr] = Field(default=None, env="BASE_API_KEY")
    api_key_header: str = Field(default="X-API-Key", env="BASE_API_KEY_HEADER")

    # Network timeouts: bounded to prevent pipeline stalling
    timeout_seconds: float = Field(default=15.0, env="BASE_TIMEOUT_SECONDS")
    connect_timeout_seconds: float = Field(default=5.0, env="BASE_CONNECT_TIMEOUT_SECONDS")
    max_retries: int = Field(default=1, env="BASE_MAX_RETRIES")

    # Configurable Endpoint Templates (avoids hardcoding unconfirmed routes)
    endpoint_save: str = Field(
        default="/api/v1/datasets/save",
        env="BASE_ENDPOINT_SAVE",
        description="Path or URL template for saving dataset records"
    )
    endpoint_fetch: str = Field(
        default="/api/v1/datasets/fetch",
        env="BASE_ENDPOINT_FETCH",
        description="Path or URL template for fetching dataset records"
    )
    endpoint_merge: str = Field(
        default="/api/v1/datasets/merge",
        env="BASE_ENDPOINT_MERGE",
        description="Path or URL template for merging dataset records"
    )
    endpoint_checkpoint_get: str = Field(
        default="/api/v1/checkpoints/{pipeline_id}",
        env="BASE_ENDPOINT_CHECKPOINT_GET",
        description="Path or URL template for retrieving checkpoint"
    )
    endpoint_checkpoint_update: str = Field(
        default="/api/v1/checkpoints/{pipeline_id}",
        env="BASE_ENDPOINT_CHECKPOINT_UPDATE",
        description="Path or URL template for updating checkpoint"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_base_config() -> BaseStorageConfig:
    """
    Cached accessor for BaseStorageConfig instance.
    """
    return BaseStorageConfig()
