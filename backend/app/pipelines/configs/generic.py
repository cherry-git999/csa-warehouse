"""Generic pipeline configurations (Phase 1 & 2 baseline)."""

GENERIC_CONFIGS = {
    "soil_collection": {
        "erp_base_url": "http://erp.csa-india.org",
        "source_name": "Soil Collection Data",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "weather_data": {
        "erp_base_url": "http://erp.csa-india.org",
        "source_name": "Weather Data",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "crop_yield": {
        "erp_base_url": "http://erp.csa-india.org",
        "source_name": "Crop Yield Data",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "sales_invoice": {
        "erp_base_url": "http://erp.csa-india.org",
        "source_name": "Sales Invoice",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "purchase_invoice": {
        "erp_base_url": "http://erp.fpohub.com",
        "source_name": "Purchase Invoice",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "cc_daily_reports": {
        "erp_base_url": "http://erp.csa-india.org",
        "source_name": "CC Daily Reports",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "stock_balance": {
        "erp_base_url": "http://erp.fpohub.com",
        "source_name": "Stock Balance",
        "source_type": "query_report",
        "sync_strategy": "snapshot",
        "identity_key": None,
        "default_filters": {
            "company": "Nelathalli Farmer Producer Company Limited",
            "from_date": "2024-01-01",
            "to_date": "2026-12-31",
        },
    },
}
