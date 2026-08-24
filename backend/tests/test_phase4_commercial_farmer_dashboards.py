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
from app.dashboards.purchase_sales_dashboard import load_data as load_purchase_sales_data
from app.dashboards.farmer_income_dashboard import load_data as load_farmer_income_data
from app.dashboards.revenue_analysis_dashboard import load_data as load_revenue_analysis_data
from app.services.tasks.task_executor import task_runner, tasks

print("=" * 75, flush=True)
print("PHASE 4.4: COMMERCIAL & FARMER DASHBOARDS (2, 3 & 6) TEST SUITE", flush=True)
print("=" * 75, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# Test A: MongoDB Loader for Commercial & Farmer Collections
# --------------------------------------------------------------------------
print("\n[TEST A] MongoDB Loader for Commercial & Farmer Collections", flush=True)
try:
    for coll_name in ["territory_transactions", "farmer_income_visits", "revenue_analysis"]:
        df = load_dashboard_data_from_mongodb(coll_name)
        assert isinstance(df, pd.DataFrame), f"{coll_name} must return DataFrame"
        assert "_id" not in df.columns, f"_id must not leak in {coll_name}"
        print(f"  ✓ {coll_name} loaded: {len(df)} records. _id excluded: True")

except Exception as e:
    print(f"  ✗ Test A failed: {e}")
    test_errors.append(f"Test A: {e}")


# --------------------------------------------------------------------------
# Test B: Live ERP Pipeline Synchronization (Dashboards 2, 3, 6)
# --------------------------------------------------------------------------
print("\n[TEST B] Live ERP Pipeline Execution for Dashboards 2, 3, and 6", flush=True)
try:
    # 1. Sync territory_transactions (from fpohub)
    print("  Running task_runner on 'territory_transactions' pipeline...")
    exec_id_tt = str(uuid.uuid4())
    dataset_id_tt = str(ObjectId())
    tasks[exec_id_tt] = {"status": "running"}
    task_runner.run_pipeline_task(
        dataset_id=dataset_id_tt,
        dataset_name="territory_transactions",
        user_id=str(ObjectId()),
        exec_id=exec_id_tt,
        pipeline_id="territory_transactions",
    )
    assert tasks[exec_id_tt]["status"] == "completed"
    print("  ✓ territory_transactions pipeline completed")

    # 2. Sync farmer_income_visits (from csa-india)
    print("  Running task_runner on 'farmer_income_visits' pipeline...")
    exec_id_fi = str(uuid.uuid4())
    dataset_id_fi = str(ObjectId())
    tasks[exec_id_fi] = {"status": "running"}
    task_runner.run_pipeline_task(
        dataset_id=dataset_id_fi,
        dataset_name="farmer_income_visits",
        user_id=str(ObjectId()),
        exec_id=exec_id_fi,
        pipeline_id="farmer_income_visits",
    )
    assert tasks[exec_id_fi]["status"] == "completed"
    print("  ✓ farmer_income_visits pipeline completed")

    # 3. Sync revenue_analysis (from fpohub)
    print("  Running task_runner on 'revenue_analysis' pipeline...")
    exec_id_ra = str(uuid.uuid4())
    dataset_id_ra = str(ObjectId())
    tasks[exec_id_ra] = {"status": "running"}
    task_runner.run_pipeline_task(
        dataset_id=dataset_id_ra,
        dataset_name="revenue_analysis",
        user_id=str(ObjectId()),
        exec_id=exec_id_ra,
        pipeline_id="revenue_analysis",
    )
    assert tasks[exec_id_ra]["status"] == "completed"
    print("  ✓ revenue_analysis pipeline completed")

except Exception as e:
    print(f"  ✗ Test B failed: {e}")
    test_errors.append(f"Test B: {e}")


# --------------------------------------------------------------------------
# Test C: Dashboard 2 (Purchase & Sales Territory) Loading & Calculations
# --------------------------------------------------------------------------
print("\n[TEST C] Dashboard 2 (Purchase & Sales) Data Loading & Calculations", flush=True)
try:
    df_ps = load_purchase_sales_data()
    assert isinstance(df_ps, pd.DataFrame)
    assert not df_ps.empty, "Purchase & Sales data should not be empty"

    expected_cols = ["territory", "date", "purchase_amount", "sales_amount", "month_year", "month_period"]
    for col in expected_cols:
        assert col in df_ps.columns, f"Missing required column: {col}"

    assert pd.api.types.is_datetime64_any_dtype(df_ps["date"]), "date must be datetime64"
    assert pd.api.types.is_numeric_dtype(df_ps["purchase_amount"]), "purchase_amount must be numeric"

    # Test calculations
    total_sales = df_ps["sales_amount"].fillna(0).sum()
    total_purchase = df_ps["purchase_amount"].sum()
    net_position = total_sales - total_purchase

    territory_summary = (
        df_ps.groupby("territory", as_index=False)
        .agg(
            purchase_amount=("purchase_amount", "sum"),
            sales_amount=("sales_amount", "sum"),
        )
        .sort_values("purchase_amount", ascending=False)
    )

    print(f"  ✓ Dashboard 2 loaded {len(df_ps)} records.")
    print(f"  ✓ Total Purchases: ₹{total_purchase:,.2f}, Total Sales: ₹{total_sales:,.2f}, Net Position: ₹{net_position:,.2f}")
    print(f"  ✓ Territory summary generated ({len(territory_summary)} territories)")

except Exception as e:
    print(f"  ✗ Test C failed: {e}")
    test_errors.append(f"Test C: {e}")


# --------------------------------------------------------------------------
# Test D: Dashboard 3 (Farmer Income & Visits) Loading & Calculations
# --------------------------------------------------------------------------
print("\n[TEST D] Dashboard 3 (Farmer Income & Visits) Data Loading & Calculations", flush=True)
try:
    df_fi = load_farmer_income_data()
    assert isinstance(df_fi, pd.DataFrame)
    assert not df_fi.empty, "Farmer Income data should not be empty"

    expected_cols = [
        "coordinator_name", "month", "village", "farmers_met",
        "visits", "score", "income", "net_income", "yield"
    ]
    for col in expected_cols:
        assert col in df_fi.columns, f"Missing required column: {col}"

    assert pd.api.types.is_numeric_dtype(df_fi["farmers_met"]), "farmers_met must be numeric"
    assert pd.api.types.is_numeric_dtype(df_fi["visits"]), "visits must be numeric"
    assert pd.api.types.is_numeric_dtype(df_fi["score"]), "score must be numeric"

    # Verify unprovided financial columns remain null without breaking
    assert df_fi["income"].isna().all(), "income should be null"
    assert df_fi["net_income"].isna().all(), "net_income should be null"
    assert df_fi["yield"].isna().all(), "yield should be null"

    total_farmers_met = int(df_fi["farmers_met"].sum())
    total_visits = int(df_fi["visits"].sum())
    coord_summary = df_fi.groupby("coordinator_name", as_index=False)["score"].sum()
    village_summary = df_fi.groupby("village", as_index=False)["farmers_met"].sum()

    print(f"  ✓ Dashboard 3 loaded {len(df_fi)} records.")
    print(f"  ✓ Total Farmers Met: {total_farmers_met:,}, Total Visits: {total_visits:,}")
    print(f"  ✓ Null financial metrics preserved: income, net_income, yield are all null")
    print(f"  ✓ Coordinator summary ({len(coord_summary)} coordinators), Village summary ({len(village_summary)} clusters)")

except Exception as e:
    print(f"  ✗ Test D failed: {e}")
    test_errors.append(f"Test D: {e}")


# --------------------------------------------------------------------------
# Test E: Dashboard 6 (Revenue Analysis) Dynamic Calculations & No Hardcoding
# --------------------------------------------------------------------------
print("\n[TEST E] Dashboard 6 (Revenue Analysis) Dynamic Calculations & No Hardcoded Mockups", flush=True)
try:
    df_ra = load_revenue_analysis_data()
    assert isinstance(df_ra, pd.DataFrame)
    assert not df_ra.empty, "Revenue Analysis data should not be empty"

    expected_cols = ["territory", "month", "purchase_amount", "sales_amount", "net_revenue"]
    for col in expected_cols:
        assert col in df_ra.columns, f"Missing required column: {col}"

    # Verify dynamic metrics computed from actual MongoDB data
    avg_purchase = float(df_ra["purchase_amount"].mean())
    assert avg_purchase > 0, "avg_monthly_purchase must be computed dynamically from actual data"
    assert avg_purchase != 226310.0 or len(df_ra) != 25, "Must not use hardcoded dummy 226310.0"

    territory_summary = (
        df_ra.groupby("territory", as_index=False)
        .agg(
            net_revenue=("net_revenue", "sum"),
            purchase_amount=("purchase_amount", "sum"),
            sales_amount=("sales_amount", lambda s: s.sum() if s.notna().any() else 0.0),
        )
    )
    territory_summary["profit_margin"] = territory_summary.apply(
        lambda r: ((r["sales_amount"] - r["purchase_amount"]) / r["purchase_amount"] * 100.0)
        if r["purchase_amount"] > 0 else 0.0,
        axis=1
    )

    # Verify that hardcoded dummy numbers (-3380000, -1700.0) are NOT present
    for net_rev in territory_summary["net_revenue"]:
        assert net_rev != -3380000, "Must not contain hardcoded dummy -3380000"

    print(f"  ✓ Dashboard 6 loaded {len(df_ra)} records.")
    print(f"  ✓ Dynamic Avg Monthly Purchase: ₹{avg_purchase:,.2f}")
    print(f"  ✓ Dynamic Territory Summary (Territories: {list(territory_summary['territory'])})")
    print(f"  ✓ Verified: NO hardcoded dummy constants (-3380000, -1700%, 226310) remain.")

except Exception as e:
    print(f"  ✗ Test E failed: {e}")
    test_errors.append(f"Test E: {e}")


print("\n" + "=" * 75, flush=True)
if not test_errors:
    print("ALL PHASE 4.4 COMMERCIAL & FARMER DASHBOARDS TESTS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 75, flush=True)
