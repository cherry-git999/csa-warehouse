"""
BASE Configuration.

Defines connection, authentication, transport, and network timeout settings
for the BASE API. Speculative hardcoded endpoint route templates have been
removed in Phase 1 streamlining.
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

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_base_config() -> BaseStorageConfig:
    """
    Cached accessor for BaseStorageConfig instance.
    """
    return BaseStorageConfig()
