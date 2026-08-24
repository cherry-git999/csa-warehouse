import os
from typing import Optional, Dict, Any, Union, List
import pandas as pd
from dotenv import load_dotenv

from app.config.logging import get_logger, setup_logging
from app.config.pipeline_mapping import get_pipeline_config
from erp_client.erp_next_client import ERPNextClient

setup_logging()
logger = get_logger("services.erp")
load_dotenv()


def pull_dataset(
    pipeline_id: str,
    filters: Optional[Dict[str, Any]] = None,
    since_timestamp: Optional[str] = None,
) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Generic ERP extraction bridge for CSA Warehouse.
    Uses ERPNextClient to pull standard DocTypes or Query Reports.
    Supports multi-ERP instance routing based on pipeline configuration.

    Args:
        pipeline_id (str): Internal pipeline ID or ERP dataset/report name.
        filters (Optional[Dict[str, Any]]): Optional query filters.
        since_timestamp (Optional[str]): If provided, only fetch records modified on or after this timestamp.

    Returns:
        pd.DataFrame or List[Dict[str, Any]]: Retrieved raw ERP dataset or document list.
    """
    config = get_pipeline_config(pipeline_id)
    source_name = config.get("source_name", pipeline_id)
    source_type = config.get("source_type", "doctype")
    sync_strategy = config.get("sync_strategy", "timestamp" if source_type == "doctype" else "snapshot")
    applied_filters = dict(filters or config.get("default_filters") or {})
    fetch_full_docs = config.get("fetch_full_docs", False)

    # Determine ERP instance URL (from pipeline config or environment fallback)
    erp_uri = config.get("erp_base_url") or os.getenv("ERP_URI") or os.getenv("ERPNEXT_URI")
    erp_username = os.getenv("ERP_USERNAME") or os.getenv("ERPNEXT_USERNAME")
    erp_password = os.getenv("ERP_PASSWORD") or os.getenv("ERPNEXT_PASSWORD")

    if not all([erp_uri, erp_username, erp_password]):
        raise ValueError("Missing required environment variables: ERP_URI, ERP_USERNAME, ERP_PASSWORD")

    # For timestamp-based DocType sync, apply watermark filter if since_timestamp provided
    if source_type == "doctype" and sync_strategy == "timestamp" and since_timestamp:
        applied_filters["modified"] = [">=", str(since_timestamp)]
        logger.info(f"Applying incremental sync watermark filter: modified >= {since_timestamp}")

    logger.info(
        f"Pulling pipeline '{pipeline_id}': erp_uri='{erp_uri}', source_name='{source_name}', source_type='{source_type}', sync_strategy='{sync_strategy}'"
    )

    try:
        logger.info(f"Connecting to ERP instance: {erp_uri}")
        client = ERPNextClient(base_url=erp_uri)

        client.login(username=erp_username, password=erp_password)
        logger.info(f"Successfully logged in to ERP: {erp_uri}")

        logger.info(f"Fetching dataset via ERPNextClient: {source_name} ({source_type})")
        try:
            if source_type == "query_report":
                dataset = client.get_query_report(
                    report_name=source_name,
                    filters=applied_filters or None,
                )
            elif fetch_full_docs:
                # Fetch full documents including embedded child tables (e.g. for CC Daily Reports)
                doc_obj = client.get_dataset_object(
                    dataset_id=source_name,
                    filters=applied_filters or None,
                )
                return doc_obj.get("records", [])
            else:
                # Standard DocType: fetch with fields=["*"] to get audit attributes (name, modified, creation)
                dataset = client.get_dataset(
                    dataset_id=source_name,
                    fields=["*"],
                    filters=applied_filters or None,
                )

            if isinstance(dataset, pd.DataFrame):
                logger.info(f"Successfully retrieved {len(dataset)} records. Columns: {list(dataset.columns)}")
                return dataset
            elif isinstance(dataset, list):
                return dataset
            else:
                return pd.DataFrame(dataset)

        except Exception as dataset_error:
            if "404" in str(dataset_error) or "NOT FOUND" in str(dataset_error) or "Does not exist" in str(dataset_error):
                logger.warning(
                    f"Dataset '{source_name}' not found in ERP system ({dataset_error}). Returning empty DataFrame."
                )
                return pd.DataFrame()
            else:
                raise dataset_error

    except Exception as e:
        logger.exception(f"Error while pulling dataset for pipeline '{pipeline_id}': {e}")
        raise


if __name__ == "__main__":
    print("Testing pull_dataset with Soil Collection Data:")
    print(pull_dataset("soil_collection"))

