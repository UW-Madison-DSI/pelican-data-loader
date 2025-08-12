import streamlit as st

from app.state import TypedSessionState

from ._generate import render_generate
from ._info import render_metadata_input
from ._publish import render_publish
from ._upload import render_upload


def render_ingest():
    """Render the publishing tab."""

    state = TypedSessionState.get_or_create()

    st.markdown("This tab is designed for ***library data stewards*** to publish new datasets to the UW-Madison Data Repository.")

    st.subheader("Step 1: Input Dataset Metadata")
    with st.container(border=True):
        render_metadata_input(state)

    st.subheader("Step 2. Upload Dataset")
    st.info(
        "This step will upload a CSV dataset to [UW-Madison Research Object S3](https://web.s3.wisc.edu/pelican-data-loader).",
        icon="ℹ️",
    )
    with st.container(border=True):
        render_upload(state)

    st.subheader("Step 3. Generate Croissant Metadata")
    st.info(
        "Generate Croissant metadata (JSON-LD format), validate it, and upload it to [UW-Madison Research Object S3](https://web.s3.wisc.edu/pelican-data-loader).",
        icon="ℹ️",
    )
    with st.container(border=True):
        render_generate(state)

    st.header("Step 4. Publish to UW-Madison Data Repo")
    st.info("Publish your dataset to the UW-Madison Data Repository.", icon="ℹ️")
    with st.container(border=True):
        render_publish(state)
