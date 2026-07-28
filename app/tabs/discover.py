from pathlib import Path
from time import sleep

import streamlit as st
from sqlmodel import select

from app.db_connection import get_cached_db_session
from app.state import TypedSessionState
from pelican_data_loader.data import delete_from_s3, s3_object_name_from_url
from pelican_data_loader.db import Dataset

# Add parent directory to path to import from main

USAGE_CODE_TEMPLATE = """
# Consume with Hugging Face's `datasets` package
from datasets import load_dataset

dataset = load_dataset("{file_type}", data_files="{pelican_uri}")

# Convert to format of your choice, see https://huggingface.co/docs/datasets/v4.0.0/en/use_with_pytorch
torch_dataset = dataset.with_format("torch")
torch_dataset
"""


USAGE_CODE_TEMPLATE_V2 = """
from pelican_data_loader import load_uw_data
dataset = load_uw_data({key})

# Display the first record
list(dataset["train"].take(1))
"""

README = """
Designed for ***end-users*** to explore datasets in the UW–Madison Data Repository. Users can browse interactively and generate code snippets to integrate the datasets into their applications.

Future features might include:
- Semantic search with BEAR
- Dataset filtering
- User-friendly data exploration tools

Other design references:
- [Hugging Face Datasets Hub](https://huggingface.co/datasets)
- [Kaggle datasets](https://www.kaggle.com/datasets)
- [Google datasets](https://datasetsearch.research.google.com/)
- [Data.gov](https://data.gov/)

"""


def render_discover():
    """Render the view published datasets tab with a list of all datasets in the metadata database."""
    st.write(README)

    # Get SessionState
    typed_state = TypedSessionState.get_or_create()

    try:
        # Get cached database session
        session = get_cached_db_session(typed_state.system_config.metadata_db_engine_url)

        # Query all datasets from the database
        statement = select(Dataset)
        datasets = session.exec(statement).all()

        if not datasets:
            st.info("No published datasets found in the database.")
            return

        st.markdown(f"**Total datasets:** {len(datasets)}")

        # Display datasets in a expandable format
        for dataset in datasets:
            render_dataset(dataset, typed_state)

    except Exception as e:
        st.error(f"Error accessing database: {str(e)}")
        st.info("Make sure the database has been initialized and contains data.")


def render_dataset(dataset: Dataset, typed_state: TypedSessionState):
    """Renders a single dataset in an expandable format."""
    with st.expander(f"{dataset.name} (v{dataset.version})", icon="📄"):
        st.subheader("Dataset information")

        metadata_rows = {
            "Name": dataset.name,
            "Authors/Creators": ", ".join(f"{creator.first_name} {creator.last_name} ({creator.email})" for creator in dataset.creators)
            if dataset.creators
            else "Not provided",
            "Description": dataset.description or "Not provided",
            "Version": dataset.version,
            "SHA256": f"`{dataset.primary_source_sha256[:16]}...`" if dataset.primary_source_sha256 else "Not provided",
            "Published Date": dataset.published_date,
            "License": dataset.license,
            "Keywords": dataset.keywords or "Not provided",
            "Primary Source URL": dataset.primary_source_url or "Not provided",
            "Croissant Metadata URL": dataset.croissant_jsonld_url or "Not provided",
            "Pelican URI": dataset.pelican_uri or "Not provided",
            "Pelican HTTP URL": dataset.pelican_http_url or "Not provided",
        }
        st.table(metadata_rows)

        # Croissant JSON-LD metadata
        if dataset.pelican_uri:
            st.subheader("Consuming Dataset")

            st.markdown("Use Huggingface's dataset with pelican fs")

            file_type = Path(dataset.pelican_uri).suffix.replace(".", "")
            st.code(
                USAGE_CODE_TEMPLATE.format(pelican_uri=dataset.pelican_uri, file_type=file_type),
            )
            st.markdown("---")
            st.markdown("This is a simpler mockup that will need data uploader identity and NetID integration later:")
            st.code(
                USAGE_CODE_TEMPLATE_V2.format(key='"netid/dataset_key"'),
            )

        render_delete(dataset, typed_state)


def render_delete(dataset: Dataset, typed_state: TypedSessionState):
    """Render the delete control for a single dataset, behind a confirmation step."""
    st.markdown("---")
    st.subheader("⚠️ Danger zone")

    if typed_state.pending_delete_dataset_id != dataset.id:
        if st.button("🗑️ Delete dataset", key=f"delete_{dataset.id}"):
            typed_state.pending_delete_dataset_id = dataset.id
            st.rerun()
        return

    st.warning(
        f"Permanently delete **{dataset.name}** (v{dataset.version})? This removes its record from the "
        "repository database and deletes its data and metadata files from S3."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm delete", key=f"confirm_delete_{dataset.id}", type="primary"):
            handle_delete(dataset, typed_state)
    with col2:
        if st.button("Cancel", key=f"cancel_delete_{dataset.id}"):
            typed_state.pending_delete_dataset_id = None
            st.rerun()


def handle_delete(dataset: Dataset, typed_state: TypedSessionState):
    """Delete a dataset's S3 objects, then its database record.

    S3 objects go first: removing them is idempotent, so if the database delete
    fails the whole operation can be retried without leaving anything behind.
    """
    name = dataset.name

    with st.spinner(f"Deleting {name}..."):
        for label, url in (("data file", dataset.primary_source_url), ("metadata file", dataset.croissant_jsonld_url or "")):
            object_name = s3_object_name_from_url(url)
            if object_name is None:
                st.warning(f"Skipped the {label}: {url or 'no URL recorded'} is not in the configured S3 bucket.")
                continue
            try:
                delete_from_s3(object_name, bucket_name=typed_state.system_config.s3_bucket_name)
            except Exception as e:
                st.warning(f"Could not delete the {label} ({object_name}) from S3: {str(e)}")

        # The listing was queried from this cached session, so delete through it to
        # avoid leaving a stale copy of the row behind.
        session = get_cached_db_session(typed_state.system_config.metadata_db_engine_url)
        try:
            session.delete(dataset)
            session.commit()
        except Exception as e:
            # The session is shared across the app, so an open failed transaction
            # would break every later query.
            session.rollback()
            st.error(f"Error deleting dataset record: {str(e)}")
            return

    typed_state.pending_delete_dataset_id = None
    st.success(f"🗑️ Deleted {name}.")
    sleep(2)
    st.rerun()
