import streamlit as st
from constant import LICENSES

from app.state import TypedSessionState


def render_info():
    """Render the dataset information tab with basic info, S3 config, and authors."""
    st.header("Dataset Information")

    # Get SessionState
    typed_state = TypedSessionState.get_or_create()

    if typed_state.dataframe is None:
        st.warning("Please upload a CSV file first in the File Upload tab.")
    else:
        st.subheader("Dataset Basic Information")
        col1, col2 = st.columns(2)

        with col1:
            dataset_name = st.text_input(
                "Dataset Name", value=typed_state.dataset_info.name, help="A human-readable name for the dataset"
            )
            dataset_description = st.text_area(
                "Dataset Description",
                value=typed_state.dataset_info.description,
                help="A detailed description of the dataset",
            )
            dataset_version = st.text_input(
                "Version", value=typed_state.dataset_info.version, help="Version of the dataset, e.g., '1.0.0'"
            )
            cite_as = st.text_input("Citation", value=typed_state.dataset_info.cite_as, help="How to cite this dataset")

        with col2:
            # Find current license index
            license_index = None
            if typed_state.dataset_info.license:
                try:
                    license_index = LICENSES.index(typed_state.dataset_info.license)
                except ValueError:
                    license_index = None

            license_url = st.selectbox(
                "License", options=LICENSES, help="Choose a license for the dataset", index=license_index
            )
            keywords_input = st.text_input(
                "Keywords (comma-separated)",
                value=", ".join(typed_state.dataset_info.keywords),
                help="Keywords describing the dataset, separated by commas",
            )

        # Update dataset_info with current form values
        typed_state.update_dataset_info(
            name=dataset_name,
            description=dataset_description,
            version=dataset_version,
            cite_as=cite_as,
            license=license_url or "",
            keywords=keywords_input.split(", ") if keywords_input else [],
        )

        # Authors/Creators section
        st.subheader("Authors/Creators")

        # Get current authors from dataset_info
        current_authors = typed_state.dataset_info.authors

        if current_authors:
            st.write("**Current Authors**")
            for i, author in enumerate(current_authors):
                col1, col2, col3 = st.columns([3, 3, 1], vertical_alignment="bottom")
                with col1:
                    new_name = st.text_input("Name", value=author.name, key=f"name_{i}")
                with col2:
                    new_email = st.text_input("Email", value=author.email, key=f"email_{i}")
                with col3:
                    if st.button("🗑️", key=f"delete_{i}", help="Delete author"):
                        typed_state.remove_author(i)
                        st.rerun()

                # Update author info in dataset_info
                current_authors[i].name = new_name
                current_authors[i].email = new_email

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
                    typed_state.add_author(new_author_name, new_author_email)
                    st.rerun()
                else:
                    st.error("Please provide both name and email")
