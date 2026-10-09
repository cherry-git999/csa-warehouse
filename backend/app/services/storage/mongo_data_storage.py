"""
MongoDataStorage Compatibility Adapter.

Implements the BaseDataStorage interface by delegating to existing, verified
MongoDB storage functions (mongodb_service.py).

ARCHITECTURAL RULES:
1. Preserve existing MongoDB schemas and persistence semantics:
   - mode="replace" executes snapshot replacement
   - mode="upsert" executes existing _merge_records behavior with identity_key
2. DEFERRED IMPORTS: Does not import database.py or mongodb_service.py at module level
   to prevent premature MongoClient initialization and network side effects at import time.
3. Checkpoint management is decoupled and handled by TaskRunner directly.
4. Failures are never swallowed and raise BaseStorageError.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId

from app.schemas.base_schema import StorageResult
from app.services.storage.base_data_storage import (
    BaseDataStorage,
    BaseStorageError,
)

logger = logging.getLogger(__name__)


class MongoDataStorage(BaseDataStorage):
    """
    MongoDB implementation of BaseDataStorage.
    Delegates to existing MongoDB collections and services using lazy execution.
    """

    def _resolve_target_dataset(self, pipeline_id: str) -> Tuple[str, str, str]:
        """
        Resolve the MongoDB dataset identity (dataset_id, dataset_name, user_id) for pipeline_id.

        Primary identity rule: pipeline_id is the canonical storage identity.
        Precedence:
        1. Exact pipeline_id match in dataset_information_collection.
        2. Exact dataset_name == pipeline_id match (where pipeline_id is empty or matches).
        3. Unambiguous legacy metadata with source_name, only if source_name uniquely maps
           to exactly one pipeline in PIPELINE_CONFIG. If shared across multiple pipelines
           (e.g. 'Stock Balance', 'Purchase Invoice', 'CC Daily Reports'), legacy matching
           is rejected as ambiguous.
        4. Fresh unambiguous identifiers initialized for a new dataset.
        """
        from app.db.database import dataset_information_collection
        from app.config.pipeline_mapping import PIPELINE_CONFIG
        from bson import ObjectId

        # 1. Exact pipeline_id match (primary identity)
        id_query: Dict[str, Any] = {"pipeline_id": pipeline_id}
        if ObjectId.is_valid(pipeline_id):
            id_query = {"$or": [{"pipeline_id": pipeline_id}, {"pipeline_id": ObjectId(pipeline_id)}]}

        matches = list(dataset_information_collection.find(id_query))
        if len(matches) > 1:
            raise BaseStorageError(
                f"Ambiguous metadata: multiple dataset_information documents found for pipeline_id '{pipeline_id}'."
            )
        elif len(matches) == 1:
            doc = matches[0]
            users = doc.get("user_id", [])
            u_id = str(users[0]) if (users and ObjectId.is_valid(str(users[0]))) else str(ObjectId())
            return str(doc["dataset_id"]), doc.get("dataset_name", pipeline_id), u_id

        # 2. Exact dataset_name == pipeline_id match
        name_matches = list(dataset_information_collection.find({"dataset_name": pipeline_id}))
        valid_name_matches = [
            d for d in name_matches
            if not d.get("pipeline_id") or str(d.get("pipeline_id")) == str(pipeline_id)
        ]
        if len(valid_name_matches) > 1:
            raise BaseStorageError(
                f"Ambiguous metadata: multiple dataset_information documents found with dataset_name '{pipeline_id}'."
            )
        elif len(valid_name_matches) == 1:
            doc = valid_name_matches[0]
            users = doc.get("user_id", [])
            u_id = str(users[0]) if (users and ObjectId.is_valid(str(users[0]))) else str(ObjectId())
            return str(doc["dataset_id"]), pipeline_id, u_id

        # 3. Safe handling for legacy metadata without pipeline_id
        erp_source = PIPELINE_CONFIG.get(pipeline_id, {}).get("source_name")
        if erp_source:
            sharing_pids = [
                pid for pid, cfg in PIPELINE_CONFIG.items()
                if cfg.get("source_name") == erp_source
            ]
            legacy_matches = list(dataset_information_collection.find({
                "dataset_name": erp_source,
                "pipeline_id": {"$in": [None, ""]},
            }))
            if legacy_matches:
                if len(sharing_pids) > 1:
                    raise BaseStorageError(
                        f"Ambiguous legacy metadata: found legacy dataset_information with dataset_name '{erp_source}', "
                        f"but source name is shared by multiple pipelines {sharing_pids}. "
                        f"Cannot claim legacy dataset for pipeline '{pipeline_id}' without explicit association."
                    )
                elif len(legacy_matches) == 1:
                    doc = legacy_matches[0]
                    users = doc.get("user_id", [])
                    u_id = str(users[0]) if (users and ObjectId.is_valid(str(users[0]))) else str(ObjectId())
                    return str(doc["dataset_id"]), erp_source, u_id
                else:
                    raise BaseStorageError(
                        f"Ambiguous legacy metadata: multiple legacy documents found with dataset_name '{erp_source}'."
                    )

        # 4. Fresh unambiguous identifiers for new pipeline dataset
        target_dataset_id = pipeline_id if ObjectId.is_valid(pipeline_id) else str(ObjectId())
        return target_dataset_id, pipeline_id, str(ObjectId())

    def save_dataset(
        self,
        pipeline_id: str,
        records: List[Dict[str, Any]],
        mode: str = "upsert",
        identity_key: Optional[str] = None,
    ) -> StorageResult:
        """
        Save dataset records using the existing store_to_mongodb function.

        Enforces:
        - Primary identity resolution via pipeline_id.
        - Empty snapshot replacement protection (Phase 3.1): Rejects empty replace operations
          when existing storage contains non-empty data.

        Args:
            pipeline_id: Canonical pipeline identifier.
            records: Normalized records to persist.
            mode: 'upsert' (merge by identity_key) or 'replace' (snapshot overwrite).
            identity_key: Field used for matching when mode='upsert'.

        Returns:
            StorageResult detailing operation outcome and record count.

        Raises:
            BaseStorageError: On persistence failure or safety policy violation.
        """
        # Lazy import avoids import-time database side effects
        from app.services.storage.mongodb_service import store_to_mongodb
        from app.db.database import datasets_collection
        from bson import ObjectId

        try:
            target_dataset_id, target_dataset_name, target_user_id = self._resolve_target_dataset(pipeline_id)

            # EMPTY SNAPSHOT SAFETY POLICY (Phase 3.1):
            # If mode='replace' and incoming records is empty, check whether existing storage has records.
            # Do not erase existing non-empty snapshots due to unexpected empty extractions.
            if mode == "replace" and not records:
                existing_doc = None
                if ObjectId.is_valid(target_dataset_id):
                    existing_doc = datasets_collection.find_one({"_id": ObjectId(target_dataset_id)})
                if not existing_doc:
                    existing_doc = datasets_collection.find_one({"_id": target_dataset_id})

                if existing_doc:
                    existing_records = existing_doc.get("data", [])
                    existing_count = existing_doc.get("record_count", len(existing_records))
                    if existing_count > 0:
                        msg = (
                            f"Empty snapshot replacement rejected for pipeline '{pipeline_id}': "
                            f"incoming extraction has 0 records, but existing storage contains {existing_count} records. "
                            f"Preserving existing data to protect against extraction anomalies."
                        )
                        logger.error(msg)
                        raise BaseStorageError(msg)

            result = store_to_mongodb(
                dataset_id=target_dataset_id,
                dataset_name=target_dataset_name,
                user_id=target_user_id,
                username="",
                user_email="",
                dataset_records=records,
                pipeline_id=pipeline_id,
                identity_key=identity_key,
                mode=mode,
            )

            record_count = result.get("record_count", len(records))
            return StorageResult(
                pipeline_id=pipeline_id,
                record_count=record_count,
                mode=mode,
                message="Dataset successfully saved in MongoDB",
            )
        except BaseStorageError:
            raise
        except Exception as e:
            msg = f"Failed to save dataset '{pipeline_id}' in MongoDB: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    def fetch_dataset(
        self,
        pipeline_id: str,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch dataset records from MongoDB. Resolves via direct collection or datasets collection.

        Args:
            pipeline_id: Canonical pipeline identifier.
            filters: Key-value equality filters.
            columns: List of columns to project.
            limit: Maximum records to return.
            offset: Record offset for pagination.

        Returns:
            List of record dictionaries.

        Raises:
            BaseStorageError: On retrieval failure.
        """
        # Lazy import avoids import-time database side effects
        from app.db.database import (
            db,
            datasets_collection,
        )
        from bson import ObjectId

        try:
            records: List[Dict[str, Any]] = []

            # 1. Check direct collection
            if pipeline_id in db.list_collection_names():
                coll = db[pipeline_id]
                mongo_query = filters or {}
                projection = {"_id": 0}
                if columns:
                    for col in columns:
                        projection[col] = 1
                cursor = coll.find(mongo_query, projection)
                if offset:
                    cursor = cursor.skip(offset)
                if limit:
                    cursor = cursor.limit(limit)
                docs = list(cursor)
                if docs:
                    return docs

            # 2. Check datasets_information / datasets collection via strict resolution
            target_dataset_id, _, _ = self._resolve_target_dataset(pipeline_id)
            doc = None
            if ObjectId.is_valid(target_dataset_id):
                doc = datasets_collection.find_one({"_id": ObjectId(target_dataset_id)})
            if not doc:
                doc = datasets_collection.find_one({"_id": target_dataset_id})

            if doc and "data" in doc:
                records = doc["data"]

            return self._apply_filters_and_slices(records, filters, columns, limit, offset)
        except BaseStorageError:
            raise
        except Exception as e:
            msg = f"Failed to fetch dataset '{pipeline_id}' from MongoDB: {e}"
            logger.error(msg)
            raise BaseStorageError(msg) from e

    @staticmethod
    def _apply_filters_and_slices(
        records: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Filter, project columns, and paginate in-memory records."""
        result = records

        if filters:
            result = [
                r for r in result
                if all(r.get(k) == v for k, v in filters.items())
            ]

        if columns:
            result = [
                {k: r.get(k) for k in columns if k in r}
                for r in result
            ]

        off = offset or 0
        if off > 0:
            result = result[off:]
        if limit is not None and limit >= 0:
            result = result[:limit]

        return result
