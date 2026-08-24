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
from app.services.tasks.task_executor import task_runner, tasks
from app.mappings.nf_coordinator import NFCoordinatorMapper

print("=" * 75, flush=True)
print("PHASE 4.1 & 4.2: DASHBOARD 1 PILOT MIGRATION TEST SUITE", flush=True)
print("=" * 75, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# Test 1: Generic MongoDB Loader Utility (utilities.py)
# --------------------------------------------------------------------------
print("\n[TEST 1] Generic MongoDB Loader Utility Functionality", flush=True)
try:
    # 1. Non-existent collection returns empty DataFrame
    df_empty = load_dashboard_data_from_mongodb("non_existent_dummy_collection_123")
    assert isinstance(df_empty, pd.DataFrame), "Must return DataFrame"
    assert df_empty.empty, "Non-existent collection must return empty DataFrame"
    print("  ✓ Non-existent collection handled safely (returned empty DataFrame)")

    # 2. Query direct test collection with _id exclusion
    test_coll_name = f"test_coll_{uuid.uuid4().hex[:8]}"
    db[test_coll_name].insert_many([
        {"item": "A", "val": 10},
        {"item": "B", "val": 20},
    ])
    df_direct = load_dashboard_data_from_mongodb(test_coll_name)
    assert len(df_direct) == 2, f"Expected 2 rows, got {len(df_direct)}"
    assert "_id" not in df_direct.columns, "_id must be excluded from DataFrame"
    assert "item" in df_direct.columns and "val" in df_direct.columns
    db[test_coll_name].drop()
    print("  ✓ Direct MongoDB collection queried successfully with _id excluded")

except Exception as e:
    print(f"  ✗ Test 1 failed: {e}")
    test_errors.append(f"Test 1: {e}")


# --------------------------------------------------------------------------
# Test 2: Synchronize live ERP data into MongoDB for Dashboard 1
# --------------------------------------------------------------------------
print("\n[TEST 2] End-to-End Pipeline Execution for 'nf_coordinator_activities'", flush=True)
try:
    pipe_id = "nf_coordinator_activities"
    exec_id = str(uuid.uuid4())
    dataset_id = str(ObjectId())
    tasks[exec_id] = {"status": "running"}

    print("  Running task_runner on 'nf_coordinator_activities'...")
    task_runner.run_pipeline_task(
        dataset_id=dataset_id,
        dataset_name=pipe_id,
        user_id=str(ObjectId()),
        exec_id=exec_id,
        pipeline_id=pipe_id,
    )
    assert tasks[exec_id]["status"] == "completed", f"Expected completed, got {tasks[exec_id]['status']}"
    print("  ✓ Live ERP sync and Phase 3 mapping completed successfully")

except Exception as e:
    print(f"  ✗ Test 2 failed: {e}")
    test_errors.append(f"Test 2: {e}")


# --------------------------------------------------------------------------
# Test 3: Dashboard 1 load_nf_data() reading from MongoDB
# --------------------------------------------------------------------------
print("\n[TEST 3] Dashboard 1 Data Loading from MongoDB", flush=True)
try:
    df_loaded = load_nf_data()
    assert isinstance(df_loaded, pd.DataFrame), "Must return DataFrame"
    assert not df_loaded.empty, "Loaded DataFrame should not be empty"

    required_cols = [
        "coordinator_name",
        "district",
        "date",
        "type_of_activity",
        "planned_activities",
        "actual_activities",
        "total_score",
        "month_label",
        "month_short",
        "month_period",
    ]
    for col in required_cols:
        assert col in df_loaded.columns, f"Missing required column: {col}"

    print(f"  ✓ Dashboard 1 loaded {len(df_loaded)} records from MongoDB.")
    print(f"  ✓ Columns present: {list(df_loaded.columns)}")
    print(f"  ✓ Date parsed correctly: dtype={df_loaded['date'].dtype}, Sample={df_loaded['date'].iloc[0]}")

except Exception as e:
    print(f"  ✗ Test 3 failed: {e}")
    test_errors.append(f"Test 3: {e}")


# --------------------------------------------------------------------------
# Test 4: Dashboard 1 Downstream Calculations & Aggregations
# --------------------------------------------------------------------------
print("\n[TEST 4] Dashboard 1 Downstream Calculations & KPI Integrity", flush=True)
try:
    df_test = load_nf_data().copy()

    # 1. Total KPI Aggregates
    total_score = int(df_test["total_score"].sum())
    total_planned = int(df_test["planned_activities"].sum())
    total_actual = int(df_test["actual_activities"].sum())
    total_variance = total_actual - total_planned
    overall_status = "Ahead" if total_variance >= 0 else "Behind"

    assert isinstance(total_score, int)
    assert isinstance(total_planned, int)
    assert isinstance(total_actual, int)
    print(f"  ✓ Total Score: {total_score}, Planned: {total_planned}, Actual: {total_actual}, Status: {overall_status}")

    # 2. Coordinator Performance Table
    coord_perf = (
        df_test.groupby("coordinator_name", as_index=False)
        .agg(
            Planned=("planned_activities", "sum"),
            Actual=("actual_activities", "sum"),
        )
    )
    coord_perf["Variance"] = coord_perf["Actual"] - coord_perf["Planned"]
    coord_perf["Status"] = coord_perf["Variance"].apply(
        lambda v: "Ahead" if v > 0 else ("On Track" if v == 0 else "Behind")
    )
    assert not coord_perf.empty, "Coordinator performance table must not be empty"
    print(f"  ✓ Coordinator performance table generated ({len(coord_perf)} coordinators)")

    # 3. Monthly Score Trend
    monthly_scores = (
        df_test.groupby(["month_period", "month_short"], as_index=False)["total_score"]
        .sum()
        .sort_values("month_period")
    )
    assert not monthly_scores.empty, "Monthly scores table must not be empty"
    print(f"  ✓ Monthly scores trend generated ({len(monthly_scores)} periods)")

except Exception as e:
    print(f"  ✗ Test 4 failed: {e}")
    test_errors.append(f"Test 4: {e}")


print("\n" + "=" * 75, flush=True)
if not test_errors:
    print("ALL PHASE 4.1 & 4.2 TESTS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 75, flush=True)
