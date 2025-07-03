import json

import streamlit as st
from sqlmodel import Session, create_engine, select

from pelican_data_loader.db import Dataset


def render_discover_tab():
    """Render the view published datasets tab with a list of all datasets in the metadata database."""
    st.header("Published Datasets")

    # Get system config from session state
    system_config = st.session_state.get("system_config")
    if not system_config:
        st.error("System configuration not found. Please restart the application.")
        return

    try:
        # Create database engine and session
        engine = create_engine(system_config.metadata_db_engine_url, echo=False)

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
                    # Basic information
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

                        # Create columns for viewing options
                        view_col1, view_col2 = st.columns(2)

                        with view_col1:
                            if st.button("View JSON-LD", key=f"view_jsonld_{dataset.id}"):
                                st.session_state[f"show_jsonld_{dataset.id}"] = True

                        with view_col2:
                            if st.button("Download JSON-LD", key=f"download_jsonld_{dataset.id}"):
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
                            except json.JSONDecodeError:
                                st.error("Invalid JSON-LD data in database")

                    st.markdown("---")

    except Exception as e:
        st.error(f"Error accessing database: {str(e)}")
        st.info("Make sure the database has been initialized and contains data.")
