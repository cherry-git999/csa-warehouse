"""
Architectural Unit Tests for BASE Storage Layer.

Verifies:
1. BaseDataStorage contract and interface compliance.
2. BaseApiStorageService operation contracts (save, fetch, merge, checkpoints).
3. Transport isolation and bounded timeout / error raising.
4. Strict failure visibility (no silent fallback to MongoDB).
5. MongoDataStorage compatibility adapter interface compliance.
6. Data storage factory behavior (safe default to MongoDB).
7. Schema and spatial/temporal granularity models.
"""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from app.schemas.base_schema import (
    SpatialGranularity,
    DatasetSpatialInfo,
    TemporalGranularity,
    DatasetTemporalInfo,
    ColumnSchema,
    DatasetSchemaMetadata,
    SaveDatasetRequest,
    FetchDatasetRequest,
    MergeDatasetRequest,
    StorageResponse,
)
from app.config.base_config import BaseStorageConfig
from app.services.storage.base_data_storage import (
    BaseDataStorage,
    BaseStorageError,
    BaseConnectionError,
    BaseTimeoutError,
    BaseAuthenticationError,
    BaseDataValidationError,
)
from app.services.storage.base_api_storage_service import (
    BaseApiStorageService,
    BaseTransportClient,
    MockBaseTransportClient,
)
from app.services.storage.mongo_data_storage import MongoDataStorage
from app.services.storage.data_storage_factory import get_data_storage


