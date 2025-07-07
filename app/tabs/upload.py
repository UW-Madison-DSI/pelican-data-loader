from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from pelican_data_loader.config import SystemConfig
from pelican_data_loader.data import upload_to_s3
from pelican_data_loader.utils import get_sha256, sanitize_name


def render_upload_tab():
    st.header("Upload CSV File")

    uploaded_file = st.file_uploader(
        "Choose a CSV file", type="csv", help="Upload a CSV file to generate Croissant metadata"
    )

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [sanitize_name(col) for col in df.columns]
            st.session_state.dataframe = df
            st.session_state.uploaded_file_name = uploaded_file.name
            st.success(f"Successfully loaded {uploaded_file.name}")
            st.write(f"**Shape:** {df.shape[0]} rows, {df.shape[1]} columns")

            # Show data preview
            st.subheader("Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            # Show column information
            st.subheader("Column Information")
            col_info = pd.DataFrame(
                {
                    "Column": df.columns,
                    "Data Type": df.dtypes,
                    "Non-Null Count": df.count(),
                    "Null Count": df.isnull().sum(),
                }
            )
            st.dataframe(col_info, use_container_width=True)

            st.subheader("Upload to S3")
            st.write("Upload the CSV file to S3 so others can download it.")
            if st.button("Upload dataset to S3", icon="⬆️", type="primary"):
                with st.spinner("Uploading to S3..."):
                    s3_data = handle_s3_upload(st.session_state.system_config)
                    st.session_state.dataset_info.update(s3_data)
                    st.success("File uploaded successfully!")

        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")


def handle_s3_upload(config: SystemConfig) -> dict:
    """Handle the S3 upload of the CSV file."""

    if "dataframe" not in st.session_state:
        st.warning("Please upload a CSV file first in the File Upload tab.")
        return {}

    with NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
        st.session_state.dataframe.to_csv(tmp_file.name, index=False)
        upload_to_s3(
            file_path=tmp_file.name,
            bucket_name=config.s3_bucket_name,
            object_name=st.session_state.uploaded_file_name,
        )

    return {
        "s3_file_id": Path(st.session_state.uploaded_file_name).stem,
        "s3_file_name": st.session_state.uploaded_file_name,
        "s3_file_url": f"{config.s3_url}/{st.session_state.uploaded_file_name}",
        "s3_file_sha256": get_sha256(Path(tmp_file.name)),
    }
