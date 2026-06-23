"""
Anomaly Detection -- Z-score, IsolationForest, or combined.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timezone, timedelta, date

from src.components.styles import GLOBAL_CSS
from src.core.config_manager import load_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler
from src.analysis.anomaly_detector import detect_anomalies, compute_statistics

st.set_page_config(page_title="Anomaly Detection | IIoT Platform", page_icon="🔍", layout="wide")
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
    st.markdown("**Detection Guide**")
    st.caption("**Z-score** - flags points more than N std devs from the mean.")
    st.caption("**Isolation Forest** - ML model, handles non-Gaussian data.")
    st.caption("**Combined** - union of both methods.")

st.title("🔍 Anomaly Detection")

if not mongo.connected:
    st.error("MongoDB not connected. Go to **Settings** to connect.")
    st.stop()
if not all_tags:
    st.warning("No tags configured. Go to **Settings** to add tags.")
    st.stop()

# ------------------------------------------------------------------
# Controls
# ------------------------------------------------------------------
with st.container(border=True):
    r1c1, r1c2, r1c3 = st.columns([2, 2, 2])
    with r1c1:
        tag_names = [t.get("name", t["path"]) for t in all_tags]
        selected_tag_name = st.selectbox("Tag to analyse", tag_names)
        selected_tag = next((t for t in all_tags if t.get("name", t["path"]) == selected_tag_name), None)
    with r1c2:
        PRESETS = {
            "Last 1 hour": timedelta(hours=1), "Last 6 hours": timedelta(hours=6),
            "Last 24 hours": timedelta(hours=24), "Last 7 days": timedelta(days=7),
            "Custom range": None,
        }
        preset_label = st.selectbox("Time range", list(PRESETS.keys()), index=2)
    with r1c3:
        if preset_label == "Custom range":
            today = date.today()
            dr = st.date_input("From / To", value=(today - timedelta(days=1), today), max_value=today)
            if isinstance(dr, (list, tuple)) and len(dr) == 2:
                start_dt = datetime.combine(dr[0], datetime.min.time(), tzinfo=timezone.utc)
                end_dt = datetime.combine(dr[1], datetime.max.time(), tzinfo=timezone.utc)
            else:
                start_dt = datetime.now(tz=timezone.utc) - timedelta(days=1)
                end_dt = datetime.now(tz=timezone.utc)
        else:
            end_dt = datetime.now(tz=timezone.utc)
            start_dt = end_dt - PRESETS[preset_label]
            st.info(f"{start_dt.strftime('%d %b %H:%M')} to {end_dt.strftime('%d %b %H:%M')} UTC")
    r2c1, r2c2, r2c3, r2c4 = st.columns([2, 2, 2, 1])
    with r2c1:
        method = st.selectbox("Detection method",
            ["zscore", "isolation_forest", "combined"],
            format_func=lambda x: {"zscore": "Z-score (statistical)",
                                   "isolation_forest": "Isolation Forest (ML)",
                                   "combined": "Combined (Z-score + IF)"}[x])
    with r2c2:
        zscore_threshold = st.slider("Z-score threshold", 1.0, 5.0, 2.5, 0.1,
                                     disabled=(method == "isolation_forest"))
    with r2c3:
        contamination = st.slider("Expected anomaly rate", 0.01, 0.20, 0.05, 0.01,
                                  format="%.0f%%", disabled=(method == "zscore"))
    with r2c4:
        st.markdown("&nbsp;")
        run_btn = st.button("Run Detection", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# Run detection
# ------------------------------------------------------------------
if run_btn and selected_tag:
    with st.spinner("Fetching data and running detection..."):
        docs = mongo.query(selected_tag["path"], start=start_dt, end=end_dt)
    if not docs:
        st.warning("No data found for this tag in the selected time range.")
        st.stop()
    df_raw = pd.DataFrame(docs)
    df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], utc=True)
    df_raw["value"] = pd.to_numeric(df_raw["value"], errors="coerce")
    df_raw = df_raw.dropna(subset=["value"]).sort_values("timestamp").reset_index(drop=True)
    if len(df_raw) < 3:
        st.warning("Too few data points (minimum 3 required).")
        st.stop()
    df_result = detect_anomalies(df_raw, method=method,
                                 zscore_threshold=zscore_threshold, contamination=contamination)
    st.session_state.anomaly_result = df_result
    st.session_state.anomaly_tag = selected_tag
    st.session_state.anomaly_method = method

if "anomaly_result" not in st.session_state:
    st.info("Configure the parameters above and press **Run Detection**.")
    st.stop()

df_result = st.session_state.anomaly_result
tag_cfg = st.session_state.anomaly_tag
unit = tag_cfg.get("unit", "")
anomalies = df_result[df_result["is_anomaly"]]
normal = df_result[~df_result["is_anomaly"]]
anomaly_pct = 100 * len(anomalies) / len(df_result) if len(df_result) else 0

# ------------------------------------------------------------------
# Summary metrics
# ------------------------------------------------------------------
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Points", f"{len(df_result):,}")
m2.metric("Anomalies Found", f"{len(anomalies):,}",
          delta=f"{anomaly_pct:.1f}% of data", delta_color="inverse")
m3.metric("Normal Points", f"{len(normal):,}")
m4.metric("Max Z-score", f"{df_result['z_score'].max():.2f}" if "z_score" in df_result.columns else "--")
m5.metric("Time Range",
          f"{(df_result['timestamp'].max() - df_result['timestamp'].min()).total_seconds() / 3600:.1f} h")

# ------------------------------------------------------------------
# Anomaly chart
# ------------------------------------------------------------------
st.subheader("Anomaly Chart")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=normal["timestamp"], y=normal["value"], mode="lines", name="Normal",
    line=dict(color="#4a90e2", width=1.5),
    hovertemplate=f"<b>Normal</b><br>%{{x|%H:%M:%S}}<br>%{{y:.4g}} {unit}<extra></extra>",
))
if not anomalies.empty:
    hover_text = []
    for _, row in anomalies.iterrows():
        txt = f"<b>ANOMALY</b><br>Value: {row['value']:.4g} {unit}"
        if "z_score" in row:
            txt += f"<br>Z-score: {row['z_score']:.2f}"
        hover_text.append(txt)
    fig.add_trace(go.Scatter(
        x=anomalies["timestamp"], y=anomalies["value"], mode="markers", name="Anomaly",
        marker=dict(color="#e74c3c", size=10, symbol="circle",
                    line=dict(color="white", width=1.5)),
        text=hover_text, hovertemplate="%{text}<extra></extra>",
    ))

lo = float(tag_cfg.get("min_range", df_result["value"].min()))
hi = float(tag_cfg.get("max_range", df_result["value"].max()))
fig.add_hrect(y0=lo + (hi - lo) * 0.9, y1=hi * 1.05,
              fillcolor="rgba(231,76,60,0.06)", line_width=0,
              annotation_text="Warning zone", annotation_position="top left",
              annotation_font_color="#e74c3c")
fig.update_layout(
    height=420, margin=dict(l=10, r=10, t=30, b=10),
    paper_bgcolor="white", plot_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)"),
    yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)", title=unit),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# Z-score timeline
if "z_score" in df_result.columns:
    with st.expander("Z-score timeline"):
        fig_z = go.Figure()
        fig_z.add_trace(go.Scatter(x=df_result["timestamp"], y=df_result["z_score"],
                                   mode="lines", line=dict(color="#9b59b6", width=1.5),
                                   fill="tozeroy", fillcolor="rgba(155,89,182,0.1)"))
        fig_z.add_hline(y=zscore_threshold, line_dash="dash", line_color="#e74c3c",
                        annotation_text=f"Threshold ({zscore_threshold})")
        fig_z.update_layout(height=220, margin=dict(l=10, r=10, t=20, b=10),
                            paper_bgcolor="white", plot_bgcolor="white",
                            yaxis=dict(title="Z-score"))
        st.plotly_chart(fig_z, use_container_width=True)

# ------------------------------------------------------------------
# Tabs
# ------------------------------------------------------------------
tab_table, tab_stats = st.tabs(["Anomaly Records", "Statistics"])

with tab_table:
    if anomalies.empty:
        st.success("No anomalies detected with the current settings.")
    else:
        display_cols = ["timestamp", "value", "unit"]
        if "z_score" in anomalies.columns:
            display_cols.append("z_score")
        display_df = anomalies[display_cols].copy()
        display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        if "z_score" in display_df:
            display_df["z_score"] = display_df["z_score"].round(3)
        st.dataframe(display_df.rename(columns={"timestamp": "Timestamp", "value": f"Value ({unit})",
                                                  "z_score": "Z-score"}),
                     use_container_width=True, hide_index=True)
        csv = display_df.to_csv(index=False)
        st.download_button("Download Anomaly Records CSV", data=csv,
                           file_name=f"anomalies_{selected_tag_name.replace(' ', '_')}.csv",
                           mime="text/csv")

with tab_stats:
    stats = compute_statistics(df_result)
    if stats:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Full dataset**")
            st.dataframe(pd.DataFrame.from_dict(stats, orient="index", columns=["Value"]),
                         use_container_width=True)
        with c2:
            if not anomalies.empty:
                st.markdown("**Anomalies only**")
                st.dataframe(pd.DataFrame.from_dict(compute_statistics(anomalies),
                                                    orient="index", columns=["Value"]),
                             use_container_width=True)
