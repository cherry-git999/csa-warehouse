from typing import List, Dict, Any, Union, Optional
import pandas as pd
from app.mappings.base import BaseMapper


class RevenueAnalysisMapper(BaseMapper):
    """
    Dashboard 6 — Revenue Analysis Mapper.
    Maps Purchase Invoice records from http://erp.fpohub.com into 'revenue_analysis'.
    Aggregates transactions by (territory, month).
    Note: Purchase Invoices provide procurement amounts; sales_amount is set to None.
    """

    target_fields = [
        "territory",
        "month",
        "purchase_amount",
        "sales_amount",
    ]
    optional_fields = ["sales_amount"]

    def _resolve_territory(self, row: Dict[str, Any]) -> str:
        """
        Resolve territory from verified ERP fields: territory, place_of_supply, address, or company.
        """
        if row.get("territory"):
            return str(row["territory"]).strip()

        pos = row.get("place_of_supply")
        if pos:
            parts = str(pos).split("-")
            return parts[-1].strip() if parts else str(pos).strip()

        addr = row.get("billing_address_display") or row.get("shipping_address_display")
        if addr and isinstance(addr, str):
            for state in ["Telangana", "Andhra Pradesh", "Warangal", "Ananthapur", "Kadapa", "Kurnool"]:
                if state.lower() in addr.lower():
                    return state

        company = row.get("company")
        if company and isinstance(company, str):
            return company.split()[0]

        return "All Territories"

    def transform(self, raw_data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]) -> pd.DataFrame:
        records: List[Dict[str, Any]] = []

        if isinstance(raw_data, pd.DataFrame):
            raw_docs = raw_data.to_dict(orient="records")
        elif isinstance(raw_data, dict):
            raw_docs = [raw_data]
        elif isinstance(raw_data, list):
            raw_docs = raw_data
        else:
            raw_docs = []

        for doc in raw_docs:
            if not isinstance(doc, dict):
                continue

            raw_date = doc.get("posting_date") or doc.get("bill_date") or doc.get("creation")
            norm_month = self.normalize_month(raw_date)
            if not norm_month:
                continue

            territory = self._resolve_territory(doc)

            purchase_amt = (
                self.normalize_number(doc.get("grand_total"))
                or self.normalize_number(doc.get("base_grand_total"))
                or self.normalize_number(doc.get("net_total"))
                or 0.0
            )

            records.append({
                "territory": territory,
                "month": norm_month,
                "purchase_amount": float(purchase_amt),
                "sales_amount": None,
            })

        if not records:
            empty_df = pd.DataFrame(columns=self.target_fields)
            self.validate_schema(empty_df)
            return empty_df

        df = pd.DataFrame(records)

        # Aggregate by (territory, month)
        aggregated = (
            df.groupby(["territory", "month"], as_index=False)
            .agg({
                "purchase_amount": "sum",
            })
        )
        aggregated["sales_amount"] = None
        aggregated["purchase_amount"] = aggregated["purchase_amount"].round(2)

        self.validate_schema(aggregated)
        return aggregated[self.target_fields]
