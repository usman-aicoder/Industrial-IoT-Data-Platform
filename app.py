"""
Navigation router — defines sidebar nav labels, order, and visible pages.
"""
import streamlit as st

pg = st.navigation([
    st.Page("home.py",                          title="APP",                icon="🏭", default=True),
    st.Page("pages/01_Settings.py",             title="Settings",           icon="⚙️"),
    st.Page("pages/02_Dashboard.py",            title="Dashboard",          icon="📊"),
    st.Page("pages/03_Realtime_Monitor.py",     title="Realtime Monitor",   icon="📡"),
    st.Page("pages/04_Historical_Analysis.py",  title="Historical Analysis",icon="📈"),
    st.Page("pages/05_Anomaly_Detection.py",    title="Anomaly Detection",  icon="🔍"),
    st.Page("pages/07_Reports.py",              title="Reports",            icon="📄"),
    # AI Chat excluded — uncomment to re-enable:
    # st.Page("pages/06_AI_Chat.py", title="AI Chat", icon="🤖"),
])
pg.run()
