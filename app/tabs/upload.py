from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import streamlit as st

from app.state import TypedSessionState
from pelican_data_loader.config import SystemConfig
from pelican_data_loader.data import upload_to_s3
from pelican_data_loader.utils import get_sha256, sanitize_name


def render_upload():
    st.header("Upload CSV File")
    st.markdown(
        "This tab allows you to upload a CSV file containing your dataset to [UW-Madison Research Object S3](https://web.s3.wisc.edu/pelican-data-loader)."
    )

    # Get SessionState
    typed_state = TypedSessionState.get_or_create()

    uploaded_file = st.file_uploader(
        "Choose a CSV file", type="csv", help="Upload a CSV file to generate Croissant metadata"
    )

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [sanitize_name(col) for col in df.columns]
            typed_state.dataframe = df
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
            if st.button(
                "Upload dataset to S3",
                icon="⬆️",
                type="primary",
                on_click=handle_s3_upload,
                args=(typed_state.system_config, uploaded_file.name, typed_state),
            ):
                st.success("File uploaded successfully!")

        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")


def handle_s3_upload(config: SystemConfig, file_name: str, typed_state: TypedSessionState) -> None:
    """Handle the S3 upload of the CSV file."""

    if typed_state.dataframe is None:
        st.warning("Please upload a CSV file first in the File Upload tab.")
        return

    with NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
        typed_state.dataframe.to_csv(tmp_file.name, index=False)
        upload_to_s3(
            file_path=tmp_file.name,
            bucket_name=config.s3_bucket_name,
            object_name=file_name,
        )

    typed_state.dataset_info.s3_file_id = Path(file_name).stem
    typed_state.dataset_info.s3_file_name = file_name
    typed_state.dataset_info.s3_file_url = f"{config.s3_url}/{file_name}"
    typed_state.dataset_info.s3_file_sha256 = get_sha256(Path(tmp_file.name))
