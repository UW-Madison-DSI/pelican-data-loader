import streamlit as st
from state import TypedSessionState
from tabs.dataset_info import render_dataset_info_tab
from tabs.discover import render_discover_tab
from tabs.generate import render_generate_tab
from tabs.publish import render_publish_tab
from tabs.upload import render_upload_tab

st.set_page_config(page_title="Croissant Dataset Uploader", page_icon="🥐", layout="wide")

st.title("🥐 Croissant Dataset Uploader (MVP)")
st.markdown("Upload your datasets to UW–Madison's research dataset repository.")

# Initialize SessionState
app_state = TypedSessionState.get_or_create()

# Main content area
tab_labels = [
    "📁 File Upload",
    "📋 Dataset Info",
    "📄 Generate Metadata",
    "📢 Publish to UW-Madison Data Repo",
    "👁️ Discover Datasets",
]

# Create the tabs in the UI
upload_tab, dataset_info_tab, generate_tab, publish_tab, discover_tab = st.tabs(tab_labels)

with upload_tab:
    render_upload_tab()

with dataset_info_tab:
    render_dataset_info_tab()

with generate_tab:
    render_generate_tab()

with publish_tab:
    render_publish_tab()

with discover_tab:
    render_discover_tab()


# Footer
st.markdown("---")
st.markdown("💡 **Note:** This prototype uses the `mlcroissant` package to generate Croissant v1.0 metadata.")
