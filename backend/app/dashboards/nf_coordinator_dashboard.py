"""
NF Coordinator Performance Dashboard v1.0

Data source: data/nf_coordinator_data.csv  (dummy CSV)
─────────────────────────────────────────────────────────
TODO – MongoDB migration:
  Replace load_nf_data() body with:

      from pymongo import MongoClient
      client = MongoClient(MONGO_URI)
      collection = client["csa_db"]["nf_coordinator_activities"]
      df = pd.DataFrame(list(collection.find({}, {"_id": 0})))
      df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
      return df

  All downstream code remains unchanged.
─────────────────────────────────────────────────────────
See docs/nf_coordinator_mapping.md for detailed ERP mapping specification.
"""

import base64
import logging
from typing import Optional
from pymongo.errors import PyMongoError
try:
    from utilities import initialize_page, _get_mongodb_db
except ImportError:
    from app.dashboards.utilities import initialize_page, _get_mongodb_db

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit_shadcn_ui as ui
from pathlib import Path

logger = logging.getLogger(__name__)
PIPELINE_ID = "nf_coordinator_activities"


# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR  = Path(__file__).parent / "data"
NF_CSV    = DATA_DIR / "nf_coordinator_data.csv"
LOGO_PATH = Path(__file__).parent / "assets" / "images" / "csalogo.png"



# ── Page config + CSS — identical to kisan_mitra.py ──────────────────────────
# initialize_page() calls st.set_page_config (wide layout, expanded sidebar)
# AND injects assets/styles.css — this is what gives the correct background.
initialize_page()


# ── Data loading — Dashboard-owned MongoDB primary with CSV fallback ───────────
def _query_mongodb_for_pipeline() -> Optional[pd.DataFrame]:
    """
    Directly query MongoDB for NF Coordinator dataset.
    Resolves primarily via datasets_information -> datasets, with fallback to direct collection.
    """
    try:
        db = _get_mongodb_db()

        # Primary resolution: datasets_information -> datasets
        info = db["datasets_information"].find_one({"pipeline_id": PIPELINE_ID})
        if info and "dataset_id" in info:
            ds_doc = db["datasets"].find_one({"_id": info["dataset_id"]})
            if ds_doc and "data" in ds_doc:
                return pd.DataFrame(ds_doc["data"])

        # Secondary resolution: direct collection (backward compatibility)
        if PIPELINE_ID in db.list_collection_names():
            docs = list(db[PIPELINE_ID].find({}, {"_id": 0}))
            if docs:
                return pd.DataFrame(docs)

        return None
    except PyMongoError as db_err:
        logger.warning(f"MongoDB connection error for pipeline '{PIPELINE_ID}': {db_err}")
        st.sidebar.warning("⚠️ Live database unavailable. Showing reference data.")
        return None


def load_nf_data() -> pd.DataFrame:
    """
    Load NF Coordinator activity data for Dashboard 1.
    Primary: MongoDB via canonical pipeline metadata lookup.
    Fallback: Local reference CSV if MongoDB is empty or unreachable.
    """
    df = _query_mongodb_for_pipeline()

    if df is None or df.empty:
        if NF_CSV.exists():
            df = pd.read_csv(NF_CSV, encoding="ISO-8859-1")
        else:
            return pd.DataFrame(columns=[
                "coordinator_name", "district", "date", "type_of_activity",
                "planned_activities", "actual_activities", "total_score"
            ])

    try:
        df["date"]        = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
        df["month_label"] = df["date"].dt.strftime("%b %Y")
        df["month_short"] = df["date"].dt.strftime("%B")
        df["month_period"]= df["date"].dt.to_period("M")
        return df
    except (KeyError, ValueError, AttributeError, TypeError) as prog_err:
        logger.exception(f"Unexpected data transformation error in {PIPELINE_ID}: {prog_err}")
        st.error(f"Error computing dashboard date metrics: {prog_err}")
        return df


df = load_nf_data()


# ── Sidebar ────────────────────────────────────────────────────────────────────
def _b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


