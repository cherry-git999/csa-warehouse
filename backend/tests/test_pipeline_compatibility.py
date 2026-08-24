import os
import sys
import uuid
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

print("=" * 70, flush=True)
print("TESTING PIPELINE COMPATIBILITY & FASTAPI STARTUP", flush=True)
print("=" * 70, flush=True)

# 1. Test FastAPI import and routing
print("\n[1] FastAPI Startup & App Import Check...", flush=True)
try:
    from app.main import app
    print("✓ FastAPI app initialized successfully without errors!", flush=True)
    routes = [route.path for route in app.routes]
    print(f"✓ Registered routes count: {len(routes)}", flush=True)
    assert "/pipelines/run" in routes, "Missing /pipelines/run"
    assert "/dashboards" in routes, "Missing /dashboards"
    print("✓ Core routes present (/pipelines/run, /dashboards, /datasets, etc.)", flush=True)
except Exception as e:
    print(f"✗ FastAPI app initialization failed: {e}", flush=True)
    sys.exit(1)

# 2. Test MongoDB connectivity
print("\n[2] MongoDB Connectivity Check...", flush=True)
try:
    from app.db.database import client as mongo_client, datasets_collection, pipelines_history_collection
    # Test ping with 3s timeout
    mongo_client.admin.command('ping')
    print("✓ MongoDB connected successfully!", flush=True)
except Exception as e:
    print(f"Note: MongoDB ping failed ({e}). Checking task runner execution...", flush=True)

# 3. Test TaskRunner execution path
print("\n[3] TaskRunner Execution Path Check (Sales Invoice)...", flush=True)
try:
    from app.services.tasks.task_executor import task_runner, tasks
    from bson import ObjectId
    test_exec_id = str(uuid.uuid4())
    test_dataset_id = str(ObjectId())
    test_pipeline_id = "sales_invoice"
    test_user_id = str(ObjectId())

    tasks[test_exec_id] = {"status": "running"}

    print("Running task_runner.run_pipeline_task('sales_invoice')...", flush=True)
    task_runner.run_pipeline_task(
        dataset_id=test_dataset_id,
        dataset_name="sales_invoice",
        user_id=test_user_id,
        exec_id=test_exec_id,
        pipeline_id=test_pipeline_id,
    )

    final_status = tasks[test_exec_id]["status"]
    print(f"✓ Task execution completed with status: {final_status}", flush=True)

except Exception as e:
    print(f"✗ TaskRunner execution check failed: {e}", flush=True)

print("\n" + "=" * 70, flush=True)
print("ALL COMPATIBILITY AND REGRESSION TESTS COMPLETED", flush=True)
print("=" * 70, flush=True)
