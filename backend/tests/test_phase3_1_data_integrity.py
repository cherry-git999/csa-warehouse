"""
Phase 3.1: Data-Integrity Regression Tests.

Verifies:
1. Pipelines sharing ERP source names (Stock Balance, Purchase Invoice, CC Daily Reports)
   cannot collide or resolve to each other's storage records.
2. Canonical pipeline_id is treated as the primary storage identity.
3. Ambiguous metadata (multiple docs with same pipeline_id or same dataset_name) fails safely.
4. Ambiguous legacy metadata for shared ERP source names cannot be claimed by competing pipelines.
5. Unambiguous legacy metadata for uniquely mapped ERP source names is safely reused.
6. Extraction errors (404, missing reports) are propagated and never converted to empty DataFrames.
7. Empty snapshot replacement (mode="replace") is rejected when existing storage has non-empty records.
8. Legitimate empty snapshot (initial run with no existing records) is permitted.
9. Empty upsert (mode="upsert") preserves existing records and allows checkpoint advancement.
10. Rejected empty snapshot prevents checkpoint advancement in TaskRunner and flags error status.
11. Both stock_inventory and stock_movement snapshot pipelines are protected against destructive wipeout.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import uuid
import pandas as pd
from bson import ObjectId

from app.services.storage.mongo_data_storage import MongoDataStorage
from app.services.storage.base_data_storage import BaseStorageError
from app.services.tasks.task_executor import TaskRunner, tasks
from app.utils.erp import pull_dataset
from app.config.pipeline_mapping import PIPELINE_CONFIG


class TestDatasetIdentityResolutionPhase31(unittest.TestCase):
    """Phase B: Dataset identity resolution tests (isolated with mocks)."""

    def setUp(self):
        self.storage = MongoDataStorage()

    # 1. Pipelines sharing "Stock Balance" cannot resolve to each other's storage records
    @patch("app.db.database.dataset_information_collection")
    def test_pipelines_sharing_stock_balance_cannot_collide(self, mock_info_coll):
        inv_ds_id = str(ObjectId())
        mov_ds_id = str(ObjectId())

        # Simulate metadata documents having distinct pipeline_id values
        def find_side_effect(query):
            pid = query.get("pipeline_id")
            if pid == "stock_inventory":
                return [{"_id": ObjectId(), "dataset_id": inv_ds_id, "pipeline_id": "stock_inventory", "dataset_name": "stock_inventory", "user_id": []}]
            elif pid == "stock_movement":
                return [{"_id": ObjectId(), "dataset_id": mov_ds_id, "pipeline_id": "stock_movement", "dataset_name": "stock_movement", "user_id": []}]
            return []

        mock_info_coll.find.side_effect = find_side_effect

        target_inv, name_inv, _ = self.storage._resolve_target_dataset("stock_inventory")
        target_mov, name_mov, _ = self.storage._resolve_target_dataset("stock_movement")

        self.assertEqual(target_inv, inv_ds_id)
        self.assertEqual(target_mov, mov_ds_id)
        self.assertNotEqual(target_inv, target_mov, "stock_inventory and stock_movement must not resolve to the same dataset ID")

    # 2. Pipelines sharing "Purchase Invoice" cannot collide
    @patch("app.db.database.dataset_information_collection")
    def test_pipelines_sharing_purchase_invoice_cannot_collide(self, mock_info_coll):
        terr_ds_id = str(ObjectId())
        rev_ds_id = str(ObjectId())

        def find_side_effect(query):
            pid = query.get("pipeline_id")
            if pid == "territory_transactions":
                return [{"_id": ObjectId(), "dataset_id": terr_ds_id, "pipeline_id": "territory_transactions", "dataset_name": "territory_transactions", "user_id": []}]
            elif pid == "revenue_analysis":
                return [{"_id": ObjectId(), "dataset_id": rev_ds_id, "pipeline_id": "revenue_analysis", "dataset_name": "revenue_analysis", "user_id": []}]
            return []

        mock_info_coll.find.side_effect = find_side_effect

        target_terr, _, _ = self.storage._resolve_target_dataset("territory_transactions")
        target_rev, _, _ = self.storage._resolve_target_dataset("revenue_analysis")

        self.assertEqual(target_terr, terr_ds_id)
        self.assertEqual(target_rev, rev_ds_id)
        self.assertNotEqual(target_terr, target_rev, "territory_transactions and revenue_analysis must not collide")

    # 3. Pipelines sharing "CC Daily Reports" cannot collide
    @patch("app.db.database.dataset_information_collection")
    def test_pipelines_sharing_cc_daily_reports_cannot_collide(self, mock_info_coll):
        coord_ds_id = str(ObjectId())
        farmer_ds_id = str(ObjectId())

        def find_side_effect(query):
            pid = query.get("pipeline_id")
            if pid == "nf_coordinator_activities":
                return [{"_id": ObjectId(), "dataset_id": coord_ds_id, "pipeline_id": "nf_coordinator_activities", "dataset_name": "nf_coordinator_activities", "user_id": []}]
            elif pid == "farmer_income_visits":
                return [{"_id": ObjectId(), "dataset_id": farmer_ds_id, "pipeline_id": "farmer_income_visits", "dataset_name": "farmer_income_visits", "user_id": []}]
            return []

        mock_info_coll.find.side_effect = find_side_effect

        target_coord, _, _ = self.storage._resolve_target_dataset("nf_coordinator_activities")
        target_farmer, _, _ = self.storage._resolve_target_dataset("farmer_income_visits")

        self.assertEqual(target_coord, coord_ds_id)
        self.assertEqual(target_farmer, farmer_ds_id)
        self.assertNotEqual(target_coord, target_farmer, "nf_coordinator_activities and farmer_income_visits must not collide")

    # 4. Exact pipeline_id match in metadata is preferred over dataset_name
    @patch("app.db.database.dataset_information_collection")
    def test_exact_pipeline_id_match_preferred(self, mock_info_coll):
        primary_id = str(ObjectId())

        def find_side_effect(query):
            if "pipeline_id" in query:
                return [{"_id": ObjectId(), "dataset_id": primary_id, "pipeline_id": "sales_invoice", "dataset_name": "custom_name", "user_id": []}]
            return []

        mock_info_coll.find.side_effect = find_side_effect

        target_id, target_name, _ = self.storage._resolve_target_dataset("sales_invoice")
        self.assertEqual(target_id, primary_id)
        self.assertEqual(target_name, "custom_name")

    # 5. Exact dataset_name == pipeline_id match resolved when pipeline_id field is empty
    @patch("app.db.database.dataset_information_collection")
    def test_exact_dataset_name_equals_pipeline_id_resolved(self, mock_info_coll):
        name_id = str(ObjectId())

        def find_side_effect(query):
            if "pipeline_id" in query:
                return []
            if query.get("dataset_name") == "custom_pipeline":
                return [{"_id": ObjectId(), "dataset_id": name_id, "pipeline_id": None, "dataset_name": "custom_pipeline", "user_id": []}]
            return []

        mock_info_coll.find.side_effect = find_side_effect

        target_id, target_name, _ = self.storage._resolve_target_dataset("custom_pipeline")
        self.assertEqual(target_id, name_id)
        self.assertEqual(target_name, "custom_pipeline")

    # 6. Ambiguous metadata with multiple docs having same pipeline_id raises BaseStorageError
    @patch("app.db.database.dataset_information_collection")
    def test_ambiguous_pipeline_id_metadata_raises_error(self, mock_info_coll):
        mock_info_coll.find.return_value = [
            {"_id": ObjectId(), "dataset_id": str(ObjectId()), "pipeline_id": "duplicate_pipeline"},
            {"_id": ObjectId(), "dataset_id": str(ObjectId()), "pipeline_id": "duplicate_pipeline"},
        ]

        with self.assertRaises(BaseStorageError) as ctx:
            self.storage._resolve_target_dataset("duplicate_pipeline")
        self.assertIn("Ambiguous metadata", str(ctx.exception))

    # 7. Ambiguous legacy metadata for shared ERP source name cannot be claimed
    @patch("app.db.database.dataset_information_collection")
    def test_ambiguous_legacy_metadata_for_shared_source_raises_error(self, mock_info_coll):
        # Suppose a legacy doc exists with dataset_name: "Stock Balance" and no pipeline_id
        def find_side_effect(query):
            if "pipeline_id" in query and query.get("pipeline_id") == "stock_inventory":
                return []
            if query.get("dataset_name") == "stock_inventory":
                return []
            if query.get("dataset_name") == "Stock Balance":
                return [{"_id": ObjectId(), "dataset_id": str(ObjectId()), "dataset_name": "Stock Balance", "pipeline_id": None}]
            return []

        mock_info_coll.find.side_effect = find_side_effect

        # Attempting to resolve stock_inventory must fail rather than guessing or overwriting
        with self.assertRaises(BaseStorageError) as ctx:
            self.storage._resolve_target_dataset("stock_inventory")
        self.assertIn("Ambiguous legacy metadata", str(ctx.exception))
        self.assertIn("Stock Balance", str(ctx.exception))

    # 8. Unambiguous legacy metadata for unique ERP source name is safely reused
    @patch("app.db.database.dataset_information_collection")
    def test_unambiguous_legacy_metadata_for_unique_source_reused(self, mock_info_coll):
        legacy_sales_id = str(ObjectId())

        def find_side_effect(query):
            if "pipeline_id" in query and query.get("pipeline_id") == "sales_invoice":
                return []
            if query.get("dataset_name") == "sales_invoice":
                return []
            if query.get("dataset_name") == "Sales Invoice":
                return [{"_id": ObjectId(), "dataset_id": legacy_sales_id, "dataset_name": "Sales Invoice", "pipeline_id": None}]
            return []

        mock_info_coll.find.side_effect = find_side_effect

        # Sales Invoice uniquely maps only to sales_invoice in PIPELINE_CONFIG
        target_id, target_name, _ = self.storage._resolve_target_dataset("sales_invoice")
        self.assertEqual(target_id, legacy_sales_id)
        self.assertEqual(target_name, "Sales Invoice")


class TestEmptySnapshotProtectionPhase31(unittest.TestCase):
    """Phase C: Empty snapshot protection and extraction failure handling."""

    def setUp(self):
        self.storage = MongoDataStorage()
        self.runner = TaskRunner()
        self.exec_id = str(uuid.uuid4())
        tasks[self.exec_id] = {"status": "running"}

    # 1. ERP 404 or missing report error raises and is not converted to empty DataFrame
    @patch("app.utils.erp.ERPNextClient")
    def test_erp_404_or_missing_report_raises_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_query_report.side_effect = Exception("Resource 404 Not Found: Stock Balance")

        with patch.dict("os.environ", {"ERP_URI": "http://erp.fpohub.com", "ERP_USERNAME": "u", "ERP_PASSWORD": "p"}):
            with self.assertRaises(Exception) as ctx:
                pull_dataset("stock_inventory")
            self.assertIn("404", str(ctx.exception))

    # 2. Unexpected empty snapshot rejected when existing records are present
    @patch("app.db.database.datasets_collection")
    @patch.object(MongoDataStorage, "_resolve_target_dataset")
    def test_empty_snapshot_rejected_when_existing_records_present(self, mock_resolve, mock_ds_coll):
        mock_resolve.return_value = ("ds_inv_123", "stock_inventory", "user_1")
        mock_ds_coll.find_one.return_value = {
            "_id": "ds_inv_123",
            "data": [{"item": "ITEM01", "qty": 10}, {"item": "ITEM02", "qty": 5}],
            "record_count": 2,
        }

        with self.assertRaises(BaseStorageError) as ctx:
            self.storage.save_dataset(
                pipeline_id="stock_inventory",
                records=[],
                mode="replace",
                identity_key=None,
            )
        self.assertIn("Empty snapshot replacement rejected", str(ctx.exception))
        self.assertIn("existing storage contains 2 records", str(ctx.exception))

    # 3. Legitimate empty snapshot permitted when no existing records are present
    @patch("app.services.storage.mongodb_service.store_to_mongodb")
    @patch("app.db.database.datasets_collection")
    @patch.object(MongoDataStorage, "_resolve_target_dataset")
    def test_legitimate_empty_snapshot_permitted_when_no_existing_records(
        self, mock_resolve, mock_ds_coll, mock_store_mongo
    ):
        mock_resolve.return_value = ("ds_new_123", "stock_inventory", "user_1")
        # No existing document or empty data document
        mock_ds_coll.find_one.return_value = None
        mock_store_mongo.return_value = {"record_count": 0, "inserted": True}

        res = self.storage.save_dataset(
            pipeline_id="stock_inventory",
            records=[],
            mode="replace",
            identity_key=None,
        )
        self.assertEqual(res.record_count, 0)
        mock_store_mongo.assert_called_once()

    # 4. Empty upsert preserves existing records and allows checkpoint advancement
    @patch("app.services.storage.mongodb_service.store_to_mongodb")
    @patch.object(MongoDataStorage, "_resolve_target_dataset")
    def test_empty_upsert_preserves_records_and_succeeds(self, mock_resolve, mock_store_mongo):
        mock_resolve.return_value = ("ds_upsert_123", "territory_transactions", "user_1")
        mock_store_mongo.return_value = {"record_count": 50, "updated": True}

        res = self.storage.save_dataset(
            pipeline_id="territory_transactions",
            records=[],
            mode="upsert",
            identity_key="date",
        )
        self.assertEqual(res.record_count, 50)
        self.assertEqual(res.mode, "upsert")

    # 5. Rejected empty snapshot prevents checkpoint advancement in TaskRunner
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[])
    @patch("app.db.database.datasets_collection")
    @patch.object(MongoDataStorage, "_resolve_target_dataset")
    def test_empty_snapshot_rejection_prevents_checkpoint_advancement_in_task_runner(
        self, mock_resolve, mock_ds_coll, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        mock_resolve.return_value = ("ds_stock_123", "stock_inventory", "user_1")
        # Existing document in MongoDB has 41 records
        mock_ds_coll.find_one.return_value = {
            "_id": "ds_stock_123",
            "data": [{"item": f"I_{i}"} for i in range(41)],
            "record_count": 41,
        }

        self.runner.run_pipeline_task(
            dataset_id="stock_inventory",
            dataset_name="stock_inventory",
            user_id="user_123",
            exec_id=self.exec_id,
            pipeline_id="stock_inventory",
        )

        # Invariant: checkpoint must NOT be advanced
        mock_update_cp.assert_not_called()
        self.assertEqual(tasks[self.exec_id]["status"], "error")
        # History entry must report rejected empty snapshot
        error_msg = mock_hist.call_args[1]["error"]
        self.assertIn("Empty snapshot replacement rejected", error_msg)

    # 6. Both stock_inventory and stock_movement snapshot pipelines are protected
    @patch("app.db.database.datasets_collection")
    @patch.object(MongoDataStorage, "_resolve_target_dataset")
    def test_both_stock_inventory_and_stock_movement_protected(self, mock_resolve, mock_ds_coll):
        for pid in ["stock_inventory", "stock_movement"]:
            mock_resolve.return_value = (f"ds_{pid}_id", pid, "user_1")
            mock_ds_coll.find_one.return_value = {
                "_id": f"ds_{pid}_id",
                "data": [{"key": "val"}],
                "record_count": 1,
            }

            with self.assertRaises(BaseStorageError) as ctx:
                self.storage.save_dataset(
                    pipeline_id=pid,
                    records=[],
                    mode="replace",
                    identity_key=None,
                )
            self.assertIn("Empty snapshot replacement rejected", str(ctx.exception))
            self.assertIn(pid, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
