"""Pipeline configuration for NF Coordinator Activities."""

PIPELINE_ID = "nf_coordinator_activities"

CONFIG = {
    "erp_base_url": "http://erp.csa-india.org",
    "source_name": "CC Daily Reports",
    "source_type": "doctype",
    "sync_strategy": "timestamp",
    "identity_key": "date",
    "target_collection": "nf_coordinator_activities",
    "mapper": "NFCoordinatorMapper",
    "fetch_full_docs": True,
}
