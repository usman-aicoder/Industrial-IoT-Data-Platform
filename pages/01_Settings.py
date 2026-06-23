"""
Settings -- configure OPC UA, MongoDB, OpenAI key, tags, and monitoring thresholds.
All values are saved to config/settings.json (gitignored).
"""

import streamlit as st
import pandas as pd

from src.components.styles import GLOBAL_CSS
from src.core.config_manager import load_config, save_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler

st.set_page_config(page_title="Settings | IIoT Platform", page_icon="⚙️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------
# Session state bootstrap
# ------------------------------------------------------------------
if "config" not in st.session_state:
    st.session_state.config = load_config()
if "opcua" not in st.session_state:
    st.session_state.opcua = OPCUAClient()
elif not isinstance(st.session_state.opcua, OPCUAClient) or not hasattr(st.session_state.opcua, "browse_node"):
    st.session_state.opcua = OPCUAClient()
if "mongo" not in st.session_state:
    st.session_state.mongo = MongoDBHandler()
# Tag browser tree state
if "bx_cache" not in st.session_state:
    st.session_state.bx_cache = {}      # node_id (or "root") → list of child dicts
if "bx_expanded" not in st.session_state:
    st.session_state.bx_expanded = set()  # set of expanded node IDs
if "bx_adding" not in st.session_state:
    st.session_state.bx_adding = None   # node dict currently being configured

cfg = st.session_state.config

with st.sidebar:
    st.markdown("## 🏭 IIoT Platform")

st.title("⚙️ Settings")
st.caption("Changes are saved to `config/settings.json` (gitignored) and never committed to version control.")

tab_opcua, tab_mongo, tab_tags, tab_browser, tab_monitoring = st.tabs(
    ["🔌 OPC UA", "🗄️ MongoDB", "📋 Tag Manager", "🌐 Tag Browser", "⚙️ Monitoring"]
)

# =====================================================================
# OPC UA
# =====================================================================
with tab_opcua:
    st.subheader("OPC UA Server")
    opcua_cfg = cfg.get("opcua", {})

    endpoint_url = st.text_input(
        "Endpoint URL",
        value=opcua_cfg.get("url", "opc.tcp://localhost:49320"),
        placeholder="opc.tcp://host:port/path",
        help="Full OPC UA endpoint URL, e.g. opc.tcp://localhost:49320/",
    )

    use_auth = st.toggle("Use username/password", value=opcua_cfg.get("use_auth", False))
    opcua_user = opcua_pwd = ""
    if use_auth:
        c1, c2 = st.columns(2)
        opcua_user = c1.text_input("Username", value=opcua_cfg.get("username", ""))
        opcua_pwd = c2.text_input("Password", value=opcua_cfg.get("password", ""), type="password")

    col_conn, col_disconn, col_save = st.columns([2, 2, 2])

    with col_conn:
        if st.button("🔌 Connect", use_container_width=True, type="primary"):
            with st.spinner(f"Connecting to {endpoint_url}..."):
                client = OPCUAClient()
                ok = client.connect(
                    server_url=endpoint_url,
                    username=opcua_user if use_auth else None,
                    password=opcua_pwd if use_auth else None,
                )
            if ok:
                st.session_state.opcua = client
                # Reset browser when reconnecting
                st.session_state.browser_path = []
                st.session_state.browser_nodes = []
                st.session_state.browser_adding = None
                cfg["opcua"] = {
                    "url": endpoint_url,
                    "use_auth": use_auth,
                    "username": opcua_user if use_auth else "",
                    "password": opcua_pwd if use_auth else "",
                }
                save_config(cfg)
                st.session_state.config = cfg
                st.success(f"Connected to {endpoint_url}")
                st.rerun()
            else:
                st.error(f"Connection failed: {client.last_error}")

    with col_disconn:
        if st.session_state.opcua.connected:
            if st.button("⏏ Disconnect", use_container_width=True):
                st.session_state.opcua.disconnect()
                st.session_state.browser_path = []
                st.session_state.browser_nodes = []
                st.rerun()

    with col_save:
        if st.button("💾 Save without connecting", use_container_width=True):
            cfg["opcua"] = {
                "url": endpoint_url,
                "use_auth": use_auth,
                "username": opcua_user if use_auth else "",
                "password": opcua_pwd if use_auth else "",
            }
            save_config(cfg)
            st.session_state.config = cfg
            st.success("Settings saved.")

    if st.session_state.opcua.connected:
        st.success(f"Connected to: `{st.session_state.opcua.server_url}`")
    else:
        st.warning("Not connected.")

# =====================================================================
# MongoDB
# =====================================================================
with tab_mongo:
    st.subheader("MongoDB Atlas / Local")
    mongo_cfg = cfg.get("mongodb", {})

    mongo_uri = st.text_input("MongoDB URI",
                              value=mongo_cfg.get("uri", "mongodb://localhost:27017"),
                              type="password",
                              placeholder="mongodb+srv://user:pass@cluster.mongodb.net/")
    c1, c2 = st.columns(2)
    mongo_db = c1.text_input("Database name", value=mongo_cfg.get("database", "iiot"))
    mongo_col = c2.text_input("Collection name", value=mongo_cfg.get("collection", "tag_data"))

    col_save, col_test = st.columns([1, 1])
    with col_save:
        if st.button("Save MongoDB Settings", type="primary", use_container_width=True):
            # Strip accidental "uri:" prefix that Atlas copy sometimes includes
            clean_uri = mongo_uri.strip()
            if clean_uri.startswith("uri:"):
                clean_uri = clean_uri[4:].strip()
            cfg["mongodb"] = {"uri": clean_uri, "database": mongo_db, "collection": mongo_col}
            save_config(cfg)
            st.session_state.config = cfg
            st.success("MongoDB settings saved.")

    with col_test:
        if st.button("Test MongoDB Connection", use_container_width=True):
            handler = MongoDBHandler()
            clean_uri = mongo_uri.strip()
            if clean_uri.startswith("uri:"):
                clean_uri = clean_uri[4:].strip()
            ok = handler.connect(uri=clean_uri, database=mongo_db, collection=mongo_col)
            if ok:
                stats = handler.get_statistics()
                st.success("Connected!")
                if stats:
                    st.json({"total_records": stats["total_records"],
                             "unique_tags": stats["unique_tags"]})
                st.session_state.mongo = handler
            else:
                st.error("MongoDB connection failed.")

# =====================================================================
# Tag Manager (manual edit table)
# =====================================================================
with tab_tags:
    st.subheader("Tag Manager")
    st.caption("Edit tags directly. Use the **Tag Browser** tab to add tags by browsing the OPC UA server.")

    existing_tags = cfg.get("tags", [])

    # ── Live values strip ──────────────────────────────────────────
    if existing_tags and st.session_state.opcua.connected:
        lv_col, lv_btn = st.columns([6, 1])
        lv_col.markdown("**Live Values** (from OPC UA)")
        refresh_live = lv_btn.button("🔄 Refresh", use_container_width=True, key="tm_refresh")

        if refresh_live or "tm_live_values" not in st.session_state:
            paths = [t["path"] for t in existing_tags]
            with st.spinner("Reading tags..."):
                raw_vals = st.session_state.opcua.read_tags(paths)
            st.session_state.tm_live_values = raw_vals

        live = st.session_state.get("tm_live_values", {})
        live_rows = []
        for tag in existing_tags:
            val = live.get(tag["path"])
            unit = tag.get("unit", "")
            lo = tag.get("min_range")
            hi = tag.get("max_range")

            if val is None:
                status = "❌ No data"
                val_str = "—"
                pct = 0.0
            elif isinstance(val, bool):
                status = "🟢 ON" if val else "⚫ OFF"
                val_str = str(val)
                pct = 1.0 if val else 0.0
            elif isinstance(val, (int, float)):
                val_str = f"{float(val):.4g} {unit}".strip()
                if lo is not None and hi is not None and hi != lo:
                    pct = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
                    if pct >= 0.9:   status = "🔴 HIGH"
                    elif pct >= 0.7: status = "🟡 WARNING"
                    elif pct <= 0.05: status = "🔴 LOW"
                    else:             status = "🟢 NORMAL"
                else:
                    pct = 0.5
                    status = "🟢 OK"
            else:
                val_str = str(val)
                status = "🟢 OK"
                pct = 0.5

            bar = f'<div style="background:#e8ecf0;border-radius:4px;height:6px;width:100%">' \
                  f'<div style="background:#4a90e2;border-radius:4px;height:6px;width:{pct*100:.1f}%"></div></div>'

            live_rows.append({
                "Tag": tag.get("name", tag["path"]),
                "Node Path": tag["path"],
                "Value": val_str,
                "Range": f"{lo} – {hi} {unit}".strip() if lo is not None and hi is not None else "—",
                "Status": status,
            })

        st.dataframe(
            pd.DataFrame(live_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tag":       st.column_config.TextColumn(width="medium"),
                "Node Path": st.column_config.TextColumn(width="large"),
                "Value":     st.column_config.TextColumn(width="small"),
                "Range":     st.column_config.TextColumn(width="medium"),
                "Status":    st.column_config.TextColumn(width="small"),
            },
        )
    elif existing_tags and not st.session_state.opcua.connected:
        st.info("Connect to OPC UA (OPC UA tab) to see live values.")
    DEFAULT_COLS = {"path": "", "name": "", "unit": "", "min_range": None, "max_range": None, "description": ""}

    def _normalise(t: dict) -> dict:
        return {k: t.get(k, v) for k, v in DEFAULT_COLS.items()}

    tag_df = pd.DataFrame([_normalise(t) for t in existing_tags] if existing_tags else [DEFAULT_COLS])

    edited_df = st.data_editor(
        tag_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "path": st.column_config.TextColumn("OPC UA Node Path", help="e.g. ns=2;s=Channel1.Tag1"),
            "name": st.column_config.TextColumn("Display Name"),
            "unit": st.column_config.TextColumn("Unit (optional)", max_chars=20),
            "min_range": st.column_config.NumberColumn("Min (optional)", format="%.2f"),
            "max_range": st.column_config.NumberColumn("Max (optional)", format="%.2f"),
            "description": st.column_config.TextColumn("Description"),
        },
    )

    if st.button("Save Tags", type="primary"):
        new_tags = []
        for _, row in edited_df.iterrows():
            if str(row.get("path", "")).strip():
                tag = {
                    "path": str(row["path"]).strip(),
                    "name": str(row["name"]).strip() or str(row["path"]).strip(),
                    "unit": str(row.get("unit", "")).strip(),
                    "description": str(row.get("description", "")).strip(),
                }
                # Only add min/max if user actually filled them in
                if pd.notna(row.get("min_range")) and row["min_range"] is not None:
                    tag["min_range"] = float(row["min_range"])
                if pd.notna(row.get("max_range")) and row["max_range"] is not None:
                    tag["max_range"] = float(row["max_range"])
                new_tags.append(tag)
        cfg["tags"] = new_tags
        save_config(cfg)
        st.session_state.config = cfg
        st.success(f"Saved {len(new_tags)} tag(s).")

    if existing_tags and st.session_state.opcua.connected:
        if st.button("Verify all tags against OPC UA server"):
            results = []
            for tag in existing_tags:
                val = st.session_state.opcua.read_tag(tag["path"])
                results.append({"Tag": tag.get("name", tag["path"]),
                                 "Path": tag["path"],
                                 "Status": "OK" if val is not None else "Not found",
                                 "Current Value": str(val) if val is not None else "—"})
            st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

