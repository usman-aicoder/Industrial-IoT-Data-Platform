"""
Shared design system — CSS injection and HTML card builders used across all pages.

Color palette
  Navy dark   #0a1628   sidebar, headings
  Navy mid    #1a2744   sidebar gradient end
  Blue        #4a90e2   primary accent, links
  Orange      #f7971e   secondary accent, warnings
  Teal        #00b09b   success, positive trend
  Red         #e74c3c   danger, anomaly
  Purple      #8e44ad   info cards
  BG          #f0f4f8   page background
  Card        #ffffff   card background
"""

# ------------------------------------------------------------------
# Global CSS — inject with st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
# ------------------------------------------------------------------
GLOBAL_CSS = """
<style>
/* ── Page background ─────────────────────────── */
.stApp { background: #f0f4f8 !important; }

/* ── Block container padding ────────────────── */
.main .block-container {
    padding: 1.2rem 2rem 2rem !important;
    max-width: 100% !important;
}

/* ── Sidebar: dark navy gradient ────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1628 0%, #1a2744 100%) !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] > div:first-child {
    background: transparent !important;
}
/* Sidebar text → white */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] p,
section[data-testid="stSidebar"] [data-testid="stMetricValue"],
section[data-testid="stSidebar"] [data-testid="stMetricDelta"] {
    color: rgba(255,255,255,0.9) !important;
}
/* Sidebar metric mini-cards */
section[data-testid="stSidebar"] [data-testid="metric-container"] {
    background: rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
}
/* Sidebar selectbox */
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: rgba(255,255,255,0.1) !important;
    border-color: rgba(255,255,255,0.2) !important;
    color: white !important;
}
/* Sidebar divider */
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.15) !important;
}
/* Sidebar caption */
section[data-testid="stSidebar"] .stCaption p {
    color: rgba(255,255,255,0.5) !important;
}

/* ── Dividers ────────────────────────────────── */
hr { border-color: rgba(26,26,46,0.08) !important; }

/* ── Page title ──────────────────────────────── */
h1 { color: #0a1628 !important; font-weight: 700 !important; }
h2, h3 { color: #1a2744 !important; }

/* ── Tabs ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #e8ecf0;
    border-radius: 10px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 6px 16px;
    font-weight: 500;
    color: #555;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #4a90e2 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

/* ── Buttons ─────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4a90e2 0%, #357abd 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(74,144,226,0.3) !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(74,144,226,0.4) !important;
}
.stButton > button[kind="secondary"] {
    border-radius: 10px !important;
    border-color: #4a90e2 !important;
    color: #4a90e2 !important;
}

/* ── Input fields ────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    border-radius: 8px !important;
    border-color: #dde3ea !important;
}
.stSelectbox > div > div {
    border-radius: 8px !important;
}

/* ── Dataframe ───────────────────────────────── */
.stDataFrame { border-radius: 12px; overflow: hidden; }

/* ── Expander ────────────────────────────────── */
.streamlit-expanderHeader {
    background: white !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
}

/* ── Alerts ──────────────────────────────────── */
.stAlert { border-radius: 10px !important; }

/* ── Page link nav buttons ───────────────────── */
div[data-testid="stPageLink"] a {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    padding: 7px 12px !important;
    margin-top: 6px !important;
    background: #f5f8ff !important;
    border: 1.5px solid #d8e3f5 !important;
    border-radius: 10px !important;
    color: #4a90e2 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    text-decoration: none !important;
    transition: all 0.18s !important;
}
div[data-testid="stPageLink"] a:hover {
    background: #4a90e2 !important;
    color: white !important;
    border-color: #4a90e2 !important;
    box-shadow: 0 4px 12px rgba(74,144,226,0.25) !important;
    transform: translateY(-1px) !important;
}
</style>
"""

# ------------------------------------------------------------------
# Reusable HTML component builders
# ------------------------------------------------------------------

