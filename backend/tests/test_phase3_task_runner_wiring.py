"""
Phase 3 Regression Tests: TaskRunner Wiring with StorageRouter.

Verifies:
1. TaskRunner obtains adapter through StorageRouter.
2. Normal pipelines write through MongoDataStorage with correct mode and identity_key.
3. stock_inventory pipeline strictly uses MongoDB (guardrail enforcement).
4. Successful storage permits checkpoint advancement (verified ordering).
5. Storage exception strictly prevents checkpoint advancement.
6. Extraction or mapping failure strictly prevents checkpoint advancement.
7. Empty dataset behavior is preserved and advances checkpoint safely.
8. Router error (unknown pipeline / unsupported backend) surfaces without fallback.
9. Pipeline status transitions and return structures remain compatible.
10. All six production pipelines resolve to MongoDataStorage.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import uuid

from app.services.tasks.task_executor import task_runner, tasks, TaskRunner
from app.services.storage.storage_router import (
    get_storage_router,
    UnknownPipelineError,
    UnsupportedStorageBackendError,
)
from app.services.storage.mongo_data_storage import MongoDataStorage
from app.services.storage.base_data_storage import BaseDataStorage, BaseStorageError
from app.schemas.base_schema import StorageResult
from app.config.pipeline_mapping import PIPELINE_CONFIG


class TestTaskRunnerWiringPhase3(unittest.TestCase):

    def setUp(self):
        self.runner = TaskRunner()
        self.exec_id = str(uuid.uuid4())
        tasks[self.exec_id] = {"status": "running"}

    # 1. TaskRunner obtains adapter through StorageRouter
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[{"name": "doc1"}])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[{"name": "doc1"}])
    def test_task_runner_obtains_adapter_through_storage_router(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        router = get_storage_router()
        with patch.object(router, "get_storage", wraps=router.get_storage) as spy_get_storage:
            self.runner.run_pipeline_task(
                dataset_id="nf_coordinator_activities",
                dataset_name="nf_coordinator_activities",
                user_id="user_123",
                exec_id=self.exec_id,
                pipeline_id="nf_coordinator_activities",
            )
            spy_get_storage.assert_called_once_with("nf_coordinator_activities")
            self.assertEqual(tasks[self.exec_id]["status"], "completed")

    # 2. Normal pipeline writes through MongoDataStorage with correct semantics
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[{"name": "doc1", "date": "2026-10-09"}])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[{"name": "doc1", "date": "2026-10-09"}])
    def test_normal_pipeline_writes_through_mongo_with_correct_semantics(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        mock_mongo = MagicMock(spec=MongoDataStorage)
        mock_mongo.save_dataset.return_value = StorageResult(
            pipeline_id="territory_transactions",
            record_count=1,
            mode="upsert",
            message="Saved",
        )

        with patch.object(get_storage_router(), "get_storage", return_value=mock_mongo):
            self.runner.run_pipeline_task(
                dataset_id="territory_transactions",
                dataset_name="territory_transactions",
                user_id="user_123",
                exec_id=self.exec_id,
                pipeline_id="territory_transactions",
            )

            mock_mongo.save_dataset.assert_called_once_with(
                pipeline_id="territory_transactions",
                records=[{"name": "doc1", "date": "2026-10-09"}],
                mode="upsert",
                identity_key="date",
            )
            self.assertEqual(tasks[self.exec_id]["status"], "completed")

    # 3. stock_inventory strictly uses MongoDataStorage
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[{"item_code": "ITEM01"}])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[{"item_code": "ITEM01"}])
    def test_stock_inventory_always_uses_mongo_even_if_misconfigured(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        mock_mongo = MagicMock(spec=MongoDataStorage)
        mock_mongo.save_dataset.return_value = StorageResult(
            pipeline_id="stock_inventory",
            record_count=1,
            mode="replace",
            message="Saved",
        )

        # Simulate accidental "base" configuration
        with patch.dict(PIPELINE_CONFIG["stock_inventory"], {"storage_backend": "base"}):
            with patch.object(get_storage_router(), "_get_mongo", return_value=mock_mongo):
                self.runner.run_pipeline_task(
                    dataset_id="stock_inventory",
                    dataset_name="stock_inventory",
                    user_id="user_123",
                    exec_id=self.exec_id,
                    pipeline_id="stock_inventory",
                )
                mock_mongo.save_dataset.assert_called_once_with(
                    pipeline_id="stock_inventory",
                    records=[{"item_code": "ITEM01"}],
                    mode="replace",
                    identity_key=None,
                )
                self.assertEqual(tasks[self.exec_id]["status"], "completed")

    # 4. Successful storage permits checkpoint advancement (Ordering Check)
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[{"modified": "2026-10-09 12:00:00"}])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[{"modified": "2026-10-09 12:00:00"}])
    def test_successful_storage_permits_checkpoint_advancement_in_order(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        call_order = []

        def fake_save(*args, **kwargs):
            call_order.append("save_dataset")
            return StorageResult(pipeline_id="sales_invoice", record_count=1, mode="upsert")

        def fake_update_cp(*args, **kwargs):
            call_order.append("update_sync_checkpoint")

        mock_storage = MagicMock(spec=MongoDataStorage)
        mock_storage.save_dataset.side_effect = fake_save
        mock_update_cp.side_effect = fake_update_cp

        with patch.object(get_storage_router(), "get_storage", return_value=mock_storage):
            self.runner.run_pipeline_task(
                dataset_id="sales_invoice",
                dataset_name="sales_invoice",
                user_id="user_123",
                exec_id=self.exec_id,
                pipeline_id="sales_invoice",
            )

        self.assertEqual(call_order, ["save_dataset", "update_sync_checkpoint"])
        mock_update_cp.assert_called_once()
        self.assertEqual(tasks[self.exec_id]["status"], "completed")

    # 5. Storage exception strictly prevents checkpoint advancement
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[{"name": "doc1"}])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[{"name": "doc1"}])
    def test_storage_exception_prevents_checkpoint_advancement(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        mock_storage = MagicMock(spec=MongoDataStorage)
        mock_storage.save_dataset.side_effect = BaseStorageError("Simulated storage write error")

        with patch.object(get_storage_router(), "get_storage", return_value=mock_storage):
            self.runner.run_pipeline_task(
                dataset_id="sales_invoice",
                dataset_name="sales_invoice",
                user_id="user_123",
                exec_id=self.exec_id,
                pipeline_id="sales_invoice",
            )

        # Invariant: checkpoint must NOT advance
        mock_update_cp.assert_not_called()
        self.assertEqual(tasks[self.exec_id]["status"], "error")
        # History entry must report error
        mock_hist.assert_called_with(
            "sales_invoice",
            self.exec_id,
            "error",
            "user_123",
            pipeline_id="sales_invoice",
            error="Simulated storage write error",
        )

    # 6. Extraction or mapping failure strictly prevents checkpoint advancement
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", side_effect=RuntimeError("ERP timeout"))
    def test_extraction_failure_prevents_checkpoint_advancement(
        self, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        with patch.object(get_storage_router(), "get_storage") as spy_storage:
            self.runner.run_pipeline_task(
                dataset_id="sales_invoice",
                dataset_name="sales_invoice",
                user_id="user_123",
                exec_id=self.exec_id,
                pipeline_id="sales_invoice",
            )
            spy_storage.assert_not_called()
            mock_update_cp.assert_not_called()
            self.assertEqual(tasks[self.exec_id]["status"], "error")

    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[{"raw": 1}])
    @patch("app.services.tasks.task_executor.map_erp_data", side_effect=ValueError("Mapping schema invalid"))
    def test_mapping_failure_prevents_checkpoint_advancement(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        with patch.object(get_storage_router(), "get_storage") as spy_storage:
            self.runner.run_pipeline_task(
                dataset_id="sales_invoice",
                dataset_name="sales_invoice",
                user_id="user_123",
                exec_id=self.exec_id,
                pipeline_id="sales_invoice",
            )
            spy_storage.assert_not_called()
            mock_update_cp.assert_not_called()
            self.assertEqual(tasks[self.exec_id]["status"], "error")

    # 7. Empty dataset behavior is preserved
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[])
    def test_empty_dataset_preserves_behavior_and_advances_checkpoint(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        mock_storage = MagicMock(spec=MongoDataStorage)
        mock_storage.save_dataset.return_value = StorageResult(
            pipeline_id="sales_invoice",
            record_count=0,
            mode="upsert",
            message="No records",
        )

        with patch.object(get_storage_router(), "get_storage", return_value=mock_storage):
            self.runner.run_pipeline_task(
                dataset_id="sales_invoice",
                dataset_name="sales_invoice",
                user_id="user_123",
                exec_id=self.exec_id,
                pipeline_id="sales_invoice",
            )

            mock_storage.save_dataset.assert_called_once_with(
                pipeline_id="sales_invoice",
                records=[],
                mode="upsert",
                identity_key="name",
            )
            mock_update_cp.assert_called_once()
            self.assertEqual(mock_update_cp.call_args[1]["record_count"], 0)
            self.assertEqual(tasks[self.exec_id]["status"], "completed")

    # 8. Unsupported backend or router error surfaced without fallback
    @patch("app.services.tasks.task_executor.add_pipeline_history_entry")
    @patch("app.services.tasks.task_executor.update_sync_checkpoint")
    @patch("app.services.tasks.task_executor.get_sync_checkpoint", return_value=None)
    @patch("app.services.tasks.task_executor.pull_dataset", return_value=[{"name": "1"}])
    @patch("app.services.tasks.task_executor.map_erp_data", return_value=[{"name": "1"}])
    def test_unknown_pipeline_error_surfaced_without_fallback(
        self, mock_map, mock_pull, mock_get_cp, mock_update_cp, mock_hist
    ):
        self.runner.run_pipeline_task(
            dataset_id="unknown_pipeline_id_123",
            dataset_name="unknown_pipeline_id_123",
            user_id="user_123",
            exec_id=self.exec_id,
            pipeline_id="unknown_pipeline_id_123",
        )

        mock_update_cp.assert_not_called()
        self.assertEqual(tasks[self.exec_id]["status"], "error")
        # Ensure error message mentions unknown pipeline
        error_msg = mock_hist.call_args[1]["error"]
        self.assertIn("Unknown pipeline_id", error_msg)

    # 9. Pipeline status transitions and return structures remain compatible
    def test_submit_task_returns_compatible_structures(self):
        from app.services.tasks.task_executor import submit_task
        with patch.object(TaskRunner, "run_pipeline_task") as mock_run:
            task_dict, exec_id = submit_task(
                dataset_id="sales_invoice",
                dataset_name="sales_invoice",
                user_id="user_test",
                pipeline_id="sales_invoice",
            )
            self.assertEqual(task_dict["status"], "running")
            self.assertEqual(task_dict["user_id"], "user_test")
            self.assertIn("executed_at", task_dict)
            self.assertTrue(len(exec_id) > 10)

    # 10. All six production pipelines resolve to MongoDataStorage
    def test_all_six_production_pipelines_resolve_to_mongo(self):
        router = get_storage_router()
        production_pipelines = [
            "nf_coordinator_activities",
            "territory_transactions",
            "farmer_income_visits",
            "stock_movement",
            "stock_inventory",
            "revenue_analysis",
        ]
        for pid in production_pipelines:
            storage = router.get_storage(pid)
            self.assertIsInstance(
                storage,
                MongoDataStorage,
                f"Pipeline '{pid}' did not resolve to MongoDataStorage",
            )


if __name__ == "__main__":
    unittest.main()
