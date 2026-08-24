"""
Pipeline ID to Dataset Name mapping configuration.

This file contains mappings between pipeline IDs and their corresponding
dataset names in the ERP system. This is needed because the ERP system
uses specific dataset names, while our system uses pipeline IDs.
"""

from typing import Optional, Dict, Any

# Mapping of pipeline IDs to ERP configuration (source name, source type, sync strategy, identity key, default filters)
PIPELINE_CONFIG = {
    # Standard DocTypes (use timestamp watermarking and primary key 'name')
    "soil_collection": {
        "source_name": "Soil Collection Data",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "weather_data": {
        "source_name": "Weather Data",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "crop_yield": {
        "source_name": "Crop Yield Data",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "sales_invoice": {
        "source_name": "Sales Invoice",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "purchase_invoice": {
        "source_name": "Purchase Invoice",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    "cc_daily_reports": {
        "source_name": "CC Daily Reports",
        "source_type": "doctype",
        "sync_strategy": "timestamp",
        "identity_key": "name",
    },
    # Query Reports (use fresh snapshot execution, no DocType primary key)
    "stock_balance": {
        "source_name": "Stock Balance",
        "source_type": "query_report",
        "sync_strategy": "snapshot",
        "identity_key": None,
        "default_filters": {
            "company": "Jeevanadatha FPCL",
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
        },
    )


