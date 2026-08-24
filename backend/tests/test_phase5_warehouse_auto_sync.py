import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "dashboards"))
load_dotenv()

from bson import ObjectId
from app.db.database import db, sync_checkpoints_collection
from app.dashboards.utilities import (
    trigger_warehouse_auto_sync,
    load_dashboard_data_from_mongodb,
)
from app.dashboards.stock_inventory_dashboard import load_data as load_stock_inventory_data
from app.dashboards.stock_movement_dashboard import load_data as load_stock_movement_data
from app.services.tasks.task_executor import task_runner, tasks

print("=" * 80, flush=True)
print("PHASE 5: WAREHOUSE REFRESH / REOPEN AUTO-SYNC TEST SUITE", flush=True)
print("=" * 80, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# [TEST 1] Warehouse Open/Refresh Auto-Sync Trigger Connection
# --------------------------------------------------------------------------
print("\n[TEST 1] Warehouse Auto-Sync Trigger Functionality", flush=True)
try:
    # 1. Trigger auto-sync for stock_inventory
    success_inv = trigger_warehouse_auto_sync("stock_inventory")
    assert success_inv is True, "trigger_warehouse_auto_sync('stock_inventory') should return True"
    print("  ✓ trigger_warehouse_auto_sync('stock_inventory') executed successfully")

    # 2. Trigger auto-sync for stock_movement
    success_mov = trigger_warehouse_auto_sync("stock_movement")
    assert success_mov is True, "trigger_warehouse_auto_sync('stock_movement') should return True"
    print("  ✓ trigger_warehouse_auto_sync('stock_movement') executed successfully")

except Exception as e:
    print(f"  ✗ Test 1 failed: {e}")
    test_errors.append(f"Test 1: {e}")


# --------------------------------------------------------------------------
# [TEST 2] Case 1: Live Data Sync on Warehouse Open/Refresh
# --------------------------------------------------------------------------
print("\n[TEST 2] Case 1: Data Loaded on Open/Refresh via Auto-Sync", flush=True)
try:
    # Load stock_inventory with auto_sync=True
    df_inv = load_dashboard_data_from_mongodb("stock_inventory", auto_sync=True)
    assert isinstance(df_inv, pd.DataFrame), "Must return DataFrame"
    assert not df_inv.empty, "stock_inventory DataFrame must not be empty"
    assert len(df_inv) == 35, f"Expected 35 records, got {len(df_inv)}"
    assert "_id" not in df_inv.columns, "_id must not leak"

    total_qty = df_inv["stock_qty"].sum()
    total_val = df_inv["stock_value"].sum()
    assert np.isclose(total_qty, 1178.0), f"Expected total qty 1178, got {total_qty}"
    assert np.isclose(total_val, 1174762.58, atol=1.0), f"Expected total value ₹1,174,762.58, got {total_val}"
    print(f"  ✓ Live stock_inventory loaded: {len(df_inv)} items, total_qty={total_qty:,.2f}, total_val=₹{total_val:,.2f}")

    # Load stock_movement with auto_sync=True
    df_mov = load_dashboard_data_from_mongodb("stock_movement", auto_sync=True)
    assert isinstance(df_mov, pd.DataFrame), "Must return DataFrame"
    assert not df_mov.empty, "stock_movement DataFrame must not be empty"
    assert len(df_mov) == 1, f"Expected 1 record, got {len(df_mov)}"
    assert "_id" not in df_mov.columns, "_id must not leak"

    total_in = df_mov["in_qty"].sum()
    total_out = df_mov["out_qty"].sum()
    net_mov = total_in - total_out
    assert np.isclose(total_in, 309.0), f"Expected in_qty 309, got {total_in}"
    assert np.isclose(total_out, 17.0), f"Expected out_qty 17, got {total_out}"
    assert np.isclose(net_mov, 292.0), f"Expected net_mov 292, got {net_mov}"
    print(f"  ✓ Live stock_movement loaded: in_qty={total_in:,.2f}, out_qty={total_out:,.2f}, net={net_mov:,.2f}")

except Exception as e:
    print(f"  ✗ Test 2 failed: {e}")
    test_errors.append(f"Test 2: {e}")


# --------------------------------------------------------------------------
# [TEST 3] Case 2: Repeated Opens / Refreshes & Zero Duplication
# --------------------------------------------------------------------------
print("\n[TEST 3] Case 2: Repeated Reopens & Idempotency Check", flush=True)
try:
    initial_inv_df = load_dashboard_data_from_mongodb("stock_inventory", auto_sync=False)
    initial_mov_df = load_dashboard_data_from_mongodb("stock_movement", auto_sync=False)
    initial_inv_count = len(initial_inv_df)
    initial_mov_count = len(initial_mov_df)

    # Trigger multiple consecutive syncs as if user repeatedly refreshes the page
    for i in range(3):
        trigger_warehouse_auto_sync("stock_inventory")
        trigger_warehouse_auto_sync("stock_movement")

    post_inv_df = load_dashboard_data_from_mongodb("stock_inventory", auto_sync=False)
    post_mov_df = load_dashboard_data_from_mongodb("stock_movement", auto_sync=False)
    post_inv_count = len(post_inv_df)
    post_mov_count = len(post_mov_df)

    assert post_inv_count == initial_inv_count, f"Duplication detected in stock_inventory! Initial={initial_inv_count}, Post={post_inv_count}"
    assert post_mov_count == initial_mov_count, f"Duplication detected in stock_movement! Initial={initial_mov_count}, Post={post_mov_count}"
    print(f"  ✓ Repeated syncs verified: stock_inventory={post_inv_count} docs, stock_movement={post_mov_count} docs (0 duplicates)")

except Exception as e:
    print(f"  ✗ Test 3 failed: {e}")
    test_errors.append(f"Test 3: {e}")


# --------------------------------------------------------------------------
# [TEST 4] Checkpoints Preservation & Watermark Integrity
# --------------------------------------------------------------------------
print("\n[TEST 4] Checkpoints & Watermark Integrity", flush=True)
try:
    for pipe_id in ["stock_inventory", "stock_movement"]:
        cp = sync_checkpoints_collection.find_one({"_id": pipe_id}) or sync_checkpoints_collection.find_one({"pipeline_id": pipe_id})
        assert cp is not None, f"Checkpoint document for '{pipe_id}' must exist"
        assert cp.get("sync_status") == "success", f"Checkpoint status for '{pipe_id}' must be 'success'"
        print(f"  ✓ Checkpoint verified for '{pipe_id}': status='{cp.get('sync_status')}', records={cp.get('record_count')}")

except Exception as e:
    print(f"  ✗ Test 4 failed: {e}")
    test_errors.append(f"Test 4: {e}")


# --------------------------------------------------------------------------
# [TEST 5] Case 3: Fault Tolerance When ERP is Temporarily Unavailable
# --------------------------------------------------------------------------
print("\n[TEST 5] Case 3: Fault Tolerance & MongoDB Preservation on ERP Failure", flush=True)
try:
    # Record initial state
    before_inv_df = load_dashboard_data_from_mongodb("stock_inventory", auto_sync=False)
    before_cp = sync_checkpoints_collection.find_one({"_id": "stock_inventory"}) or sync_checkpoints_collection.find_one({"pipeline_id": "stock_inventory"})
    before_sync_time = before_cp.get("last_sync_timestamp")

    # Simulate ERP network outage / 500 error during pull_dataset
    with patch("app.services.tasks.task_executor.pull_dataset") as mock_pull:
        mock_pull.side_effect = RuntimeError("ERP Connection Refused (Simulation Outage)")

        # Attempt auto-sync during failure
        sync_result = trigger_warehouse_auto_sync("stock_inventory")
        assert sync_result is False, "trigger_warehouse_auto_sync should return False on failure"

        # Load dashboard data during failure
        df_fallback = load_dashboard_data_from_mongodb("stock_inventory", auto_sync=False)
        assert not df_fallback.empty, "Existing MongoDB data MUST be preserved during ERP outage"
        assert len(df_fallback) == len(before_inv_df), "Document count must remain unchanged"

        # Verify checkpoint did NOT advance
        after_cp = sync_checkpoints_collection.find_one({"_id": "stock_inventory"}) or sync_checkpoints_collection.find_one({"pipeline_id": "stock_inventory"})
        assert after_cp.get("last_sync_timestamp") == before_sync_time, "Checkpoint must NOT advance on failure!"

    print("  ✓ ERP Outage safely isolated: MongoDB documents preserved intact (35 docs)")
    print("  ✓ Checkpoint watermark safely frozen at previous valid timestamp")
    print("  ✓ Dashboard seamlessly loads last known good state from MongoDB")

except Exception as e:
    print(f"  ✗ Test 5 failed: {e}")
    test_errors.append(f"Test 5: {e}")


# --------------------------------------------------------------------------
# [TEST 6] Dashboard Script Execution & Downstream Computations
# --------------------------------------------------------------------------
print("\n[TEST 6] Dashboard Script Data Loaders & Calculations", flush=True)
try:
    # 1. stock_inventory_dashboard.load_data()
    df_inv_dash = load_stock_inventory_data(force_sync=True)
    assert not df_inv_dash.empty
    assert len(df_inv_dash) == 35
    assert df_inv_dash["warehouse"].nunique() == 2
    assert "Stores - NFPCL" in df_inv_dash["warehouse"].values

    # 2. stock_movement_dashboard.load_data()
    df_mov_dash = load_stock_movement_data(force_sync=True)
    assert not df_mov_dash.empty
    assert len(df_mov_dash) == 1
    assert "year" in df_mov_dash.columns
    assert df_mov_dash["year"].iloc[0] == "2026"

    print("  ✓ stock_inventory_dashboard loaded fresh MongoDB state correctly")
    print("  ✓ stock_movement_dashboard loaded fresh MongoDB state correctly")

except Exception as e:
    print(f"  ✗ Test 6 failed: {e}")
    test_errors.append(f"Test 6: {e}")


print("\n" + "=" * 80, flush=True)
if not test_errors:
    print("ALL PHASE 5 WAREHOUSE AUTO-SYNC TESTS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 80, flush=True)
