import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
import pandas as pd

from app.utils.erp import pull_dataset
from app.services.storage.mongodb_service import (
    store_to_mongodb,
    get_sync_checkpoint,
    update_sync_checkpoint,
)
from app.config.pipeline_mapping import get_pipeline_config
from app.mappings import map_erp_data
from app.config.logging import LoggerMixin
from app.db.database import datasets_collection, pipelines_collection, pipelines_history_collection

# In-memory store for task metadata
tasks: Dict[str, Dict[str, Any]] = {}


class TaskRunner(LoggerMixin):
    def run_pipeline_task(
        self, dataset_id: str, dataset_name: str, user_id: str, exec_id: str, pipeline_id: str = None
    ) -> None:
        self.logger.info(
            f"[Thread: {threading.current_thread().name}] Starting task {exec_id} for dataset {dataset_id}"
        )

        # Add initial "running" entry to pipeline history
        add_pipeline_history_entry(dataset_name, exec_id, "running", user_id)

        target_pipeline_id = pipeline_id or dataset_name

        try:
            # Determine pipeline config (source_type, sync_strategy, identity_key, mapper)
            config = get_pipeline_config(target_pipeline_id)
            source_type = config.get("source_type", "doctype")
            sync_strategy = config.get("sync_strategy", "timestamp" if source_type == "doctype" else "snapshot")
            identity_key = config.get("identity_key", "name" if source_type == "doctype" else None)
            mapper_name = config.get("mapper")

            # Retrieve checkpoint for incremental sync
            since_timestamp = None
            if sync_strategy == "timestamp":
                checkpoint = get_sync_checkpoint(target_pipeline_id)
                if checkpoint and checkpoint.get("sync_status") == "success":
                    since_timestamp = checkpoint.get("last_sync_timestamp")
                    self.logger.info(f"[{exec_id}] Found existing checkpoint for '{target_pipeline_id}': {since_timestamp}")
                else:
                    self.logger.info(f"[{exec_id}] No previous successful checkpoint found for '{target_pipeline_id}'. Running initial full sync.")

            # Pull fresh dataset from ERP (incremental if since_timestamp provided)
            raw_dataset = pull_dataset(target_pipeline_id, since_timestamp=since_timestamp)
            raw_count = len(raw_dataset) if hasattr(raw_dataset, "__len__") else 0
            self.logger.info(f"[{exec_id}] Pulled raw dataset with {raw_count} records.")

            # Apply Phase 3 Dashboard Data Mapping if configured
            mapped_data = map_erp_data(raw_dataset, target_pipeline_id, mapper_name=mapper_name)

            if isinstance(mapped_data, pd.DataFrame):
                dataset_json = mapped_data.to_dict(orient="records")
            elif isinstance(mapped_data, list):
                dataset_json = mapped_data
            else:
                dataset_json = [mapped_data]

            self.logger.info(
                f"[{exec_id}] Prepared {len(dataset_json)} mapped records for storage.")

            # Store/update dataset in MongoDB using upsert/merge or snapshot replacement
            storage_mode = "upsert" if sync_strategy == "timestamp" else "replace"
            result = store_to_mongodb(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                user_id=user_id,
                username="",
                user_email="",
                dataset_records=dataset_json,
                pipeline_id=target_pipeline_id,
                identity_key=identity_key,
                mode=storage_mode,
            )

            if result.get("updated"):
                self.logger.info(
                    f"[{exec_id}] Updated dataset {dataset_id} (total records in DB: {result.get('record_count')}).")
            elif result.get("inserted"):
                self.logger.info(
                    f"[{exec_id}] Created new dataset {dataset_id} (total records in DB: {result.get('record_count')}).")

            # Determine latest watermark timestamp to save
            latest_watermark = datetime.now(timezone.utc).isoformat()
            if dataset_json and isinstance(dataset_json, list):
                modified_dates = [
                    r["modified"] for r in dataset_json
                    if isinstance(r, dict) and "modified" in r and r["modified"]
                ]
                if modified_dates:
                    latest_watermark = str(max(modified_dates))

            # ONLY advance checkpoint after successful storage
            update_sync_checkpoint(
                pipeline_id=target_pipeline_id,
                last_sync_timestamp=latest_watermark,
                execution_id=exec_id,
                record_count=len(dataset_json),
                status="success",
                source_type=source_type,
            )
            self.logger.info(f"[{exec_id}] Checkpoint advanced to {latest_watermark} for '{target_pipeline_id}'.")

            # Update in-memory status
            tasks[exec_id]["status"] = "completed"

            # Add "completed" entry to pipeline history
            add_pipeline_history_entry(
                dataset_name, exec_id, "completed", user_id)

        except Exception as e:
            self.logger.error(
                f"[{exec_id}] Task failed with error: {e}", exc_info=True)

            # Update in-memory status
            tasks[exec_id]["status"] = "error"

            # Add "error" entry to pipeline history (Checkpoint is NOT advanced)
            add_pipeline_history_entry(
                dataset_name, exec_id, "error", user_id)



