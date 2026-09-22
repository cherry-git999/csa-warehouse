"""
MongoDataStorage Compatibility Adapter.

Implements the BaseDataStorage interface by delegating to the existing, verified
MongoDB storage functions (mongodb_service.py).

ARCHITECTURAL RULES:
1. Preserve existing MongoDB schemas:
   - datasets
   - datasets_information
   - sync_checkpoints
2. Do not change existing dashboard business logic or pipeline history.
3. Provides a reference compatibility layer to compare against BASE-backed behavior.
4. This adapter is a migration compatibility bridge, NOT the final production BASE architecture.
5. DEFERRED IMPORTS: Does not import database.py or mongodb_service.py at module level
   to prevent premature MongoClient initialization and network side effects at import time.
"""

import logging
from typing import Optional, List, Dict, Any, Union
from bson import ObjectId

from app.schemas.base_schema import (
    SaveDatasetRequest,
    FetchDatasetRequest,
    MergeDatasetRequest,
    StorageResponse,
)
from app.services.storage.base_data_storage import (
    BaseDataStorage,
    BaseStorageError,
)

logger = logging.getLogger(__name__)


class MongoDataStorage(BaseDataStorage):
    """
    MongoDB Compatibility Adapter implementing BaseDataStorage.
    Delegates directly to existing MongoDB collections and services using lazy execution.
    """

    def save_dataset(
        self,
        request: Union[SaveDatasetRequest, Dict[str, Any]],
        **kwargs: Any
    ) -> StorageResponse:
        """
        Save dataset records using the existing store_to_mongodb function.
        """
        # Lazy import to avoid import-time database side effects
        from app.services.storage.mongodb_service import store_to_mongodb

        if isinstance(request, dict):
            req_model = SaveDatasetRequest(**request)
        else:
            req_model = request

        try:
            result = store_to_mongodb(
                dataset_id=req_model.dataset_id,
                dataset_name=req_model.dataset_name,
                user_id=req_model.user_id or str(ObjectId()),
                username="",
                user_email="",
                dataset_records=req_model.records,
                pipeline_id=req_model.pipeline_id,
                identity_key=req_model.identity_key,
                mode=req_model.mode,
            )

            record_count = result.get("record_count", len(req_model.records))
            updated = bool(result.get("updated", False))
            inserted = bool(result.get("inserted", False))

            return StorageResponse(
                success=True,
                dataset_id=str(result.get("dataset_id") or req_model.dataset_id),
                dataset_name=result.get("dataset_name") or req_model.dataset_name,
                record_count=record_count,
                updated=updated,
                inserted=inserted,
                message="Dataset successfully saved in MongoDB",
                details=result,
            )
        except Exception as e:
            msg = f"Failed to save dataset '{req_model.dataset_id}' in MongoDB: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def fetch_dataset(
        self,
        request: Union[FetchDatasetRequest, Dict[str, Any], str],
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Fetch dataset records from the MongoDB datasets collection.
        Resolves dataset by ID, dataset_name, or pipeline_id.
        """
        # Lazy import to avoid import-time database side effects
        from app.db.database import (
            datasets_collection,
            dataset_information_collection,
        )

        if isinstance(request, str):
            req_model = FetchDatasetRequest(dataset_id=request)
        elif isinstance(request, dict):
            req_model = FetchDatasetRequest(**request)
        else:
            req_model = request

        target_id = req_model.dataset_id
        target_name = req_model.dataset_name
        pipeline_id = req_model.pipeline_id

        try:
            # 1. If target_id provided, look up datasets_collection directly
            if target_id:
                oid = ObjectId(target_id) if ObjectId.is_valid(target_id) else target_id
                doc = datasets_collection.find_one({"_id": oid})
                if not doc and oid != target_id:
                    doc = datasets_collection.find_one({"_id": target_id})
                if doc and "data" in doc:
                    records = doc["data"]
                    return self._apply_filters_and_slices(records, req_model)

            # 2. Look up via datasets_information collection
            query_conditions = []
            if target_id:
                oid = ObjectId(target_id) if ObjectId.is_valid(target_id) else target_id
                query_conditions.append({"dataset_id": oid})
                query_conditions.append({"dataset_id": target_id})
            if target_name:
                query_conditions.append({"dataset_name": target_name})
            if pipeline_id:
                query_conditions.append({"pipeline_id": pipeline_id})
                if ObjectId.is_valid(pipeline_id):
                    query_conditions.append({"pipeline_id": ObjectId(pipeline_id)})

            if query_conditions:
                info = dataset_information_collection.find_one({"$or": query_conditions})
                if info and "dataset_id" in info:
                    doc = datasets_collection.find_one({"_id": info["dataset_id"]})
                    if doc and "data" in doc:
                        records = doc["data"]
                        return self._apply_filters_and_slices(records, req_model)

            # 3. Fallback: check if target_name or pipeline_id is stored directly as _id
            search_key = target_name or pipeline_id
            if search_key:
                doc = datasets_collection.find_one({"_id": search_key})
                if doc and "data" in doc:
                    records = doc["data"]
                    return self._apply_filters_and_slices(records, req_model)

            return []
        except Exception as e:
            msg = f"Failed to fetch dataset from MongoDB: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def merge_dataset(
        self,
        request: Union[MergeDatasetRequest, Dict[str, Any]],
        **kwargs: Any
    ) -> StorageResponse:
        """
        Merge records into target dataset in MongoDB using upsert logic.
        """
        if isinstance(request, dict):
            req_model = MergeDatasetRequest(**request)
        else:
            req_model = request

        try:
            records = req_model.source_records or []
            if not records and req_model.source_dataset_id:
                records = self.fetch_dataset(req_model.source_dataset_id)

            save_req = SaveDatasetRequest(
                dataset_id=req_model.target_dataset_id,
                dataset_name=req_model.target_dataset_id,
                records=records,
                identity_key=req_model.identity_key,
                mode="upsert",
            )
            return self.save_dataset(save_req)
        except Exception as e:
            msg = f"Failed to merge records into dataset '{req_model.target_dataset_id}' in MongoDB: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def get_checkpoint(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve sync checkpoint using existing get_sync_checkpoint.
        """
        # Lazy import to avoid import-time database side effects
        from app.services.storage.mongodb_service import get_sync_checkpoint

        try:
            return get_sync_checkpoint(pipeline_id)
        except Exception as e:
            msg = f"Failed to get checkpoint for pipeline '{pipeline_id}' from MongoDB: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def update_checkpoint(
        self,
        pipeline_id: str,
        last_sync_timestamp: Optional[str] = None,
        execution_id: Optional[str] = None,
        record_count: int = 0,
        status: str = "success",
        source_type: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Update sync checkpoint using existing update_sync_checkpoint.
        """
        # Lazy import to avoid import-time database side effects
        from app.services.storage.mongodb_service import update_sync_checkpoint

        try:
            return update_sync_checkpoint(
                pipeline_id=pipeline_id,
                last_sync_timestamp=last_sync_timestamp,
                execution_id=execution_id,
                record_count=record_count,
                status=status,
                source_type=source_type,
            )
        except Exception as e:
            msg = f"Failed to update checkpoint for pipeline '{pipeline_id}' in MongoDB: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def _apply_filters_and_slices(
        self,
        records: List[Dict[str, Any]],
        req: FetchDatasetRequest
    ) -> List[Dict[str, Any]]:
        """Filter, project columns, and paginate in-memory records."""
        result = records

        # Filter by key-value if provided
        if req.filters:
            result = [
                r for r in result
                if all(r.get(k) == v for k, v in req.filters.items())
            ]

        # Select columns if specified
        if req.columns:
            result = [
                {k: r.get(k) for k in req.columns if k in r}
                for r in result
            ]

        # Apply offset and limit
        offset = req.offset or 0
        if offset > 0:
            result = result[offset:]
        if req.limit is not None and req.limit >= 0:
            result = result[:req.limit]

        return result
