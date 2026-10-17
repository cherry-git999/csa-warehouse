"""
Regression Test Suite for Krishna's PR #22 Review Comments.

Covers:
1. Comment 2: Official Agriworks ERPNext Git dependency resolution and imports.
2. Comment 1: Decentralized dashboard mapping documentation existence and pointer index.
3. Comment 3: Decentralized dashboard-owned data loaders, exact datasets_information -> datasets
   resolution, PyMongoError handling, CSV fallback, and stock auto-sync lifecycle decoupling.
4. Comment 4: Pipeline configuration registry, single authoritative dictionary instance,
   in-place patch.dict compatibility, and storage architecture invariants.
"""

import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

dashboards_dir = str(Path(__file__).parent.parent / "app" / "dashboards")
if dashboards_dir not in sys.path:
    sys.path.insert(0, dashboards_dir)

import pandas as pd
from pymongo.errors import ServerSelectionTimeoutError, PyMongoError

from app.config.pipeline_mapping import (
    PIPELINE_CONFIG,
    get_pipeline_config,
    get_dataset_name_for_pipeline,
    get_pipeline_source_type,
    get_pipeline_sync_strategy,
)
from app.config.pipeline_registry import get_pipeline_registry
from app.services.storage.storage_router import StorageRouter
from app.services.storage.mongo_data_storage import MongoDataStorage


