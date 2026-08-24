from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import pandas as pd


class BaseMapper(ABC):
    """
    Abstract Base Class for Dashboard Data Mappers.
    Transforms raw ERP datasets (DataFrames or raw doc dicts) into target dashboard schemas.
    """

    target_fields: List[str] = []
    optional_fields: List[str] = []

    @abstractmethod
    def transform(self, raw_data: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]) -> pd.DataFrame:
        """
        Transform raw ERP data into the target dashboard DataFrame.
        """
        pass

    def validate_schema(self, df: pd.DataFrame) -> bool:
        """
        Validate that the transformed DataFrame conforms to the required target schema.
        Raises ValueError if required fields are missing.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Mapper output must be a pandas DataFrame, got {type(df)}")

        missing_fields = [field for field in self.target_fields if field not in df.columns]
        if missing_fields:
            raise ValueError(f"Schema validation failed. Missing required target fields: {missing_fields}")

        return True

    @staticmethod
    def normalize_date(val: Any) -> Optional[str]:
        """
        Convert dates into the dashboard-required DD-MM-YYYY string format.
        """
        if val is None or pd.isna(val) or val == "":
            return None
        if isinstance(val, str):
            val_str = val.strip()
            # Try common ERP date formats
            for fmt in [
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%d-%m-%Y",
                "%d/%m/%Y",
                "%Y/%m/%d",
            ]:
                try:
                    dt = datetime.strptime(val_str, fmt)
                    return dt.strftime("%d-%m-%Y")
                except ValueError:
                    continue
            # If string length is 10 and matches YYYY-MM-DD
            if len(val_str) >= 10 and val_str[4] == "-" and val_str[7] == "-":
                try:
                    dt = datetime.strptime(val_str[:10], "%Y-%m-%d")
                    return dt.strftime("%d-%m-%Y")
                except ValueError:
                    pass
            return val_str
        elif isinstance(val, (datetime, pd.Timestamp)):
            return val.strftime("%d-%m-%Y")
        return str(val)

    @staticmethod
    def normalize_month(val: Any) -> Optional[str]:
        """
        Convert date or month string into short month name (e.g., 'Jan', 'Aug', 'Dec').
        """
        if val is None or pd.isna(val) or val == "":
            return None
        val_str = str(val).strip()
        month_names = {
            "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
            "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
            "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
            "jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr",
            "jun": "Jun", "jul": "Jul", "aug": "Aug", "sep": "Sep",
            "oct": "Oct", "nov": "Nov", "dec": "Dec",
            "1": "Jan", "01": "Jan", "2": "Feb", "02": "Feb", "3": "Mar", "03": "Mar",
            "4": "Apr", "04": "Apr", "5": "May", "05": "May", "6": "Jun", "06": "Jun",
            "7": "Jul", "07": "Jul", "8": "Aug", "08": "Aug", "9": "Sep", "09": "Sep",
            "10": "Oct", "11": "Nov", "12": "Dec",
        }
        if val_str.lower() in month_names:
            return month_names[val_str.lower()]

        # Try parsing as full date
        for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"]:
            try:
                dt = datetime.strptime(val_str[:10], fmt[:8] if len(fmt) > 8 else fmt)
                return dt.strftime("%b")
            except ValueError:
                continue
        return val_str[:3].capitalize()

    @staticmethod
    def normalize_number(val: Any, default: Optional[float] = 0.0) -> Optional[float]:
        """
        Safely convert value to float, or return default if conversion fails.
        """
        if val is None or pd.isna(val):
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def normalize_int(val: Any, default: Optional[int] = 0) -> Optional[int]:
        """
        Safely convert value to int, or return default if conversion fails.
        """
        if val is None or pd.isna(val):
            return default
        try:
            return int(round(float(val)))
        except (ValueError, TypeError):
            return default
