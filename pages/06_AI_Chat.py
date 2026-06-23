"""
AI Chat -- ask plain-English questions about your industrial data.
Routes to OPC UA (live) or MongoDB (historical) for context, then GPT-4 answers.
"""

import streamlit as st

from src.components.styles import GLOBAL_CSS
from src.core.config_manager import load_config
from src.core.opcua_client import OPCUAClient
from src.core.mongodb_handler import MongoDBHandler

st.set_page_config(page_title="AI Chat | IIoT Platform", page_icon="🤖", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

if "config" not in st.session_state:
    st.session_state.config = load_config()
if "opcua" not in st.session_state:
    st.session_state.opcua = OPCUAClient()
if "mongo" not in st.session_state:
    st.session_state.mongo = MongoDBHandler()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_meta" not in st.session_state:
    st.session_state.chat_meta = []
if "agent" not in st.session_state:
    st.session_state.agent = None

cfg = st.session_state.config
tags = cfg.get("tags", [])
api_key = cfg.get("openai", {}).get("api_key", "")

with st.sidebar:
    st.markdown("## 🏭 IIoT Platform")
    st.markdown("**Model**")
    model = st.selectbox("GPT Model", ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-4"],
                         index=0, label_visibility="collapsed")
    st.markdown("**Routing**")
    st.caption("🟢 **Live** -- reads current OPC UA tag values")
    st.caption("🔵 **Historical** -- queries last 24h from MongoDB")
    st.caption("⚪ **General** -- no data lookup")
    if st.button("Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.chat_meta = []
        st.session_state.agent = None
        st.rerun()

st.title("🤖 AI Chat")

if not api_key:
    st.error("No OpenAI API key configured. Go to **Settings > AI Configuration** to add your key.")
    st.stop()


def _get_agent(model_name: str):
    from src.agents.industrial_agent import IndustrialAgent
    return IndustrialAgent(api_key=api_key, mongo_handler=st.session_state.mongo,
                           opcua_client=st.session_state.opcua, tags=tags, model=model_name)


if st.session_state.agent is None:
    st.session_state.agent = _get_agent(model)

# Example prompts
if not st.session_state.chat_history:
    st.markdown("#### Example questions")
    examples = [
        "What are the current values of all sensors?",
        "Has the temperature been trending up or down in the last 24 hours?",
        "Were there any anomalies detected recently? What could cause them?",
        "Compare current flow rate to its historical average.",
        "What does a high Z-score mean for my temperature sensor?",
        "Give me a health summary of the system right now.",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(ex, use_container_width=True, key=f"ex_{i}"):
            st.session_state._pending_question = ex
            st.rerun()

# Render existing messages
for i, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and i // 2 < len(st.session_state.chat_meta):
            meta = st.session_state.chat_meta[i // 2]
            qtype = meta.get("query_type", "general")
            badge = {"live": "🟢 Live data", "historical": "🔵 Historical data",
                     "general": "⚪ General"}.get(qtype, "⚪")
            st.caption(f"Route: {badge}")
            if meta.get("context"):
                with st.expander("View data context used"):
                    st.code(meta["context"], language="text")

# Chat input
pending = st.session_state.pop("_pending_question", None)
user_input = st.chat_input("Ask anything about your industrial process...") or pending

if user_input:
    st.session_state.agent = _get_agent(model)
    with st.chat_message("user"):
        st.markdown(user_input)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer, query_type, context = st.session_state.agent.chat(
                    history=st.session_state.chat_history, question=user_input)
            except Exception as exc:
                answer = f"Error: {exc}\n\nCheck your OpenAI API key in Settings."
                query_type = "error"
                context = ""
        st.markdown(answer)
        badge = {"live": "🟢 Live data", "historical": "🔵 Historical data",
                 "general": "⚪ General"}.get(query_type, "⚠️ Error")
        st.caption(f"Route: {badge}")
        if context:
            with st.expander("View data context used"):
                st.code(context, language="text")

    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    st.session_state.chat_meta.append({"query_type": query_type, "context": context})