class TestDecentralizationReviewComments(unittest.TestCase):
    """Pytest-compatible test suite verifying all 4 PR review comments."""

    def setUp(self):
        self.router = StorageRouter()

    # --------------------------------------------------------------------------
    # 1. Comment 2: Agriworks Git Dependency
    # --------------------------------------------------------------------------

    def test_agriworks_git_dependency_import(self):
        """ERPNextClient imports successfully from the installed Agriworks package."""
        from erp_client.erp_next_client import ERPNextClient
        self.assertIsNotNone(ERPNextClient)

    # --------------------------------------------------------------------------
    # 2. Comment 1: Decentralized Mapping Documentation
    # --------------------------------------------------------------------------

    def test_decentralized_mapping_docs_exist(self):
        """All 6 decentralized dashboard mapping markdown files exist under app/dashboards/docs/."""
        docs_dir = Path(__file__).parent.parent / "app" / "dashboards" / "docs"
        expected_files = [
            "nf_coordinator_mapping.md",
            "purchase_sales_mapping.md",
            "farmer_income_mapping.md",
            "stock_movement_mapping.md",
            "stock_inventory_mapping.md",
            "revenue_analysis_mapping.md",
        ]
        for fname in expected_files:
            spec_file = docs_dir / fname
            self.assertTrue(spec_file.exists(), f"Missing decentralized spec: {fname}")
            content = spec_file.read_text()
            self.assertIn("Field Mapping Matrix", content)
            self.assertIn("Target MongoDB Collection", content)

    def test_central_mapping_doc_is_pointer_index(self):
        """backend/docs/dashboard_mapping.md is a pointer index linking to the 6 decentralized files."""
        central_doc = Path(__file__).parent.parent / "docs" / "dashboard_mapping.md"
        self.assertTrue(central_doc.exists())
        content = central_doc.read_text()
        self.assertIn("Dashboard-Specific ERP Data Mapping Specifications", content)
        self.assertIn("docs/nf_coordinator_mapping.md", content)
        self.assertIn("docs/revenue_analysis_mapping.md", content)

    # --------------------------------------------------------------------------
    # 3. Comment 3: Dashboard-Owned Data Loaders & Decoupled Lifecycle
    # --------------------------------------------------------------------------

    def test_no_dashboards_import_central_loader(self):
        """Zero dashboard scripts in app/dashboards/ import load_dashboard_data_from_mongodb."""
        dashboards_dir = Path(__file__).parent.parent / "app" / "dashboards"
        dashboard_files = list(dashboards_dir.glob("*_dashboard.py"))
        self.assertEqual(len(dashboard_files), 6)

        for dash_file in dashboard_files:
            tree = ast.parse(dash_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported_names = [alias.name for alias in node.names]
                    self.assertNotIn(
                        "load_dashboard_data_from_mongodb",
                        imported_names,
                        f"{dash_file.name} still imports load_dashboard_data_from_mongodb",
                    )

    @patch("app.dashboards.revenue_analysis_dashboard._get_mongodb_db")
    def test_revenue_analysis_loader_metadata_lookup_and_transformation(self, mock_get_db):
        """revenue_analysis queries datasets_information -> datasets and calculates net_revenue."""
        from app.dashboards.revenue_analysis_dashboard import load_data, PIPELINE_ID
        self.assertEqual(PIPELINE_ID, "revenue_analysis")

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.list_collection_names.return_value = []
        mock_info_coll = MagicMock()
        mock_info_coll.find_one.return_value = {
            "pipeline_id": "revenue_analysis",
            "dataset_id": "ds_123",
        }
        mock_ds_coll = MagicMock()
        mock_ds_coll.find_one.return_value = {
            "_id": "ds_123",
            "data": [
                {"territory": "Telangana", "month": "Sep", "purchase_amount": 200.0, "sales_amount": 500.0},
            ],
        }
        colls = {"datasets_information": mock_info_coll, "datasets": mock_ds_coll}
        mock_db.__getitem__.side_effect = lambda name: colls.get(name, MagicMock())

        df = load_data()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["net_revenue"], 300.0)

    @patch("app.dashboards.stock_inventory_dashboard._get_mongodb_db")
    def test_stock_inventory_loader_metadata_lookup(self, mock_get_db):
        """stock_inventory queries datasets_information -> datasets for canonical pipeline_id."""
        from app.dashboards.stock_inventory_dashboard import load_data, PIPELINE_ID
        self.assertEqual(PIPELINE_ID, "stock_inventory")

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.list_collection_names.return_value = []
        mock_info_coll = MagicMock()
        mock_info_coll.find_one.return_value = {
            "pipeline_id": "stock_inventory",
            "dataset_id": "ds_inv",
        }
        mock_ds_coll = MagicMock()
        mock_ds_coll.find_one.return_value = {
            "_id": "ds_inv",
            "data": [
                {"company": "FPO 1", "warehouse": "W1", "item_name": "Item A", "item_group": "Produce", "stock_qty": 10.0, "stock_value": 1000.0},
            ],
        }
        colls = {"datasets_information": mock_info_coll, "datasets": mock_ds_coll}
        mock_db.__getitem__.side_effect = lambda name: colls.get(name, MagicMock())

        df = load_data()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["item_name"], "Item A")

    @patch("app.dashboards.revenue_analysis_dashboard._get_mongodb_db")
    def test_dashboard_direct_collection_fallback(self, mock_get_db):
        """Loader falls back to direct collection if datasets_information has no record."""
        from app.dashboards.revenue_analysis_dashboard import load_data

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db["datasets_information"].find_one.return_value = None
        mock_db.list_collection_names.return_value = ["revenue_analysis"]
        mock_coll = MagicMock()
        mock_db.__getitem__.side_effect = lambda name: mock_coll if name == "revenue_analysis" else MagicMock()
        mock_coll.find.return_value = [
            {"territory": "Warangal", "month": "Oct", "purchase_amount": 100.0, "sales_amount": 250.0}
        ]

        df = load_data()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["territory"], "Warangal")
        self.assertEqual(df.iloc[0]["net_revenue"], 150.0)

    @patch("app.dashboards.revenue_analysis_dashboard._get_mongodb_db")
    def test_dashboard_csv_fallback_when_mongodb_empty(self, mock_get_db):
        """Reachable but empty MongoDB triggers clean fallback to reference CSV."""
        from app.dashboards.revenue_analysis_dashboard import load_data

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db["datasets_information"].find_one.return_value = None
        mock_db.list_collection_names.return_value = []

        df = load_data()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty, "CSV fallback should load reference data")
        self.assertIn("net_revenue", df.columns)

    @patch("app.dashboards.revenue_analysis_dashboard._get_mongodb_db")
    def test_dashboard_pymongo_error_handling(self, mock_get_db):
        """PyMongo connection error logs warning and gracefully falls back to CSV without crash."""
        from app.dashboards.revenue_analysis_dashboard import load_data

        mock_get_db.side_effect = ServerSelectionTimeoutError("Connection timed out")

        df = load_data()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty, "Should fall back to CSV upon PyMongoError")

    @patch("app.dashboards.stock_movement_dashboard._get_mongodb_db")
    @patch("app.dashboards.stock_movement_dashboard.trigger_warehouse_auto_sync")
    def test_stock_load_data_does_not_trigger_sync(self, mock_sync, mock_get_db):
        """Calling stock_movement load_data() strictly queries data and does NOT trigger auto_sync."""
        from app.dashboards.stock_movement_dashboard import load_data

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db["datasets_information"].find_one.return_value = None
        mock_db.list_collection_names.return_value = []

        load_data()
        mock_sync.assert_not_called()

    # --------------------------------------------------------------------------
    # 4. Comment 4: Pipeline Registry & In-Place Configuration Facade
    # --------------------------------------------------------------------------

    def test_registry_contains_all_13_pipelines(self):
        """PipelineRegistry contains all 6 dashboard and 7 generic pipelines."""
        registry = get_pipeline_registry()
        expected_pids = [
            "nf_coordinator_activities",
            "territory_transactions",
            "farmer_income_visits",
            "stock_movement",
            "stock_inventory",
            "revenue_analysis",
            "soil_collection",
            "weather_data",
            "crop_yield",
            "sales_invoice",
            "purchase_invoice",
            "cc_daily_reports",
            "stock_balance",
        ]
        for pid in expected_pids:
            self.assertIn(pid, registry.configs)
            cfg = registry.get(pid)
            self.assertIn("source_name", cfg)
            self.assertIn("source_type", cfg)
            self.assertIn("sync_strategy", cfg)

    def test_pipeline_config_is_exact_registry_instance(self):
        """PIPELINE_CONFIG is the exact same dictionary instance as registry.configs (zero divergence)."""
        registry = get_pipeline_registry()
        self.assertIs(
            PIPELINE_CONFIG,
            registry.configs,
            "PIPELINE_CONFIG must reference the exact registry dictionary instance",
        )

    def test_pipeline_config_in_place_patch_dict(self):
        """patch.dict(PIPELINE_CONFIG, ...) mutates the registry dictionary in place and restores cleanly."""
        registry = get_pipeline_registry()
        test_pid = "test_custom_pipeline_999"

        self.assertNotIn(test_pid, PIPELINE_CONFIG)
        self.assertNotIn(test_pid, registry.configs)

        with patch.dict(PIPELINE_CONFIG, {test_pid: {"source_name": "Test DocType", "source_type": "doctype"}}):
            # Assert immediate visibility in registry and get_pipeline_config
            self.assertIn(test_pid, registry.configs)
            cfg = get_pipeline_config(test_pid)
            self.assertEqual(cfg["source_name"], "Test DocType")

        # Assert clean restoration
        self.assertNotIn(test_pid, PIPELINE_CONFIG)
        self.assertNotIn(test_pid, registry.configs)

    def test_nested_patch_dict_stock_inventory_guardrail(self):
        """patch.dict on PIPELINE_CONFIG['stock_inventory'] works and router guardrail holds."""
        self.assertIsInstance(self.router.get_storage("stock_inventory"), MongoDataStorage)

        with patch.dict(PIPELINE_CONFIG["stock_inventory"], {"storage_backend": "base"}):
            self.assertEqual(PIPELINE_CONFIG["stock_inventory"]["storage_backend"], "base")
            # Strict guardrail: stock_inventory must ALWAYS return MongoDataStorage
            storage = self.router.get_storage("stock_inventory")
            self.assertIsInstance(storage, MongoDataStorage)

        self.assertNotIn("storage_backend", PIPELINE_CONFIG["stock_inventory"])

    @patch("app.dashboards.nf_coordinator_dashboard._get_mongodb_db")
    def test_nf_coordinator_loader_and_filter_resilient_to_nulls(self, mock_get_db):
        """NF Coordinator loader and filter options handle records with null/None fields gracefully."""
        from app.dashboards.nf_coordinator_dashboard import load_nf_data
        from bson import ObjectId
        import numpy as np

        mock_db = MagicMock()
        mock_info_coll = MagicMock()
        mock_ds_coll = MagicMock()

        target_ds_id = ObjectId("6a8c936260022eecb52bc8a2")
        mock_info_coll.find_one.return_value = {
            "pipeline_id": "nf_coordinator_activities",
            "dataset_id": target_ds_id,
        }

        # Simulate real data containing valid rows and rows with None/NaN
        raw_data = [
            {
                "coordinator_name": "Anusha K",
                "district": "Kadapa",
                "date": "13-08-2026",
                "type_of_activity": "Field Visit",
                "planned_activities": 1.0,
                "actual_activities": 2.0,
                "total_score": 20.0,
            },
            {
                "coordinator_name": "Besta Udaya Kumar",
                "district": "Kurnool",
                "date": "14-08-2026",
                "type_of_activity": "Group Meeting",
                "planned_activities": 2.0,
                "actual_activities": 1.0,
                "total_score": 10.0,
            },
            {
                "coordinator_name": None,
                "district": None,
                "date": None,
                "type_of_activity": None,
                "planned_activities": np.nan,
                "actual_activities": np.nan,
                "total_score": np.nan,
            },
        ]
        mock_ds_coll.find_one.return_value = {
            "_id": target_ds_id,
            "data": raw_data,
        }

        mock_db.__getitem__.side_effect = lambda col: {
            "datasets_information": mock_info_coll,
            "datasets": mock_ds_coll,
        }.get(col, MagicMock())
        mock_get_db.return_value = mock_db

        df = load_nf_data()
        self.assertEqual(len(df), 3)

        # Verify filter options do not crash on mixed types (float nan vs str)
        all_coordinators = sorted([c for c in df["coordinator_name"].dropna().unique() if str(c).strip()])
        self.assertEqual(all_coordinators, ["Anusha K", "Besta Udaya Kumar"])

        all_districts = sorted([d for d in df["district"].dropna().unique() if str(d).strip()])
        self.assertEqual(all_districts, ["Kadapa", "Kurnool"])

        months_ordered = (
            df[["month_label", "month_period"]]
            .dropna()
            .drop_duplicates()
            .sort_values("month_period")["month_label"]
            .tolist()
        )
        self.assertEqual(months_ordered, ["Aug 2026"])

        all_activities = sorted([a for a in df["type_of_activity"].dropna().unique() if str(a).strip()])
        self.assertEqual(all_activities, ["Field Visit", "Group Meeting"])

        # Verify numeric aggregates ignore NaNs safely
        total_score = int(df["total_score"].fillna(0).sum())
        self.assertEqual(total_score, 30)


if __name__ == "__main__":
    unittest.main()
