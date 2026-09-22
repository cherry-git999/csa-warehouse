"""
BASE Schema and Metadata Models.

Defines the dataset schema, spatial granularity, temporal granularity,
and storage operation contracts for BASE integration.

Architectural Source of Truth (Krishna's diagrams):
- Centralized dataset storage and schema-aware integration.
- Spatial granularity: country, state, district, city, administrative division, GPS.
- Temporal granularity: year, month, day, hour, minute, second, start/end ranges.
- Datasets only provide spatial/temporal fields if they possess those dimensions.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


# ==============================================================================
# SPATIAL GRANULARITY MODEL
# ==============================================================================

class SpatialGranularity(str, Enum):
    """
    Supported spatial granularity levels defined in Krishna's architecture diagrams.
    """
    COUNTRY = "country"
    STATE = "state"
    DISTRICT = "district"
    CITY = "city"
    ADMINISTRATIVE_DIVISION = "administrative_division"
    GPS = "gps"


class DatasetSpatialInfo(BaseModel):
    """
    Spatial dimension metadata for datasets that possess geographic attributes.
    Datasets without spatial data simply omit this or set is_spatial=False.
    """
    is_spatial: bool = False
    granularities: List[SpatialGranularity] = Field(default_factory=list)
    location_columns: List[str] = Field(default_factory=list)
    country_column: Optional[str] = None
    state_column: Optional[str] = None
    district_column: Optional[str] = None
    city_column: Optional[str] = None
    admin_division_column: Optional[str] = None
    latitude_column: Optional[str] = None
    longitude_column: Optional[str] = None
    srid: Optional[int] = 4326  # Default WGS84 for GPS coordinates

    class Config:
        extra = "allow"


# ==============================================================================
# TEMPORAL GRANULARITY MODEL
# ==============================================================================

class TemporalGranularity(str, Enum):
    """
    Supported temporal granularity levels defined in Krishna's architecture diagrams.
    """
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"
    RANGE = "range"


class DatasetTemporalInfo(BaseModel):
    """
    Temporal dimension metadata for datasets that possess time attributes.
    Datasets without temporal data simply omit this or set is_temporal=False.
    """
    is_temporal: bool = False
    granularities: List[TemporalGranularity] = Field(default_factory=list)
    time_columns: List[str] = Field(default_factory=list)
    primary_timestamp_column: Optional[str] = None
    range_start_column: Optional[str] = None
    range_end_column: Optional[str] = None
    timezone: Optional[str] = "UTC"

    class Config:
        extra = "allow"


# ==============================================================================
# DATASET SCHEMA DEFINITION
# ==============================================================================

class ColumnSchema(BaseModel):
    """
    Field-level schema specification for dataset columns.
    """
    name: str
    data_type: str = "string"  # e.g., string, integer, float, datetime, boolean, json
    nullable: bool = True
    description: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False

    class Config:
        extra = "allow"


class DatasetSchemaMetadata(BaseModel):
    """
    Complete schema and granularity metadata for a dataset in BASE.
    Enables schema-aware integration and dataset merging.
    """
    dataset_id: str
    dataset_name: str
    pipeline_id: Optional[str] = None
    version: str = "1.0"
    source: Optional[str] = None  # e.g., erpnext, government, nonprofit, manual
    description: Optional[str] = None
    columns: List[ColumnSchema] = Field(default_factory=list)
    identity_key: Optional[str] = "name"
    spatial_info: Optional[DatasetSpatialInfo] = None
    temporal_info: Optional[DatasetTemporalInfo] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


# ==============================================================================
# OPERATION REQUEST / RESPONSE MODELS
# ==============================================================================

class SaveDatasetRequest(BaseModel):
    """
    Request model for saving a dataset into BASE or compatibility datastore.
    """
    dataset_id: str
    dataset_name: str
    records: List[Dict[str, Any]]
    pipeline_id: Optional[str] = None
    user_id: Optional[str] = None
    identity_key: Optional[str] = "name"
    mode: str = "upsert"  # "upsert" or "replace"
    metadata: Optional[DatasetSchemaMetadata] = None

    class Config:
        extra = "allow"


class FetchDatasetRequest(BaseModel):
    """
    Request model for fetching a dataset from BASE or compatibility datastore.
    """
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    pipeline_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[str]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    class Config:
        extra = "allow"


class MergeDatasetRequest(BaseModel):
    """
    Request model for merging datasets in BASE using identity/granularity rules.
    """
    target_dataset_id: str
    source_dataset_id: Optional[str] = None
    source_records: Optional[List[Dict[str, Any]]] = None
    identity_key: Optional[str] = "name"
    merge_strategy: str = "upsert"  # "upsert", "append", "spatial_join", "temporal_join"
    spatial_resolution: Optional[SpatialGranularity] = None
    temporal_resolution: Optional[TemporalGranularity] = None

    class Config:
        extra = "allow"


class StorageResponse(BaseModel):
    """
    Standard response returned by storage operations (save, merge).
    """
    success: bool
    dataset_id: str
    dataset_name: Optional[str] = None
    record_count: int = 0
    updated: bool = False
    inserted: bool = False
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class CheckpointData(BaseModel):
    """
    Checkpoint representation for pipeline synchronization watermarks.
    """
    pipeline_id: str
    last_sync_timestamp: Optional[str] = None
    last_sync_time: Optional[str] = None
    record_count: int = 0
    status: str = "success"
    execution_id: Optional[str] = None
    source_type: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        extra = "allow"
