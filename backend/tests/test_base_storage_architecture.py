"""
Architectural Unit Tests for Streamlined BASE Storage Layer & StorageRouter (Phase 1 & Phase 2).

Verifies:
1. BaseDataStorage contract and interface compliance.
2. StorageResult DTO structure and approved fields.
3. BaseStorageError exception hierarchy.
4. MongoDataStorage conforms to the streamlined interface.
5. BaseApiStorageService conforms to the streamlined interface.
6. Mock BASE transport simulates success (save and fetch lifecycle).
7. Mock BASE transport simulates failure.
8. BASE failure raises an exception.
9. Strict failure visibility: No silent MongoDB fallback inside BaseApiStorageService.
10. Data storage factory resolution (legacy & pipeline_id shim).
11. StorageRouter routing rules (Phase 2):
    - Known pipeline with no storage_backend -> MongoDataStorage
    - Known pipeline explicitly configured with storage_backend="mongodb" -> MongoDataStorage
    - Known pipeline configured with storage_backend="base" -> BaseApiStorageService
    - stock_inventory guardrail -> MongoDataStorage (even if configured as "base")
    - Unknown pipeline -> UnknownPipelineError
    - Unsupported backend -> UnsupportedStorageBackendError
    - Conformance to BaseDataStorage
    - Router does not execute network calls or BASE API requests during routing
    - All six production warehouse pipelines resolve to MongoDataStorage
"""

import unittest
from unittest.mock import MagicMock, patch

from app.schemas.base_schema import StorageResult
from app.config.base_config import BaseStorageConfig
from app.config.pipeline_mapping import PIPELINE_CONFIG
from app.services.storage.base_data_storage import (
    BaseDataStorage,
    BaseStorageError,
    BaseConnectionError,
    BaseTimeoutError,
    BaseAuthenticationError,
)
from app.services.storage.base_api_storage_service import (
    BaseApiStorageService,
    BaseTransportClient,
    MockBaseTransportClient,
)
from app.services.storage.mongo_data_storage import MongoDataStorage
from app.services.storage.data_storage_factory import get_data_storage
from app.services.storage.storage_router import (
    StorageRouter,
    get_storage_router,
    StorageRouterError,
    UnknownPipelineError,
    UnsupportedStorageBackendError,
)