st.sidebar.markdown(
    f"""
    <div style="display:flex;justify-content:center;margin-bottom:20px;">
        <img src="data:image/png;base64,{_b64(LOGO_PATH)}" style="max-width:100%;height:auto;">
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    """<div class="sidebar-header">NF Coordinator Dashboard</div>""",
    unsafe_allow_html=True,
)

if st.sidebar.button("🔄 Refresh Data", key="refresh_nf_btn"):
    st.rerun()
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

# ── Filter widgets ─────────────────────────────────────────────────────────────
all_coordinators = sorted([c for c in df["coordinator_name"].dropna().unique() if str(c).strip()])
sel_coordinators = st.sidebar.multiselect(
    "NF Coordinator:",
    options=all_coordinators,
    default=[],
    placeholder="All Coordinators",
)

all_districts = sorted([d for d in df["district"].dropna().unique() if str(d).strip()])
sel_districts = st.sidebar.multiselect(
    "District:",
    options=all_districts,
    default=[],
    placeholder="All Districts",
)

months_ordered = (
    df[["month_label", "month_period"]]
    .dropna()
    .drop_duplicates()
    .sort_values("month_period")["month_label"]
    .tolist()
)
sel_months = st.sidebar.multiselect(
    "Plan of Month:",
    options=months_ordered,
    default=[],
    placeholder="All Months",
)

all_activities = sorted([a for a in df["type_of_activity"].dropna().unique() if str(a).strip()])
sel_activities = st.sidebar.multiselect(
    "Type of Activity:",
    options=all_activities,
    default=[],
    placeholder="All Activities",
)

st.sidebar.markdown(
    "<hr style='margin-top:45px;margin-bottom:50px;'>",
    unsafe_allow_html=True,
)


# ── Apply filters ──────────────────────────────────────────────────────────────
df_f = df.copy()
if sel_coordinators:
    df_f = df_f[df_f["coordinator_name"].isin(sel_coordinators)]
if sel_districts:
    df_f = df_f[df_f["district"].isin(sel_districts)]
if sel_months:
    df_f = df_f[df_f["month_label"].isin(sel_months)]
if sel_activities:
    df_f = df_f[df_f["type_of_activity"].isin(sel_activities)]


# ── Aggregates ─────────────────────────────────────────────────────────────────
total_score    = int(df_f["total_score"].fillna(0).sum()) if not df_f.empty and "total_score" in df_f.columns else 0
total_planned  = int(df_f["planned_activities"].fillna(0).sum()) if not df_f.empty and "planned_activities" in df_f.columns else 0
total_actual   = int(df_f["actual_activities"].fillna(0).sum()) if not df_f.empty and "actual_activities" in df_f.columns else 0
total_variance = total_actual - total_planned
overall_status = "Ahead" if total_variance >= 0 else "Behind"


# ── Coordinator-level performance table ────────────────────────────────────────
coord_perf = (
    df_f.dropna(subset=["coordinator_name"])
    .groupby("coordinator_name", as_index=False)
    .agg(
        Planned=("planned_activities", "sum"),
        Actual=("actual_activities", "sum"),
    )
)
coord_perf["Variance"] = coord_perf["Actual"] - coord_perf["Planned"]
coord_perf["Status"]   = coord_perf["Variance"].apply(
    lambda v: "Ahead" if v > 0 else ("On Track" if v == 0 else "Behind")
)
coord_perf = coord_perf.sort_values("Actual", ascending=False)
coord_perf.columns = [
    "Name of NF Coordinator",
    "Planned Activities",
    "Actual Activities",
    "Variance",
    "Status",
]

totals_row = pd.DataFrame([{
    "Name of NF Coordinator": "Total",
    "Planned Activities":     coord_perf["Planned Activities"].sum() if not coord_perf.empty else 0,
    "Actual Activities":      coord_perf["Actual Activities"].sum() if not coord_perf.empty else 0,
    "Variance":               coord_perf["Variance"].sum() if not coord_perf.empty else 0,
    "Status":                 overall_status,
}])
table_data = pd.concat([coord_perf, totals_row], ignore_index=True)


# ── Monthly score trend ────────────────────────────────────────────────────────
monthly_scores = (
    df_f.dropna(subset=["month_period", "month_short"])
    .groupby(["month_period", "month_short"], as_index=False)["total_score"]
    .sum()
    .sort_values("month_period")
)


############################################
#  LAYOUT
############################################

st.title("NF Coordinator Performance Dashboard v1.0")

# ── KPI cards ──────────────────────────────────────────────────────────────────
st.markdown("""<h3 class="sub">KPIs</h3>""", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.metric_card("Total Score Sum", f"{total_score:,}")
with c2:
    ui.metric_card("Total Planned Activities", f"{total_planned:,}")
with c3:
    ui.metric_card("Total Actual Activities", f"{total_actual:,}")
with c4:
    ui.metric_card("Overall Status", overall_status)

st.divider()

# ── Performance table ──────────────────────────────────────────────────────────
st.markdown(
    """<h3 class="sub">Performance Summary — NF Coordinator, District, Plan of Month, Type of Activity</h3>""",
    unsafe_allow_html=True,
)
st.dataframe(table_data, use_container_width=True, hide_index=True)

st.divider()

# ── Charts ─────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2, gap="large")

with col_left:
    st.markdown("""<h3 class="sub">Total Score Sum by Month</h3>""", unsafe_allow_html=True)

    if not monthly_scores.empty:
        fig_line = px.line(
            monthly_scores,
            x="month_short",
            y="total_score",
            markers=True,
            text="total_score",
        )
        fig_line.update_traces(
            line=dict(color="steelblue", width=2),
            marker=dict(size=8, color="steelblue"),
            textposition="top center",
            texttemplate="%{y:,}",
        )
        fig_line.update_layout(
            xaxis_title="Month",
            yaxis_title="Total Score Sum",
            height=420,
            margin=dict(l=50, r=20, t=40, b=60),
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No score data available for the selected filters.")

with col_right:
    st.markdown(
        """<h3 class="sub">Actual Activities and Planned Activities by Name of NF Coordinator</h3>""",
        unsafe_allow_html=True,
    )

    chart_df = coord_perf[coord_perf["Name of NF Coordinator"] != "Total"].copy()
    melted = chart_df.melt(
        id_vars="Name of NF Coordinator",
        value_vars=["Actual Activities", "Planned Activities"],
        var_name="Type",
        value_name="Count",
    )

    if not melted.empty:
        fig_bar = px.bar(
            melted,
            x="Name of NF Coordinator",
            y="Count",
            color="Type",
            barmode="group",
            text="Count",
            color_discrete_map={
                "Actual Activities":  "#1f77b4",
                "Planned Activities": "#aec7e8",
            },
        )
        fig_bar.update_layout(
            xaxis_title="Name of NF Coordinator",
            yaxis_title="Actual Activities and Planned Activities",
            height=420,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            margin=dict(l=40, r=20, t=60, b=120),
            xaxis=dict(tickangle=-45),
        )
        fig_bar.update_traces(textposition="outside", textfont_size=9)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No activity data available for the selected filters.")

st.divider()

# ── Data expanders ─────────────────────────────────────────────────────────────
with st.expander("📋 Full Activity Data (filtered)"):
    st.write(f"Showing {len(df_f):,} records.")
    st.dataframe(df_f, use_container_width=True)

with st.expander("📊 Coordinator Performance Detail"):
    st.dataframe(table_data, use_container_width=True, hide_index=True)
