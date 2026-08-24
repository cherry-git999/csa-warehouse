import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from bson import ObjectId
from app.db.database import (
    client as mongo_client,
    datasets_collection,
    dataset_information_collection,
    pipelines_history_collection,
    sync_checkpoints_collection,
)
from app.services.storage.mongodb_service import (
    store_to_mongodb,
    get_sync_checkpoint,
    update_sync_checkpoint,
    _merge_records,
)
from app.config.pipeline_mapping import (
    get_pipeline_config,
    get_pipeline_source_type,
    get_pipeline_sync_strategy,
    get_pipeline_identity_key,
)
from app.utils.erp import pull_dataset
from app.services.tasks.task_executor import task_runner, tasks

print("=" * 75, flush=True)
print("PHASE 2: STORAGE ABSTRACTION & SYNCHRONIZATION TEST SUITE", flush=True)
print("=" * 75, flush=True)

test_errors = []

# --------------------------------------------------------------------------
# Test A: Initial Full Sync & Storage
# --------------------------------------------------------------------------
print("\n[TEST A] Initial Full Sync & Storage Creation", flush=True)
try:
    test_pipeline_id = f"test_pipe_initial_{uuid.uuid4().hex[:8]}"
    test_dataset_id = str(ObjectId())
    test_user_id = str(ObjectId())
    test_exec_id = str(uuid.uuid4())

    initial_records = [
        {"name": "INV-001", "customer": "Farmer A", "amount": 100, "modified": "2026-08-20 10:00:00"},
        {"name": "INV-002", "customer": "Farmer B", "amount": 200, "modified": "2026-08-20 11:00:00"},
    ]

    # Verify no checkpoint exists initially
    chk_before = get_sync_checkpoint(test_pipeline_id)
    assert chk_before is None, "Checkpoint should not exist before initial sync"

    # Store via enhanced store_to_mongodb
    res = store_to_mongodb(
        dataset_id=test_dataset_id,
        dataset_name=test_pipeline_id,
        user_id=test_user_id,
        username="",
        user_email="",
        dataset_records=initial_records,
        pipeline_id=test_pipeline_id,
        identity_key="name",
        mode="upsert",
    )
    assert res.get("inserted") is True or res.get("record_count") == 2

    # Advance checkpoint
    update_sync_checkpoint(
        pipeline_id=test_pipeline_id,
        last_sync_timestamp="2026-08-20 11:00:00",
        execution_id=test_exec_id,
        record_count=2,
        status="success",
        source_type="doctype",
    )

    chk_after = get_sync_checkpoint(test_pipeline_id)
    assert chk_after is not None, "Checkpoint must exist after update"
    assert chk_after["last_sync_timestamp"] == "2026-08-20 11:00:00"
    assert chk_after["sync_status"] == "success"

    # Verify document in DB
    db_doc = datasets_collection.find_one({"_id": ObjectId(test_dataset_id)})
    assert db_doc is not None, "Dataset document should exist in MongoDB"
    assert len(db_doc["data"]) == 2, f"Expected 2 records, got {len(db_doc['data'])}"
    print(f"  ✓ Initial dataset stored: {len(db_doc['data'])} records, checkpoint recorded at {chk_after['last_sync_timestamp']}")

except Exception as e:
    print(f"  ✗ Test A failed: {e}")
    test_errors.append(f"Test A: {e}")


# --------------------------------------------------------------------------
# Test B: Repeated Sync & Idempotency (Zero Duplicates)
# --------------------------------------------------------------------------
print("\n[TEST B] Repeated Sync & Idempotency (Zero Duplicates)", flush=True)
try:
    # Run the exact same records through store_to_mongodb again
    res_repeat = store_to_mongodb(
        dataset_id=test_dataset_id,
        dataset_name=test_pipeline_id,
        user_id=test_user_id,
        username="",
        user_email="",
        dataset_records=initial_records,
        pipeline_id=test_pipeline_id,
        identity_key="name",
        mode="upsert",
    )

    db_doc_repeat = datasets_collection.find_one({"_id": ObjectId(test_dataset_id)})
    assert len(db_doc_repeat["data"]) == 2, f"Expected 2 records, got {len(db_doc_repeat['data'])} (Duplicates detected!)"
    print(f"  ✓ Repeated sync with identical records resulted in exactly {len(db_doc_repeat['data'])} records (no duplicates)")

except Exception as e:
    print(f"  ✗ Test B failed: {e}")
    test_errors.append(f"Test B: {e}")