class TestBaseStorageArchitecturePhase1(unittest.TestCase):

    def setUp(self):
        self.config = BaseStorageConfig(
            storage_backend="base",
            base_api_url="http://mock-base.internal",
            transport="mock",
            timeout_seconds=5.0,
            connect_timeout_seconds=2.0,
        )

    # --------------------------------------------------------------------------
    # 1. BaseDataStorage Contract
    # --------------------------------------------------------------------------

    def test_base_data_storage_cannot_be_instantiated_directly(self):
        """BaseDataStorage is an abstract base class and cannot be instantiated."""
        with self.assertRaises(TypeError):
            BaseDataStorage()

    # --------------------------------------------------------------------------
    # 2. StorageResult DTO Structure
    # --------------------------------------------------------------------------

    def test_storage_result_fields(self):
        """StorageResult contains approved fields and does not use success boolean."""
        res = StorageResult(
            pipeline_id="territory_transactions",
            record_count=42,
            mode="upsert",
            message="Saved successfully",
        )
        self.assertEqual(res.pipeline_id, "territory_transactions")
        self.assertEqual(res.record_count, 42)
        self.assertEqual(res.mode, "upsert")
        self.assertEqual(res.message, "Saved successfully")

    # --------------------------------------------------------------------------
    # 3. Exception Hierarchy
    # --------------------------------------------------------------------------

    def test_exception_hierarchy(self):
        """All storage exceptions inherit from BaseStorageError."""
        self.assertTrue(issubclass(BaseConnectionError, BaseStorageError))
        self.assertTrue(issubclass(BaseTimeoutError, BaseStorageError))
        self.assertTrue(issubclass(BaseAuthenticationError, BaseStorageError))

        # Test raising and catching as base type
        with self.assertRaises(BaseStorageError):
            raise BaseConnectionError("Connection failed")

        with self.assertRaises(BaseStorageError):
            raise BaseTimeoutError("Request timed out")

        with self.assertRaises(BaseStorageError):
            raise BaseAuthenticationError("Invalid API key")

    # --------------------------------------------------------------------------
    # 4. MongoDataStorage Interface Conformance
    # --------------------------------------------------------------------------

    def test_mongo_data_storage_conforms_to_interface(self):
        """MongoDataStorage implements BaseDataStorage and exposes required methods."""
        mongo_storage = MongoDataStorage()
        self.assertIsInstance(mongo_storage, BaseDataStorage)
        self.assertTrue(callable(getattr(mongo_storage, "save_dataset")))
        self.assertTrue(callable(getattr(mongo_storage, "fetch_dataset")))

    # --------------------------------------------------------------------------
    # 5. BaseApiStorageService Interface Conformance
    # --------------------------------------------------------------------------

    def test_base_api_storage_service_conforms_to_interface(self):
        """BaseApiStorageService implements BaseDataStorage and exposes required methods."""
        service = BaseApiStorageService(config=self.config)
        self.assertIsInstance(service, BaseDataStorage)
        self.assertTrue(callable(getattr(service, "save_dataset")))
        self.assertTrue(callable(getattr(service, "fetch_dataset")))

    # --------------------------------------------------------------------------
    # 6. Mock BASE Transport Simulates Success
    # --------------------------------------------------------------------------

    def test_mock_base_transport_simulate_success(self):
        """BaseApiStorageService with MockBaseTransportClient persists and retrieves records."""
        mock_transport = MockBaseTransportClient(config=self.config)
        service = BaseApiStorageService(config=self.config, transport=mock_transport)

        records = [
            {"territory": "Telangana", "date": "2026-01-01", "purchase_amount": 1000.0},
            {"territory": "Andhra Pradesh", "date": "2026-01-01", "purchase_amount": 2000.0},
        ]
        res = service.save_dataset(
            pipeline_id="territory_transactions",
            records=records,
            mode="upsert",
            identity_key="territory",
        )
        self.assertIsInstance(res, StorageResult)
        self.assertEqual(res.pipeline_id, "territory_transactions")
        self.assertEqual(res.record_count, 2)
        self.assertEqual(res.mode, "upsert")

        fetched = service.fetch_dataset("territory_transactions")
        self.assertEqual(len(fetched), 2)
        self.assertEqual(fetched[0]["territory"], "Telangana")

    # --------------------------------------------------------------------------
    # 7. Mock BASE Transport Simulates Failure
    # --------------------------------------------------------------------------

    def test_mock_base_transport_simulate_failure(self):
        """Transport failure raises appropriate BaseStorageError subclass."""
        failing_transport = MagicMock(spec=BaseTransportClient)
        failing_transport.execute_request.side_effect = BaseConnectionError("BASE service unreachable")

        service = BaseApiStorageService(config=self.config, transport=failing_transport)
        with self.assertRaises(BaseConnectionError):
            service.save_dataset(
                pipeline_id="nf_coordinator_activities",
                records=[{"date": "2026-01-01"}],
                mode="upsert",
            )

    # --------------------------------------------------------------------------
    # 8. BASE Failure Raises Exception
    # --------------------------------------------------------------------------

    def test_base_timeout_raises_exception(self):
        """Timeout in BASE transport raises BaseTimeoutError."""
        timeout_transport = MagicMock(spec=BaseTransportClient)
        timeout_transport.execute_request.side_effect = BaseTimeoutError("Operation timed out after 5.0s")

        service = BaseApiStorageService(config=self.config, transport=timeout_transport)
        with self.assertRaises(BaseTimeoutError):
            service.fetch_dataset("revenue_analysis")

    # --------------------------------------------------------------------------
    # 9. Strict Failure Visibility (NO Silent MongoDB Fallback)
    # --------------------------------------------------------------------------

    def test_no_silent_fallback_to_mongo(self):
        """BaseApiStorageService must NEVER fall back silently to MongoDB on failure."""
        failing_transport = MagicMock(spec=BaseTransportClient)
        failing_transport.execute_request.side_effect = BaseConnectionError("Connection refused")

        service = BaseApiStorageService(config=self.config, transport=failing_transport)

        with self.assertRaises(BaseConnectionError):
            service.save_dataset(
                pipeline_id="stock_movement",
                records=[{"in_qty": 50}],
                mode="replace",
            )

        with self.assertRaises(BaseConnectionError):
            service.fetch_dataset("stock_movement")

    # --------------------------------------------------------------------------
    # 10. Data Storage Factory (Legacy & Shim)
    # --------------------------------------------------------------------------

    def test_factory_returns_mongo_by_default(self):
        """Factory returns MongoDataStorage for 'mongodb'."""
        storage = get_data_storage(storage_backend="mongodb")
        self.assertIsInstance(storage, MongoDataStorage)

    def test_factory_returns_base_when_configured(self):
        """Factory returns BaseApiStorageService for 'base'."""
        storage = get_data_storage(storage_backend="base")
        self.assertIsInstance(storage, BaseApiStorageService)

    def test_factory_rejects_unsupported_backend(self):
        """Factory raises ValueError for invalid backend."""
        with self.assertRaises(ValueError):
            get_data_storage(storage_backend="invalid_storage_backend")

    def test_factory_delegates_to_router_when_pipeline_id_provided(self):
        """Factory delegates to StorageRouter when pipeline_id is provided."""
        storage = get_data_storage(pipeline_id="stock_inventory")
        self.assertIsInstance(storage, MongoDataStorage)


