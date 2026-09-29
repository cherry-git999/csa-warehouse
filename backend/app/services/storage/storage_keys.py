from enum import Enum


class PipelineStatus(str, Enum):
    """Canonical pipeline execution states across the warehouse lifecycle."""
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    NULL = "null"


class PipelineStorageKeys:
    """Canonical MongoDB keys for pipeline execution tracking."""
    # pipelines_history document keys
    EXECUTION_ID = "execution_id"
    PIPELINE_ID = "pipeline_id"
    PIPELINE_NAME = "pipeline_name"
    USER_ID = "user_id"
    STATUS = "status"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    ERROR = "error"

    # pipelines collection keys
    ID = "_id"
    NAME = "pipeline_name"
    IS_ENABLED = "is_enabled"
    HISTORY = "history"


class PipelineDisplayStatus:
    """Canonical display status strings for UI logs and execution records."""
    RUNNING = "Running"
    COMPLETED = "Completed"
    ERROR = "Error"
    UNKNOWN = "Unknown"
