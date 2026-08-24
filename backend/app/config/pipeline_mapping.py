"""
Pipeline ID to Dataset Name mapping configuration.

This file contains mappings between pipeline IDs and their corresponding
dataset names in the ERP system. This is needed because the ERP system
uses specific dataset names, while our system uses pipeline IDs.
"""

from typing import Optional, Dict, Any

# Mapping of pipeline IDs to ERP configuration (source name, source type, sync strategy, identity key, default filters)
PIPELINE_CONFIG = {
    # -------------------------------------------------------------------------
    # Dashboard Pipelines (Phase 3 Verified Mappings)
    # -------------------------------------------------------------------------
    "nf_coordinator_activities": {
        "erp_base_url": "http://erp.csa-india.org",
        "source_name": "CC Daily Reports",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "date",
        "target_collection": "nf_coordinator_activities",
        "mapper": "NFCoordinatorMapper",
        "fetch_full_docs": True,
    },
    "territory_transactions": {
        "erp_base_url": "http://erp.fpohub.com",
        "source_name": "Purchase Invoice",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "date",
        "target_collection": "territory_transactions",
        "mapper": "TerritoryTransactionsMapper",
    },
    "farmer_income_visits": {
        "erp_base_url": "http://erp.csa-india.org",
        "source_name": "CC Daily Reports",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "coordinator_name",
        "target_collection": "farmer_income_visits",
        "mapper": "FarmerIncomeVisitsMapper",
        "fetch_full_docs": True,
    },
    "stock_movement": {
        "erp_base_url": "http://erp.fpohub.com",
        "source_name": "Stock Balance",
        "source_type": "query_report",
        "sync_strategy": "snapshot",
        "identity_key": None,
        "target_collection": "stock_movement",
        "mapper": "StockMovementMapper",
        "default_filters": {
            "company": "Nelathalli Farmer Producer Company Limited",
            "from_date": "2024-01-01",
            "to_date": "2026-12-31",
        },
    },
    "stock_inventory": {
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
    },
    "revenue_analysis": {
        "erp_base_url": "http://erp.fpohub.com",
        "source_name": "Purchase Invoice",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "territory",
        "target_collection": "revenue_analysis",
        "mapper": "RevenueAnalysisMapper",
    },

    # -------------------------------------------------------------------------
    # Generic Pipelines (Phase 1 & 2)
    # -------------------------------------------------------------------------
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

# Legacy dictionary for backward compatibility
PIPELINE_DATASET_MAPPING = {
    pid: cfg["source_name"] for pid, cfg in PIPELINE_CONFIG.items()
}


def get_dataset_name_for_pipeline(pipeline_id: str) -> str:
    """
    Get the ERP dataset name for a given pipeline ID.

    Args:
        pipeline_id: The pipeline ID to look up

    Returns:
        The corresponding dataset name, or the pipeline_id itself if no mapping exists
    """
    if pipeline_id in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[pipeline_id]["source_name"]
    return PIPELINE_DATASET_MAPPING.get(pipeline_id, pipeline_id)


def get_pipeline_source_type(pipeline_id: str) -> str:
    """
    Get the ERP source type ('doctype' or 'query_report') for a given pipeline ID.

    Args:
        pipeline_id: The pipeline ID to look up

    Returns:
        'doctype' or 'query_report' (defaults to 'doctype')
    """
    if pipeline_id in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[pipeline_id].get("source_type", "doctype")
    name = get_dataset_name_for_pipeline(pipeline_id).lower()
    if "report" in name or name in ("stock balance", "general ledger"):
        return "query_report"
    return "doctype"


def get_pipeline_sync_strategy(pipeline_id: str) -> str:
    """
    Get the sync strategy ('timestamp' or 'snapshot') for a given pipeline ID.
    """
    if pipeline_id in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[pipeline_id].get("sync_strategy", "timestamp")
    stype = get_pipeline_source_type(pipeline_id)
    return "snapshot" if stype == "query_report" else "timestamp"


def get_pipeline_identity_key(pipeline_id: str) -> Optional[str]:
    """
    Get the primary record identity key for upserting records (e.g. 'name' for DocTypes).
    """
    if pipeline_id in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[pipeline_id].get("identity_key", "name")
    stype = get_pipeline_source_type(pipeline_id)
    return None if stype == "query_report" else "name"


def get_pipeline_erp_url(pipeline_id: str) -> Optional[str]:
    """
    Get the configured ERP base URL for a pipeline (http://erp.csa-india.org vs http://erp.fpohub.com).
    """
    if pipeline_id in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[pipeline_id].get("erp_base_url")
    return None


def get_pipeline_mapper(pipeline_id: str) -> Optional[str]:
    """
    Get the configured mapper name for a pipeline (e.g. 'NFCoordinatorMapper').
    """
    if pipeline_id in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[pipeline_id].get("mapper")
    return None


def get_pipeline_target_collection(pipeline_id: str) -> str:
    """
    Get the target MongoDB collection name for a pipeline.
    """
    if pipeline_id in PIPELINE_CONFIG:
        return PIPELINE_CONFIG[pipeline_id].get("target_collection", pipeline_id)
    return pipeline_id


def get_pipeline_config(pipeline_id: str) -> dict:
    """
    Get the full pipeline configuration for a given pipeline ID.
    """
    return PIPELINE_CONFIG.get(
        pipeline_id,
        {
            "source_name": get_dataset_name_for_pipeline(pipeline_id),
            "source_type": get_pipeline_source_type(pipeline_id),
            "sync_strategy": get_pipeline_sync_strategy(pipeline_id),
            "identity_key": get_pipeline_identity_key(pipeline_id),
            "erp_base_url": get_pipeline_erp_url(pipeline_id),
            "mapper": get_pipeline_mapper(pipeline_id),
            "target_collection": get_pipeline_target_collection(pipeline_id),
        },
    )



