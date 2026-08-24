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
from app.dashboards.stock_movement_dashboard import load_data as load_stock_movement_data
from app.dashboards.stock_inventory_dashboard import load_data as load_stock_inventory_data
from app.services.tasks.task_executor import task_runner, tasks

print("=" * 75, flush=True)
print("PHASE 4.3: STOCK DASHBOARDS (DASHBOARD 4 & 5) MIGRATION TEST SUITE", flush=True)
print("=" * 75, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# Test A: MongoDB Loader for Stock Collections
# --------------------------------------------------------------------------
print("\n[TEST A] MongoDB Loader for Stock Collections", flush=True)
try:
    df_mov = load_dashboard_data_from_mongodb("stock_movement")
    assert isinstance(df_mov, pd.DataFrame), "stock_movement must return DataFrame"
    assert "_id" not in df_mov.columns, "_id must not leak into stock_movement DataFrame"
    print(f"  ✓ stock_movement loaded: {len(df_mov)} records. _id excluded: {'_id' not in df_mov.columns}")

    df_inv = load_dashboard_data_from_mongodb("stock_inventory")
    assert isinstance(df_inv, pd.DataFrame), "stock_inventory must return DataFrame"
    assert "_id" not in df_inv.columns, "_id must not leak into stock_inventory DataFrame"
    print(f"  ✓ stock_inventory loaded: {len(df_inv)} records. _id excluded: {'_id' not in df_inv.columns}")

except Exception as e:
    print(f"  ✗ Test A failed: {e}")
    test_errors.append(f"Test A: {e}")


# --------------------------------------------------------------------------
# Test B: Live Pipeline Execution for Stock Balance (Dashboards 4 & 5)
# --------------------------------------------------------------------------
print("\n[TEST B] Live ERP Pipeline Execution from http://erp.fpohub.com", flush=True)
try:
    # 1. Sync stock_inventory
    exec_id_inv = str(uuid.uuid4())
    dataset_id_inv = str(ObjectId())
    tasks[exec_id_inv] = {"status": "running"}

    print("  Running task_runner on 'stock_inventory' pipeline...")
    task_runner.run_pipeline_task(
        dataset_id=dataset_id_inv,
        dataset_name="stock_inventory",
        user_id=str(ObjectId()),
        exec_id=exec_id_inv,
        pipeline_id="stock_inventory",
    )
    assert tasks[exec_id_inv]["status"] == "completed", f"Expected completed, got {tasks[exec_id_inv]['status']}"
    print("  ✓ stock_inventory pipeline completed successfully")

    # 2. Sync stock_movement
    exec_id_mov = str(uuid.uuid4())
    dataset_id_mov = str(ObjectId())
    tasks[exec_id_mov] = {"status": "running"}

    print("  Running task_runner on 'stock_movement' pipeline...")
    task_runner.run_pipeline_task(
        dataset_id=dataset_id_mov,
        dataset_name="stock_movement",
        user_id=str(ObjectId()),
        exec_id=exec_id_mov,
        pipeline_id="stock_movement",
    )
    assert tasks[exec_id_mov]["status"] == "completed", f"Expected completed, got {tasks[exec_id_mov]['status']}"
    print("  ✓ stock_movement pipeline completed successfully")

except Exception as e:
    print(f"  ✗ Test B failed: {e}")
    test_errors.append(f"Test B: {e}")


# --------------------------------------------------------------------------
# Test C: Dashboard 4 (Stock Movement) Data Loading & Calculations
# --------------------------------------------------------------------------
print("\n[TEST C] Dashboard 4 (Stock Movement) Data Loading & Calculations", flush=True)
try:
    df_mov = load_stock_movement_data()
    assert isinstance(df_mov, pd.DataFrame), "Must return DataFrame"
    assert not df_mov.empty, "Stock movement data should not be empty"

    expected_cols = ["date", "in_qty", "out_qty", "balance_value", "year"]
    for col in expected_cols:
        assert col in df_mov.columns, f"Missing required column in stock_movement: {col}"

    assert pd.api.types.is_datetime64_any_dtype(df_mov["date"]), "date must be datetime64"
    assert pd.api.types.is_numeric_dtype(df_mov["in_qty"]), "in_qty must be numeric"
    assert pd.api.types.is_numeric_dtype(df_mov["out_qty"]), "out_qty must be numeric"
    assert pd.api.types.is_numeric_dtype(df_mov["balance_value"]), "balance_value must be numeric"

    # Test Dashboard 4 downstream calculations
    total_in = df_mov["in_qty"].sum()
    total_out = df_mov["out_qty"].sum()
    net_stock_movement = total_in - total_out
    year_summary = (
        df_mov.groupby("year", as_index=False)
        .agg(
            in_qty=("in_qty", "sum"),
            out_qty=("out_qty", "sum"),
            balance_value=("balance_value", "sum"),
        )
        .sort_values("year")
    )

    print(f"  ✓ Dashboard 4 loaded {len(df_mov)} records.")
    print(f"  ✓ Total In: {total_in:,.2f}, Total Out: {total_out:,.2f}, Net Movement: {net_stock_movement:,.2f}")
    print(f"  ✓ Year summary aggregation generated ({len(year_summary)} years)")

except Exception as e:
    print(f"  ✗ Test C failed: {e}")
    test_errors.append(f"Test C: {e}")


# --------------------------------------------------------------------------
# Test D: Dashboard 5 (Stock Inventory) Data Loading & Calculations
# --------------------------------------------------------------------------
print("\n[TEST D] Dashboard 5 (Stock Inventory) Data Loading & Calculations", flush=True)
try:
    df_inv = load_stock_inventory_data()
    assert isinstance(df_inv, pd.DataFrame), "Must return DataFrame"
    assert not df_inv.empty, "Stock inventory data should not be empty"

    expected_cols = ["company", "warehouse", "item_name", "item_group", "stock_qty", "stock_value"]
    for col in expected_cols:
        assert col in df_inv.columns, f"Missing required column in stock_inventory: {col}"

    assert pd.api.types.is_numeric_dtype(df_inv["stock_qty"]), "stock_qty must be numeric"
    assert pd.api.types.is_numeric_dtype(df_inv["stock_value"]), "stock_value must be numeric"

    # Test Dashboard 5 downstream calculations
    total_stock_qty = df_inv["stock_qty"].sum()
    total_stock_value = df_inv["stock_value"].sum()
    items_in_stock = df_inv["item_name"].nunique()
    warehouses_count = df_inv["warehouse"].nunique()
    avg_stock_value = total_stock_value / items_in_stock if items_in_stock > 0 else 0

    item_summary = (
        df_inv.groupby("item_name", as_index=False)["stock_value"]
        .sum()
        .sort_values("stock_value", ascending=True)
    )

    warehouse_summary = (
        df_inv.groupby("warehouse", as_index=False)["stock_qty"]
        .sum()
        .sort_values("stock_qty", ascending=False)
    )

    print(f"  ✓ Dashboard 5 loaded {len(df_inv)} records.")
    print(f"  ✓ Total Stock Qty: {total_stock_qty:,.2f}, Total Value: ₹{total_stock_value:,.2f}")
    print(f"  ✓ Unique Items: {items_in_stock}, Warehouses: {warehouses_count}, Avg Value: ₹{avg_stock_value:,.2f}")
    print(f"  ✓ Item summary ({len(item_summary)} items), Warehouse summary ({len(warehouse_summary)} warehouses)")

except Exception as e:
    print(f"  ✗ Test D failed: {e}")
    test_errors.append(f"Test D: {e}")


# --------------------------------------------------------------------------
# Test E: Filtering & Slicing Integrity
# --------------------------------------------------------------------------
print("\n[TEST E] Filtering & Slicing Integrity", flush=True)
try:
    # Test Dashboard 5 filters
    companies = sorted(df_inv["company"].dropna().unique())
    if companies:
        df_filtered = df_inv[df_inv["company"] == companies[0]]
        assert not df_filtered.empty, "Filtered DataFrame should contain records for existing company"
        print(f"  ✓ Company filter verified on '{companies[0]}': {len(df_filtered)} records")

    warehouses = sorted(df_inv["warehouse"].dropna().unique())
    if warehouses:
        df_filtered_wh = df_inv[df_inv["warehouse"] == warehouses[0]]
        assert not df_filtered_wh.empty
        print(f"  ✓ Warehouse filter verified on '{warehouses[0]}': {len(df_filtered_wh)} records")

    # Test Dashboard 4 year filter
    years = sorted(df_mov["year"].dropna().unique())
    if years:
        df_filtered_yr = df_mov[df_mov["year"] == years[0]]
        assert not df_filtered_yr.empty
        print(f"  ✓ Year filter verified on '{years[0]}': {len(df_filtered_yr)} records")

except Exception as e:
    print(f"  ✗ Test E failed: {e}")
    test_errors.append(f"Test E: {e}")


print("\n" + "=" * 75, flush=True)
if not test_errors:
    print("ALL PHASE 4.3 STOCK DASHBOARD TESTS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 75, flush=True)
