from datetime import datetime, timezone
from typing import List, Dict, Any, Union
import pandas as pd
from app.mappings.base import BaseMapper


class StockMovementMapper(BaseMapper):
    """
    Dashboard 4 — Stock Movement Mapper.
    Maps Stock Balance Query Report records (http://erp.fpohub.com) into 'stock_movement'.
    Extracts in_qty, out_qty, and balance_value (bal_val).
    """

    target_fields = [
        "date",
        "in_qty",
        "out_qty",
        "balance_value",
    ]

    def transform(self, raw_data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]) -> pd.DataFrame:
        records: List[Dict[str, Any]] = []

        if isinstance(raw_data, pd.DataFrame):
            raw_docs = raw_data.to_dict(orient="records")
        elif isinstance(raw_data, dict):
            # Query report dict containing "records" list
            raw_docs = raw_data.get("records", []) if "records" in raw_data else [raw_data]
        elif isinstance(raw_data, list):
            raw_docs = raw_data
        else:
            raw_docs = []

        # Determine reference date for the report snapshot
        now_date = datetime.now(timezone.utc).strftime("%d-%m-%Y")

        for row in raw_docs:
            if not isinstance(row, dict):
                continue

            row_date = self.normalize_date(row.get("posting_date") or row.get("date") or row.get("to_date")) or now_date
            in_qty = self.normalize_number(row.get("in_qty"), default=0.0)
            out_qty = self.normalize_number(row.get("out_qty"), default=0.0)
            bal_val = self.normalize_number(row.get("bal_val") or row.get("stock_value"), default=0.0)

            records.append({
                "date": row_date,
                "in_qty": float(in_qty),
                "out_qty": float(out_qty),
                "balance_value": float(bal_val),
            })

        if not records:
            empty_df = pd.DataFrame(columns=self.target_fields)
            self.validate_schema(empty_df)
            return empty_df

        df = pd.DataFrame(records)

        # Aggregate totals by date
        aggregated = (
            df.groupby("date", as_index=False)
            .agg({
                "in_qty": "sum",
                "out_qty": "sum",
                "balance_value": "sum",
            })
        )

        aggregated["in_qty"] = aggregated["in_qty"].round(2)
        aggregated["out_qty"] = aggregated["out_qty"].round(2)
        aggregated["balance_value"] = aggregated["balance_value"].round(2)

        self.validate_schema(aggregated)
        return aggregated[self.target_fields]