def hex_to_rgba(hex_color: str, alpha: float = 0.12) -> str:
    """Convert '#rrggbb' to 'rgba(r,g,b,alpha)' for Plotly fillcolor."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def kpi_card(title: str, value: str, subtitle: str, icon: str, accent: str) -> str:
    """Large KPI card with icon, value, and coloured accent strip."""
    return f"""
    <div style="
        background: white;
        border-radius: 16px;
        padding: 22px 24px 18px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.07);
        border-top: 4px solid {accent};
        position: relative;
        overflow: hidden;
        min-height: 130px;
        transition: transform 0.2s, box-shadow 0.2s;
    ">
        <div style="
            position: absolute; right: 18px; top: 18px;
            width: 44px; height: 44px;
            background: {accent}18;
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-size: 22px;
        ">{icon}</div>
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;
                    letter-spacing:1.2px;color:#9aa5b4;margin-bottom:8px;">{title}</div>
        <div style="font-size:30px;font-weight:800;color:#0a1628;line-height:1.15;">{value}</div>
        <div style="font-size:12px;color:{accent};font-weight:600;margin-top:5px;">{subtitle}</div>
        <div style="
            position: absolute; right: -8px; bottom: -12px;
            font-size: 72px; opacity: 0.05; line-height: 1;
        ">{icon}</div>
    </div>"""


def tag_card(
    name: str, value, unit: str, lo: float, hi: float,
    timestamp: str, accent: str, status: str,
) -> str:
    """Tag live-value card with progress bar and status badge."""
    if isinstance(value, (int, float)):
        display = f"{float(value):.4g}"
        pct = max(0.0, min(1.0, (float(value) - lo) / (hi - lo) if hi != lo else 0.5))
        pct_label = f"{pct*100:.0f}% of range"
        bar_fill = f"{pct*100:.1f}%"
    else:
        display = str(value)
        pct = 0.5
        pct_label = ""
        bar_fill = "50%"

    status_bg = {"NORMAL": "#00b09b", "WARNING": "#f7971e", "HIGH": "#e74c3c", "LOW": "#e74c3c"}.get(status, "#4a90e2")

    return f"""
    <div style="
        background: white;
        border-radius: 16px;
        padding: 20px 22px 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.07);
        border-left: 4px solid {accent};
        height: 100%;
        min-height: 175px;
    ">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px;">
            <div style="font-size:12px;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.8px;color:#9aa5b4;">{name}</div>
            <div style="
                background:{status_bg};color:white;
                font-size:9px;font-weight:800;letter-spacing:0.8px;
                padding:3px 9px;border-radius:20px;text-transform:uppercase;
            ">{status}</div>
        </div>
        <div style="margin:10px 0 4px;">
            <span style="font-size:38px;font-weight:800;color:#0a1628;line-height:1;">{display}</span>
            <span style="font-size:15px;font-weight:500;color:#9aa5b4;margin-left:5px;">{unit}</span>
        </div>
        <div style="
            background:#e8ecf0;border-radius:6px;height:7px;width:100%;margin:12px 0 6px;
        ">
            <div style="
                background:linear-gradient(90deg,{accent}88,{accent});
                border-radius:6px;height:7px;width:{bar_fill};
                transition: width 0.5s ease;
            "></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:10px;color:#bbb;">
            <span>{lo} {unit}</span>
            <span style="color:{accent};font-weight:600;">{pct_label}</span>
            <span>{hi} {unit}</span>
        </div>
        <div style="font-size:10px;color:#ccc;margin-top:8px;">🕐 {timestamp}</div>
    </div>"""


def section_header(title: str, subtitle: str = "") -> str:
    """Bold section divider with optional subtitle."""
    sub_html = f'<div style="font-size:13px;color:#9aa5b4;margin-top:2px;">{subtitle}</div>' if subtitle else ""
    return f"""
    <div style="margin:24px 0 12px;">
        <div style="font-size:17px;font-weight:700;color:#0a1628;">{title}</div>
        {sub_html}
    </div>"""


def status_banner(opcua_ok: bool, mongo_ok: bool) -> str:
    """Top-of-page connection status strip."""
    def dot(ok):
        color = "#00b09b" if ok else "#e74c3c"
        label = "Connected" if ok else "Disconnected"
        pulse = "animation:pulse 1.5s infinite;" if ok else ""
        return (
            f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'background:white;border-radius:20px;padding:5px 12px;'
            f'font-size:12px;font-weight:600;color:#444;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.06);">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{color};{pulse}display:inline-block;"></span>'
            f'{label}</span>'
        )

    return f"""
    <style>
    @keyframes pulse {{
        0%,100% {{ opacity:1; box-shadow:0 0 0 0 rgba(0,176,155,0.4); }}
        50% {{ opacity:.85; box-shadow:0 0 0 5px rgba(0,176,155,0); }}
    }}
    </style>
    <div style="
        display:flex;gap:10px;align-items:center;
        background:linear-gradient(135deg,#0a1628,#1a2744);
        border-radius:14px;padding:14px 20px;margin-bottom:20px;
        box-shadow:0 4px 20px rgba(10,22,40,0.15);
    ">
        <div style="flex:1;">
            <div style="font-size:18px;font-weight:800;color:white;">Industrial IoT Platform</div>
            <div style="font-size:12px;color:rgba(255,255,255,0.55);margin-top:2px;">Real-time monitoring dashboard</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
            <span style="font-size:11px;color:rgba(255,255,255,0.5);">OPC UA</span>{dot(opcua_ok)}
            <span style="font-size:11px;color:rgba(255,255,255,0.5);margin-left:6px;">MongoDB</span>{dot(mongo_ok)}
        </div>
    </div>"""
