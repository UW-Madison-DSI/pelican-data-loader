import streamlit as st
from constant import LICENSES

from app.state import TypedSessionState


def parse_keywords_input(keywords_input: str) -> list[str]:
    """Process the keywords input from the user."""
    if not keywords_input:
        return []
    if "," in keywords_input:
        return [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
    return [keywords_input.strip()]


def render_metadata_input(state: TypedSessionState):
    """Render dataset metadata input fields."""

    st.subheader("Step 1: Input Dataset Metadata")
    with st.container(border=True):
        st.subheader("Basic Information")
        col1, col2 = st.columns(2)

        with col1:
            dataset_name = st.text_input("Dataset Name", value=state.dataset_info.name, placeholder="A human-readable name for the dataset")
            dataset_description = st.text_area(
                "Dataset Description",
                value=state.dataset_info.description,
                placeholder="A detailed description of the dataset",
            )
            dataset_version = st.text_input("Version", value=state.dataset_info.version, placeholder="e.g., '1.0.0'")
            cite_as = st.text_input(
                "Citation", value=state.dataset_info.cite_as, placeholder="How to cite this dataset, future version should integrate with doi minting"
            )

        with col2:
            # Find current license index
            license_index = None
            if state.dataset_info.license:
                try:
                    license_index = LICENSES.index(state.dataset_info.license)
                except ValueError:
                    license_index = None

            license_url = st.selectbox("License", options=LICENSES, placeholder="Choose a license for the dataset", index=license_index)
            keywords_input = st.text_input(
                "Keywords (comma-separated)",
                value=", ".join(state.dataset_info.keywords),
                placeholder="Keywords describing the dataset, separated by commas",
            )

        # Update dataset_info with current form values

        state.update_dataset_info(
            name=dataset_name,
            description=dataset_description,
            version=dataset_version,
            cite_as=cite_as,
            license=license_url or "",
            keywords=parse_keywords_input(keywords_input),
        )

        # Authors/Creators section
        st.subheader("Authors/Creators")

        # Get current authors from dataset_info
        current_authors = state.dataset_info.authors

        if current_authors:
            st.write("**Added Authors**")
            for i, author in enumerate(current_authors):
                col1, col2, col3 = st.columns([3, 3, 1], vertical_alignment="bottom")
                with col1:
                    new_name = st.text_input("Name", value=author.name, key=f"name_{i}")
                with col2:
                    new_email = st.text_input("Email", value=author.email, key=f"email_{i}")
                with col3:
                    if st.button("🗑️", key=f"delete_{i}", help="Delete author"):
                        state.remove_author(i)
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
                    state.add_author(new_author_name, new_author_email)
                    st.rerun()
                else:
                    st.error("Please provide both name and email")
