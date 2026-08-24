# utilities.py
import streamlit as st
import pandas as pd
from datetime import timedelta
import base64
import streamlit_shadcn_ui as ui

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATE_CSV = DATA_DIR / "Dim_Date.csv"
CATEGORY_CSV = DATA_DIR / "Issue_Category_6May2025.csv"
DEPT_CSV = DATA_DIR / "Issue_Dept_6May2025.csv"
ISSUE_CSV = DATA_DIR / "Issue_6May2025.csv"

CSS_PATH = Path(__file__).parent / "assets" / "styles.css"


def encode_image_base64(img_path: Path) -> str:
    with open(img_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


def initialize_page():
    st.set_page_config(
        page_title="Kisan Mitra Helpline Dashboard",
        layout="wide",
        page_icon="📞",
        initial_sidebar_state="expanded",
    )
    # Load CSS
    with open(CSS_PATH, "rb") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def indian_financial_quarter(date):
    # Shift months so Apr=1, May=2,... Mar=12
    shifted_month = (date.month - 4) % 12 + 1
    quarter = (shifted_month - 1) // 3 + 1
    return quarter


def process_date_ranges(scenario, max_date, min_date):
    prev_custom_start = None

    if scenario == "All Time":
        # For "All Time", use the full range of available data

        current_start = min_date
        current_end = max_date
        prev_start = None
        prev_end = None
        comparison_label = ""
        prev_custom_start = None

    elif scenario == "This Month":
        # Get current month dates
        current_month = max_date.month
        current_year = max_date.year
        day_of_month = max_date.day

        # Current period: From 1st of current month to current day
        current_start = pd.Timestamp(
            year=current_year, month=current_month, day=1)
        current_end = max_date

        # Previous month
        if current_month == 1:  # January
            prev_month = 12
            prev_year = current_year - 1
        else:
            prev_month = current_month - 1
            prev_year = current_year

        # Previous period: From 1st of previous month to same day of previous month
        prev_start = pd.Timestamp(year=prev_year, month=prev_month, day=1)

        try:
            prev_end = pd.Timestamp(
                year=prev_year, month=prev_month, day=day_of_month)
        except ValueError:
            # If day doesn't exist in previous month (e.g., March 31 -> Feb 28/29)
            if prev_month == 2:  # February
                prev_end = (
                    pd.Timestamp(year=prev_year, month=prev_month, day=29)
                    if (
                        prev_year % 4 == 0
                        and (prev_year % 100 != 0 or prev_year % 400 == 0)
                    )
                    else pd.Timestamp(year=prev_year, month=prev_month, day=28)
                )
            else:
                last_day = pd.Timestamp(
                    year=prev_year, month=prev_month + 1, day=1
                ) - timedelta(days=1)
                prev_end = last_day

        comparison_label = "vs PM"

    elif scenario == "This Quarter":

        def adjusted_year_month(base_year, shifted_month):
            if shifted_month > 12:
                return base_year + 1, shifted_month - 12
            return base_year, shifted_month

        quarter_end_month = {1: 6, 2: 9, 3: 12, 4: 3}

        # Get current quarter info
        current_year = max_date.year
        current_quarter = indian_financial_quarter(max_date)

        current_year_adjusted, quarter_start_month = adjusted_year_month(
            current_year, (current_quarter - 1) * 3 + 4
        )
        current_quarter_start = pd.Timestamp(
            year=current_year_adjusted, month=quarter_start_month, day=1
        )
        current_start = current_quarter_start
        current_end = max_date
        days_into_quarter = (max_date - current_quarter_start).days

        # Previous quarter info
        if current_quarter == 1:
            prev_quarter = 4
            prev_year = current_year - 1
        else:
            prev_quarter = current_quarter - 1
            prev_year = current_year

        prev_year_adjusted, prev_quarter_start_month = adjusted_year_month(
            prev_year, (prev_quarter - 1) * 3 + 4
        )
        prev_start = pd.Timestamp(
            year=prev_year_adjusted, month=prev_quarter_start_month, day=1
        )

        # Calculate capped prev_end (based on actual quarter end)
        end_month = quarter_end_month[prev_quarter]
        if end_month < prev_quarter_start_month:
            end_year = prev_year_adjusted + 1
        else:
            end_year = prev_year_adjusted

        prev_end = pd.Timestamp(end_year, end_month, 1) + \
            pd.offsets.MonthEnd(1)

        comparison_label = "vs PQ"

    elif scenario == "This Year":
        # Get current year dates up to max_date
        current_year = max_date.year

        # Calculate days into year
        year_start = pd.Timestamp(year=current_year, month=1, day=1)
        days_into_year = (max_date - year_start).days - 1

        # Current period: From Jan 1 to max_date of current year
        current_start = year_start
        current_end = max_date

        # Previous period: Same number of days into previous year
        prev_year = current_year - 1
        prev_start = pd.Timestamp(year=prev_year, month=1, day=1)
        prev_end = prev_start + timedelta(days=days_into_year)

        comparison_label = "vs PY"

    elif scenario == "Custom":
        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(max_date - timedelta(days=180), max_date),
            min_value=min_date.date(),
            max_value=max_date.date(),
            key="custom_date_picker",  # optional: ensures independent key
        )

        if len(date_range) == 2:
            current_start = pd.Timestamp(date_range[0])
            current_end = pd.Timestamp(date_range[1])
            prev_custom_start = pd.Timestamp(date_range[0])
            prev_start = None
            prev_end = None
            comparison_label = ""
        else:
            st.error("Please select both start and end dates")
            current_start = max_date - timedelta(days=30)
            current_end = max_date
            prev_start = None
            prev_end = None
            comparison_label = ""

    # Display selected date range
    st.sidebar.markdown(
        f"""
        <div class="simpleTextFirst">
            <p>Selected range:</p>                
            <p class="textBlak">{current_start.strftime("%b %d, %Y")} - {current_end.strftime("%b %d, %Y")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Display comparison date range if available
    # if prev_start is not None and prev_end is not None:
    #     st.sidebar.markdown(
    #         f"""
    #         <div class="simpleText">
    #             <p>Comparison:</p>
    #             <p class="textBlak">{prev_start.strftime("%b %d, %Y")} - {prev_end.strftime("%b %d, %Y")}</p>
    #         </div>
    #         """,
    #         unsafe_allow_html=True,
    #     )

    st.sidebar.markdown(
        "<hr style='margin-top:45px; margin-bottom: 50px;'>", unsafe_allow_html=True
    )

    return (
        current_start,
        current_end,
        prev_start,
        prev_end,
        comparison_label,
        prev_custom_start,
    )


def load_csv(path, parse_dates=None, date_format=None):
    df = pd.read_csv(path, encoding="ISO-8859-1")
    if parse_dates:
        for col in parse_dates:
            df[col] = pd.to_datetime(
                df[col], format=date_format, errors="coerce")
    return df


@st.cache_data
def read_date_data():
    return load_csv(DATE_CSV, parse_dates=["date"], date_format="%d-%m-%Y")


@st.cache_data
def read_category_data():
    return load_csv(CATEGORY_CSV)


@st.cache_data
def read_department_data():
    return load_csv(DEPT_CSV)


@st.cache_data
def read_issue_data(df_date):
    df = pd.read_csv(ISSUE_CSV, encoding="ISO-8859-1")
    df_raw = pd.read_csv(ISSUE_CSV, encoding="ISO-8859-1")

    # Parse dates to set format
    df["Opening Date"] = pd.to_datetime(
        df["Opening Date"], format="%d-%m-%Y", errors="coerce"
    )
    df["Opening Date Time"] = pd.to_datetime(
        df["Opening Date Time"], format="%d-%m-%Y %H:%M", errors="coerce"
    )
    df["Resolution Date Time"] = pd.to_datetime(
        df["Resolution Date Time"], format="%d-%m-%Y %H:%M", errors="coerce"
    )

    df_raw["Opening Date"] = pd.to_datetime(
        df_raw["Opening Date"], dayfirst=True, errors="coerce"
    )
    true_min_date = df_raw["Opening Date"].dropna().min()
    true_max_date = df_raw["Opening Date"].dropna().max()

    total_records = len(df)

    # Count rows where Opening Date is null
    null_opening_dates = df["Opening Date"].isna().sum()

    # Drop rows with null Opening Date
    df = df[df["Opening Date"].notna()]

    # Count rows where Status is "Resolved" but Resolution Date Time is null
    null_resolution_dates = df[
        (df["Status"] == "Resolved") & (df["Resolution Date Time"].isna())
    ].shape[0]

    # Drop rows with Status = "Resolved" and missing Resolution Date Time
    df = df[(df["Status"] != "Resolved") | (
        df["Resolution Date Time"].notna())]

    # Extract Year and Month from Opening Date
    df["Year"] = df["Opening Date"].dt.year
    df["Month"] = df["Opening Date"].dt.month

    # Merge Issue CSV with date dimensions season and fiscal year
    df_merged = df.merge(
        df_date[["date", "season", "fiscal_year"]],
        left_on="Opening Date",
        right_on="date",
        how="left",
    )

    return (
        df_merged,
        null_opening_dates,
        null_resolution_dates,
        total_records,
        true_min_date,
        true_max_date,
    )


def create_sidebar(df_issues, df_date, min_date_raw, max_date_raw):
    logo_path = CSS_PATH.parent / "images" / "csalogo.png"

    # Sidebar header with logo
    st.sidebar.markdown(
        f"""
    <div style="display: flex; justify-content: center; margin-bottom: 20px;">
        <img src="data:image/png;base64,{encode_image_base64(logo_path)}" width=auto height=auto>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        """
    <div class="sidebar-header"> Analytics Dashboard </div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
    <style>
    .sidebar-header {
        font-size: 16px;
        font-weight: bold;
        color: #778899;
        text-align: center;
        margin-bottom: 15px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("<hr>", unsafe_allow_html=True)
    # st.sidebar.markdown("<div class='sidebar-section-title'>Filters</div>", unsafe_allow_html=True)

    # Time period selector
    scenario = st.sidebar.selectbox(
        "Time Period:",
        options=["All Time", "This Month",
                 "This Quarter", "This Year", "Custom"],
        index=0,
        key="time_period_selector",
    )

    # Season multiselect
    # seasons = sorted(df_date["season"].dropna().unique().tolist())
    # selected_seasons = st.sidebar.multiselect(
    # "Seasons:", options=seasons, default=None, placeholder="All")

    # max_date = df_issues["Opening Date"].max()
    # min_date = df_issues["Opening Date"].min()

    min_date = min_date_raw
    max_date = max_date_raw

    # Process date ranges based on scenario and current page
    (
        current_start,
        current_end,
        prev_start,
        prev_end,
        comparison_label,
        prev_custom_start,
    ) = process_date_ranges(scenario, max_date, min_date)

    return (
        current_start,
        current_end,
        prev_start,
        prev_end,
        comparison_label,
        prev_custom_start,
    )


# ------------------ MongoDB Dashboard Data Loader ------------------
def _get_mongodb_db():
    """
    Get the existing MongoDB database instance.
    """
    import sys
    backend_dir = str(Path(__file__).resolve().parent.parent.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    try:
        from app.db.database import db
        return db
    except Exception as e:
        import os
        from dotenv import load_dotenv
        from pymongo import MongoClient
        load_dotenv()
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        client = MongoClient(mongo_uri)
        return client["fastapi_db"]


def trigger_warehouse_auto_sync(pipeline_id: str) -> bool:
    """
    Triggers synchronization for a warehouse pipeline using the existing TaskRunner.
    Reuses Phase 1 extraction, Phase 2 checkpoint sync, Phase 3 mapping, and MongoDB storage.
    Catches any ERP/network exceptions gracefully so existing MongoDB data is preserved.

    Args:
        pipeline_id (str): The pipeline identifier (e.g. 'stock_inventory' or 'stock_movement')

    Returns:
        bool: True if sync succeeded, False otherwise
    """
    if not pipeline_id:
        return False

    try:
        import uuid
        from bson import ObjectId
        from app.services.tasks.task_executor import task_runner, tasks

        exec_id = str(uuid.uuid4())
        dataset_id = str(ObjectId())
        user_id = str(ObjectId())
        tasks[exec_id] = {"status": "running"}

        task_runner.run_pipeline_task(
            dataset_id=dataset_id,
            dataset_name=pipeline_id,
            user_id=user_id,
            exec_id=exec_id,
            pipeline_id=pipeline_id,
        )

        status = tasks.get(exec_id, {}).get("status")
        return status == "completed"
    except Exception as e:
        print(f"Warehouse auto-sync execution error for pipeline '{pipeline_id}': {e}")
        return False


def load_dashboard_data_from_mongodb(collection_or_dataset_name: str, auto_sync: bool = False) -> pd.DataFrame:
    """
    Generic utility to load dashboard data from MongoDB.
    Optionally triggers an automatic background/synchronous pipeline synchronization before query.

    Queries:
    1. Direct collection in database: db[collection_or_dataset_name]
    2. Datasets collection via dataset_information (where dataset_name or pipeline_id matches)
    3. Datasets collection directly by _id

    Args:
        collection_or_dataset_name (str): The target collection or dataset name.
        auto_sync (bool): If True, triggers auto-sync via existing TaskRunner before reading.

    Returns:
        pd.DataFrame: Retrieved data with _id excluded, or empty DataFrame if not found.
    """
    if not collection_or_dataset_name:
        return pd.DataFrame()

    if auto_sync:
        try:
            trigger_warehouse_auto_sync(collection_or_dataset_name)
        except Exception as sync_err:
            print(f"Auto-sync failed gracefully for '{collection_or_dataset_name}': {sync_err}")

    try:
        db = _get_mongodb_db()

        # 1. Check direct collection
        if collection_or_dataset_name in db.list_collection_names():
            coll = db[collection_or_dataset_name]
            docs = list(coll.find({}, {"_id": 0}))
            if docs:
                return pd.DataFrame(docs)

        # 2. Check datasets_information / datasets collection
        datasets_info_coll = db["datasets_information"]
        datasets_coll = db["datasets"]

        info = datasets_info_coll.find_one({
            "$or": [
                {"dataset_name": collection_or_dataset_name},
                {"pipeline_id": collection_or_dataset_name},
            ]
        })
        if info and "dataset_id" in info:
            dataset_doc = datasets_coll.find_one({"_id": info["dataset_id"]})
            if dataset_doc and "data" in dataset_doc:
                return pd.DataFrame(dataset_doc["data"])

        # 3. Check datasets collection directly by _id (string or ObjectId)
        dataset_doc = datasets_coll.find_one({"_id": collection_or_dataset_name})
        if dataset_doc and "data" in dataset_doc:
            return pd.DataFrame(dataset_doc["data"])

        return pd.DataFrame()

    except Exception as e:
        print(f"Error loading dashboard data from MongoDB for '{collection_or_dataset_name}': {e}")
        return pd.DataFrame()


