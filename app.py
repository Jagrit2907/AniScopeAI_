"""AniScope AI — entry point.  Run with:  streamlit run app.py"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(page_title="AniScope AI", page_icon="🍙", layout="wide", initial_sidebar_state="expanded")

from components import styles, widgets  # noqa: E402
from src import state  # noqa: E402

styles.inject()
state.init()

pages = {
    "Investigate": [
        st.Page("views/command_center.py", title="Command Center", icon=":material/space_dashboard:", default=True),
        st.Page("views/trending_radar.py", title="Trending Radar", icon=":material/trending_up:"),
        st.Page("views/audience_intelligence.py", title="Audience Intelligence", icon=":material/forum:"),
    ],
    "Develop": [
        st.Page("views/creative_lab.py", title="Creative Opportunity Lab", icon=":material/lightbulb:"),
        st.Page("views/business_planner.py", title="Business Opportunity Planner", icon=":material/storefront:"),
        st.Page("views/opportunity_brief.py", title="Opportunity Brief", icon=":material/description:"),
    ],
    "Workspace": [
        st.Page("views/data_methods.py", title="Data & Methods", icon=":material/database:"),
    ],
}
nav = st.navigation(pages)
widgets.sidebar_status()
nav.run()
