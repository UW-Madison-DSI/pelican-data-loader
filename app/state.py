import pandas as pd
from pydantic import BaseModel, Field

from pelican_data_loader.config import SystemConfig


class Author(BaseModel):
    """Represents an author/creator of the dataset."""

    name: str = ""
    email: str = ""


class DatasetInfo(BaseModel):
    """Represents the dataset information."""

    name: str = ""
    description: str = ""
    version: str = ""
    cite_as: str = ""
    license: str = ""
    keywords: str = ""  # Comma-separated keywords
    authors: list[Author] = Field(default_factory=list, description="List of authors/creators of the dataset")

    # S3 file related fields
    s3_file_id: str = ""
    s3_file_name: str = ""
    s3_file_url: str = ""
    s3_file_sha256: str = ""


class SessionState(BaseModel):
    """Represents the state of a session.

    Note. This is not used in the current implementation but can be useful for understanding what is stored in st.session_state.
    """

    system_config: SystemConfig
    dataframe: pd.DataFrame | None = None
    dataset_info: DatasetInfo
    generated_metadata: dict | None = None  # Croissant metadata JSON-LD
