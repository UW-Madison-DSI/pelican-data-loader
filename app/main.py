import streamlit as st
from tabs.dataset_info import render_dataset_info_tab
from tabs.generate import render_generate_tab
from tabs.upload import render_upload_tab

from pelican_data_loader.config import SystemConfig

st.set_page_config(page_title="Croissant Metadata Generator", page_icon="🥐", layout="wide")

st.title("🥐 Croissant Metadata Generator")
st.markdown("Generate Croissant-compliant metadata for your datasets interactively")
st.session_state.setdefault("system_config", SystemConfig())  # type: ignore

# Main content area
tab_labels = ["📁 File Upload", "📋 Dataset Info", "📄 Generate Metadata"]

# Create the tabs in the UI
upload_tab, dataset_info_tab, generate_tab = st.tabs(tab_labels)

with upload_tab:
    render_upload_tab()

with dataset_info_tab:
    render_dataset_info_tab()

with generate_tab:
    render_generate_tab()

# Footer
st.markdown("---")
st.markdown("💡 **Note:** This prototype uses the `mlcroissant` package to generate Croissant v1.0 metadata.")
