import json
from datetime import datetime

import mlcroissant as mlc
import streamlit as st

from pelican_data_loader.config import SystemConfig
from pelican_data_loader.utils import parse_col


def render_generate_tab():
    """Render the Generate Metadata tab with configuration summary and metadata generation."""
    st.header("Generate Croissant Metadata")

    config = SystemConfig()  # type: ignore
    if "dataframe" not in st.session_state:
        st.warning("Please upload a CSV file first in the File Upload tab.")
    elif "dataset_info" not in st.session_state:
        st.warning("Please fill in dataset information in the Dataset Info tab.")
    else:
        # Display configuration summary
        st.subheader("Dataset Information")
        st.write("Please review the dataset information below before generating metadata.")
        st.json(st.session_state.dataset_info, expanded=True)

        if st.button("🥐 Generate Croissant Metadata", type="primary"):
            try:
                with st.spinner("Generating Croissant metadata..."):
                    jsonld = session_state_to_mlc_metadata(st.session_state.to_dict(), config)
                    dataset = mlc.Dataset(jsonld=jsonld)

                    # Store in session state
                    st.session_state.generated_metadata = dataset.jsonld

                st.success("✅ Croissant metadata generated successfully!")

                # Display the generated metadata
                st.subheader("Generated Metadata (JSON-LD)")

                # Pretty print JSON
                json_str = json.dumps(st.session_state.generated_metadata, indent=2)
                st.code(json_str, language="json")

                # Download button
                st.download_button(
                    label="📥 Download Metadata (JSON-LD)",
                    data=json_str,
                    file_name=f"{st.session_state.dataset_info['name'].lower().replace(' ', '_')}_metadata.json",
                    mime="application/json",
                )
            except Exception as e:
                st.error(f"Error generating metadata: {str(e)}")
                st.error(
                    "Note: mlcroissant is still not production ready, many typing issues and missing date types... be extra cautious"
                )

        # Validation
        if "generated_metadata" in st.session_state:
            st.subheader("Validation")
            try:
                validation_dataset = mlc.Dataset(jsonld=st.session_state.generated_metadata)
                issues = validation_dataset.metadata.issues

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


def session_state_to_mlc_metadata(state: dict, config: SystemConfig) -> dict:
    """Convert state dictionary to mlc metadata JSON-LD."""

    for key in ("dataframe", "uploaded_file_name", "dataset_info"):
        if key not in state:
            raise KeyError(f"Missing required state key: {key}")

    for key in (
        "s3_file_id",
        "s3_file_name",
        "s3_file_url",
        "name",
        "description",
        "version",
        "cite_as",
        "license",
        "keywords",
    ):
        if key not in state["dataset_info"]:
            raise KeyError(f"Missing required dataset_info key: {key}")

    # Get data from state
    df = state["dataframe"]
    dataset_info = state["dataset_info"]
    authors = state["dataset_info"].get("authors", [])

    # Create S3 bucket file object
    mlc_s3 = mlc.FileObject(
        id=config.mlc_s3_bucket_name,
        name=config.mlc_s3_bucket_name,
        content_url=config.s3_url,
        encoding_formats=["https"],
        sha256="main",
    )

    # Create CSV file object
    mlc_file_object = mlc.FileObject(
        contained_in=[mlc_s3.id],
        id=dataset_info["s3_file_id"],
        name=dataset_info["s3_file_name"],
        sha256=dataset_info["s3_file_sha256"],
        content_url=dataset_info["s3_file_url"],
        encoding_formats=[mlc.EncodingFormat.CSV],
    )

    mlc_distribution = [mlc_s3, mlc_file_object]

    # Create record set
    record_set = mlc.RecordSet(
        id=f"{dataset_info['s3_file_id']}_record_set",
        name=dataset_info["name"],
        fields=[parse_col(df[col], parent_id=mlc_file_object.id) for col in df.columns],
    )

    # Create metadata
    metadata = mlc.Metadata(
        name=dataset_info["name"],
        description=dataset_info["description"],
        version=dataset_info["version"],
        distribution=mlc_distribution,  # type: ignore
        record_sets=[record_set],
        cite_as=dataset_info["cite_as"],
        license=[dataset_info["license"]],
        date_published=datetime.now(),
        creators=[mlc.Person(**author) for author in authors],
        keywords=dataset_info["keywords"],
    )

    # Generate JSON-LD
    jsonld = metadata.to_json()
    # Fix datetime bug in mlcroissant
    jsonld["datePublished"] = datetime.now().strftime("%Y-%m-%d")
    return jsonld
