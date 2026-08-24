from typing import List, Dict, Any, Union
import pandas as pd
from app.mappings.base import BaseMapper


class StockInventoryMapper(BaseMapper):
    """
    Dashboard 5 — Stock Inventory Mapper.
    Maps Stock Balance Query Report records (http://erp.fpohub.com) into 'stock_inventory'.
    Extracts item, warehouse, item group, stock quantity (bal_qty), and stock value (bal_val).
    """

    target_fields = [
        "company",
        "warehouse",
        "item_name",
        "item_group",
        "stock_qty",
        "stock_value",
    ]

    def transform(self, raw_data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]) -> pd.DataFrame:
        records: List[Dict[str, Any]] = []

        if isinstance(raw_data, pd.DataFrame):
            raw_docs = raw_data.to_dict(orient="records")
        elif isinstance(raw_data, dict):
            raw_docs = raw_data.get("records", []) if "records" in raw_data else [raw_data]
        elif isinstance(raw_data, list):
            raw_docs = raw_data
        else:
            raw_docs = []

        for row in raw_docs:
            if not isinstance(row, dict):
                continue

            company = row.get("company") or "FPOHub"
            warehouse = row.get("warehouse") or "Main Warehouse"
            item_name = row.get("item_name") or row.get("item_code") or "Unknown Item"
            item_group = row.get("item_group") or "Produce"
            stock_qty = self.normalize_number(row.get("bal_qty") or row.get("stock_qty"), default=0.0)
            stock_value = self.normalize_number(row.get("bal_val") or row.get("stock_value"), default=0.0)

            records.append({
                "company": str(company).strip(),
                "warehouse": str(warehouse).strip(),
                "item_name": str(item_name).strip(),
                "item_group": str(item_group).strip(),
                "stock_qty": float(stock_qty),
                "stock_value": float(stock_value),
            })

        if not records:
            empty_df = pd.DataFrame(columns=self.target_fields)
            self.validate_schema(empty_df)
            return empty_df

        df = pd.DataFrame(records)

        # Aggregate duplicate items within the same company and warehouse if any
        aggregated = (
            df.groupby(["company", "warehouse", "item_name", "item_group"], as_index=False)
            .agg({
                "stock_qty": "sum",
                "stock_value": "sum",
            })
        )

        aggregated["stock_qty"] = aggregated["stock_qty"].round(2)
        aggregated["stock_value"] = aggregated["stock_value"].round(2)

        self.validate_schema(aggregated)
        return aggregated[self.target_fields]
