"""Pipeline configuration for Farmer Income & Visits."""

PIPELINE_ID = "farmer_income_visits"

CONFIG = {
    "erp_base_url": "http://erp.csa-india.org",
    "source_name": "CC Daily Reports",
    "source_type": "doctype",
    "sync_strategy": "timestamp",
    "identity_key": "coordinator_name",
    "target_collection": "farmer_income_visits",
    "mapper": "FarmerIncomeVisitsMapper",
    "fetch_full_docs": True,
}
