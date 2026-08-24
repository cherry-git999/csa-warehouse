import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "dashboards"))
load_dotenv()

from bson import ObjectId
from app.db.database import db, datasets_collection
from app.dashboards.utilities import load_dashboard_data_from_mongodb
from app.dashboards.nf_coordinator_dashboard import load_nf_data
from app.dashboards.purchase_sales_dashboard import load_data as load_d2_data
from app.dashboards.farmer_income_dashboard import load_data as load_d3_data
from app.dashboards.stock_movement_dashboard import load_data as load_d4_data
from app.dashboards.stock_inventory_dashboard import load_data as load_d5_data
from app.dashboards.revenue_analysis_dashboard import load_data as load_d6_data
from app.services.tasks.task_executor import task_runner, tasks

print("=" * 80, flush=True)
print("PHASE 4.5: COMPLETE MASTER END-TO-END INTEGRATION & REGRESSION TEST SUITE", flush=True)
print("=" * 80, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# Section 1: All 6 Pipelines Live Synchronization
# --------------------------------------------------------------------------
print("\n[SECTION 1] Live ERP Extraction & Pipeline Synchronization", flush=True)
pipelines = [
    ("Dashboard 1", "nf_coordinator_activities", "CC Daily Reports", "http://erp.csa-india.org"),
    ("Dashboard 2", "territory_transactions", "Purchase Invoice", "http://erp.fpohub.com"),
    ("Dashboard 3", "farmer_income_visits", "CC Daily Reports", "http://erp.csa-india.org"),
    ("Dashboard 4", "stock_movement", "Stock Balance", "http://erp.fpohub.com"),
    ("Dashboard 5", "stock_inventory", "Stock Balance", "http://erp.fpohub.com"),
    ("Dashboard 6", "revenue_analysis", "Purchase Invoice", "http://erp.fpohub.com"),
]

for d_name, p_id, dataset_src, erp_url in pipelines:
    try:
        exec_id = str(uuid.uuid4())
        dataset_id = str(ObjectId())
        tasks[exec_id] = {"status": "running"}
        
        print(f"  Running pipeline '{p_id}' ({d_name}) from {erp_url} [{dataset_src}]...")
        task_runner.run_pipeline_task(
            dataset_id=dataset_id,
            dataset_name=p_id,
            user_id=str(ObjectId()),
            exec_id=exec_id,
            pipeline_id=p_id,
        )
        assert tasks[exec_id]["status"] == "completed", f"{p_id} failed with status: {tasks[exec_id].get('status')}"
        print(f"  ✓ {p_id} completed successfully")
    except Exception as e:
        print(f"  ✗ {p_id} execution failed: {e}")
        test_errors.append(f"Pipeline {p_id}: {e}")


# --------------------------------------------------------------------------
# Section 2: MongoDB Collections Audit & Document Counts
# --------------------------------------------------------------------------
print("\n[SECTION 2] MongoDB Collections Audit & Data Verification", flush=True)
collections = [
    ("nf_coordinator_activities", ["coordinator_name", "district", "date", "type_of_activity", "planned_activities", "actual_activities", "total_score"]),
    ("territory_transactions", ["territory", "date", "purchase_amount", "sales_amount"]),
    ("farmer_income_visits", ["coordinator_name", "month", "village", "farmers_met", "visits", "score", "income", "net_income", "yield"]),
    ("stock_movement", ["date", "in_qty", "out_qty", "balance_value"]),
    ("stock_inventory", ["company", "warehouse", "item_name", "item_group", "stock_qty", "stock_value"]),
    ("revenue_analysis", ["territory", "month", "purchase_amount", "sales_amount"]),
]

collection_counts = {}

for coll_name, expected_fields in collections:
    try:
        df = load_dashboard_data_from_mongodb(coll_name)
        assert isinstance(df, pd.DataFrame), f"{coll_name} must return DataFrame"
        assert not df.empty, f"{coll_name} must contain documents"
        assert "_id" not in df.columns, f"_id leaked in {coll_name}"
        
        for field in expected_fields:
            assert field in df.columns, f"Missing field '{field}' in {coll_name}"
            
        count = len(df)
        collection_counts[coll_name] = count
        print(f"  ✓ Collection '{coll_name}': {count} documents, schema valid, _id excluded")
    except Exception as e:
        print(f"  ✗ Collection '{coll_name}' audit failed: {e}")
        test_errors.append(f"Collection {coll_name}: {e}")


# --------------------------------------------------------------------------
# Section 3: Dashboard-by-Dashboard Data Loading & Calculations
# --------------------------------------------------------------------------
print("\n[SECTION 3] Dashboard-by-Dashboard Verification", flush=True)

# Dashboard 1
print("  [Dashboard 1 — NF Coordinator]")
try:
    df1 = load_nf_data()
    assert not df1.empty
    assert pd.api.types.is_datetime64_any_dtype(df1["date"])
    assert df1["total_score"].sum() > 0
    assert df1["planned_activities"].sum() > 0
    assert df1["actual_activities"].sum() > 0
    print(f"    ✓ Dashboard 1: {len(df1)} records, total score={df1['total_score'].sum()}, planned={df1['planned_activities'].sum()}, actual={df1['actual_activities'].sum()}")
except Exception as e:
    print(f"    ✗ Dashboard 1 failed: {e}")
    test_errors.append(f"Dashboard 1: {e}")

# Dashboard 2
print("  [Dashboard 2 — Purchase & Sales Territory]")
try:
    df2 = load_d2_data()
    assert not df2.empty
    assert pd.api.types.is_datetime64_any_dtype(df2["date"])
    assert pd.api.types.is_numeric_dtype(df2["purchase_amount"])
    assert df2["sales_amount"].isna().all(), "sales_amount must remain null"
    total_purchases_d2 = df2["purchase_amount"].sum()
    assert total_purchases_d2 > 0
    print(f"    ✓ Dashboard 2: {len(df2)} records, total purchases=₹{total_purchases_d2:,.2f}, sales safely null")
except Exception as e:
    print(f"    ✗ Dashboard 2 failed: {e}")
    test_errors.append(f"Dashboard 2: {e}")

# Dashboard 3
print("  [Dashboard 3 — Farmer Income & Visits]")
try:
    df3 = load_d3_data()
    assert not df3.empty
    assert pd.api.types.is_numeric_dtype(df3["farmers_met"])
    assert pd.api.types.is_numeric_dtype(df3["visits"])
    assert pd.api.types.is_numeric_dtype(df3["score"])
    assert df3["income"].isna().all(), "income must remain null"
    assert df3["net_income"].isna().all(), "net_income must remain null"
    assert df3["yield"].isna().all(), "yield must remain null"
    print(f"    ✓ Dashboard 3: {len(df3)} records, farmers met={df3['farmers_met'].sum()}, visits={df3['visits'].sum()}, score={df3['score'].sum()}, financial fields safely null")
except Exception as e:
    print(f"    ✗ Dashboard 3 failed: {e}")
    test_errors.append(f"Dashboard 3: {e}")

# Dashboard 4
print("  [Dashboard 4 — Stock Movement]")
try:
    df4 = load_d4_data()
    assert not df4.empty
    assert pd.api.types.is_datetime64_any_dtype(df4["date"])
    assert pd.api.types.is_numeric_dtype(df4["in_qty"])
    assert pd.api.types.is_numeric_dtype(df4["out_qty"])
    assert pd.api.types.is_numeric_dtype(df4["balance_value"])
    net_movement = df4["in_qty"].sum() - df4["out_qty"].sum()
    print(f"    ✓ Dashboard 4: {len(df4)} records, total in={df4['in_qty'].sum()}, out={df4['out_qty'].sum()}, net={net_movement:,.2f}")
except Exception as e:
    print(f"    ✗ Dashboard 4 failed: {e}")
    test_errors.append(f"Dashboard 4: {e}")

# Dashboard 5
print("  [Dashboard 5 — Stock Inventory]")
try:
    df5 = load_d5_data()
    assert not df5.empty
    assert pd.api.types.is_numeric_dtype(df5["stock_qty"])
    assert pd.api.types.is_numeric_dtype(df5["stock_value"])
    total_qty = df5["stock_qty"].sum()
    total_val = df5["stock_value"].sum()
    print(f"    ✓ Dashboard 5: {len(df5)} records, total qty={total_qty:,.2f}, total value=₹{total_val:,.2f}, items={df5['item_name'].nunique()}, warehouses={df5['warehouse'].nunique()}")
except Exception as e:
    print(f"    ✗ Dashboard 5 failed: {e}")
    test_errors.append(f"Dashboard 5: {e}")

# Dashboard 6
print("  [Dashboard 6 — Revenue Analysis]")
try:
    df6 = load_d6_data()
    assert not df6.empty
    assert pd.api.types.is_numeric_dtype(df6["purchase_amount"])
    assert "net_revenue" in df6.columns
    avg_purchase_d6 = float(df6["purchase_amount"].mean())
    assert avg_purchase_d6 > 0
    assert avg_purchase_d6 != 226310.0 or len(df6) != 25, "Hardcoded constant 226310.0 detected!"
    print(f"    ✓ Dashboard 6: {len(df6)} records, dynamic avg monthly purchase=₹{avg_purchase_d6:,.2f}, hardcoded mockups eliminated")
except Exception as e:
    print(f"    ✗ Dashboard 6 failed: {e}")
    test_errors.append(f"Dashboard 6: {e}")


# --------------------------------------------------------------------------
# Section 4: CSV Decoupling & Fallback Preservation Check
# --------------------------------------------------------------------------
print("\n[SECTION 4] CSV Reference Files Preservation Check", flush=True)
csv_files = [
    "nf_coordinator_data.csv",
    "purchase_sales_data.csv",
    "farmer_income_data.csv",
    "stock_movement_data.csv",
    "stock_inventory_data.csv",
    "revenue_analysis_data.csv",
]

for csv_f in csv_files:
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "dashboards", "data", csv_f)
    assert os.path.exists(csv_path), f"CSV reference file missing: {csv_path}"
    print(f"  ✓ Preserved reference CSV: {csv_f} ({os.path.getsize(csv_path)} bytes)")


# --------------------------------------------------------------------------
# Section 5: Checkpoints & Incremental Watermarks Integrity
# --------------------------------------------------------------------------
print("\n[SECTION 5] Checkpoints & Incremental Watermarks Verification", flush=True)
try:
    checkpoints_coll = db["sync_checkpoints"]
    all_checkpoints = list(checkpoints_coll.find({}))
    assert len(all_checkpoints) > 0, "sync_checkpoints collection should not be empty"
    for cp in all_checkpoints:
        p_id = cp.get("pipeline_id") or cp.get("_id")
        wm = cp.get("watermark") or cp.get("last_successful_sync")
        print(f"  ✓ Active Checkpoint: pipeline='{p_id}', watermark='{wm}'")
except Exception as e:
    print(f"  ✗ Checkpoint verification failed: {e}")
    test_errors.append(f"Checkpoints: {e}")


print("\n" + "=" * 80, flush=True)
if not test_errors:
    print("ALL PHASE 4.5 END-TO-END INTEGRATION TESTS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 80, flush=True)
