from typing import List, Dict, Any, Union, Optional
import pandas as pd
from app.mappings.base import BaseMapper


class FarmerIncomeVisitsMapper(BaseMapper):
    """
    Dashboard 3 — Farmer Income & Visits Mapper.
    Extracts and maps the CONSOLIDATED REPORT child table from CC Daily Reports (http://erp.csa-india.org)
    into the 'farmer_income_visits' collection schema.
    Note: income, net_income, and yield are optional/unavailable in CC Daily Reports and preserved as None.
    """

    target_fields = [
        "coordinator_name",
        "month",
        "village",
        "farmers_met",
        "visits",
        "score",
        "income",
        "net_income",
        "yield",
    ]
    optional_fields = ["income", "net_income", "yield"]

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

            coordinator = doc.get("name_of_nf_coordinator") or doc.get("coordinator") or "Unknown"
            month = doc.get("month") or self.normalize_month(doc.get("creation")) or "August"
            parent_village = doc.get("village") or doc.get("cluster") or doc.get("mandal") or "General Village"

            consolidated_rows = doc.get("consolidated_report", [])

            if isinstance(consolidated_rows, list) and consolidated_rows:
                # Process child rows from consolidated_report
                for row in consolidated_rows:
                    if not isinstance(row, dict):
                        continue

                    # Extract village or FPO name
                    village = row.get("village") or row.get("name_of_the_fpo") or parent_village
                    farmers_met = self.normalize_int(row.get("number_of_participants"), default=0)
                    visits = self.normalize_int(row.get("sub_activity_count"), default=1)
                    score = visits * 10

                    records.append({
                        "coordinator_name": str(coordinator).strip(),
                        "month": str(month).strip(),
                        "village": str(village).strip(),
                        "farmers_met": farmers_met,
                        "visits": visits,
                        "score": score,
                        "income": None,
                        "net_income": None,
                        "yield": None,
                    })
            else:
                # If consolidated_report child table is not nested, check field_visit / cc_daily_reports or parent
                records.append({
                    "coordinator_name": str(coordinator).strip(),
                    "month": str(month).strip(),
                    "village": str(parent_village).strip(),
                    "farmers_met": self.normalize_int(doc.get("quantity") or doc.get("number_of_participants"), default=0),
                    "visits": 1,
                    "score": 10,
                    "income": None,
                    "net_income": None,
                    "yield": None,
                })

        if not records:
            empty_df = pd.DataFrame(columns=self.target_fields)
            self.validate_schema(empty_df)
            return empty_df

        df = pd.DataFrame(records)

        # Aggregate by (coordinator_name, month, village)
        aggregated = (
            df.groupby(["coordinator_name", "month", "village"], as_index=False)
            .agg({
                "farmers_met": "sum",
                "visits": "sum",
                "score": "sum",
            })
        )

        aggregated["income"] = None
        aggregated["net_income"] = None
        aggregated["yield"] = None

        aggregated["farmers_met"] = aggregated["farmers_met"].astype(int)
        aggregated["visits"] = aggregated["visits"].astype(int)
        aggregated["score"] = aggregated["score"].astype(int)

        self.validate_schema(aggregated)
        return aggregated[self.target_fields]
