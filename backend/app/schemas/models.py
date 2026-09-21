from typing import List, Optional, Dict, Any, Literal, Annotated, Union
from uuid import UUID
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId


# For API responses, we'll use strings for ObjectIds to avoid JSON schema issues
# The database will still store actual ObjectIds
PyObjectId = str


# --------------------------------- /datasets ---------------------------------


class DatasetDocument(BaseModel):
    """Schema for documents in the datasets collection"""
    data: List[Dict[str, Any]] = Field(..., description="Dataset records")
    columns: List[str] = Field(..., description="Column names")
    record_count: int = Field(...,
                              description="Number of records in the dataset")


class DatasetCardInfo(BaseModel):
    dataset_id: str = Field(...,
                            description="Unique identifier for the dataset")
    dataset_name: str = Field(..., description="Name of the dataset")
    description: str = Field(..., description="Description about the dataset")
    pulled_from_pipeline: bool = Field(
        ..., description="Whether dataset is pulled from a pipeline")
    updated_at: datetime = Field(...,
                                 description="Timestamp when the dataset was updated")
    user_emails: List[str] = Field(
        ..., description="List of user emails associated with the dataset")
    user_names: List[str] = Field(
        ..., description="List of user names associated with the dataset")


class DatasetInfo(BaseModel):
    """Schema representing a single dataset entry"""

    dataset_id: str = Field(...,
                            description="Unique identifier for the dataset")
    dataset_name: str = Field(..., description="Name of the dataset")
    file_id: str = Field(..., description="ID of the file in storage")
    description: str = Field(..., description="Description about the dataset")
    tags: List[str] = Field(...,
                            description="List of tags associated with the dataset")
    dataset_type: str = Field(..., description="Type of the dataset")
    permissions: str = Field(...,
                             description="Permissions associated with the dataset")
    is_spatial: bool = Field(...,
                             description="Whether the dataset has spatial data")
    is_temporal: bool = Field(...,
                              description="Whether the dataset has temporal data")
    pulled_from_pipeline: bool = Field(
        ..., description="Whether dataset is pulled from a pipeline")
    created_at: datetime = Field(...,
                                 description="Timestamp when the dataset is created")
    updated_at: datetime = Field(...,
                                 description="Timestamp when the dataset was updated")
    user_id: List[str] = Field(...,
                               description="List of user IDs associated with the dataset")


class BrowseResponse(BaseModel):
    """Schema representing the response returned when browsing datasets"""

    data: List[DatasetCardInfo]


class ManageResponse(BaseModel):
    data: List[DatasetCardInfo]


# --------------------------------- /datasets/create ---------------------------------


class TemporalGranularity(str, Enum):
    YEAR = "year"
    MONTH = "month"
    DAY = "day"


class SpatialGranularity(str, Enum):
    COUNTRY = "country"
    STATE = "state"
    DISTRICT = "district"
    VILLAGE = "village"
    LAT_LONG = "lat_long"


class CreateDatasetInformationRequest(BaseModel):
    dataset_id: str = Field(...,
                            description="Dataset ID from /datasets/extract")
    file_id: str = Field(..., description="File ID from /datasets/extract")
    dataset_name: str = Field(..., description="Name of the dataset")
    description: str = Field(..., description="Description of the dataset")
    tags: List[str] = Field(..., description="Tags for dataset")
    dataset_type: str = Field(..., description="Type of dataset")
    permission: str = Field(..., description="Access permission")
    is_spatial: bool = Field(..., description="Spatial dataset?")
    is_temporal: bool = Field(..., description="Temporal dataset?")
    temporal_granularities: List[TemporalGranularity] = Field(
        ..., description="Temporal granularities")
    spatial_granularities: List[SpatialGranularity] = Field(
        ..., description="Spatial granularities")
    location_columns: List[str] = Field(..., description="location columns")
    time_columns: List[str] = Field(..., description="time columns")


class CreateDatasetInformationResponse(BaseModel):
    status: str = Field(..., description="Response Status")
    id: str = Field(..., description="Unique identifier for the dataset")


# --------------------------------- /datasets/{dataset_id} ---------------------------------


class DatasetDetail(BaseModel):
    """Schema representing detailed dataset information."""

    dataset_id: str = Field(...,
                            description="Unique identifier for the dataset")
    dataset_name: str = Field(..., description="Name of the dataset")
    file_id: str = Field(..., description="ID of the file in storage")
    description: str = Field(...,
                             description="Optional description of the dataset")
    tags: List[str] = Field(...,
                            description="List of tags associated with the dataset")
    dataset_type: str = Field(..., description="Type of the dataset")
    permissions: str = Field(...,
                             description="Permissions associated with the dataset")
    is_spatial: bool = Field(...,
                             description="Whether the dataset contains spatial data")
    is_temporal: bool = Field(...,
                              description="Whether the dataset contains temporal data")
    temporal_granularities: Optional[List[TemporalGranularity]
                                     ] = Field(..., description="Temporal Granularities")
    spatial_granularities: Optional[List[SpatialGranularity]
                                    ] = Field(..., description="Spatial Granularities")
    location_columns: Optional[List[str]
                               ] = Field(..., description="location columns")
    time_columns: Optional[List[str]] = Field(..., description="time columns")
    pulled_from_pipeline: bool = Field(
        ..., description="Whether the dataset was pulled from a pipeline")
    created_at: datetime = Field(...,
                                 description="Timestamp when the dataset was created")
    updated_at: datetime = Field(...,
                                 description="Timestamp when the dataset was last updated")
    user_names: List[str] = Field(...,
                                  description="List of user names associated with the dataset")
    user_emails: List[str] = Field(...,
                                   description="List of user emails associated with the dataset")
    rows: List[Dict[str, Union[str, int, float, bool, None]]] = Field(
        ..., description="Preview of dataset records (top 10 rows & columns)")


