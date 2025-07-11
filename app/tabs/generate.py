import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st
from state import TypedSessionState

from pelican_data_loader.data import upload_to_s3


def render_generate_tab():
    """Render the Generate Metadata tab with configuration summary and metadata generation."""
    st.header("Generate Croissant Metadata")

    # Get SessionState
    typed_state = TypedSessionState.get_or_create()

    if typed_state.dataframe is None:
        st.warning("Please upload a CSV file first in the File Upload tab.")
    elif not typed_state.dataset_info.name:  # Check if basic info is filled
        st.warning("Please fill in dataset information in the Dataset Info tab.")
    else:
        # Display configuration summary
        st.subheader("Dataset Information")
        st.write("Please review the dataset information below before generating metadata.")
        st.json(typed_state.dataset_info, expanded=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🥐 Generate Croissant Metadata", type="primary"):
                try:
                    with st.spinner("Generating Croissant metadata..."):
                        typed_state.generate_mlc_metadata()  # This will save a copy in .generated_metadata

                    st.success("✅ Croissant metadata generated successfully!")
                    # Validation
                    try:
                        issues = typed_state.validate_metadata()

                        if issues.errors:
                            st.error(f"❌ Validation errors found: {len(issues.errors)}")
                            for error in issues.errors:
                                st.error(f"- {error}")
                        else:
                            st.success("✅ Metadata validation passed!")

                        if issues.warnings:
                            st.warning(f"⚠️ Validation warnings: {len(issues.warnings)}")
                            for warning in issues.warnings:
                                st.warning(f"- {warning}")

                    except Exception as e:
                        st.error(f"Validation error: {str(e)}")

                except Exception as e:
                    st.error(f"Error generating metadata: {str(e)}")
                    st.error(
                        "Note: mlcroissant is still not production ready, many typing issues and missing date types... be extra cautious"
                    )
        with col2:
            if typed_state.generated_metadata is not None:
                st.download_button(
                    label="📥 Download Metadata (JSON-LD)",
                    data=json.dumps(typed_state.generated_metadata, indent=2),
                    file_name=f"{typed_state.dataset_info.name.lower().replace(' ', '_')}_metadata.json",
                    mime="application/json",
                    type="primary",
                )

        with col3:
            if typed_state.generated_metadata is not None:
                file_path = typed_state.dataset_info.s3_file_name
                if not file_path:
                    st.error("No file path found in dataset information. Please upload a file first.")

                # Create metadata path by adding _metadata and replace extension with .json suffix
                metadata_file_path = Path(file_path).with_name(Path(file_path).stem + ".json")
                meta_data_s3_path = f"metadata/{metadata_file_path.name}"

                if st.button("⬆️ Upload Metadata to S3", type="primary"):
                    try:
                        with (
                            st.spinner("Uploading metadata to S3..."),
                            NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f,
                        ):
                            json.dump(typed_state.generated_metadata, f, indent=2)
                            f.flush()  # Ensure the file is fully written before uploading
                            upload_to_s3(
                                file_path=f.name,
                                bucket_name=typed_state.system_config.s3_bucket_name,
                                object_name=meta_data_s3_path,
                            )
                        # Update dataset info with metadata URL
                        s3_metadata_url = f"{typed_state.system_config.s3_url}/{meta_data_s3_path}"
                        typed_state.update_dataset_info(s3_metadata_url=s3_metadata_url)
                        st.success(f"Metadata uploaded to: {s3_metadata_url}")
                    except Exception as e:
                        st.error(f"Error uploading metadata: {str(e)}")

        if typed_state.generated_metadata is not None:
            with st.expander("View JSON-LD Metadata", icon="🔍", expanded=False):
                st.json(typed_state.generated_metadata, expanded=True)
