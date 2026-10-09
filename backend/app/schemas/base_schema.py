"""
BASE Storage Schema Models.

Defines the data-transfer objects (DTOs) required by the Warehouse-side
storage abstraction layer. Speculative spatial/temporal hierarchies, join
requests, and checkpoint models have been removed in Phase 1 streamlining.
"""

from pydantic import BaseModel, Field


class StorageResult(BaseModel):
    """
    Standard result returned upon successful dataset persistence.
    Failures raise BaseStorageError and do not return StorageResult.

    Fields:
        pipeline_id: Canonical identifier of the pipeline / dataset.
        record_count: Number of records processed/stored.
        mode: Storage mode used ('upsert' or 'replace').
        message: Human-readable status message.
    """
    pipeline_id: str
    record_count: int = 0
    mode: str = "upsert"
    message: str = ""

    class Config:
        extra = "allow"
