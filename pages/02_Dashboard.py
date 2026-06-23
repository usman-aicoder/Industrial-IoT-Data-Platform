"""
Dashboard — enhanced UI with dark sidebar, KPI cards, live gauges, trend charts.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timezone

from src.core.config_manager import load_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler
from src.core.data_collector import collect_once, append_to_buffer
from src.components.styles import (
    GLOBAL_CSS, kpi_card, tag_card, section_header, status_banner, hex_to_rgba,
)

st.set_page_config(
    page_title="Dashboard | IIoT Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
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
if "dash_prev" not in st.session_state:
    st.session_state.dash_prev = {}
if "dash_buffer" not in st.session_state:
    st.session_state.dash_buffer = {}
if "dash_last_readings" not in st.session_state:
    st.session_state.dash_last_readings = []

cfg = st.session_state.config
tags = cfg.get("tags", [])
opcua = st.session_state.opcua
mongo = st.session_state.mongo

# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏭 IIoT Platform")
    refresh_rate = st.selectbox(
        "Auto-refresh",
        [2, 5, 10, 30],
        index=1,
        format_func=lambda x: f"Every {x}s",
    )
    if not opcua.connected:
        st.caption("⚙️ Go to Settings to connect")

# ------------------------------------------------------------------
# Hero banner
# ------------------------------------------------------------------
st.markdown(status_banner(opcua.connected, mongo.connected), unsafe_allow_html=True)

if not tags:
    st.info("No tags configured yet. Head to **⚙️ Settings** to add your OPC UA tags.")
    st.stop()

# ------------------------------------------------------------------
# Colour palette per tag (cycles)
# ------------------------------------------------------------------
ACCENTS = ["#4a90e2", "#f7971e", "#00b09b", "#e74c3c", "#8e44ad", "#1abc9c"]


def _accent(i: int) -> str:
    return ACCENTS[i % len(ACCENTS)]


# ------------------------------------------------------------------
# Helper: derive status label from value + range
# ------------------------------------------------------------------
def _status(value, lo: float, hi: float) -> tuple[str, str]:
    if not isinstance(value, (int, float)):
        return "ON" if value else "OFF", "#4a90e2"
    pct = (float(value) - lo) / (hi - lo) if hi != lo else 0.5
    if pct >= 0.9:
        return "HIGH", "#e74c3c"
    if pct >= 0.7:
        return "WARNING", "#f7971e"
    if pct <= 0.05:
        return "LOW", "#e74c3c"
    return "NORMAL", "#00b09b"


# ==================================================================
# Live fragment — the only part that re-polls on the timer
# ==================================================================
@st.fragment(run_every=refresh_rate)
def live_section():
    monitoring_cfg = cfg.get("monitoring", {})

    # ---- Poll OPC UA ----
    readings, updated_prev = collect_once(
        opcua_client=st.session_state.opcua,
        mongo_handler=st.session_state.mongo,
        tags=tags,
        previous_values=st.session_state.dash_prev,
        threshold=float(monitoring_cfg.get("change_threshold", 0.01)),
        store_on_change=bool(monitoring_cfg.get("store_on_change_only", True)),
    )
    if readings:
        st.session_state.dash_prev = updated_prev
        st.session_state.dash_buffer = append_to_buffer(
            st.session_state.dash_buffer, readings, max_points=180
        )
        st.session_state.dash_last_readings = readings

    last = {r["path"]: r for r in st.session_state.dash_last_readings}

    # ------------------------------------------------------------------
    # KPI row
    # ------------------------------------------------------------------
    stats = mongo.get_statistics() if mongo.connected else None
    total_records = stats["total_records"] if stats else 0
    last_ts = stats["last_record"].strftime("%H:%M") if stats and stats["last_record"] else "—"

    st.markdown(section_header("📈 Key Metrics", "Live system overview"), unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(kpi_card(
            "OPC UA Server",
            "🟢 Live" if opcua.connected else "🔴 Off",
            opcua.server_url.replace("opc.tcp://", "") if opcua.connected else "Not connected",
            "🔌", "#4a90e2",
        ), unsafe_allow_html=True)
    with k2:
        st.markdown(kpi_card(
            "MongoDB",
            "🟢 Live" if mongo.connected else "🔴 Off",
            f"{mongo.database_name}.{mongo.collection_name}" if mongo.connected else "Not connected",
            "🗄️", "#00b09b",
        ), unsafe_allow_html=True)
    with k3:
        st.markdown(kpi_card(
            "Total Records",
            f"{total_records:,}",
            f"Last at {last_ts}" if last_ts != "—" else "No data yet",
            "💾", "#f7971e",
        ), unsafe_allow_html=True)
    with k4:
        anom_tags = sum(
            1 for t in tags
            if last.get(t["path"]) and _status(last[t["path"]]["value"], t.get("min_range", 0), t.get("max_range", 100))[0] in ("HIGH", "LOW", "WARNING")
        )
        st.markdown(kpi_card(
            "Active Tags",
            str(len(tags)),
            f"{anom_tags} need attention" if anom_tags else "All within range",
            "📡", "#8e44ad",
        ), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Tag cards grid
    # ------------------------------------------------------------------
    st.markdown(section_header("🔴 Live Tag Values", f"Polled every {refresh_rate}s · last update {datetime.now().strftime('%H:%M:%S')}"), unsafe_allow_html=True)

    cols_per_row = min(len(tags), 3)
    cols = st.columns(cols_per_row)

    for i, tag in enumerate(tags):
        path = tag["path"]
        r = last.get(path)
        col = cols[i % cols_per_row]

        with col:
            if r:
                status_label, _ = _status(r["value"], tag.get("min_range", 0), tag.get("max_range", 100))
                st.markdown(
                    tag_card(
                        name=tag.get("name", path),
                        value=r["value"],
                        unit=tag.get("unit", ""),
                        lo=float(tag.get("min_range", 0)),
                        hi=float(tag.get("max_range", 100)),
                        timestamp=r["timestamp"].strftime("%H:%M:%S"),
                        accent=_accent(i),
                        status=status_label,
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    tag_card(
                        name=tag.get("name", path),
                        value="—",
                        unit=tag.get("unit", ""),
                        lo=float(tag.get("min_range", 0)),
                        hi=float(tag.get("max_range", 100)),
                        timestamp="waiting…",
                        accent=_accent(i),
                        status="OFFLINE",
                    ),
                    unsafe_allow_html=True,
                )

    # ------------------------------------------------------------------
    # Trend charts
    # ------------------------------------------------------------------
    buffer = st.session_state.dash_buffer
    if not buffer:
        st.info("Trend charts appear once data starts flowing from OPC UA.")
        return

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.markdown(section_header("📉 Trend Charts", "Rolling window from live readings"), unsafe_allow_html=True)

    chart_tags = [t for t in tags if t["path"] in buffer]
    if not chart_tags:
        return

    # Pair tags into rows of 2
    for row_start in range(0, len(chart_tags), 2):
        row_tags = chart_tags[row_start: row_start + 2]
        row_cols = st.columns(len(row_tags))

        for ci, tag in enumerate(row_tags):
            path = tag["path"]
            pts = buffer.get(path, [])
            if not pts:
                continue

            df = pd.DataFrame(pts)
            accent = _accent(tags.index(tag))
            name = tag.get("name", path)
            unit = tag.get("unit", "")

            latest_val = df["value"].iloc[-1] if not df.empty else None
            status_label, _ = _status(latest_val, tag.get("min_range", 0), tag.get("max_range", 100))

            fig = go.Figure()

            # Fill area
            fig.add_trace(go.Scatter(
                x=df["timestamp"], y=df["value"],
                mode="lines",
                line=dict(color=accent, width=2.5, shape="spline"),
                fill="tozeroy",
                fillcolor=hex_to_rgba(accent, 0.09),
                name=name,
                hovertemplate=f"<b>{name}</b><br>%{{x|%H:%M:%S}}<br>%{{y:.4g}} {unit}<extra></extra>",
            ))

            # Latest value dot
            if latest_val is not None and not df.empty:
                fig.add_trace(go.Scatter(
                    x=[df["timestamp"].iloc[-1]],
                    y=[df["value"].iloc[-1]],
                    mode="markers",
                    marker=dict(color=accent, size=10, line=dict(color="white", width=2)),
                    showlegend=False,
                    hoverinfo="skip",
                ))

            fig.update_layout(
                title=dict(
                    text=f"<b>{name}</b>  <span style='font-size:14px;color:{accent};'>{f'{float(latest_val):.4g} {unit}' if isinstance(latest_val, (int,float)) else '—'}</span>",
                    font=dict(size=15),
                    x=0,
                ),
                height=240,
                margin=dict(l=10, r=10, t=40, b=10),
                paper_bgcolor="white",
                plot_bgcolor="white",
                showlegend=False,
                xaxis=dict(
                    showgrid=False, zeroline=False, showticklabels=True,
                    tickfont=dict(size=10, color="#aaa"),
                ),
                yaxis=dict(
                    showgrid=True, gridcolor="#f0f4f8", zeroline=False,
                    tickfont=dict(size=10, color="#aaa"),
                    title=dict(text=unit, font=dict(size=11, color="#aaa")),
                ),
                hovermode="x unified",
            )

            # Wrap in card-style container
            with row_cols[ci]:
                st.markdown(
                    '<div style="background:white;border-radius:16px;padding:16px;'
                    'box-shadow:0 4px 24px rgba(0,0,0,0.07);">',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(fig, use_container_width=True, key=f"trend_{path}_{row_start}")
                st.markdown("</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Bottom row: DB stats + tag status table
    # ------------------------------------------------------------------
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.markdown(section_header("📊 System Overview"), unsafe_allow_html=True)

    left, right = st.columns([1, 2])

    with left:
        st.markdown(
            '<div style="background:linear-gradient(135deg,#0a1628,#1a2744);'
            'border-radius:16px;padding:22px;box-shadow:0 4px 24px rgba(0,0,0,0.12);">',
            unsafe_allow_html=True,
        )
        if stats:
            items = [
                ("📦 Total Records", f"{stats['total_records']:,}"),
                ("🏷️ Stored Tags", str(stats["unique_tags"])),
                ("🕐 Latest Record", stats["last_record"].strftime("%d %b %H:%M") if stats["last_record"] else "—"),
                ("📅 First Record", stats["first_record"].strftime("%d %b %H:%M") if stats["first_record"] else "—"),
            ]
        else:
            items = [("Status", "Not connected")]

        for label, val in items:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.07);">'
                f'<span style="color:rgba(255,255,255,0.55);font-size:12px;">{label}</span>'
                f'<span style="color:white;font-size:13px;font-weight:600;">{val}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        # Tag status table
        rows = []
        for i, tag in enumerate(tags):
            path = tag["path"]
            r = last.get(path)
            val = r["value"] if r else None
            status_label, status_color = _status(val, tag.get("min_range", 0), tag.get("max_range", 100))
            val_str = f"{float(val):.4g} {tag.get('unit','')}" if isinstance(val, (int, float)) else (str(val) if val is not None else "—")
            rows.append({
                "Tag": tag.get("name", path),
                "Value": val_str,
                "Status": status_label,
                "Updated": r["timestamp"].strftime("%H:%M:%S") if r else "—",
            })

        if rows:
            df_table = pd.DataFrame(rows)
            st.dataframe(
                df_table,
                use_container_width=True,
                hide_index=True,
                height=220,
            )


live_section()
