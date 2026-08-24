import sys
import erp_client
from erp_client.erp_next_client import ERPNextClient

print("erp_client location:", erp_client.__file__)
client = ERPNextClient("http://localhost")
expected_methods = [
    "sync_pull_dataset",
    "sync_pull_dataset_object",
    "run_query_report",
    "get_query_report",
    "get_data",
    "get_data_object",
    "to_dataframe",
    "get_dataset",
    "get_dataset_schema",
    "login",
]

for method in expected_methods:
    available = hasattr(client, method)
    print(f"Method {method}: {available}")
    assert available, f"Missing method: {method}"

print("\nALL EXPECTED METHODS AVAILABLE AND VERIFIED!")
