import streamlit as st

from app.state import TypedSessionState

from ._generate import render_generate
from ._info import render_metadata_input
from ._publish import render_publish
from ._upload import render_upload

README = """
Designed for ***library data stewards*** to publish datasets to the UW-Madison Data Repository.

Common dataset types can be ingested through the GUI, while more complex datasets require using the python API to define their structure and upload data files. Future features might include:

- DOI minting via https://datacite.org/
- Backups
- Dataset versioning
- Support for user-submitted datasets + approval process?
"""

def render_ingest():
    """Render the publishing tab."""

    st.markdown(README)

    state = TypedSessionState.get_or_create()
    render_metadata_input(state)
    render_upload(state)
    render_generate(state)
    render_publish(state)