class DatasetInfoResponse(BaseModel):
    """Response schema for fetching dataset details."""

    status: str = Field(..., description="Status of the request")
    data: DatasetDetail


# --------------------------------- /pipelines ---------------------------------

class PipelineStatus(str, Enum):
    """Enum for pipeline status values"""
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    NULL = "null"


class PipelineHistoryItem(BaseModel):
    exec_id: str = Field(..., description="Execution ID of the pipeline run")
    status: PipelineStatus = Field(
        ..., description="Status of the execution (success, failed, running, completed)")
    user_id: str = Field(..., description="User ID who executed the pipeline")
    created_at: datetime = Field(...,
                                 description="Timestamp when the pipeline execution was created")
    updated_at: datetime = Field(...,
                                 description="Timestamp when the pipeline execution was last updated")


class PipelineHistoryDocument(BaseModel):
    """Schema for documents in the pipelines_history collection"""
    model_config = {"arbitrary_types_allowed": True}

    exec_id: str = Field(..., description="Execution ID of the pipeline run")
    status: PipelineStatus = Field(
        ..., description="Status of the execution (success, failed, running, completed)")
    user_id: ObjectId = Field(...,
                              description="User ID who executed the pipeline")
    created_at: datetime = Field(...,
                                 description="Timestamp when the pipeline execution was created")
    updated_at: datetime = Field(...,
                                 description="Timestamp when the pipeline execution was last updated")


class PipelineItem(BaseModel):
    """Internal model for database operations with ObjectId support"""
    model_config = {"arbitrary_types_allowed": True, "populate_by_name": True}

    id: str = Field(..., alias="_id",
                    description="MongoDB unique identifier of the pipeline")
    pipeline_name: str = Field(..., description="Name of the pipeline")
    is_enabled: bool = Field(...,
                             description="Whether the pipeline is enabled")
    pipeline_status: PipelineStatus = Field(
        default=PipelineStatus.NULL, description="Status of the pipeline")
    history: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Pipeline execution history entries")
    history_ids: Optional[List[str]] = Field(
        default=None, description="History entry IDs")
    latest_execution: Optional[Dict[str, Any]] = Field(
        default=None, description="Latest execution details")


class RunPipelineRequest(BaseModel):
    pipeline_id: str = Field(...,
                             description="Unique identifier of the pipeline to run")
    pipeline_name: str = Field(..., description="Name of the pipeline")


class RunPipelineResponse(BaseModel):
    status: PipelineStatus = Field(
        ..., description="The current status of the pipeline")
    execution_id: str = Field(..., description="Execution ID for the pipeline")
    executed_at: str = Field(...,
                             description="Timestamp when the pipeline was executed")


# --------------------------------- /pipelines/status ---------------------------------


class HistoryItem(BaseModel):
    exec_id: str = Field(...,
                         description="Unique execution ID of the pipeline run")
    status: PipelineStatus = Field(
        ..., description="Status of the pipeline run (running, success, failed, error)")
    executed_at: str = Field(...,
                             description="ISO formatted timestamp of execution")
    user: str = Field(..., description="User who executed the pipeline")


class PipelineStatusResponse(BaseModel):
    # history: List[HistoryItem] = Field(..., description = "List of matching pipeline execution history items")
    status: PipelineStatus = Field(..., description="Status of the pipeline")


class ExecutionLogRecord(BaseModel):
    """Record matching the frontend table format for pipeline execution logs"""
    id: str = Field(..., description="Execution ID")
    commands: str = Field(..., description="Pipeline name / command")
    dateTime: str = Field(..., description="Formatted or ISO timestamp")
    user: str = Field(..., description="User name or email")
    status: str = Field(..., description="Status string (Running, Completed, Error)")
    duration: str = Field(..., description="Duration string (e.g. 12s or --)")
    pipeline_id: Optional[str] = Field(None, description="Associated pipeline ID")
    created_at: Optional[str] = Field(None, description="ISO timestamp of creation")
    updated_at: Optional[str] = Field(None, description="ISO timestamp of update")
    error: Optional[str] = Field(None, description="Error message if execution failed")


class PipelineStatistics(BaseModel):
    """Aggregate statistics derived directly from execution history"""
    total_executions: int = Field(default=0, description="Total pipeline executions")
    successful_executions: int = Field(default=0, description="Successful executions")
    failed_executions: int = Field(default=0, description="Failed executions")
    running_executions: int = Field(default=0, description="Currently running executions")


