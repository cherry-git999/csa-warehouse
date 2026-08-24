from typing import List, Dict, Any, Union, Optional
import pandas as pd
from app.mappings.base import BaseMapper


class TerritoryTransactionsMapper(BaseMapper):
    """
    Dashboard 2 — Purchase & Sales Territory Mapper.
    Maps Purchase Invoice records from http://erp.fpohub.com into 'territory_transactions'.
    Aggregates transactions by (territory, date).
    Note: Purchase Invoices provide procurement amounts; sales_amount is set to None.
    """

    target_fields = [
        "territory",
        "date",
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

        # Check place of supply (e.g., '36-Telangana' -> 'Telangana')
        pos = row.get("place_of_supply")
        if pos:
            parts = str(pos).split("-")
            return parts[-1].strip() if parts else str(pos).strip()

        # Check address display
        addr = row.get("billing_address_display") or row.get("shipping_address_display")
        if addr and isinstance(addr, str):
            for state in ["Telangana", "Andhra Pradesh", "Warangal", "Ananthapur", "Kadapa", "Kurnool"]:
                if state.lower() in addr.lower():
                    return state

        # Fallback to company name prefix if specific
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

            # Determine invoice date
            raw_date = doc.get("posting_date") or doc.get("bill_date") or doc.get("creation")
            norm_date = self.normalize_date(raw_date)
            if not norm_date:
                continue

            territory = self._resolve_territory(doc)

            # Purchase amount from grand_total or net_total
            purchase_amt = (
                self.normalize_number(doc.get("grand_total"))
                or self.normalize_number(doc.get("base_grand_total"))
                or self.normalize_number(doc.get("net_total"))
                or 0.0
            )

            # Sales amount is not present in Purchase Invoices (preserved as None)
            sales_amt: Optional[float] = None

            records.append({
                "territory": territory,
                "date": norm_date,
                "purchase_amount": float(purchase_amt),
                "sales_amount": sales_amt,
            })

        if not records:
            empty_df = pd.DataFrame(columns=self.target_fields)
            self.validate_schema(empty_df)
            return empty_df

        df = pd.DataFrame(records)

        # Aggregate purchase_amount by (territory, date)
        aggregated = (
            df.groupby(["territory", "date"], as_index=False)
            .agg({
                "purchase_amount": "sum",
            })
        )
        # Preserve sales_amount as None
        aggregated["sales_amount"] = None

        # Round purchase amount
        aggregated["purchase_amount"] = aggregated["purchase_amount"].round(2)

        self.validate_schema(aggregated)
        return aggregated[self.target_fields]
