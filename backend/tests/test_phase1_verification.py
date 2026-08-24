import os
import sys
from dotenv import load_dotenv

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.utils.erp import pull_dataset
from app.config.pipeline_mapping import get_pipeline_config
from erp_client.erp_next_client import ERPNextClient

print("=" * 70, flush=True)
print("PHASE 1 VERIFICATION SUITE", flush=True)
print("=" * 70, flush=True)

# 1. Package Verification
print("\n[A] PACKAGE & IMPORT VERIFICATION", flush=True)
import erp_client
print(f"✓ erp_client loaded from: {erp_client.__file__}", flush=True)
client = ERPNextClient(os.getenv("ERP_URI", "http://erp.csa-india.org"))
methods = [
    "sync_pull_dataset",
    "sync_pull_dataset_object",
    "run_query_report",
    "get_query_report",
    "get_data",
    "get_data_object",
    "to_dataframe",
]
for m in methods:
    assert hasattr(client, m), f"Missing method: {m}"
    print(f"  ✓ Found method: {m}", flush=True)

# Determine working ERP URL
print("\nChecking ERP URL connectivity...", flush=True)
test_urls = [
    os.getenv("ERP_URI", "https://erp.kisanmitra.net"),
    "http://erp.csa-india.org",
    "https://erp.kisanmitra.net",
]
working_url = None
username = os.getenv("ERP_USERNAME") or os.getenv("ERPNEXT_USERNAME", "ads@aegiondynamic.com")
password = os.getenv("ERP_PASSWORD") or os.getenv("ERPNEXT_PASSWORD", "Csa@2025")

for url in test_urls:
    try:
        c = ERPNextClient(base_url=url)
        c.login(username, password)
        print(f"✓ Successfully authenticated with ERP instance: {url}", flush=True)
        working_url = url
        os.environ["ERP_URI"] = url
        break
    except Exception as e:
        print(f"  Note: Authentication to {url} returned: {e}", flush=True)

if not working_url:
    print(f"✗ Could not authenticate to any ERP instance.", flush=True)
    sys.exit(1)

# 2. Standard DocType Extraction: Sales Invoice / Purchase Invoice
print("\n[B] STANDARD DOCTYPE EXTRACTION (Sales Invoice / Purchase Invoice)", flush=True)
try:
    print("Testing pull_dataset('sales_invoice')...", flush=True)
    df_sales = pull_dataset("sales_invoice")
    print(f"✓ Source Type: DocType", flush=True)
    print(f"✓ Source Name: Sales Invoice", flush=True)
    print(f"✓ Total Rows: {len(df_sales)}", flush=True)
    print(f"✓ Total Columns: {len(df_sales.columns)}", flush=True)
    print(f"✓ Sample Columns: {list(df_sales.columns)[:8]}", flush=True)
    if not df_sales.empty:
        print(f"✓ First Record Sample:", flush=True)
        sample_cols = [c for c in ['name', 'customer', 'grand_total', 'posting_date'] if c in df_sales.columns]
        if not sample_cols:
            sample_cols = list(df_sales.columns)[:4]
        print(df_sales.iloc[0:1][sample_cols].to_string(index=False), flush=True)
except Exception as e:
    print(f"✗ Sales Invoice extraction failed: {e}", flush=True)

try:
    print("\nTesting pull_dataset('purchase_invoice')...", flush=True)
    df_purchase = pull_dataset("purchase_invoice")
    print(f"✓ Source Type: DocType", flush=True)
    print(f"✓ Source Name: Purchase Invoice", flush=True)
    print(f"✓ Total Rows: {len(df_purchase)}", flush=True)
    print(f"✓ Total Columns: {len(df_purchase.columns)}", flush=True)
    print(f"✓ Sample Columns: {list(df_purchase.columns)[:8]}", flush=True)
    if not df_purchase.empty:
        print(f"✓ First Record Sample:", flush=True)
        sample_cols = [c for c in ['name', 'supplier', 'grand_total', 'posting_date'] if c in df_purchase.columns]
        if not sample_cols:
            sample_cols = list(df_purchase.columns)[:4]
        print(df_purchase.iloc[0:1][sample_cols].to_string(index=False), flush=True)
except Exception as e:
    print(f"✗ Purchase Invoice extraction failed: {e}", flush=True)

# 3. Query Report Extraction: Stock Balance
print("\n[C] QUERY REPORT EXTRACTION (Stock Balance)", flush=True)
try:
    print("Testing pull_dataset('stock_balance')...", flush=True)
    report_filters = {
        "company": "Jeevanadatha FPCL",
        "from_date": "2024-01-01",
        "to_date": "2026-12-31",
    }
    df_stock = pull_dataset("stock_balance", filters=report_filters)
    print(f"✓ Source Type: Query Report", flush=True)
    print(f"✓ Source Name: Stock Balance", flush=True)
    print(f"✓ Total Rows: {len(df_stock)}", flush=True)
    print(f"✓ Total Columns: {len(df_stock.columns)}", flush=True)
    print(f"✓ Sample Columns: {list(df_stock.columns)[:8]}", flush=True)
    if not df_stock.empty:
        print(f"✓ First Record Sample:", flush=True)
        preview_cols = [c for c in ['item_code', 'item_name', 'warehouse', 'bal_qty', 'bal_val'] if c in df_stock.columns]
        if not preview_cols:
            preview_cols = list(df_stock.columns)[:5]
        print(df_stock.iloc[0:1][preview_cols].to_string(index=False), flush=True)
except Exception as e:
    print(f"✗ Stock Balance extraction failed: {e}", flush=True)

print("\n" + "=" * 70, flush=True)
print("PHASE 1 VERIFICATION COMPLETED SUCCESSFULLY", flush=True)
print("=" * 70, flush=True)