# --------------------------------------------------------------------------
# Test C: Modified Record In-Place Update
# --------------------------------------------------------------------------
print("\n[TEST C] Modified Record In-Place Update", flush=True)
try:
    # Simulate an update to INV-001 (amount changed from 100 to 999) + 1 new record INV-003
    updated_batch = [
        {"name": "INV-001", "customer": "Farmer A", "amount": 999, "modified": "2026-08-21 14:00:00", "status": "Paid"},
        {"name": "INV-003", "customer": "Farmer C", "amount": 350, "modified": "2026-08-21 15:00:00"},
    ]

    res_update = store_to_mongodb(
        dataset_id=test_dataset_id,
        dataset_name=test_pipeline_id,
        user_id=test_user_id,
        username="",
        user_email="",
        dataset_records=updated_batch,
        pipeline_id=test_pipeline_id,
        identity_key="name",
        mode="upsert",
    )

    db_doc_updated = datasets_collection.find_one({"_id": ObjectId(test_dataset_id)})
    data = db_doc_updated["data"]
    assert len(data) == 3, f"Expected 3 records total (2 updated/preserved + 1 new), got {len(data)}"

    # Check that INV-001 was updated in place
    inv_001 = next(r for r in data if r["name"] == "INV-001")
    assert inv_001["amount"] == 999, f"Expected amount 999, got {inv_001['amount']}"
    assert inv_001["status"] == "Paid", "Expected new field 'status' to be merged"

    # Check that INV-002 was preserved
    inv_002 = next(r for r in data if r["name"] == "INV-002")
    assert inv_002["amount"] == 200, "Expected INV-002 to be preserved"

    # Check that INV-003 was appended
    inv_003 = next(r for r in data if r["name"] == "INV-003")
    assert inv_003["amount"] == 350, "Expected INV-003 to be appended"

    print(f"  ✓ Modified record updated in-place (INV-001: amount={inv_001['amount']}, status='{inv_001.get('status')}')")
    print(f"  ✓ Prior records preserved (INV-002 present), new records appended (INV-003 present)")

except Exception as e:
    print(f"  ✗ Test C failed: {e}")
    test_errors.append(f"Test C: {e}")


# --------------------------------------------------------------------------
# Test D: Incremental Pull with Watermark Filter
# --------------------------------------------------------------------------
print("\n[TEST D] Incremental Pull Watermark Filtering", flush=True)
try:
    # Test pull_dataset with since_timestamp parameter
    test_watermark = "2024-01-01 00:00:00"
    df_incremental = pull_dataset("sales_invoice", since_timestamp=test_watermark)
    print(f"  ✓ pull_dataset('sales_invoice', since_timestamp='{test_watermark}') returned {len(df_incremental)} records")
    if not df_incremental.empty:
        print(f"  ✓ Columns returned including audit fields: {[c for c in ['name', 'modified', 'creation'] if c in df_incremental.columns]}")

except Exception as e:
    print(f"  ✗ Test D failed: {e}")
    test_errors.append(f"Test D: {e}")


# --------------------------------------------------------------------------
# Test E: Failure Isolation (Checkpoint is NOT advanced)
# --------------------------------------------------------------------------
print("\n[TEST E] Failure Isolation (Checkpoint Must NOT Advance on Failure)", flush=True)
try:
    fail_pipeline_id = f"test_pipe_fail_{uuid.uuid4().hex[:8]}"
    initial_watermark = "2026-08-20 00:00:00"

    # Set an initial successful checkpoint
    update_sync_checkpoint(
        pipeline_id=fail_pipeline_id,
        last_sync_timestamp=initial_watermark,
        execution_id="initial-exec-id",
        record_count=10,
        status="success",
    )

    chk_initial = get_sync_checkpoint(fail_pipeline_id)
    assert chk_initial["last_sync_timestamp"] == initial_watermark

    # Simulate a failing task execution with invalid dataset_id
    fail_exec_id = str(uuid.uuid4())
    tasks[fail_exec_id] = {"status": "running"}

    # Pass an invalid target that causes an error in task runner
    task_runner.run_pipeline_task(
        dataset_id="invalid_not_an_object_id_!!!",
        dataset_name=fail_pipeline_id,
        user_id=str(ObjectId()),
        exec_id=fail_exec_id,
        pipeline_id=fail_pipeline_id,
    )

    assert tasks[fail_exec_id]["status"] == "error", "Task must be marked as error"

    # Check that checkpoint was NOT modified
    chk_after_fail = get_sync_checkpoint(fail_pipeline_id)
    assert chk_after_fail["last_sync_timestamp"] == initial_watermark, "Checkpoint MUST NOT advance on failure!"
    assert chk_after_fail["last_execution_id"] == "initial-exec-id"
    print(f"  ✓ Failure verified: Task marked 'error', checkpoint safely retained at {chk_after_fail['last_sync_timestamp']}")