class TestStorageRouterPhase2(unittest.TestCase):
    """
    Phase 2: Comprehensive verification of StorageRouter rules and dataset routing.
    """

    def setUp(self):
        self.router = StorageRouter()

    # --------------------------------------------------------------------------
    # 1. Known pipeline with no storage_backend -> MongoDataStorage
    # --------------------------------------------------------------------------

    def test_known_pipeline_missing_backend_defaults_to_mongo(self):
        """Pipelines without an explicit storage_backend default safely to MongoDataStorage."""
        with patch.dict(PIPELINE_CONFIG, {"test_pipe_default": {"source_name": "Test"}}):
            storage = self.router.get_storage("test_pipe_default")
            self.assertIsInstance(storage, MongoDataStorage)

    # --------------------------------------------------------------------------
    # 2. Known pipeline explicitly configured with storage_backend="mongodb"
    # --------------------------------------------------------------------------

    def test_known_pipeline_explicit_mongo_resolves_mongo(self):
        """Pipelines explicitly configured with storage_backend='mongodb' resolve to MongoDataStorage."""
        with patch.dict(PIPELINE_CONFIG, {"test_pipe_mongo": {"storage_backend": "mongodb"}}):
            storage = self.router.get_storage("test_pipe_mongo")
            self.assertIsInstance(storage, MongoDataStorage)

    # --------------------------------------------------------------------------
    # 3. Known pipeline configured with storage_backend="base"
    # --------------------------------------------------------------------------

    def test_known_pipeline_configured_base_resolves_base(self):
        """Pipelines configured with storage_backend='base' resolve to BaseApiStorageService."""
        with patch.dict(PIPELINE_CONFIG, {"test_pipe_base": {"storage_backend": "base"}}):
            storage = self.router.get_storage("test_pipe_base")
            self.assertIsInstance(storage, BaseApiStorageService)

    # --------------------------------------------------------------------------
    # 4. stock_inventory guardrail
    # --------------------------------------------------------------------------

    def test_stock_inventory_guardrail_always_resolves_mongo(self):
        """stock_inventory ALWAYS resolves to MongoDataStorage, even if accidentally configured as 'base'."""
        # 1. Normal configuration
        storage = self.router.get_storage("stock_inventory")
        self.assertIsInstance(storage, MongoDataStorage)

        # 2. Attempted misconfiguration to 'base'
        with patch.dict(PIPELINE_CONFIG, {"stock_inventory": {"storage_backend": "base"}}):
            guarded_storage = self.router.get_storage("stock_inventory")
            self.assertIsInstance(guarded_storage, MongoDataStorage)

    # --------------------------------------------------------------------------
    # 5. Unknown pipeline -> clear configuration error
    # --------------------------------------------------------------------------

    def test_unknown_pipeline_raises_error(self):
        """Unknown pipeline_id raises UnknownPipelineError (subclass of KeyError/ValueError)."""
        with self.assertRaises(UnknownPipelineError):
            self.router.get_storage("nonexistent_pipeline_id_12345")

        with self.assertRaises(UnknownPipelineError):
            self.router.get_storage("")

    # --------------------------------------------------------------------------
    # 6. Unsupported backend -> clear configuration error
    # --------------------------------------------------------------------------

    def test_unsupported_storage_backend_raises_error(self):
        """Configuring an invalid or unsupported storage_backend raises UnsupportedStorageBackendError."""
        for invalid_backend in ["postgres", "redis", "random", "s3", "mysql"]:
            with patch.dict(PIPELINE_CONFIG, {"test_pipe_invalid": {"storage_backend": invalid_backend}}):
                with self.assertRaises(UnsupportedStorageBackendError):
                    self.router.get_storage("test_pipe_invalid")

    # --------------------------------------------------------------------------
    # 7. Router returns instances conforming to BaseDataStorage
    # --------------------------------------------------------------------------

    def test_router_returns_base_data_storage_conforming_instances(self):
        """All returned adapters conform to the BaseDataStorage ABC."""
        storage_mongo = self.router.get_storage("stock_inventory")
        self.assertIsInstance(storage_mongo, BaseDataStorage)
        self.assertTrue(callable(getattr(storage_mongo, "save_dataset")))
        self.assertTrue(callable(getattr(storage_mongo, "fetch_dataset")))

        with patch.dict(PIPELINE_CONFIG, {"test_pipe_base": {"storage_backend": "base"}}):
            storage_base = self.router.get_storage("test_pipe_base")
            self.assertIsInstance(storage_base, BaseDataStorage)
            self.assertTrue(callable(getattr(storage_base, "save_dataset")))
            self.assertTrue(callable(getattr(storage_base, "fetch_dataset")))

    # --------------------------------------------------------------------------
    # 8. Singleton accessor
    # --------------------------------------------------------------------------

    def test_get_storage_router_returns_singleton(self):
        """get_storage_router() returns the same singleton instance."""
        r1 = get_storage_router()
        r2 = get_storage_router()
        self.assertIs(r1, r2)
        self.assertIsInstance(r1, StorageRouter)

    # --------------------------------------------------------------------------
    # 9. Router does not call BASE during routing
    # --------------------------------------------------------------------------

    def test_router_does_not_call_base_during_routing(self):
        """Resolving a pipeline to BASE does not invoke any network transport requests."""
        with patch.dict(PIPELINE_CONFIG, {"test_pipe_base": {"storage_backend": "base"}}):
            with patch.object(BaseTransportClient, "execute_request") as mock_exec:
                storage = self.router.get_storage("test_pipe_base")
                self.assertIsInstance(storage, BaseApiStorageService)
                # Verify execute_request was NOT called during resolution
                mock_exec.assert_not_called()

    # --------------------------------------------------------------------------
    # 10. CRITICAL INVARIANT: All six production pipelines resolve to MongoDB
    # --------------------------------------------------------------------------

    def test_all_six_current_pipelines_resolve_to_mongodb(self):
        """
        Verify that all six production warehouse pipelines resolve to MongoDataStorage
        under current configuration in Phase 2. Zero production datasets route to BASE.
        """
        production_pipelines = [
            "nf_coordinator_activities",
            "territory_transactions",
            "farmer_income_visits",
            "stock_movement",
            "stock_inventory",
            "revenue_analysis",
        ]

        for pipeline_id in production_pipelines:
            # Confirm pipeline is registered in PIPELINE_CONFIG
            self.assertIn(
                pipeline_id,
                PIPELINE_CONFIG,
                f"Production pipeline '{pipeline_id}' must be registered in PIPELINE_CONFIG",
            )

            # Confirm router resolves pipeline to MongoDataStorage
            storage = self.router.get_storage(pipeline_id)
            self.assertIsInstance(
                storage,
                MongoDataStorage,
                f"Production pipeline '{pipeline_id}' MUST resolve to MongoDataStorage in Phase 2",
            )


if __name__ == "__main__":
    unittest.main()
