import streamlit as st
from tabs import (
    render_discover,
    render_generate,
    render_info,
    render_publish,
    render_upload,
)

from app.state import TypedSessionState

typed_state = TypedSessionState.get_or_create()
st.set_page_config(page_title="UW–Madison Dataset Repository", page_icon="🥐", layout="wide")

st.title("🥐 UW–Madison Dataset Repository (MVP)")
with st.expander("About this prototype", expanded=False):
    st.markdown("""
    This prototype demonstrates a potential design for the UW–Madison dataset repository.

    - **Publishing dataset**: Use tabs 1–4 to `Upload File`, `Input dataset info`, `Generate metadata`, and `Publish to UW-Madison Data Repository`. While this could be a single step in production, we've split it into multiple tabs to show the full workflow.
    - **Exploring datasets**: Use the `Discover Datasets` tab to explore available datasets.
                
    """)
    st.warning(
        "Note. Currently, only CSV is supported in this MVP. Pelican integration with CHTC is still pending.", icon="⚠️"
    )

tab_labels = [
    "📁 Upload File",
    "📋 Input Dataset Info",
    "📄 Generate Metadata",
    "📢 Publish to UW-Madison Data Repository",
    "👁️ Discover Datasets",
]
render_functions = [
    render_upload,
    render_info,
    render_generate,
    render_publish,
    render_discover,
]

tabs = st.tabs(tab_labels)
for tab, render_function in zip(tabs, render_functions):
    with tab:
        render_function()

st.markdown("---")
st.markdown("© 2025 Data Science Institute, University of Wisconsin–Madison")
