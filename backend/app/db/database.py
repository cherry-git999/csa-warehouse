import uuid
from pymongo import MongoClient
from ..config.settings import get_database_settings

settings = get_database_settings()

# ------------------ MongoDB Setup ------------------
MONGO_URI = str(settings.mongodb_uri)
client = MongoClient(MONGO_URI)
db = client["fastapi_db"]

users_collection = db["users"]

# Collection for user roles
roles_collection = db["roles"]

# Collection for data from ERP and user
datasets_collection = db["datasets"]

# Collection for dataset information
dataset_information_collection = db["datasets_information"]

# Collection for files
files = db["files"]

# Collection for pipelines
pipelines_collection = db["pipelines"]

# Collection for pipeline execution history
pipelines_history_collection = db["pipelines_history"]

# Collection for synchronization checkpoints / watermarks
sync_checkpoints_collection = db["sync_checkpoints"]

# Collection for endpoint access control
endpoint_access_collection = db["endpoint_access"]

