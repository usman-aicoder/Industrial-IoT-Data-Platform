"""
Historical Analysis -- query MongoDB data, visualise trends, export CSV.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta, date

from src.components.styles import GLOBAL_CSS
from src.core.config_manager import load_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler
from src.analysis.anomaly_detector import build_stats_table

st.set_page_config(page_title="Historical Analysis | IIoT Platform", page_icon="📈", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

if "config" not in st.session_state:
    st.session_state.config = load_config()
if "opcua" not in st.session_state:
    st.session_state.opcua = OPCUAClient()
if "mongo" not in st.session_state:
    st.session_state.mongo = MongoDBHandler()

cfg = st.session_state.config
all_tags = cfg.get("tags", [])
mongo = st.session_state.mongo

with st.sidebar:
    st.markdown("## 🏭 IIoT Platform")

st.title("📈 Historical Analysis")

if not mongo.connected:
    st.error("MongoDB not connected. Go to **Settings** to connect.")
    st.stop()
if not all_tags:
    st.warning("No tags configured. Go to **Settings** to add tags.")
    st.stop()

# ------------------------------------------------------------------
# Query controls
# ------------------------------------------------------------------
PRESETS = {
    "Last 1 hour": timedelta(hours=1),
    "Last 6 hours": timedelta(hours=6),
    "Last 24 hours": timedelta(hours=24),
    "Last 7 days": timedelta(days=7),
    "Last 30 days": timedelta(days=30),
    "Custom range": None,
}

with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        preset_label = st.selectbox("Time range", list(PRESETS.keys()), index=2)
    with c2:
        if preset_label == "Custom range":
            today = date.today()
            date_range = st.date_input("From / To", value=(today - timedelta(days=1), today), max_value=today)
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                start_dt = datetime.combine(date_range[0], datetime.min.time(), tzinfo=timezone.utc)
                end_dt = datetime.combine(date_range[1], datetime.max.time(), tzinfo=timezone.utc)
            else:
                start_dt = datetime.now(tz=timezone.utc) - timedelta(days=1)
                end_dt = datetime.now(tz=timezone.utc)
        else:
            end_dt = datetime.now(tz=timezone.utc)
            start_dt = end_dt - PRESETS[preset_label]
            st.info(f"From **{start_dt.strftime('%d %b %H:%M')}** to **{end_dt.strftime('%d %b %H:%M')}** UTC")
    with c3:
        tag_names = [t.get("name", t["path"]) for t in all_tags]
        selected_names = st.multiselect("Tags", tag_names, default=tag_names)

    col_btn, col_opt = st.columns([1, 3])
    with col_btn:
        fetch = st.button("Fetch Data", type="primary", use_container_width=True)
    with col_opt:
        normalize = st.toggle("Normalize to 0-1", help="Scale all tags to same axis.")

# ------------------------------------------------------------------
# Fetch
# ------------------------------------------------------------------
if fetch:
    selected_tags = [t for t in all_tags if t.get("name", t["path"]) in selected_names]
    tag_data: dict = {}
    with st.spinner("Querying MongoDB..."):
        for tag in selected_tags:
            docs = mongo.query(tag["path"], start=start_dt, end=end_dt)
            if docs:
                df = pd.DataFrame(docs)
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                df["value"] = pd.to_numeric(df["value"], errors="coerce")
                df = df.dropna(subset=["value"]).sort_values("timestamp").reset_index(drop=True)
                tag_data[tag.get("name", tag["path"])] = df
    st.session_state.hist_data = tag_data
    st.session_state.hist_tags = selected_tags
else:
    tag_data = st.session_state.get("hist_data", {})

if not tag_data:
    st.info("Select a time range and tags, then press **Fetch Data**.")
    st.stop()

# ------------------------------------------------------------------
# Main chart
# ------------------------------------------------------------------
st.subheader("Trend Chart")
COLORS = ["#4a90e2", "#00b09b", "#f7971e", "#e74c3c", "#9b59b6", "#1abc9c"]
fig = go.Figure()
for i, (name, df) in enumerate(tag_data.items()):
    color = COLORS[i % len(COLORS)]
    tag_cfg = next((t for t in all_tags if t.get("name", t["path"]) == name), {})
    unit = tag_cfg.get("unit", "")
    y_vals = df["value"].astype(float)
    if normalize and y_vals.max() != y_vals.min():
        y_vals = (y_vals - y_vals.min()) / (y_vals.max() - y_vals.min())
        y_label = "Normalized"
    else:
        y_label = unit
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=y_vals, mode="lines",
        name=f"{name} ({unit})" if not normalize and unit else name,
        line=dict(color=color, width=2),
        hovertemplate=f"<b>{name}</b><br>%{{x|%H:%M:%S}}<br>%{{y:.4g}} {y_label}<extra></extra>",
    ))

fig.update_layout(
    height=420, margin=dict(l=10, r=10, t=30, b=10),
    paper_bgcolor="white", plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)"),
    yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)",
               title="Normalized (0-1)" if normalize else ""),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# Tabs
# ------------------------------------------------------------------
tab_stats, tab_dist, tab_raw, tab_corr = st.tabs(["Statistics", "Distribution", "Raw Data", "Correlation"])

with tab_stats:
    stats_df = build_stats_table(tag_data)
    if not stats_df.empty:
        st.dataframe(stats_df.style.format("{:.4g}").background_gradient(cmap="Blues", axis=0),
                     use_container_width=True)
        st.markdown("**Per-tag summary**")
        sum_cols = st.columns(len(tag_data))
        for i, (name, df) in enumerate(tag_data.items()):
            tag_cfg = next((t for t in all_tags if t.get("name", t["path"]) == name), {})
            unit = tag_cfg.get("unit", "")
            vals = df["value"].astype(float)
            with sum_cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    st.metric("Mean", f"{vals.mean():.3g} {unit}")
                    st.metric("Range", f"{vals.min():.3g} - {vals.max():.3g} {unit}")
                    st.metric("Std Dev", f"{vals.std():.3g} {unit}")
                    st.metric("Samples", f"{len(vals):,}")

with tab_dist:
    dist_cols = st.columns(min(len(tag_data), 3))
    for i, (name, df) in enumerate(tag_data.items()):
        tag_cfg = next((t for t in all_tags if t.get("name", t["path"]) == name), {})
        unit = tag_cfg.get("unit", "")
        with dist_cols[i % len(dist_cols)]:
            fig_hist = px.histogram(df, x="value", nbins=40, title=name,
                                    labels={"value": unit or "Value"},
                                    color_discrete_sequence=["#4a90e2"])
            fig_hist.update_layout(height=280, margin=dict(l=5, r=5, t=35, b=5),
                                   paper_bgcolor="white", plot_bgcolor="white", showlegend=False)
            st.plotly_chart(fig_hist, use_container_width=True)

with tab_raw:
    for name, df in tag_data.items():
        with st.expander(f"{name} -- {len(df):,} records"):
            display_df = df[["timestamp", "value", "unit"]].copy()
            display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

with tab_corr:
    if len(tag_data) >= 2:
        resampled = {}
        for name, df in tag_data.items():
            s = df.set_index("timestamp")["value"].astype(float)
            s.index = pd.DatetimeIndex(s.index)
            resampled[name] = s.resample("1min").mean()
        corr_df = pd.DataFrame(resampled).dropna()
        if not corr_df.empty and len(corr_df) > 1:
            corr_matrix = corr_df.corr()
            fig_corr = px.imshow(corr_matrix, text_auto=".2f",
                                 color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
                                 title="Pearson Correlation (1-min resampled)")
            fig_corr.update_layout(height=400, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="white")
            st.plotly_chart(fig_corr, use_container_width=True)
        else:
            st.info("Not enough overlapping data to compute correlation.")
    else:
        st.info("Select at least 2 tags to see correlation.")

# ------------------------------------------------------------------
# Download
# ------------------------------------------------------------------
dl_cols = st.columns(len(tag_data))
for i, (name, df) in enumerate(tag_data.items()):
    with dl_cols[i]:
        csv = df[["timestamp", "value", "unit"]].to_csv(index=False)
        st.download_button(
            label=f"Download {name} CSV",
            data=csv,
            file_name=f"{name.replace(' ', '_')}_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
