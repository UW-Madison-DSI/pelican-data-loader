import streamlit as st

from app.state import TypedSessionState
from app.tabs import render_discover, render_ingest

# Setup
st.set_page_config(page_title="UW–Madison Dataset Repository", page_icon="⚙️", layout="wide")
typed_state = TypedSessionState.get_or_create()
if not typed_state.system_config:
    st.error("System configuration not found, check .env file")

# Main content
st.title("UW–Madison Dataset Repository (MVP)")

# Tabs
tabs_content = {
    "👁️ Discover Datasets": render_discover,
    "📢 Publish to UW-Madison Data Repository": render_ingest,
}
tabs_layout = st.tabs(list(tabs_content.keys()))
for tab, render_function in zip(tabs_layout, list(tabs_content.values())):
    with tab:
        render_function()

# Footer
st.markdown("---")
st.markdown("© 2025 Data Science Institute, University of Wisconsin–Madison")
