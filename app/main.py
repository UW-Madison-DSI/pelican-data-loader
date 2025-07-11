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
st.markdown("""
This prototype demonstrates a potential design for the UW–Madison dataset repository.
            
- **Publishing dataset**: Use tabs 1-4 to upload files, provide dataset information, generate metadata, and publish to the repository.
- **Exploring datasets**: Use the Discover Datasets tab to explore available datasets.
""")

tab_labels = [
    "📁 File Upload",
    "📋 Dataset Info",
    "📄 Generate Metadata",
    "📢 Publish to UW-Madison Data Repo",
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