# =====================================================================
# Tag Browser
# =====================================================================
with tab_browser:
    st.subheader("🌐 Tag Browser")

    if not st.session_state.opcua.connected:
        st.warning("Connect to the OPC UA server first (OPC UA tab) to browse its namespace.")
        st.stop()

    opcua_client = st.session_state.opcua
    existing_paths = {t["path"] for t in cfg.get("tags", [])}

    # ── Toolbar ──────────────────────────────────────────────────────
    tb1, tb2, tb3 = st.columns([2, 2, 6])
    with tb1:
        if st.button("🏠 Load / Refresh Root", use_container_width=True, type="primary"):
            with st.spinner("Browsing server root..."):
                root_nodes = opcua_client.browse_node(None)
            st.session_state.bx_cache = {"root": root_nodes}
            st.session_state.bx_expanded = set()
            st.session_state.bx_adding = None
            st.rerun()
    with tb2:
        if st.button("🔄 Clear Tree", use_container_width=True):
            st.session_state.bx_cache = {}
            st.session_state.bx_expanded = set()
            st.session_state.bx_adding = None
            st.rerun()
    with tb3:
        st.caption(f"Tags added so far: **{len(existing_paths)}**  |  "
                   "Expand folders by clicking ▶  —  click **Add** on any variable to add it as a tag.")

    # ── Add-tag form (shown at top when a variable is selected) ──────
    if st.session_state.bx_adding:
        node = st.session_state.bx_adding
        with st.container(border=True):
            st.markdown(f"#### ➕ Configure tag: `{node['name']}`")
            st.caption(f"Node ID: `{node['node_id']}`  |  "
                       f"Current value: `{node['value']}`")

            fc1, fc2 = st.columns(2)
            tag_name = fc1.text_input("Display Name", value=node["name"])
            tag_unit = fc2.text_input("Unit (optional)", placeholder="e.g. °C  bar  rpm  %")

            mc1, mc2, mc3 = st.columns(3)
            tag_min_str = mc1.text_input("Min range (optional)", placeholder="e.g. 0")
            tag_max_str = mc2.text_input("Max range (optional)", placeholder="e.g. 100")
            tag_desc   = mc3.text_input("Description (optional)", placeholder="Short note")

            # Validate min/max silently — no st.error that would shift layout
            tag_min, tag_max, range_ok = None, None, True
            if tag_min_str.strip():
                try:    tag_min = float(tag_min_str)
                except: range_ok = False
            if tag_max_str.strip():
                try:    tag_max = float(tag_max_str)
                except: range_ok = False

            if not range_ok:
                st.warning("Min/Max must be numbers. Leave blank to skip range.")

            if tag_min is not None and tag_max is not None:
                st.info(f"Range: {tag_min} – {tag_max} {tag_unit}  (used for dashboard progress bar)")

            ac1, ac2 = st.columns(2)
            if ac1.button("✅ Confirm Add Tag", type="primary",
                          use_container_width=True, disabled=not range_ok):
                new_tag = {
                    "path": node["node_id"],          # use directly — no widget involved
                    "name": tag_name.strip() or node["name"],
                    "unit": tag_unit.strip(),
                    "description": tag_desc.strip(),
                }
                if tag_min is not None:
                    new_tag["min_range"] = tag_min
                if tag_max is not None:
                    new_tag["max_range"] = tag_max

                tags = [t for t in cfg.get("tags", []) if t["path"] != node["node_id"]]
                tags.append(new_tag)
                cfg["tags"] = tags
                save_config(cfg)
                st.session_state.config = cfg
                existing_paths.add(node["node_id"])   # instant UI update
                st.session_state.bx_adding = None
                st.success(f"Tag **{new_tag['name']}** added!")
                st.rerun()
            if ac2.button("✖ Cancel", use_container_width=True):
                st.session_state.bx_adding = None
                st.rerun()
    # ── Tree renderer ─────────────────────────────────────────────────
    root_nodes = st.session_state.bx_cache.get("root")

    if root_nodes is None:
        st.info("Press **Load / Refresh Root** to browse the OPC UA server.")
    elif not root_nodes:
        st.warning("No nodes found at server root. Check connection.")
    else:
        def render_tree(nodes: list, depth: int = 0):
            pad = depth * 22   # pixels of left-indent per level
            for node in nodes:
                nid = node["node_id"]
                is_var = node["node_class"] == "Variable"
                is_expanded = nid in st.session_state.bx_expanded
                already = nid in existing_paths

                if is_var:
                    c_name, c_val, c_btn = st.columns([6, 2, 1])
                    val = node["value"]
                    val_str = (f"{val:.4g}" if isinstance(val, float)
                               else str(val) if val is not None else "—")
                    c_name.markdown(
                        f'<div style="padding-left:{pad}px;line-height:2">'
                        f'📊 <b>{node["name"]}</b>&nbsp;&nbsp;'
                        f'<span style="color:#9aa5b4;font-size:11px">{nid}</span></div>',
                        unsafe_allow_html=True,
                    )
                    c_val.code(val_str)
                    if already:
                        c_btn.markdown('<div style="text-align:center;font-size:20px;padding-top:4px">✅</div>',
                                       unsafe_allow_html=True)
                    else:
                        if c_btn.button("Add", key=f"bx_{nid}", type="primary",
                                        use_container_width=True):
                            st.session_state.bx_adding = node
                            st.rerun()
                else:
                    c_name, c_btn = st.columns([8, 1])
                    arrow = "🔽" if is_expanded else "▶"
                    icon  = "📂" if is_expanded else "📁"
                    c_name.markdown(
                        f'<div style="padding-left:{pad}px;line-height:2">'
                        f'{icon} <b>{node["name"]}</b>&nbsp;&nbsp;'
                        f'<span style="color:#9aa5b4;font-size:11px">{nid}</span></div>',
                        unsafe_allow_html=True,
                    )
                    if c_btn.button(arrow, key=f"bx_{nid}", use_container_width=True):
                        if is_expanded:
                            st.session_state.bx_expanded.discard(nid)
                        else:
                            st.session_state.bx_expanded.add(nid)
                            if nid not in st.session_state.bx_cache:
                                with st.spinner(f"Loading {node['name']}..."):
                                    st.session_state.bx_cache[nid] = opcua_client.browse_node(nid)
                        st.rerun()

                    if is_expanded and nid in st.session_state.bx_cache:
                        render_tree(st.session_state.bx_cache[nid], depth + 1)

        render_tree(root_nodes)

