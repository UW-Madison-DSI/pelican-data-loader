from pathlib import Path

import streamlit as st
from sqlmodel import Session, create_engine, select
from state import TypedSessionState

from pelican_data_loader.db import Dataset

METADATA_DB_PATH = Path("data/datasets.db")


def render_publish_tab():
    """
    Render the Publish tab in the Streamlit app.
    This tab allows users to publish their dataset to the UW-Madison Data Repository.
    """
    st.header("📢 Publish to UW-Madison Data Repo")
    st.markdown("This tab allows you to publish your dataset to the UW-Madison Data Repository.")

    # Get SessionState
    typed_state = TypedSessionState.get_or_create()

    # Check if generated metadata exists
    if typed_state.generated_metadata is None:
        st.warning("Please generate metadata first in the Generate tab.")
        return

    metadata_db = create_engine(f"sqlite:///{METADATA_DB_PATH}")
    dataset = Dataset.from_jsonld(typed_state.generated_metadata)

    # Inject s3_metadata_url in DB record if available
    if typed_state.dataset_info.s3_metadata_url:
        dataset.croissant_jsonld_url = typed_state.dataset_info.s3_metadata_url

    st.subheader("Generated Metadata Summary")
    st.json(dataset.model_dump(exclude={"croissant_jsonld"}))
    with st.expander("View Raw Croissant JSON-LD Metadata"):
        st.json(dataset.croissant_jsonld)

    st.subheader("Publishing Options (mock, not functional)")

    # Checkboxes for publishing preferences
    col1, col2 = st.columns(2)
    with col1:
        st.checkbox("Make dataset publicly accessible", value=True)
        st.checkbox("Notify creators", value=True)

    with col2:
        st.checkbox("Assign DOI", value=True)
        st.checkbox("Include data provenance", value=True)

    if st.button("🚀 Publish Dataset", type="primary", use_container_width=True):
        with st.spinner("Publishing dataset to UW-Madison Data Repository..."):
            with Session(metadata_db) as session:
                # Check if dataset already exists
                existing_dataset = session.exec(select(Dataset).where(Dataset.id == dataset.id)).first()

                if existing_dataset:
                    st.warning("Dataset with this ID already exists in the database.")
                else:
                    session.add(dataset)
                    session.commit()
            st.success("✅ Dataset published successfully!")
