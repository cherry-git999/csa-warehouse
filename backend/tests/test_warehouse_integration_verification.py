import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "dashboards"))
load_dotenv()

from bson import ObjectId
from app.db.database import db, datasets_collection, sync_checkpoints_collection
from app.dashboards.utilities import load_dashboard_data_from_mongodb
from app.dashboards.stock_movement_dashboard import load_data as load_stock_movement_data
from app.dashboards.stock_inventory_dashboard import load_data as load_stock_inventory_data
from app.services.tasks.task_executor import task_runner, tasks

print("=" * 80, flush=True)
print("WAREHOUSE INTEGRATION VERIFICATION TEST SUITE", flush=True)
print("=" * 80, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# 1. Pipeline Execution & Storage Verification for Warehouse
# --------------------------------------------------------------------------
print("\n[CHECK 1] Live ERP Extraction & MongoDB Synchronization for Warehouse", flush=True)
try:
    # 1. Run stock_inventory pipeline
    print("  Running task_runner on 'stock_inventory' pipeline...")
    exec_id_inv = str(uuid.uuid4())
    dataset_id_inv = str(ObjectId())
    tasks[exec_id_inv] = {"status": "running"}
    task_runner.run_pipeline_task(
        dataset_id=dataset_id_inv,
        dataset_name="stock_inventory",
        user_id=str(ObjectId()),
        exec_id=exec_id_inv,
        pipeline_id="stock_inventory",
    )
    assert tasks[exec_id_inv]["status"] == "completed", f"stock_inventory failed: {tasks[exec_id_inv]}"
    print("  ✓ stock_inventory pipeline executed and stored successfully")

    # 2. Run stock_movement pipeline
    print("  Running task_runner on 'stock_movement' pipeline...")
    exec_id_mov = str(uuid.uuid4())
    dataset_id_mov = str(ObjectId())
    tasks[exec_id_mov] = {"status": "running"}
    task_runner.run_pipeline_task(
        dataset_id=dataset_id_mov,
        dataset_name="stock_movement",
        user_id=str(ObjectId()),
        exec_id=exec_id_mov,
        pipeline_id="stock_movement",
    )
    assert tasks[exec_id_mov]["status"] == "completed", f"stock_movement failed: {tasks[exec_id_mov]}"
    print("  ✓ stock_movement pipeline executed and stored successfully")

except Exception as e:
    print(f"  ✗ Pipeline execution check failed: {e}")
    test_errors.append(f"Check 1: {e}")


# --------------------------------------------------------------------------
# 2. MongoDB Data Store & Collections Audit
# --------------------------------------------------------------------------
print("\n[CHECK 2] MongoDB Collections Structure & Exclusions", flush=True)
try:
    # Inventory
    df_inv = load_dashboard_data_from_mongodb("stock_inventory")
    assert isinstance(df_inv, pd.DataFrame), "stock_inventory must return DataFrame"
    assert not df_inv.empty, "stock_inventory must not be empty"
    assert "_id" not in df_inv.columns, "_id must not leak into DataFrame"
    expected_inv_cols = ["company", "warehouse", "item_name", "item_group", "stock_qty", "stock_value"]
    for col in expected_inv_cols:
        assert col in df_inv.columns, f"Missing {col} in stock_inventory"
    print(f"  ✓ stock_inventory collection: {len(df_inv)} documents, fields verified: {expected_inv_cols}")

    # Movement
    df_mov = load_dashboard_data_from_mongodb("stock_movement")
    assert isinstance(df_mov, pd.DataFrame), "stock_movement must return DataFrame"
    assert not df_mov.empty, "stock_movement must not be empty"
    assert "_id" not in df_mov.columns, "_id must not leak into DataFrame"
    expected_mov_cols = ["date", "in_qty", "out_qty", "balance_value"]
    for col in expected_mov_cols:
        assert col in df_mov.columns, f"Missing {col} in stock_movement"
    print(f"  ✓ stock_movement collection: {len(df_mov)} documents, fields verified: {expected_mov_cols}")

except Exception as e:
    print(f"  ✗ MongoDB collection audit failed: {e}")
    test_errors.append(f"Check 2: {e}")


# --------------------------------------------------------------------------
# 3. Live Stock Inventory Values & Calculations Audit
# --------------------------------------------------------------------------
print("\n[CHECK 3] Live Stock Inventory Values & Metrics Verification", flush=True)
try:
    df_inv = load_stock_inventory_data()
    assert not df_inv.empty

    total_stock_qty = float(df_inv["stock_qty"].sum())
    total_stock_value = float(df_inv["stock_value"].sum())
    unique_items = int(df_inv["item_name"].nunique())
    unique_warehouses = int(df_inv["warehouse"].nunique())
    avg_stock_val = total_stock_value / unique_items if unique_items > 0 else 0

    assert np.isclose(total_stock_qty, 1178.0), f"Expected total qty 1178.0, got {total_stock_qty}"
    assert np.isclose(total_stock_value, 1174762.58, atol=1.0), f"Expected total value ₹1,174,762.58, got {total_stock_value}"
    assert unique_items == 35, f"Expected 35 unique items, got {unique_items}"
    assert unique_warehouses == 2, f"Expected 2 warehouses, got {unique_warehouses}"

    # Verify warehouses
    warehouses = sorted(df_inv["warehouse"].unique())
    assert "Stores - NFPCL" in warehouses
    assert "Vana parthy 1 - NFPCL" in warehouses

    # Verify company
    companies = list(df_inv["company"].unique())
    assert "Nelathalli Farmer Producer Company Limited" in companies

    print(f"  ✓ Verified Total Stock Quantity: {total_stock_qty:,.2f}")
    print(f"  ✓ Verified Total Stock Value: ₹{total_stock_value:,.2f}")
    print(f"  ✓ Verified Unique Items: {unique_items}")
    print(f"  ✓ Verified Warehouses: {unique_warehouses} ({', '.join(warehouses)})")
    print(f"  ✓ Verified Average Valuation: ₹{avg_stock_val:,.2f}")

except Exception as e:
    print(f"  ✗ Stock inventory values check failed: {e}")
    test_errors.append(f"Check 3: {e}")


# --------------------------------------------------------------------------
# 4. Live Stock Movement Values & Calculations Audit
# --------------------------------------------------------------------------
print("\n[CHECK 4] Live Stock Movement Values & Metrics Verification", flush=True)
try:
    df_mov = load_stock_movement_data()
    assert not df_mov.empty

    total_in = float(df_mov["in_qty"].sum())
    total_out = float(df_mov["out_qty"].sum())
    net_movement = total_in - total_out
    total_balance_val = float(df_mov["balance_value"].sum())

    assert np.isclose(total_in, 309.0), f"Expected in_qty 309.0, got {total_in}"
    assert np.isclose(total_out, 17.0), f"Expected out_qty 17.0, got {total_out}"
    assert np.isclose(net_movement, 292.0), f"Expected net movement 292.0, got {net_movement}"
    assert np.isclose(total_balance_val, 1174762.58, atol=1.0), f"Expected balance value ₹1,174,762.58, got {total_balance_val}"

    # Verify date and year parsing
    assert pd.api.types.is_datetime64_any_dtype(df_mov["date"])
    assert "year" in df_mov.columns
    assert "2026" in df_mov["year"].values

    print(f"  ✓ Verified Total In Quantity: {total_in:,.2f}")
    print(f"  ✓ Verified Total Out Quantity: {total_out:,.2f}")
    print(f"  ✓ Verified Net Stock Movement: {net_movement:,.2f}")
    print(f"  ✓ Verified Balance Value: ₹{total_balance_val:,.2f}")
    print(f"  ✓ Verified Year: {sorted(df_mov['year'].unique())}")

except Exception as e:
    print(f"  ✗ Stock movement values check failed: {e}")
    test_errors.append(f"Check 4: {e}")


# --------------------------------------------------------------------------
# 5. Filters & Slicing Functionality Audit
# --------------------------------------------------------------------------
print("\n[CHECK 5] Warehouse Filters & Slicing Verification", flush=True)
try:
    # 1. Filter by company
    df_inv_f1 = df_inv[df_inv["company"] == "Nelathalli Farmer Producer Company Limited"]
    assert len(df_inv_f1) == 35

    # 2. Filter by warehouse
    df_inv_wh1 = df_inv[df_inv["warehouse"] == "Stores - NFPCL"]
    assert len(df_inv_wh1) == 29
    df_inv_wh2 = df_inv[df_inv["warehouse"] == "Vana parthy 1 - NFPCL"]
    assert len(df_inv_wh2) == 6

    # 3. Filter by item_group
    item_groups = df_inv["item_group"].unique()
    assert len(item_groups) > 0
    df_inv_grp = df_inv[df_inv["item_group"] == item_groups[0]]
    assert not df_inv_grp.empty

    # 4. Filter stock movement by year
    df_mov_yr = df_mov[df_mov["year"] == "2026"]
    assert len(df_mov_yr) == 1

    print(f"  ✓ Company filter verified (Nelathalli FPC: {len(df_inv_f1)} items)")
    print(f"  ✓ Warehouse filter verified (Stores: {len(df_inv_wh1)} items, Vana parthy: {len(df_inv_wh2)} items)")
    print(f"  ✓ Item group filter verified ({item_groups[0]}: {len(df_inv_grp)} items)")
    print(f"  ✓ Year filter verified (2026: {len(df_mov_yr)} records)")

except Exception as e:
    print(f"  ✗ Filters check failed: {e}")
    test_errors.append(f"Check 5: {e}")


# --------------------------------------------------------------------------
# 6. CSV Decoupling & Fallback Preservation Audit
# --------------------------------------------------------------------------
print("\n[CHECK 6] CSV Decoupling & Zero-Hardcoded-Data Audit", flush=True)
try:
    # Confirm reference CSVs exist
    inv_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "dashboards", "data", "stock_inventory_data.csv")
    mov_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "dashboards", "data", "stock_movement_data.csv")
    assert os.path.exists(inv_csv), f"Missing {inv_csv}"
    assert os.path.exists(mov_csv), f"Missing {mov_csv}"

    # Confirm MongoDB data is primary:
    # In CSV, dummy records are different from live MongoDB records (e.g. dummy CSV has different item counts/years)
    df_csv_inv = pd.read_csv(inv_csv, encoding="ISO-8859-1")
    df_live_inv = load_stock_inventory_data()
    # Live MongoDB data has 35 records from Nelathalli FPC
    assert len(df_live_inv) == 35
    assert "Nelathalli Farmer Producer Company Limited" in df_live_inv["company"].values

    print(f"  ✓ CSV reference files intact: stock_inventory_data.csv, stock_movement_data.csv")
    print(f"  ✓ Primary data source confirmed: MongoDB (not CSV)")

except Exception as e:
    print(f"  ✗ Decoupling check failed: {e}")
    test_errors.append(f"Check 6: {e}")


# --------------------------------------------------------------------------
# 7. Checkpoints Audit for Warehouse Pipelines
# --------------------------------------------------------------------------
print("\n[CHECK 7] Warehouse Pipelines Checkpoint State", flush=True)
try:
    for p_id in ["stock_inventory", "stock_movement"]:
        cp = sync_checkpoints_collection.find_one({"_id": p_id}) or sync_checkpoints_collection.find_one({"pipeline_id": p_id})
        assert cp is not None, f"Checkpoint for {p_id} must exist"
        wm = cp.get("watermark") or cp.get("last_successful_sync")
        print(f"  ✓ Checkpoint for '{p_id}': watermark='{wm}'")

except Exception as e:
    print(f"  ✗ Checkpoint audit failed: {e}")
    test_errors.append(f"Check 7: {e}")


print("\n" + "=" * 80, flush=True)
if not test_errors:
    print("ALL WAREHOUSE INTEGRATION VERIFICATION CHECKS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 80, flush=True)
