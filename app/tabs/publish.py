import streamlit as st

from app.db_connection import get_cached_db_session
from app.state import TypedSessionState
from pelican_data_loader.db import Dataset


def render_publish():
    """
    Render the Publish tab in the Streamlit app.
    This tab allows users to publish their dataset to the UW-Madison Data Repository.
    """
    st.header("📢 Publish to UW-Madison Data Repo")
    st.info("Publish your dataset to the UW-Madison Data Repository.", icon="ℹ️")

    # Get SessionState
    typed_state = TypedSessionState.get_or_create()

    # Check if generated metadata exists
    if typed_state.generated_metadata is None:
        st.warning("Please generate metadata first in the Generate tab.")
        return

    # Get cached database session
    session = get_cached_db_session()
    dataset = Dataset.from_jsonld(typed_state.generated_metadata)

    # Append Pelican and S3-related information (since it's not included in the JSON-LD)
    dataset.pelican_uri = typed_state.dataset_info.pelican_uri
    dataset.pelican_http_url = typed_state.dataset_info.pelican_http_url
    dataset.croissant_jsonld_url = typed_state.dataset_info.s3_metadata_url

    st.subheader("Dataset record pending publication")
    st.json(dataset.model_dump(exclude={"id"}))
    with st.expander("View Raw Croissant JSON-LD Metadata"):
        if typed_state.generated_metadata:
            st.json(typed_state.generated_metadata)
        else:
            st.warning("No generated metadata available.")

    st.subheader("Publishing Options (mock, not functional)")
    st.checkbox("Make dataset publicly accessible", value=True)
    st.checkbox("Notify creators", value=True)
    st.checkbox("Assign DOI", value=True)
    st.checkbox("Agree to publishing agreement", value=False)

    if st.button("🚀 Publish Dataset", type="primary", use_container_width=True):
        with st.spinner("Publishing dataset to UW-Madison Data Repository..."):
            session.add(dataset)
            session.commit()
            st.success("✅ Dataset published successfully!")
