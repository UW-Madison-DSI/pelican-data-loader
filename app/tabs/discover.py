import json

import streamlit as st
from sqlmodel import Session, create_engine, select
from state import TypedSessionState

from pelican_data_loader.db import Dataset

USAGE_CODE_TEMPLATE = """
from mlcroissant import Dataset
import itertools
import pandas as pd
dataset = Dataset(jsonld="{croissant_jsonld_url}")

records = dataset.records("bird_migration_data_record_set")
pd.DataFrame(list(itertools.islice(records, 100))).head(5)
"""


def render_discover_tab():
    """Render the view published datasets tab with a list of all datasets in the metadata database."""
    st.header("Published Datasets")

    # Get SessionState
    typed_state = TypedSessionState.get_or_create()

    if not typed_state.system_config:
        st.error("System configuration not found. Please restart the application.")
        return

    try:
        # Create database engine and session
        engine = create_engine(typed_state.system_config.metadata_db_engine_url, echo=False)

        with Session(engine) as session:
            # Query all datasets from the database
            statement = select(Dataset)
            datasets = session.exec(statement).all()

            if not datasets:
                st.info("No published datasets found in the database.")
                return

            st.markdown(f"**Total datasets:** {len(datasets)}")

            # Display datasets in a expandable format
            for dataset in datasets:
                with st.expander(f"📊 {dataset.name} (v{dataset.version})"):
                    st.subheader("Dataset information")
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Basic Information**")
                        st.markdown(f"**Name:** {dataset.name}")
                        st.markdown(f"**Version:** {dataset.version}")
                        st.markdown(f"**Published Date:** {dataset.published_date}")
                        st.markdown(f"**License:** {dataset.license}")

                        if dataset.keywords:
                            st.markdown(f"**Keywords:** {dataset.keywords}")

                    with col2:
                        st.markdown("**Source Information**")
                        if dataset.primary_source_url:
                            st.markdown(
                                f"**Primary Source URL:** [{dataset.primary_source_url}]({dataset.primary_source_url})"
                            )
                        if dataset.primary_source_sha256:
                            st.markdown(f"**SHA256:** `{dataset.primary_source_sha256[:16]}...`")

                    # Description
                    if dataset.description:
                        st.markdown("**Description**")
                        st.markdown(dataset.description)

                    # Authors/Creators
                    if dataset.creators:
                        st.markdown("**Authors/Creators**")
                        creators_info = []
                        for creator in dataset.creators:
                            creators_info.append(f"{creator.first_name} {creator.last_name} ({creator.email})")
                        st.markdown(", ".join(creators_info))

                    # Croissant JSON-LD metadata
                    if dataset.croissant_jsonld:
                        st.markdown("**Croissant Metadata**")
                        st.subheader("Consuming Croissant Metadata")
                        # This assumes the app is running locally and serving the JSON-LD.
                        # In a real deployment, this URL should be the public URL.
                        st.code(
                            USAGE_CODE_TEMPLATE.format(croissant_jsonld_url=dataset.croissant_jsonld_url),
                        )

                        st.subheader("Croissant Metadata Details")
                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("View JSON-LD", key=f"view_jsonld_{dataset.id}", type="primary"):
                                st.session_state[f"show_jsonld_{dataset.id}"] = True

                        with col2:
                            st.download_button(
                                label="Download Croissant JSON-LD",
                                data=dataset.croissant_jsonld,
                                file_name=f"{dataset.name.replace(' ', '_')}_v{dataset.version}_croissant.json",
                                mime="application/json",
                                key=f"download_btn_{dataset.id}",
                            )

                        # Show JSON-LD if requested
                        if st.session_state.get(f"show_jsonld_{dataset.id}", False):
                            try:
                                jsonld_data = json.loads(dataset.croissant_jsonld)
                                st.json(jsonld_data)
                                if st.button("Hide JSON-LD", key=f"hide_jsonld_{dataset.id}"):
                                    st.session_state[f"show_jsonld_{dataset.id}"] = False
                                    st.rerun()
                            except json.JSONDecodeError:
                                st.error("Invalid JSON-LD data in database")

    except Exception as e:
        st.error(f"Error accessing database: {str(e)}")
        st.info("Make sure the database has been initialized and contains data.")
