"""Pipeline configuration for Stock Inventory."""

PIPELINE_ID = "stock_inventory"

CONFIG = {
    "erp_base_url": "http://erp.fpohub.com",
    "source_name": "Stock Balance",
    "source_type": "query_report",
    "sync_strategy": "snapshot",
    "identity_key": None,
    "target_collection": "stock_inventory",
    "mapper": "StockInventoryMapper",
    "default_filters": {
        "company": "Nelathalli Farmer Producer Company Limited",
        "from_date": "2024-01-01",
        "to_date": "2026-12-31",
    },
}