except Exception as e:
    print(f"  ✗ Test E failed: {e}")
    test_errors.append(f"Test E: {e}")


# --------------------------------------------------------------------------
# Test F: Query Report Snapshot Replacement
# --------------------------------------------------------------------------
print("\n[TEST F] Query Report Snapshot Replacement", flush=True)
try:
    report_dataset_id = str(ObjectId())
    report_dataset_name = f"test_stock_balance_{uuid.uuid4().hex[:8]}"
    report_pipeline_id = "stock_balance"
    cfg = get_pipeline_config(report_pipeline_id)

    assert cfg["source_type"] == "query_report", "Stock balance must be query_report"
    assert cfg["sync_strategy"] == "snapshot", "Stock balance must use snapshot sync_strategy"
    assert cfg["identity_key"] is None, "Query report identity_key should be None"

    # Batch 1 (Day 1 snapshot)
    day1_records = [
        {"item_code": "ITEM-A", "warehouse": "WH-1", "bal_qty": 50, "bal_val": 500},
        {"item_code": "ITEM-B", "warehouse": "WH-1", "bal_qty": 30, "bal_val": 300},
    ]
    store_to_mongodb(
        dataset_id=report_dataset_id,
        dataset_name=report_dataset_name,
        user_id=str(ObjectId()),
        username="",
        user_email="",
        dataset_records=day1_records,
        pipeline_id=report_pipeline_id,
        identity_key=None,
        mode="replace",
    )
    doc1 = datasets_collection.find_one({"_id": ObjectId(report_dataset_id)})
    assert len(doc1["data"]) == 2

    # Batch 2 (Day 2 fresh snapshot with different items)
    day2_records = [
        {"item_code": "ITEM-C", "warehouse": "WH-2", "bal_qty": 100, "bal_val": 1000},
    ]
    store_to_mongodb(
        dataset_id=report_dataset_id,
        dataset_name=report_dataset_name,
        user_id=str(ObjectId()),
        username="",
        user_email="",
        dataset_records=day2_records,
        pipeline_id=report_pipeline_id,
        identity_key=None,
        mode="replace",
    )
    doc2 = datasets_collection.find_one({"_id": ObjectId(report_dataset_id)})
    assert len(doc2["data"]) == 1, f"Expected 1 record in snapshot replacement, got {len(doc2['data'])}"
    assert doc2["data"][0]["item_code"] == "ITEM-C", "Expected day 2 snapshot data"
    print(f"  ✓ Query Report correctly treated as snapshot: Replaced {len(doc1['data'])} records with {len(doc2['data'])} fresh records")

except Exception as e:
    print(f"  ✗ Test F failed: {e}")
    test_errors.append(f"Test F: {e}")


# --------------------------------------------------------------------------
# Test G: Existing Pipeline End-to-End Execution
# --------------------------------------------------------------------------
print("\n[TEST G] Existing Pipeline End-to-End Execution Path", flush=True)
try:
    live_dataset_id = str(ObjectId())
    live_exec_id = str(uuid.uuid4())
    tasks[live_exec_id] = {"status": "running"}

    print("Running task_runner.run_pipeline_task('sales_invoice')...", flush=True)
    task_runner.run_pipeline_task(
        dataset_id=live_dataset_id,
        dataset_name="sales_invoice",
        user_id=str(ObjectId()),
        exec_id=live_exec_id,
        pipeline_id="sales_invoice",
    )

    assert tasks[live_exec_id]["status"] == "completed", f"Expected completed, got {tasks[live_exec_id]['status']}"

    # Check live checkpoint
    live_chk = get_sync_checkpoint("sales_invoice")
    assert live_chk is not None, "Live checkpoint should exist"
    assert live_chk["sync_status"] == "success"
    print(f"  ✓ End-to-end task runner executed successfully: status='completed', checkpoint watermark='{live_chk['last_sync_timestamp']}'")

except Exception as e:
    print(f"  ✗ Test G failed: {e}")
    test_errors.append(f"Test G: {e}")


print("\n" + "=" * 75, flush=True)
if not test_errors:
    print("ALL PHASE 2 STORAGE & SYNCHRONIZATION TESTS PASSED SUCCESSFULLY!", flush=True)
else:
    print(f"FAILED WITH {len(test_errors)} ERROR(S):", flush=True)
    for err in test_errors:
        print(f"  - {err}", flush=True)
print("=" * 75, flush=True)
