"""Pipeline configuration for Revenue Analysis."""

PIPELINE_ID = "revenue_analysis"

CONFIG = {
    "erp_base_url": "http://erp.fpohub.com",
    "source_name": "Purchase Invoice",
    "source_type": "doctype",
    "sync_strategy": "timestamp",
    "identity_key": "territory",
    "target_collection": "revenue_analysis",
    "mapper": "RevenueAnalysisMapper",
}
