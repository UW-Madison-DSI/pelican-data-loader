import streamlit as st
from constant import LICENSES


def render_dataset_info_tab():
    """Render the dataset information tab with basic info, S3 config, and authors."""
    st.header("Dataset Information")

    # Initialize dataset_info in session state if not exists
    if "dataset_info" not in st.session_state:
        st.session_state.dataset_info = {
            "name": "",
            "description": "",
            "version": "",
            "cite_as": "",
            "license": "",
            "keywords": "",
            "authors": [],
        }

    if "dataframe" not in st.session_state:
        st.warning("Please upload a CSV file first in the File Upload tab.")
    else:
        st.subheader("Dataset Basic Information")
        col1, col2 = st.columns(2)

        with col1:
            dataset_name = st.text_input("Dataset Name", help="A human-readable name for the dataset")
            dataset_description = st.text_area("Dataset Description", help="A detailed description of the dataset")
            dataset_version = st.text_input("Version", help="Version of the dataset, e.g., '1.0.0'")
            cite_as = st.text_input("Citation", help="How to cite this dataset")

        with col2:
            license_url = st.selectbox("License", options=LICENSES, help="Choose a license for the dataset", index=None)
            keywords_input = st.text_input(
                "Keywords (comma-separated)", help="Keywords describing the dataset, separated by commas"
            )

        # Update dataset_info with current form values
        st.session_state.dataset_info.update(
            {
                "name": dataset_name,
                "description": dataset_description,
                "version": dataset_version,
                "cite_as": cite_as,
                "license": license_url,
                "keywords": [k.strip() for k in keywords_input.split(",") if k.strip()],
            }
        )

        # Authors/Creators section
        st.subheader("Authors/Creators")

        # Get current authors from dataset_info
        current_authors = st.session_state.dataset_info["authors"]

        if current_authors:
            st.write("**Current Authors**")
            for i, author in enumerate(current_authors):
                col1, col2, col3 = st.columns([3, 3, 1], vertical_alignment="bottom")
                with col1:
                    new_name = st.text_input("Name", value=author["name"], key=f"name_{i}")
                with col2:
                    new_email = st.text_input("Email", value=author["email"], key=f"email_{i}")
                with col3:
                    if st.button("🗑️", key=f"delete_{i}", help="Delete author"):
                        st.session_state.dataset_info["authors"].pop(i)
                        st.rerun()

                # Update author info in dataset_info
                st.session_state.dataset_info["authors"][i] = {"name": new_name, "email": new_email}

        # Add new author
        st.write("**Add New Author**")
        col1, col2, col3 = st.columns([3, 3, 1], vertical_alignment="bottom")
        with col1:
            new_author_name = st.text_input("New Author Name", key="new_name", value="")
        with col2:
            new_author_email = st.text_input("New Author Email", key="new_email", value="")
        with col3:
            if st.button("➕ Add", key="add_author"):
                if new_author_name and new_author_email:
                    st.session_state.dataset_info["authors"].append(
                        {"name": new_author_name, "email": new_author_email}
                    )
                    st.rerun()
                else:
                    st.error("Please provide both name and email")
