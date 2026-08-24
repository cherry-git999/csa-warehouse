from typing import List, Dict, Any, Union
import pandas as pd
from app.mappings.base import BaseMapper


class NFCoordinatorMapper(BaseMapper):
    """
    Dashboard 1 — NF Coordinator Performance Mapper.
    Maps CC Daily Reports (parent document and child activity tables)
    into the 'nf_coordinator_activities' schema.
    """

    target_fields = [
        "coordinator_name",
        "district",
        "date",
        "type_of_activity",
        "planned_activities",
        "actual_activities",
        "total_score",
    ]

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
            coordinator = doc.get("name_of_nf_coordinator") or doc.get("coordinator") or "Unknown"
            doc_date = self.normalize_date(doc.get("creation"))
            doc_district = doc.get("district") or doc.get("cluster") or doc.get("mandal")

            # Check for embedded child activity tables
            field_visits = doc.get("field_visit", [])
            daily_reports = doc.get("cc_daily_reports", [])

            has_children = False

            if isinstance(field_visits, list) and field_visits:
                has_children = True
                for fv in field_visits:
                    if not isinstance(fv, dict):
                        continue
                    act_date = self.normalize_date(fv.get("date")) or doc_date
                    act_type = fv.get("activity") or fv.get("sub_activity") or "Field Visit"
                    district = fv.get("mandal") or fv.get("village") or fv.get("name_of_the_fpo") or doc_district or "General"
                    records.append({
                        "coordinator_name": coordinator,
                        "district": district,
                        "date": act_date,
                        "type_of_activity": str(act_type).strip(),
                        "planned_activities": 1,
                        "actual_activities": 1,
                        "total_score": 10,
                    })

            if isinstance(daily_reports, list) and daily_reports:
                has_children = True
                for dr in daily_reports:
                    if not isinstance(dr, dict):
                        continue
                    act_date = self.normalize_date(dr.get("date")) or doc_date
                    act_type = dr.get("activity") or dr.get("sub_activity") or "Daily Activity"
                    district = dr.get("mandal") or dr.get("village") or dr.get("name_of_the_fpo") or doc_district or "General"
                    records.append({
                        "coordinator_name": coordinator,
                        "district": district,
                        "date": act_date,
                        "type_of_activity": str(act_type).strip(),
                        "planned_activities": 1,
                        "actual_activities": 1,
                        "total_score": 10,
                    })

            # If no child tables present, map parent level fields
            if not has_children:
                act_type = doc.get("activity") or doc.get("sub_activity") or "General Activity"
                records.append({
                    "coordinator_name": coordinator,
                    "district": doc_district or "General",
                    "date": doc_date,
                    "type_of_activity": str(act_type).strip(),
                    "planned_activities": 1,
                    "actual_activities": 1,
                    "total_score": 10,
                })

        if not records:
            empty_df = pd.DataFrame(columns=self.target_fields)
            self.validate_schema(empty_df)
            return empty_df

        df = pd.DataFrame(records)

        # Aggregate by (coordinator_name, district, date, type_of_activity)
        aggregated = (
            df.groupby(["coordinator_name", "district", "date", "type_of_activity"], as_index=False)
            .agg({
                "planned_activities": "sum",
                "actual_activities": "sum",
                "total_score": "sum",
            })
        )

        # Enforce typing
        aggregated["planned_activities"] = aggregated["planned_activities"].astype(int)
        aggregated["actual_activities"] = aggregated["actual_activities"].astype(int)
        aggregated["total_score"] = aggregated["total_score"].astype(int)

        self.validate_schema(aggregated)
        return aggregated[self.target_fields]