# =====================================================================
# Monitoring
# =====================================================================
with tab_monitoring:
    st.subheader("Monitoring Settings")
    mon_cfg = cfg.get("monitoring", {})

    c1, c2 = st.columns(2)
    with c1:
        store_on_change = st.toggle(
            "Store only on value change",
            value=bool(mon_cfg.get("store_on_change_only", True)),
            help="Only write to MongoDB when a tag value changes beyond the threshold.",
        )
        change_threshold = st.number_input(
            "Change threshold (%)",
            min_value=0.0, max_value=50.0,
            value=float(mon_cfg.get("change_threshold", 0.01)) * 100,
            step=0.1, format="%.2f",
        )
    with c2:
        max_buffer_points = st.number_input(
            "Max in-memory buffer points per tag",
            min_value=50, max_value=10000,
            value=int(mon_cfg.get("max_buffer_points", 300)),
        )
        default_poll = st.number_input(
            "Default poll interval (s)",
            min_value=1, max_value=300,
            value=int(mon_cfg.get("default_poll_interval", 5)),
        )

    if st.button("Save Monitoring Settings", type="primary"):
        cfg["monitoring"] = {
            "store_on_change_only": store_on_change,
            "change_threshold": change_threshold / 100.0,
            "max_buffer_points": max_buffer_points,
            "default_poll_interval": default_poll,
        }
        save_config(cfg)
        st.session_state.config = cfg
        st.success("Monitoring settings saved.")
