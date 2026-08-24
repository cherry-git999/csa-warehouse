import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from bson import ObjectId
from app.mappings import (
    BaseMapper,
    NFCoordinatorMapper,
    TerritoryTransactionsMapper,
    FarmerIncomeVisitsMapper,
    StockMovementMapper,
    StockInventoryMapper,
    RevenueAnalysisMapper,
    get_mapper,
    map_erp_data,
)
from app.config.pipeline_mapping import (
    get_pipeline_config,
    get_pipeline_erp_url,
    get_pipeline_mapper,
    get_pipeline_target_collection,
)
from app.utils.erp import pull_dataset
from app.services.tasks.task_executor import task_runner, tasks
from app.services.storage.mongodb_service import (
    get_sync_checkpoint,
    datasets_collection,
    sync_checkpoints_collection,
)

print("=" * 75, flush=True)
print("PHASE 3: DASHBOARD DATA MAPPING TEST SUITE", flush=True)
print("=" * 75, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# Test A: Dashboard 1 — NF Coordinator Performance Mapper
# --------------------------------------------------------------------------
print("\n[TEST A] NF Coordinator Performance Mapper (Dashboard 1)", flush=True)
try:
    mapper = NFCoordinatorMapper()
    sample_cc_data = [
        {
            "name": "CCDR-2026-001",
            "name_of_nf_coordinator": "Anusha K",
            "creation": "2026-08-13 10:00:00",
            "district": "Kadapa",
            "field_visit": [
                {
                    "date": "2026-08-13",
                    "activity": "Field Visit",
                    "sub_activity": "Farmer Field",
                    "mandal": "Kadapa",
                    "village": "Vontimitta",
                },
                {
                    "date": "2026-08-13",
                    "activity": "Field Visit",
                    "sub_activity": "Farmer Field",
                    "mandal": "Kadapa",
                    "village": "Vontimitta",
                },
            ],
            "cc_daily_reports": [
                {
                    "date": "2026-08-13",
                    "activity": "Group Meeting",
                    "mandal": "Kadapa",
                }
            ],
        }
    ]
    df_mapped = mapper.transform(sample_cc_data)
    assert isinstance(df_mapped, pd.DataFrame), "Output must be a DataFrame"
    assert list(df_mapped.columns) == mapper.target_fields, f"Columns mismatch: {list(df_mapped.columns)}"
    assert len(df_mapped) == 2, f"Expected 2 aggregated rows, got {len(df_mapped)}"
    
    # Check values
    fv_row = df_mapped[df_mapped["type_of_activity"] == "Field Visit"].iloc[0]
    assert fv_row["coordinator_name"] == "Anusha K"
    assert fv_row["date"] == "13-08-2026"
    assert fv_row["actual_activities"] == 2
    assert fv_row["total_score"] == 20
    print(f"  ✓ NFCoordinatorMapper succeeded. Columns: {list(df_mapped.columns)}, Row count: {len(df_mapped)}")

except Exception as e:
    print(f"  ✗ Test A failed: {e}")
    test_errors.append(f"Test A: {e}")


# --------------------------------------------------------------------------
# Test B: Dashboard 2 — Purchase & Sales Territory Mapper
# --------------------------------------------------------------------------
print("\n[TEST B] Purchase & Sales Territory Mapper (Dashboard 2)", flush=True)
try:
    mapper = TerritoryTransactionsMapper()
    sample_pi_data = [
        {
            "name": "PIN-001",
            "posting_date": "2025-12-05",
            "place_of_supply": "36-Telangana",
            "grand_total": 50000.0,
        },
        {
            "name": "PIN-002",
            "posting_date": "2025-12-05",
            "place_of_supply": "36-Telangana",
            "grand_total": 25000.0,
        },
        {
            "name": "PIN-003",
            "posting_date": "2025-12-06",
            "place_of_supply": "Andhra Pradesh",
            "grand_total": 10000.0,
        },
    ]
    df_mapped = mapper.transform(sample_pi_data)
    assert list(df_mapped.columns) == mapper.target_fields
    assert len(df_mapped) == 2, f"Expected 2 aggregated rows by (territory, date), got {len(df_mapped)}"
    
    telangana_row = df_mapped[df_mapped["territory"] == "Telangana"].iloc[0]
    assert telangana_row["purchase_amount"] == 75000.0
    assert telangana_row["date"] == "05-12-2025"
    assert pd.isna(telangana_row["sales_amount"]) or telangana_row["sales_amount"] is None, "sales_amount must be None"
    print(f"  ✓ TerritoryTransactionsMapper succeeded. Columns: {list(df_mapped.columns)}, Row count: {len(df_mapped)}")

except Exception as e:
    print(f"  ✗ Test B failed: {e}")
    test_errors.append(f"Test B: {e}")


# --------------------------------------------------------------------------
# Test C: Dashboard 3 — Farmer Income & Visits Mapper (consolidated_report)
# --------------------------------------------------------------------------
print("\n[TEST C] Farmer Income & Visits Mapper (Dashboard 3)", flush=True)
try:
    mapper = FarmerIncomeVisitsMapper()
    sample_consolidated = [
        {
            "name": "CCDR-002",
            "name_of_nf_coordinator": "P Sivarjuna Reddy",
            "month": "August",
            "consolidated_report": [
                {
                    "activity": "Farmer Group Meeting",
                    "sub_activity": "Any other meetings",
                    "sub_activity_count": "2",
                    "name_of_the_fpo": "Vemula FPCL",
                    "number_of_participants": "10",
                },
                {
                    "activity": "Farmer Group Meeting",
                    "sub_activity": "Crop Guidance",
                    "sub_activity_count": "3",
                    "name_of_the_fpo": "Vemula FPCL",
                    "number_of_participants": "15",
                },
            ],
        }
    ]
    df_mapped = mapper.transform(sample_consolidated)
    assert list(df_mapped.columns) == mapper.target_fields
    assert len(df_mapped) == 1, f"Expected 1 aggregated row by village, got {len(df_mapped)}"
    
    row = df_mapped.iloc[0]
    assert row["coordinator_name"] == "P Sivarjuna Reddy"
    assert row["month"] == "August"
    assert row["village"] == "Vemula FPCL"
    assert row["farmers_met"] == 25
    assert row["visits"] == 5
    assert row["score"] == 50
    assert pd.isna(row["income"]) or row["income"] is None
    assert pd.isna(row["net_income"]) or row["net_income"] is None
    assert pd.isna(row["yield"]) or row["yield"] is None
    print(f"  ✓ FarmerIncomeVisitsMapper succeeded. Columns: {list(df_mapped.columns)}, Row count: {len(df_mapped)}")

except Exception as e:
    print(f"  ✗ Test C failed: {e}")
    test_errors.append(f"Test C: {e}")


# --------------------------------------------------------------------------
# Test D: Dashboard 4 — Stock Movement Mapper
# --------------------------------------------------------------------------
print("\n[TEST D] Stock Movement Mapper (Dashboard 4)", flush=True)
try:
    mapper = StockMovementMapper()
    sample_stock = [
        {"item_code": "ITEM-1", "in_qty": 20.0, "out_qty": 5.0, "bal_val": 1000.0, "to_date": "2026-08-20"},
        {"item_code": "ITEM-2", "in_qty": 30.0, "out_qty": 10.0, "bal_val": 2000.0, "to_date": "2026-08-20"},
    ]
    df_mapped = mapper.transform(sample_stock)
    assert list(df_mapped.columns) == mapper.target_fields
    assert len(df_mapped) == 1
    row = df_mapped.iloc[0]
    assert row["in_qty"] == 50.0
    assert row["out_qty"] == 15.0
    assert row["balance_value"] == 3000.0
    assert row["date"] == "20-08-2026"
    print(f"  ✓ StockMovementMapper succeeded. Columns: {list(df_mapped.columns)}, Row count: {len(df_mapped)}")

except Exception as e:
    print(f"  ✗ Test D failed: {e}")
    test_errors.append(f"Test D: {e}")


# --------------------------------------------------------------------------
# Test E: Dashboard 5 — Stock Inventory Mapper
# --------------------------------------------------------------------------
print("\n[TEST E] Stock Inventory Mapper (Dashboard 5)", flush=True)
try:
    mapper = StockInventoryMapper()
    sample_inventory = [
        {
            "company": "Nelathalli FPCL",
            "warehouse": "Main WH",
            "item_name": "HDPE Tarpaulin",
            "item_group": "Farm Machinery",
            "bal_qty": 20.0,
            "bal_val": 23728.81,
        }
    ]
    df_mapped = mapper.transform(sample_inventory)
    assert list(df_mapped.columns) == mapper.target_fields
    assert len(df_mapped) == 1
    row = df_mapped.iloc[0]
    assert row["company"] == "Nelathalli FPCL"
    assert row["warehouse"] == "Main WH"
    assert row["item_name"] == "HDPE Tarpaulin"
    assert row["item_group"] == "Farm Machinery"
    assert row["stock_qty"] == 20.0
    assert row["stock_value"] == 23728.81
    print(f"  ✓ StockInventoryMapper succeeded. Columns: {list(df_mapped.columns)}, Row count: {len(df_mapped)}")

except Exception as e:
    print(f"  ✗ Test E failed: {e}")
    test_errors.append(f"Test E: {e}")


# --------------------------------------------------------------------------
# Test F: Dashboard 6 — Revenue Analysis Mapper
# --------------------------------------------------------------------------
print("\n[TEST F] Revenue Analysis Mapper (Dashboard 6)", flush=True)
try:
    mapper = RevenueAnalysisMapper()
    sample_revenue = [
        {"posting_date": "2025-12-05", "place_of_supply": "36-Telangana", "grand_total": 100000.0},
        {"posting_date": "2025-12-15", "place_of_supply": "36-Telangana", "grand_total": 50000.0},
    ]
    df_mapped = mapper.transform(sample_revenue)
    assert list(df_mapped.columns) == mapper.target_fields
    assert len(df_mapped) == 1
    row = df_mapped.iloc[0]
    assert row["territory"] == "Telangana"
    assert row["month"] == "Dec"
    assert row["purchase_amount"] == 150000.0
    assert pd.isna(row["sales_amount"]) or row["sales_amount"] is None
    print(f"  ✓ RevenueAnalysisMapper succeeded. Columns: {list(df_mapped.columns)}, Row count: {len(df_mapped)}")

except Exception as e:
    print(f"  ✗ Test F failed: {e}")
    test_errors.append(f"Test F: {e}")


# --------------------------------------------------------------------------
# Test G: Schema Validation & Strictness
# --------------------------------------------------------------------------
print("\n[TEST G] Schema Validator Strictness", flush=True)
try:
    mapper = NFCoordinatorMapper()
    bad_df = pd.DataFrame([{"wrong_col": 123}])
    try:
        mapper.validate_schema(bad_df)
        assert False, "Expected ValueError on invalid schema"
    except ValueError as ve:
        print(f"  ✓ Correctly rejected invalid schema: {ve}")

except Exception as e:
    print(f"  ✗ Test G failed: {e}")
    test_errors.append(f"Test G: {e}")


# --------------------------------------------------------------------------
# Test H: Mapper Registry & Unmapped Passthrough
# --------------------------------------------------------------------------
print("\n[TEST H] Mapper Registry & Passthrough Verification", flush=True)
try:
    for pid in [
        "nf_coordinator_activities",
        "territory_transactions",
        "farmer_income_visits",
        "stock_movement",
        "stock_inventory",
        "revenue_analysis",
    ]:
        m = get_mapper(pid)
        assert m is not None, f"Mapper for {pid} must be registered"

    # Test unmapped passthrough
    raw_unmapped = pd.DataFrame([{"custom_field": "test_val"}])
    res_unmapped = map_erp_data(raw_unmapped, "unmapped_custom_pipeline")
    assert res_unmapped.equals(raw_unmapped), "Unmapped data must pass through unmodified"
    print("  ✓ Mapper registry verified for all 6 dashboards + clean unmapped passthrough")

except Exception as e:
    print(f"  ✗ Test H failed: {e}")
    test_errors.append(f"Test H: {e}")


# --------------------------------------------------------------------------
# Test I: Multi-ERP Instance Routing
# --------------------------------------------------------------------------
print("\n[TEST I] Multi-ERP Instance Routing Verification", flush=True)
try:
    assert get_pipeline_erp_url("nf_coordinator_activities") == "http://erp.csa-india.org"
    assert get_pipeline_erp_url("farmer_income_visits") == "http://erp.csa-india.org"
    assert get_pipeline_erp_url("territory_transactions") == "http://erp.fpohub.com"
    assert get_pipeline_erp_url("stock_movement") == "http://erp.fpohub.com"
    assert get_pipeline_erp_url("stock_inventory") == "http://erp.fpohub.com"
    assert get_pipeline_erp_url("revenue_analysis") == "http://erp.fpohub.com"
    print("  ✓ Multi-ERP routing URLs verified for both erp.csa-india.org and erp.fpohub.com")

except Exception as e:
    print(f"  ✗ Test I failed: {e}")
    test_errors.append(f"Test I: {e}")


# --------------------------------------------------------------------------
# Test J: Live ERP End-to-End Extraction & Mapping
# --------------------------------------------------------------------------
print("\n[TEST J] Live ERP Extraction & Mapping Verification", flush=True)
try:
    # 1. Live CC Daily Reports from csa-india
    print("  Pulling live CC Daily Reports from http://erp.csa-india.org...")
    live_cc = pull_dataset("nf_coordinator_activities")
    df_live_nf = map_erp_data(live_cc, "nf_coordinator_activities")
    assert isinstance(df_live_nf, pd.DataFrame)
    print(f"  ✓ Live CC Daily Reports mapped to nf_coordinator_activities: {len(df_live_nf)} records. Columns: {list(df_live_nf.columns)}")

    # 2. Live Farmer Income Visits (consolidated_report) from csa-india
    print("  Mapping live CC Daily Reports to farmer_income_visits...")
    df_live_farmer = map_erp_data(live_cc, "farmer_income_visits")
    assert isinstance(df_live_farmer, pd.DataFrame)
    print(f"  ✓ Live CC Daily Reports mapped to farmer_income_visits: {len(df_live_farmer)} records. Columns: {list(df_live_farmer.columns)}")

    # 3. Live Stock Balance from fpohub
    print("  Pulling live Stock Balance from http://erp.fpohub.com...")
    live_stock = pull_dataset("stock_inventory")
    df_live_inv = map_erp_data(live_stock, "stock_inventory")
    assert isinstance(df_live_inv, pd.DataFrame)
    print(f"  ✓ Live Stock Balance mapped to stock_inventory: {len(df_live_inv)} records. Columns: {list(df_live_inv.columns)}")

    df_live_mov = map_erp_data(live_stock, "stock_movement")
    assert isinstance(df_live_mov, pd.DataFrame)
    print(f"  ✓ Live Stock Balance mapped to stock_movement: {len(df_live_mov)} records. Columns: {list(df_live_mov.columns)}")

except Exception as e:
    print(f"  ✗ Test J failed: {e}")
    test_errors.append(f"Test J: {e}")


# --------------------------------------------------------------------------
# Test K: TaskRunner End-to-End Storage & Checkpoint Update
# --------------------------------------------------------------------------
print("\n[TEST K] TaskRunner End-to-End Execution with Mappers", flush=True)
try:
    test_dataset_id = str(ObjectId())
    test_exec_id = str(uuid.uuid4())
    tasks[test_exec_id] = {"status": "running"}

    print("  Executing TaskRunner on 'stock_inventory' pipeline...")
    task_runner.run_pipeline_task(
        dataset_id=test_dataset_id,
        dataset_name="stock_inventory",
        user_id=str(ObjectId()),
        exec_id=test_exec_id,
        pipeline_id="stock_inventory",
    )

    assert tasks[test_exec_id]["status"] == "completed", f"Expected completed, got {tasks[test_exec_id]['status']}"
    
    # Check MongoDB document
    db_doc = (
        datasets_collection.find_one({"_id": ObjectId(test_dataset_id)})
        or datasets_collection.find_one({"_id": test_dataset_id})
        or datasets_collection.find_one({"_id": "stock_inventory"})
    )
    if not db_doc:
        from app.db.database import dataset_information_collection
        info = dataset_information_collection.find_one({"dataset_name": "stock_inventory"})
        if info:
            db_doc = datasets_collection.find_one({"_id": info["dataset_id"]})
    assert db_doc is not None, "Mapped dataset document must exist in MongoDB"
    assert db_doc["columns"] == StockInventoryMapper.target_fields, f"Stored columns mismatch: {db_doc['columns']}"
    print(f"  ✓ TaskRunner completed. MongoDB document verified with {len(db_doc['data'])} records and target columns: {db_doc['columns']}")

    # Check Checkpoint
    chk = get_sync_checkpoint("stock_inventory")
    assert chk is not None, "Checkpoint must be created"
    assert chk["sync_status"] == "success"
    print(f"  ✓ Checkpoint verified at watermark: {chk['last_sync_timestamp']}")

except Exception as e:
    print(f"  ✗ Test K failed: {e}")
    test_errors.append(f"Test K: {e}")


print("\n" + "=" * 75, flush=True)
if not test_errors:
    print("ALL PHASE 3 DASHBOARD MAPPING TESTS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 75, flush=True)
