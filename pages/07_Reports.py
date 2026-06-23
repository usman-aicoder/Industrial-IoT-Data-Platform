"""
Reports -- generate a full analysis report for any time period and download it.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta, date

from src.components.styles import GLOBAL_CSS
from src.core.config_manager import load_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler
from src.analysis.report_generator import generate_report_data, render_html_report

st.set_page_config(page_title="Reports | IIoT Platform", page_icon="📄", layout="wide")
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

st.title("📄 Reports")

if not mongo.connected:
    st.error("MongoDB not connected. Go to **Settings** to connect.")
    st.stop()
if not all_tags:
    st.warning("No tags configured. Go to **Settings** to add tags.")
    st.stop()

# ------------------------------------------------------------------
# Report configuration
# ------------------------------------------------------------------
with st.container(border=True):
    st.markdown("**Report Configuration**")
    c1, c2 = st.columns(2)
    with c1:
        PRESETS = {
            "Last 1 hour": timedelta(hours=1), "Last 6 hours": timedelta(hours=6),
            "Last 24 hours": timedelta(hours=24), "Last 7 days": timedelta(days=7),
            "Last 30 days": timedelta(days=30), "Custom range": None,
        }
        preset = st.selectbox("Time period", list(PRESETS.keys()), index=2)
    with c2:
        if preset == "Custom range":
            today = date.today()
            dr = st.date_input("From / To", value=(today - timedelta(days=7), today), max_value=today)
            if isinstance(dr, (list, tuple)) and len(dr) == 2:
                start_dt = datetime.combine(dr[0], datetime.min.time(), tzinfo=timezone.utc)
                end_dt = datetime.combine(dr[1], datetime.max.time(), tzinfo=timezone.utc)
            else:
                start_dt = datetime.now(tz=timezone.utc) - timedelta(days=7)
                end_dt = datetime.now(tz=timezone.utc)
        else:
            end_dt = datetime.now(tz=timezone.utc)
            start_dt = end_dt - PRESETS[preset]
            st.info(f"{start_dt.strftime('%d %b %H:%M')} to {end_dt.strftime('%d %b %H:%M')} UTC")

    tag_names = [t.get("name", t["path"]) for t in all_tags]
    selected_names = st.multiselect("Include tags", tag_names, default=tag_names)
    selected_tags = [t for t in all_tags if t.get("name", t["path"]) in selected_names]

    col_btn, col_thresh = st.columns([1, 2])
    with col_btn:
        generate_btn = st.button("Generate Report", type="primary", use_container_width=True)
    with col_thresh:
        zscore_thresh = st.slider("Anomaly threshold (Z-score)", 1.5, 4.0, 2.5, 0.1)

# ------------------------------------------------------------------
# Generate
# ------------------------------------------------------------------
if generate_btn:
    if not selected_tags:
        st.error("Select at least one tag.")
        st.stop()
    with st.spinner("Fetching data and generating report..."):
        report = generate_report_data(mongo_handler=mongo, tags=selected_tags,
                                      start_dt=start_dt, end_dt=end_dt,
                                      zscore_threshold=zscore_thresh)
        html_report = render_html_report(report)
    st.session_state.last_report = report
    st.session_state.last_report_html = html_report
    st.success("Report generated!")

if "last_report" not in st.session_state:
    st.info("Configure the report above and press **Generate Report**.")
    st.stop()

report = st.session_state.last_report
html_report = st.session_state.last_report_html

# ------------------------------------------------------------------
# Preview
# ------------------------------------------------------------------
st.subheader("Report Preview")

p_start = report["period_start"].strftime("%d %b %Y %H:%M")
p_end = report["period_end"].strftime("%d %b %Y %H:%M")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Tags Analysed", report["tag_count"])
m2.metric("Total Records", f"{report['total_records']:,}")
total_anom = sum(t["anomaly_count"] for t in report["tags"])
m3.metric("Total Anomalies", total_anom,
          delta=f"{100*total_anom/max(report['total_records'],1):.1f}%", delta_color="inverse")
m4.metric("Period", f"{p_start} to {p_end}")

# Summary table
st.markdown("#### Summary Table")
if report["tags"]:
    summary_rows = []
    for t in report["tags"]:
        summary_rows.append({
            "Tag": t["name"], "Unit": t["unit"], "Records": t["records"],
            "Mean": t["stats"].get("Mean", "--") if t["stats"] else "--",
            "Min": t["stats"].get("Min", "--") if t["stats"] else "--",
            "Max": t["stats"].get("Max", "--") if t["stats"] else "--",
            "Anomalies": f"{t['anomaly_count']} ({t['anomaly_pct']}%)",
            "Trend": t["trend"],
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

# Per-tag details
st.markdown("#### Tag Details")
for t in report["tags"]:
    anom_indicator = f"{t['anomaly_count']} anomalies" if t["anomaly_count"] else "No anomalies"
    with st.expander(f"**{t['name']}** -- {anom_indicator} | {t['trend']}"):
        if t["df"].empty:
            st.info("No data for this tag in the selected period.")
            continue
        c1, c2 = st.columns([1, 2])
        with c1:
            if t["stats"]:
                st.dataframe(pd.DataFrame.from_dict(t["stats"], orient="index",
                             columns=[f"Value ({t['unit']})"]), use_container_width=True)
        with c2:
            df = t["df"]
            vals = df["value"].astype(float)
            z = np.abs((vals - vals.mean()) / (vals.std() or 1.0))
            anom_mask = z > zscore_thresh
            normal_df = df[~anom_mask]
            anom_df = df[anom_mask]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=normal_df["timestamp"], y=normal_df["value"],
                                     mode="lines", name="Normal",
                                     line=dict(color="#4a90e2", width=1.5)))
            if not anom_df.empty:
                fig.add_trace(go.Scatter(x=anom_df["timestamp"], y=anom_df["value"],
                                         mode="markers", name="Anomaly",
                                         marker=dict(color="#e74c3c", size=9)))
            fig.update_layout(height=240, margin=dict(l=5, r=5, t=10, b=5),
                              paper_bgcolor="white", plot_bgcolor="white",
                              legend=dict(orientation="h"),
                              yaxis=dict(title=t["unit"]))
            st.plotly_chart(fig, use_container_width=True, key=f"rep_{t['name']}")

# ------------------------------------------------------------------
# Downloads
# ------------------------------------------------------------------
st.markdown("#### Download")
dl1, dl2, dl3 = st.columns(3)

with dl1:
    st.download_button("Download HTML Report", data=html_report,
                       file_name=f"iiot_report_{report['generated_at'].strftime('%Y%m%d_%H%M')}.html",
                       mime="text/html", use_container_width=True, type="primary")
with dl2:
    all_frames = []
    for t in report["tags"]:
        if not t["df"].empty:
            df_copy = t["df"][["timestamp", "value", "unit"]].copy()
            df_copy.insert(0, "tag_name", t["name"])
            all_frames.append(df_copy)
    if all_frames:
        combined_csv = pd.concat(all_frames, ignore_index=True).to_csv(index=False)
        st.download_button("Download Combined CSV", data=combined_csv,
                           file_name=f"iiot_data_{report['generated_at'].strftime('%Y%m%d_%H%M')}.csv",
                           mime="text/csv", use_container_width=True)
with dl3:
    stats_rows = []
    for t in report["tags"]:
        if t["stats"]:
            row = {"tag": t["name"], "unit": t["unit"], **t["stats"],
                   "anomaly_count": t["anomaly_count"], "trend": t["trend"]}
            stats_rows.append(row)
    if stats_rows:
        stats_csv = pd.DataFrame(stats_rows).to_csv(index=False)
        st.download_button("Download Stats CSV", data=stats_csv,
                           file_name=f"iiot_stats_{report['generated_at'].strftime('%Y%m%d_%H%M')}.csv",
                           mime="text/csv", use_container_width=True)
