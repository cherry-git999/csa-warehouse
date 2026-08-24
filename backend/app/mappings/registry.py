from typing import Dict, Any, Optional, Union
import pandas as pd

from app.mappings.base import BaseMapper
from app.mappings.nf_coordinator import NFCoordinatorMapper
from app.mappings.territory_transactions import TerritoryTransactionsMapper
from app.mappings.farmer_income_visits import FarmerIncomeVisitsMapper
from app.mappings.stock_movement import StockMovementMapper
from app.mappings.stock_inventory import StockInventoryMapper
from app.mappings.revenue_analysis import RevenueAnalysisMapper

# Registry of dashboard mapper instances
_MAPPER_REGISTRY: Dict[str, BaseMapper] = {
    # By mapper class name
    "NFCoordinatorMapper": NFCoordinatorMapper(),
    "TerritoryTransactionsMapper": TerritoryTransactionsMapper(),
    "FarmerIncomeVisitsMapper": FarmerIncomeVisitsMapper(),
    "StockMovementMapper": StockMovementMapper(),
    "StockInventoryMapper": StockInventoryMapper(),
    "RevenueAnalysisMapper": RevenueAnalysisMapper(),
    # By pipeline / target collection ID
    "nf_coordinator_activities": NFCoordinatorMapper(),
    "territory_transactions": TerritoryTransactionsMapper(),
    "farmer_income_visits": FarmerIncomeVisitsMapper(),
    "stock_movement": StockMovementMapper(),
    "stock_inventory": StockInventoryMapper(),
    "revenue_analysis": RevenueAnalysisMapper(),
}


def get_mapper(name_or_pipeline_id: str) -> Optional[BaseMapper]:
    """
    Retrieve a dashboard mapper instance by mapper name or pipeline ID.
    Returns None if no mapper is configured for the pipeline.
    """
    if not name_or_pipeline_id:
        return None
    return _MAPPER_REGISTRY.get(name_or_pipeline_id)


def map_erp_data(
    raw_data: Union[pd.DataFrame, Any],
    pipeline_id: str,
    mapper_name: Optional[str] = None,
) -> Union[pd.DataFrame, Any]:
    """
    Apply dashboard-specific schema transformation if a mapper is configured.
    If no mapper is configured, returns raw_data unmodified (backward compatible).

    Args:
        raw_data: Raw ERP dataset extracted by ERPNextClient.
        pipeline_id: Pipeline identifier.
        mapper_name: Optional explicit mapper name from pipeline config.

    Returns:
        Mapped DataFrame (if mapped) or original raw_data.
    """
    mapper = get_mapper(mapper_name) if mapper_name else get_mapper(pipeline_id)
    if mapper is None:
        return raw_data

    mapped_df = mapper.transform(raw_data)
    mapper.validate_schema(mapped_df)
    return mapped_df