def add_pipeline_history_entry(pipeline_name: str, exec_id: str, status: str, user_id: str):
    try:
        current_time = datetime.now(timezone.utc).isoformat()

        # Check if pipeline exists
        existing_pipeline = pipelines_collection.find_one(
            {"pipeline_name": pipeline_name})

        if existing_pipeline:
            pipeline_id = existing_pipeline["_id"]

            # Check if history entry already exists for this execution
            existing_history = pipelines_history_collection.find_one({
                "execution_id": exec_id
            })

            if existing_history:
                # Update existing history entry
                pipelines_history_collection.update_one(
                    {"_id": existing_history["_id"]},
                    {
                        "$set": {
                            "status": status,
                            "updated_at": current_time
                        }
                    }
                )
            else:
                # Create new history document
                history_doc = {
                    "execution_id": exec_id,
                    "status": status,
                    "created_at": current_time,
                    "updated_at": current_time
                }
                history_result = pipelines_history_collection.insert_one(
                    history_doc)

                # Add history document ID to pipeline's history array
                pipelines_collection.update_one(
                    {"_id": pipeline_id},
                    {"$push": {"history": history_result.inserted_id}}
                )
        else:
            # Create new pipeline first
            pipeline_doc = {
                "_id": str(uuid.uuid4()),
                "pipeline_name": pipeline_name,
                "is_enabled": True,
                "history": []
            }
            pipeline_result = pipelines_collection.insert_one(pipeline_doc)
            pipeline_id = pipeline_result.inserted_id

            # Create history document
            history_doc = {
                "execution_id": exec_id,
                "status": status,
                "created_at": current_time,
                "updated_at": current_time
            }
            history_result = pipelines_history_collection.insert_one(
                history_doc)

            # Add history document ID to pipeline's history array
            pipelines_collection.update_one(
                {"_id": pipeline_id},
                {"$push": {"history": history_result.inserted_id}}
            )

    except Exception as e:
        print(f"Error adding pipeline history entry: {e}")


task_runner = TaskRunner()


def submit_task(dataset_id: str, dataset_name: str, user_id: str, pipeline_id: str = None) -> Tuple[dict, str]:
    exec_id = str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).isoformat()

    # Check if dataset already exists
    existing_dataset = datasets_collection.find_one({"dataset_id": dataset_id})

    # Note: Pipeline status is now tracked in pipelines_history collection

    tasks[exec_id] = {
        "status": "running",
        "executed_at": current_time,
        "user_id": user_id,
    }

    # Run task in background thread
    thread = threading.Thread(
        target=task_runner.run_pipeline_task,
        args=(dataset_id, dataset_name, user_id, exec_id, pipeline_id),
        name=f"TaskThread-{exec_id[:8]}",
    )
    thread.start()

    return tasks[exec_id], exec_id


def get_user_datasets(user_id: str) -> Dict[str, Any]:
    """
    Get all datasets that a specific user owns
    """
    try:
        cursor = datasets_collection.find({"user_id": user_id})

        documents = []
        for doc in cursor:
            documents.append(
                {
                    "_id": str(doc["_id"]),
                    "dataset_id": doc.get("dataset_id"),
                    "dataset_name": doc.get("dataset_name"),
                    "user_id": doc.get("user_id"),
                    "user_name": doc.get("user_name"),
                    "user_email": doc.get("user_email"),
                    "description": doc.get("description", ""),
                    "created_at": doc.get("created_at"),
                    "updated_at": doc.get("updated_at"),
                    "record_count": doc.get("record_count", 0),
                    "pulled_from_pipeline": doc.get("pulled_from_pipeline", False),
                }
            )

        return {"datasets": documents}

    except Exception as e:
        raise RuntimeError(f"Error fetching user datasets: {e}")
