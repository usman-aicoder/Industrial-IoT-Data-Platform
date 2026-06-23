"""
Real-time Monitor -- streaming tag values with full Plotly charts.
Uses st.fragment(run_every=N) so only the chart area refreshes.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timezone, timedelta

from src.components.styles import GLOBAL_CSS, hex_to_rgba
from src.core.config_manager import load_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler
from src.core.data_collector import collect_once, append_to_buffer

st.set_page_config(
    page_title="Real-time Monitor | IIoT Platform",
    page_icon="📡",
    layout="wide",
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------
# Session state bootstrap
# ------------------------------------------------------------------
if "config" not in st.session_state:
    st.session_state.config = load_config()
if "opcua" not in st.session_state:
    st.session_state.opcua = OPCUAClient()
if "mongo" not in st.session_state:
    st.session_state.mongo = MongoDBHandler()
if "rt_buffer" not in st.session_state:
    st.session_state.rt_buffer = {}
if "rt_prev" not in st.session_state:
    st.session_state.rt_prev = {}
if "rt_running" not in st.session_state:
    st.session_state.rt_running = True
if "rt_total_reads" not in st.session_state:
    st.session_state.rt_total_reads = 0
if "rt_total_writes" not in st.session_state:
    st.session_state.rt_total_writes = 0

cfg = st.session_state.config
all_tags = cfg.get("tags", [])
opcua = st.session_state.opcua
mongo = st.session_state.mongo

with st.sidebar:
    st.markdown("## 🏭 IIoT Platform")

st.title("📡 Real-time Monitor")

if not all_tags:
    st.warning("No tags configured. Go to **Settings** to add tags first.")
    st.stop()
if not opcua.connected:
    st.error("OPC UA not connected. Go to **Settings** to connect.")

# ------------------------------------------------------------------
# Controls
# ------------------------------------------------------------------
with st.container(border=True):
    ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([3, 2, 2, 2])
    with ctrl1:
        tag_names = [t.get("name", t["path"]) for t in all_tags]
        selected_names = st.multiselect("Tags to monitor", options=tag_names, default=tag_names)
        selected_tags = [t for t in all_tags if t.get("name", t["path"]) in selected_names]
    with ctrl2:
        poll_interval = st.selectbox("Poll interval", options=[1, 2, 5, 10, 30], index=0,
                                     format_func=lambda x: f"{x}s")
    with ctrl3:
        window_minutes = st.selectbox("Chart window", options=[1, 5, 15, 30, 60], index=1,
                                      format_func=lambda x: f"{x} min")
        max_points = window_minutes * 60 // poll_interval
    with ctrl4:
        st.markdown("&nbsp;")
        col_run, col_clear = st.columns(2)
        with col_run:
            if st.session_state.rt_running:
                if st.button("Pause", use_container_width=True):
                    st.session_state.rt_running = False
                    st.rerun()
            else:
                if st.button("Resume", use_container_width=True, type="primary"):
                    st.session_state.rt_running = True
                    st.rerun()
        with col_clear:
            if st.button("Clear", use_container_width=True):
                st.session_state.rt_buffer = {}
                st.session_state.rt_prev = {}
                st.session_state.rt_total_reads = 0
                st.session_state.rt_total_writes = 0
                st.rerun()

s1, s2, s3, s4 = st.columns(4)
s1.metric("Status", "Running" if st.session_state.rt_running else "Paused")
s2.metric("Total Polls", st.session_state.rt_total_reads)
s3.metric("DB Writes", st.session_state.rt_total_writes)
s4.metric("Buffered Points", sum(len(v) for v in st.session_state.rt_buffer.values()))
chart_area = st.empty()
table_area = st.empty()


@st.fragment(run_every=poll_interval if st.session_state.rt_running else None)
def live_monitor():
    if not st.session_state.rt_running or not selected_tags:
        with chart_area.container():
            st.info("Monitoring paused. Press Resume to continue.")
        return

    monitoring_cfg = cfg.get("monitoring", {})
    readings, updated_prev = collect_once(
        opcua_client=st.session_state.opcua,
        mongo_handler=st.session_state.mongo,
        tags=selected_tags,
        previous_values=st.session_state.rt_prev,
        threshold=float(monitoring_cfg.get("change_threshold", 0.01)),
        store_on_change=bool(monitoring_cfg.get("store_on_change_only", True)),
    )
    if readings:
        st.session_state.rt_prev = updated_prev
        st.session_state.rt_buffer = append_to_buffer(
            st.session_state.rt_buffer, readings, max_points=max_points)
        st.session_state.rt_total_reads += 1
        if mongo.connected:
            st.session_state.rt_total_writes += len(readings)

    with chart_area.container():
        if not st.session_state.rt_buffer:
            st.info("Waiting for first readings from OPC UA...")
            return
        for tag in selected_tags:
            path = tag["path"]
            pts = st.session_state.rt_buffer.get(path, [])
            if not pts:
                continue
            df = pd.DataFrame(pts)
            name = tag.get("name", path)
            unit = tag.get("unit", "")
            lo = float(tag.get("min_range", 0))
            hi = float(tag.get("max_range", 100))
            latest = df["value"].iloc[-1] if not df.empty else None
            if latest is not None and isinstance(latest, (int, float)):
                pct = (float(latest) - lo) / (hi - lo) if hi != lo else 0.5
                line_color = "#e74c3c" if pct >= 0.9 else "#f7971e" if pct >= 0.7 else "#00b09b"
            else:
                line_color = "#4a90e2"
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"], mode="lines", name=name,
                line=dict(color=line_color, width=2.5, shape="spline"),
                fill="tozeroy", fillcolor=hex_to_rgba(line_color, 0.09),
            ))
            if latest is not None and not df.empty:
                fig.add_annotation(x=df["timestamp"].iloc[-1], y=float(latest),
                    text=f"  {latest:.2f} {unit}", showarrow=False,
                    font=dict(size=13, color=line_color), xanchor="left")
            fig.update_layout(
                title=dict(text=f"{name} ({unit})", font=dict(size=16)),
                height=280, margin=dict(l=10, r=10, t=40, b=30),
                paper_bgcolor="white", plot_bgcolor="white",
                xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)"),
                yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.1)",
                           range=[lo * 0.95, hi * 1.05], title=unit),
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True, key=f"rt_{path}")

    if readings:
        with table_area.container():
            st.markdown("**Latest readings**")
            rows = [{"Tag": r["name"],
                     "Value": f"{r['value']:.4g}" if isinstance(r["value"], float) else r["value"],
                     "Unit": r["unit"],
                     "Timestamp (UTC)": r["timestamp"].strftime("%H:%M:%S")} for r in readings]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


live_monitor()
