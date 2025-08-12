import streamlit as st

from app.state import TypedSessionState

from ._generate import render_generate
from ._info import render_metadata_input
from ._publish import render_publish
from ._upload import render_upload


def render_ingest():
    """Render the publishing tab."""

    st.markdown("Designed for ***library data stewards*** to publish new datasets to the UW-Madison Data Repository.")

    state = TypedSessionState.get_or_create()
    render_metadata_input(state)
    render_upload(state)
    render_generate(state)
    render_publish(state)