class PipelineHistoryResponse(BaseModel):
    """Response containing aggregate statistics and detailed execution history"""
    statistics: PipelineStatistics
    executions: List[ExecutionLogRecord]


class GetPipelinesResponse(BaseModel):
    """Response model for the simplified pipelines endpoint"""
    data: List[PipelineItem] = Field(
        ..., description="List of pipelines")


# --------------------------------- /presignedURL ---------------------------------


class PresignedURLResponse(BaseModel):
    upload_url: str = Field(...,
                            description="Presigned URL to upload the file")
    object_name: str = Field(..., description="Object name in storage")


# --------------------------------- /datasets/extract ---------------------------------


class ExtractCsvDataRequest(BaseModel):
    file_object: str = Field(...,
                             description="MinIO object name (path) of the file")


class ExtractAndStoreResponse(BaseModel):
    status: str = Field(..., description="Response Status")
    file_id: str = Field(..., description="File ID from files collection")
    dataset_id: str = Field(...,
                            description="Dataset ID from datasets collection")


# --------------------------------- /datasets/columns ---------------------------------


class DatasetColumnsRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset identifier")
    search: str | None = Field(
        None, description="Optional search string to filter columns")


class DatasetColumnsResponse(BaseModel):
    columns: List[str] = Field(...,
                               description="List of dataset column names (filtered)")


class Tag(BaseModel):
    id: int = Field(..., description="Unique identifier of the tag", example=123)
    name: str = Field(..., description="Name of the tag")


class Role(BaseModel):
    """
    Role object representing a user role.
    """

    role_name: str = Field(..., description="Name of the role")
    description: str | None = Field(
        None, description="Description of the role")
    is_active: bool = Field(
        default=True, description="Whether the role is active")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the role was created")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the role was last updated")


class User(BaseModel):
    """
    User object.
    """
    model_config = {"arbitrary_types_allowed": True, "populate_by_name": True}

    first_name: Optional[str] = Field(
        None, description="First name of the user")
    last_name: Optional[str] = Field(None, description="Last name of the user")
    email: Optional[str] = Field(
        None, description="Email address", example="name@email.com")
    phone: Optional[str] = Field(None, description="Phone number")
    external_id: str = Field(...,
                             description="External ID from OAuth provider (e.g., Google sub)")
    role_ids: List[PyObjectId] = Field(
        default_factory=list,
        alias="role_id",
        description="List of Role IDs from roles collection")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the user was created")
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the user was last updated")

    @property
    def role_id(self) -> List[PyObjectId]:
        return self.role_ids


class CreateUserFromOAuth(BaseModel):
    """
    Schema for creating user from OAuth provider data.
    """

    first_name: Optional[str] = Field(
        None, description="First name of the user")
    last_name: Optional[str] = Field(None, description="Last name of the user")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    external_id: str = Field(...,
                             description="External ID from OAuth provider (e.g., Google sub)")


class UserResponse(BaseModel):
    """
    User response object.
    """
    model_config = {"arbitrary_types_allowed": True, "populate_by_name": True}

    id: str = Field(..., description="Unique user ID (UUID)")
    first_name: Optional[str] = Field(
        None, description="First name of the user")
    last_name: Optional[str] = Field(None, description="Last name of the user")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    external_id: str = Field(...,
                             description="External ID from OAuth provider")
    role_ids: List[PyObjectId] = Field(
        default_factory=list,
        alias="role_id",
        description="List of Role IDs assigned to the user")
    created_at: datetime = Field(...,
                                 description="Timestamp when the user was created")
    updated_at: datetime = Field(...,
                                 description="Timestamp when the user was last updated")

    @property
    def role_id(self) -> List[PyObjectId]:
        return self.role_ids


class ApiResponse(BaseModel):
    """
    Generic API response.
    """

    code: Optional[int] = Field(None, description="Response code", example=200)
    type: Optional[str] = Field(None, description="Type of response")
    message: Optional[str] = Field(
        None, description="Message accompanying the response")


class EndpointAccess(BaseModel):
    """
    Endpoint access control object.
    """

    role: str = Field(..., description="Role name")
    endpoint: str = Field(..., description="Endpoint path pattern")
    viewer: bool = Field(default=False, description="Viewer permission")
    contributor: bool = Field(
        default=False, description="Contributor permission")
    admin: bool = Field(default=False, description="Admin permission")
    created_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the access control was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Timestamp when the access control was last updated"
    )


class RoleCheckRequest(BaseModel):
    """
    Request schema for role checking.
    """

    path: str = Field(..., description="Path to check access for")


class RoleCheckResponse(BaseModel):
    """
    Response schema for role checking.
    """

    viewer: bool = Field(default=False, description="Viewer permission")
    contributor: bool = Field(
        default=False, description="Contributor permission")
    admin: bool = Field(default=False, description="Admin permission")
    role_name: Optional[str] = Field(None, description="User's role name")


class Error(BaseModel):
    """
    Error response object.
    """

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