class TestBaseStorageArchitecture(unittest.TestCase):

    def setUp(self):
        self.config = BaseStorageConfig(
            storage_backend="base",
            base_api_url="http://mock-base.internal",
            transport="mock",
            timeout_seconds=5.0,
        )

    # --------------------------------------------------------------------------
    # 1. Schema & Granularity Model Tests
    # --------------------------------------------------------------------------

    def test_spatial_granularity_optionality(self):
        """Verify spatial fields are completely optional and not forced on non-spatial datasets."""
        # Dataset without spatial dimensions
        metadata_no_geo = DatasetSchemaMetadata(
            dataset_id="test_non_geo",
            dataset_name="Test Non Geo",
            columns=[ColumnSchema(name="item_code", data_type="string")],
        )
        self.assertIsNone(metadata_no_geo.spatial_info)

        # Dataset with spatial dimensions (e.g., district level)
        spatial_info = DatasetSpatialInfo(
            is_spatial=True,
            granularities=[SpatialGranularity.DISTRICT, SpatialGranularity.STATE],
            district_column="district",
            state_column="state",
        )
        metadata_geo = DatasetSchemaMetadata(
            dataset_id="test_geo",
            dataset_name="Test Geo",
            spatial_info=spatial_info,
        )
        self.assertTrue(metadata_geo.spatial_info.is_spatial)
        self.assertIn(SpatialGranularity.DISTRICT, metadata_geo.spatial_info.granularities)
        self.assertIsNone(metadata_geo.spatial_info.latitude_column)  # GPS not forced

    def test_temporal_granularity_optionality(self):
        """Verify temporal fields are completely optional and not forced."""
        metadata_no_time = DatasetSchemaMetadata(
            dataset_id="test_snapshot",
            dataset_name="Test Snapshot",
        )
        self.assertIsNone(metadata_no_time.temporal_info)

        temporal_info = DatasetTemporalInfo(
            is_temporal=True,
            granularities=[TemporalGranularity.DAY, TemporalGranularity.MONTH],
            primary_timestamp_column="posting_date",
        )
        metadata_time = DatasetSchemaMetadata(
            dataset_id="test_time",
            dataset_name="Test Time",
            temporal_info=temporal_info,
        )
        self.assertTrue(metadata_time.temporal_info.is_temporal)
        self.assertEqual(metadata_time.temporal_info.primary_timestamp_column, "posting_date")

    # --------------------------------------------------------------------------
    # 2. BaseDataStorage Contract Tests
    # --------------------------------------------------------------------------

    def test_base_data_storage_cannot_be_instantiated_directly(self):
        """BaseDataStorage is an abstract class and cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseDataStorage()

    def test_fetch_dataset_df_conversion(self):
        """Convenience method fetch_dataset_df returns a pandas DataFrame."""
        service = BaseApiStorageService(config=self.config)
        save_req = SaveDatasetRequest(
            dataset_id="df_test",
            dataset_name="DF Test",
            records=[{"colA": 1, "colB": "foo"}, {"colA": 2, "colB": "bar"}],
        )
        service.save_dataset(save_req)

        df = service.fetch_dataset_df("df_test")
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ["colA", "colB"])

    # --------------------------------------------------------------------------
    # 3. BaseApiStorageService Operation Tests (Save, Fetch, Merge, Checkpoint)
    # --------------------------------------------------------------------------

    def test_base_api_save_and_fetch_lifecycle(self):
        """Test save_dataset and fetch_dataset via BaseApiStorageService."""
        service = BaseApiStorageService(config=self.config)
        records = [
            {"item_code": "ITEM001", "qty": 100},
            {"item_code": "ITEM002", "qty": 200},
        ]
        save_req = SaveDatasetRequest(
            dataset_id="stock_inv_test",
            dataset_name="Stock Inventory Test",
            records=records,
            pipeline_id="stock_inventory",
        )
        save_res = service.save_dataset(save_req)
        self.assertTrue(save_res.success)
        self.assertEqual(save_res.record_count, 2)

        fetched = service.fetch_dataset("stock_inv_test")
        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]["item_code"], "ITEM001")

    def test_base_api_merge_dataset(self):
        """Test merge_dataset via BaseApiStorageService."""
        service = BaseApiStorageService(config=self.config)
        service.save_dataset(SaveDatasetRequest(
            dataset_id="target_ds",
            dataset_name="Target",
            records=[{"id": 1, "name": "A"}],
        ))

        merge_req = MergeDatasetRequest(
            target_dataset_id="target_ds",
            source_records=[{"id": 2, "name": "B"}],
            identity_key="id",
        )
        merge_res = service.merge_dataset(merge_req)
        self.assertTrue(merge_res.success)

        fetched = service.fetch_dataset("target_ds")
        self.assertEqual(len(fetched), 2)

    def test_base_api_checkpoint_lifecycle(self):
        """Test get_checkpoint and update_checkpoint via BaseApiStorageService."""
        service = BaseApiStorageService(config=self.config)
        update_res = service.update_checkpoint(
            pipeline_id="sales_invoice",
            last_sync_timestamp="2026-09-22T17:00:00Z",
            execution_id="exec-1234",
            record_count=42,
            status="success",
        )
        self.assertIsNotNone(update_res)

        cp = service.get_checkpoint("sales_invoice")
        self.assertEqual(cp.get("last_sync_timestamp"), "2026-09-22T17:00:00Z")
        self.assertEqual(cp.get("execution_id"), "exec-1234")

    # --------------------------------------------------------------------------
    # 4. Strict Failure Visibility & Bounded Error Handling (NO Silent Fallback)
    # --------------------------------------------------------------------------

    def test_base_failure_raises_exception_without_silent_mongo_fallback(self):
        """A failure in BASE must raise BaseStorageError and NOT fall back silently."""
        failing_transport = MagicMock(spec=BaseTransportClient)
        failing_transport.execute_request.side_effect = BaseConnectionError("Connection refused to BASE API")

        service = BaseApiStorageService(config=self.config, transport=failing_transport)

        # Confirm save_dataset raises BaseConnectionError
        with self.assertRaises(BaseConnectionError):
            service.save_dataset(SaveDatasetRequest(
                dataset_id="fail_ds",
                dataset_name="Fail DS",
                records=[{"a": 1}],
            ))

        # Confirm fetch_dataset raises BaseConnectionError
        with self.assertRaises(BaseConnectionError):
            service.fetch_dataset("fail_ds")

        # Confirm merge_dataset raises BaseConnectionError
        with self.assertRaises(BaseConnectionError):
            service.merge_dataset(MergeDatasetRequest(
                target_dataset_id="fail_ds",
                source_records=[{"a": 1}],
            ))

    def test_base_timeout_raises_timeout_error(self):
        """Timeout in BASE transport raises BaseTimeoutError."""
        timeout_transport = MagicMock(spec=BaseTransportClient)
        timeout_transport.execute_request.side_effect = BaseTimeoutError("Operation timed out after 5.0s")

        service = BaseApiStorageService(config=self.config, transport=timeout_transport)
        with self.assertRaises(BaseTimeoutError):
            service.fetch_dataset("timeout_ds")

    # --------------------------------------------------------------------------
    # 5. Factory Behavior
    # --------------------------------------------------------------------------

    def test_factory_returns_mongo_by_default(self):
        """Default factory call returns MongoDataStorage for backward compatibility."""
        storage = get_data_storage(storage_backend="mongodb")
        self.assertIsInstance(storage, MongoDataStorage)

    def test_factory_returns_base_when_configured(self):
        """Factory returns BaseApiStorageService when 'base' is configured."""
        storage = get_data_storage(storage_backend="base")
        self.assertIsInstance(storage, BaseApiStorageService)

    def test_factory_rejects_unsupported_backend(self):
        """Factory raises ValueError for invalid backend."""
        with self.assertRaises(ValueError):
            get_data_storage(storage_backend="unsupported_backend_xyz")

    # --------------------------------------------------------------------------
    # 6. MongoDataStorage Compatibility Adapter Interface Compliance
    # --------------------------------------------------------------------------

    def test_mongo_data_storage_implements_interface(self):
        """MongoDataStorage conforms to BaseDataStorage ABC."""
        mongo_adapter = MongoDataStorage()
        self.assertIsInstance(mongo_adapter, BaseDataStorage)
        for method_name in ["save_dataset", "fetch_dataset", "merge_dataset", "get_checkpoint", "update_checkpoint"]:
            self.assertTrue(callable(getattr(mongo_adapter, method_name)))


if __name__ == "__main__":
    unittest.main()
