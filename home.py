"""
Industrial IoT Data Platform -- Home page.
"""

import streamlit as st
from src.core.config_manager import load_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler
from src.components.styles import GLOBAL_CSS, kpi_card, status_banner

st.set_page_config(
    page_title="IIoT Data Platform",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

if "config" not in st.session_state:
    st.session_state.config = load_config()
if "opcua" not in st.session_state:
    st.session_state.opcua = OPCUAClient()
if "mongo" not in st.session_state:
    st.session_state.mongo = MongoDBHandler()

cfg = st.session_state.config
opcua_ok = st.session_state.opcua.connected
mongo_ok = st.session_state.mongo.connected
tags = cfg.get("tags", [])

with st.sidebar:
    st.markdown("## 🏭 IIoT Platform")

st.markdown(status_banner(opcua_ok, mongo_ok), unsafe_allow_html=True)

has_openai = bool(cfg.get("openai", {}).get("api_key", ""))
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(kpi_card(
        "OPC UA Server",
        "🟢 Connected" if opcua_ok else "🔴 Offline",
        st.session_state.opcua.server_url.replace("opc.tcp://", "") if opcua_ok else "Configure in Settings",
        "🔌", "#4a90e2",
    ), unsafe_allow_html=True)

with c2:
    st.markdown(kpi_card(
        "MongoDB",
        "🟢 Connected" if mongo_ok else "🔴 Offline",
        f"{st.session_state.mongo.database_name}" if mongo_ok else "Configure in Settings",
        "🗄️", "#00b09b",
    ), unsafe_allow_html=True)

with c3:
    st.markdown(kpi_card(
        "Configured Tags",
        str(len(tags)),
        "tags monitored" if tags else "Add tags in Settings",
        "📡", "#f7971e",
    ), unsafe_allow_html=True)

with c4:
    st.markdown(kpi_card(
        "System",
        "🟢 Ready" if (opcua_ok and mongo_ok) else "⚙️ Setup needed",
        "All systems operational" if (opcua_ok and mongo_ok) else "Go to Settings",
        "🖥️", "#8e44ad",
    ), unsafe_allow_html=True)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
st.divider()

st.markdown(
    '<div style="font-size:18px;font-weight:700;color:#0a1628;margin-bottom:16px;">🚀 Navigate to</div>',
    unsafe_allow_html=True,
)

nav_pages = [
    ("pages/01_Settings.py",           "⚙️",  "Settings",           "Configure OPC UA, MongoDB, and all tag paths.", "#4a90e2"),
    ("pages/02_Dashboard.py",          "📊",  "Dashboard",          "Live KPI cards and trend charts — auto-refreshed.", "#f7971e"),
    ("pages/03_Realtime_Monitor.py",   "📡",  "Realtime Monitor",   "Streaming line charts per tag with pause/resume.", "#00b09b"),
    ("pages/04_Historical_Analysis.py","📈",  "Historical Analysis","Query stored data, view statistics, export CSV.", "#8e44ad"),
    ("pages/05_Anomaly_Detection.py",  "🔍",  "Anomaly Detection",  "Z-score and IsolationForest anomaly detection.", "#e74c3c"),
    ("pages/07_Reports.py",            "📄",  "Reports",            "Generate and download full HTML / CSV reports.", "#f39c12"),
]

st.markdown("""
<style>
div[data-testid="stPageLink"] a {
    display: inline-flex !important; align-items: center !important;
    justify-content: center !important; width: 100% !important;
    padding: 7px 12px !important; margin-top: 6px !important;
    background: #f5f8ff !important; border: 1.5px solid #d8e3f5 !important;
    border-radius: 10px !important; color: #4a90e2 !important;
    font-size: 13px !important; font-weight: 600 !important;
    text-decoration: none !important; transition: all 0.18s !important;
}
div[data-testid="stPageLink"] a:hover {
    background: #4a90e2 !important; color: white !important;
    border-color: #4a90e2 !important;
}
</style>
""", unsafe_allow_html=True)

row1 = st.columns(3)
row2 = st.columns(3)
all_cols = row1 + row2

for i, (page_path, icon, name, desc, color) in enumerate(nav_pages):
    with all_cols[i]:
        st.markdown(f"""
        <div style="background:white;border-radius:16px;padding:20px 20px 8px;
            box-shadow:0 4px 20px rgba(0,0,0,0.07);border-top:4px solid {color};min-height:100px;">
            <div style="font-size:26px;margin-bottom:6px;">{icon}</div>
            <div style="font-size:15px;font-weight:700;color:#0a1628;margin-bottom:4px;">{name}</div>
            <div style="font-size:12px;color:#9aa5b4;line-height:1.5;">{desc}</div>
        </div>""", unsafe_allow_html=True)
        st.page_link(page_path, label=f"Open {name} →", use_container_width=True)

if not opcua_ok and not mongo_ok:
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.info("**Get started:** Go to **⚙️ Settings** to connect your OPC UA server and MongoDB, then add tags.")
