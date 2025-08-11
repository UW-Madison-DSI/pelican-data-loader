from datetime import datetime
from typing import Any

import mlcroissant as mlc
import pandas as pd
import streamlit as st
from pydantic import BaseModel, ConfigDict, Field

from pelican_data_loader.config import SystemConfig
from pelican_data_loader.utils import parse_col


class Author(BaseModel):
    """Represents an author/creator of the dataset."""

    name: str = ""
    email: str = ""

    def to_mlc_person(self) -> mlc.Person:
        """Convert Author to mlcroissant Person."""
        return mlc.Person(name=self.name if self.name else None, email=self.email if self.email else None)


class DatasetInfo(BaseModel):
    """Represents the dataset information."""

    name: str = ""
    description: str = ""
    version: str = ""
    cite_as: str = ""
    license: str = ""
    keywords: list[str] = Field(default_factory=list, description="List of keywords for the dataset")
    authors: list[Author] = Field(default_factory=list, description="List of authors/creators of the dataset")
    encoding_formats: list[str] = Field(default_factory=lambda: [mlc.EncodingFormat.CSV])

    # S3 file related fields
    s3_file_id: str = ""
    s3_file_name: str = ""
    s3_file_url: str = ""
    s3_file_sha256: str = ""
    s3_metadata_url: str = ""  # URL of the uploaded metadata file

    # Pelican file related
    pelican_uri: str = ""
    pelican_http_url: str = ""

    def to_mlc_file_object(self) -> mlc.FileObject:
        """Convert DatasetInfo to mlcroissant FileObject."""

        return mlc.FileObject(
            id=self.s3_file_id,
            name=self.s3_file_name,
            sha256=self.s3_file_sha256,
            content_url=self.s3_file_url,
            encoding_formats=self.encoding_formats,
        )


class TypedSessionState(BaseModel):
    """Represents the state of a session. This can be used with st.session_state to provide type safety and validation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow pandas DataFrame
    system_config: SystemConfig = Field(default_factory=SystemConfig)
    dataframe: pd.DataFrame | None = None
    dataset_info: DatasetInfo = Field(default_factory=DatasetInfo)
    generated_metadata: dict | None = None  # Croissant metadata JSON-LD

    @classmethod
    def get_or_create(cls) -> "TypedSessionState":
        """Get existing SessionState from streamlit session_state or create a new one."""
        if "typed_session_state" not in st.session_state:
            st.session_state["typed_session_state"] = cls()
        return st.session_state["typed_session_state"]

    def update_dataset_info(self, **kwargs):
        """Update dataset info fields."""
        for key, value in kwargs.items():
            if hasattr(self.dataset_info, key):
                setattr(self.dataset_info, key, value)

    def add_author(self, name: str, email: str = ""):
        """Add an author to the dataset."""
        self.dataset_info.authors.append(Author(name=name, email=email))

    def remove_author(self, index: int):
        """Remove an author by index."""
        if 0 <= index < len(self.dataset_info.authors):
            self.dataset_info.authors.pop(index)

    def generate_mlc_metadata(self) -> dict[str, Any]:
        """Convert state dictionary to mlc metadata JSON-LD."""

        if self.dataframe is None:
            raise ValueError("Missing dataframe in session state.")

        # Distribution that points to the S3 file
        mlc_distribution = [self.dataset_info.to_mlc_file_object()]

        # Create record set
        record_set = mlc.RecordSet(
            id=f"{self.dataset_info.s3_file_id}_record_set",
            name=self.dataset_info.name,
            fields=[parse_col(self.dataframe[col], parent_id=mlc_distribution[0].id) for col in self.dataframe.columns],
        )

        # Create metadata
        metadata = mlc.Metadata(
            name=self.dataset_info.name,
            description=self.dataset_info.description,
            version=self.dataset_info.version,
            distribution=mlc_distribution,  # type: ignore
            record_sets=[record_set],
            cite_as=self.dataset_info.cite_as,
            license=[self.dataset_info.license],
            date_published=datetime.now(),
            creators=[author.to_mlc_person() for author in self.dataset_info.authors],
            keywords=self.dataset_info.keywords,
        )

        # Generate JSON-LD
        jsonld = metadata.to_json()

        # Fix datetime bug in mlcroissant
        jsonld["datePublished"] = datetime.now().strftime("%Y-%m-%d")

        self.generated_metadata = jsonld  # Store in session state
        return jsonld

    def validate_metadata(self) -> mlc.Issues:
        """Validate the generated metadata."""
        if self.generated_metadata is None:
            raise ValueError("No generated metadata to validate.")

        validation_dataset = mlc.Dataset(jsonld=self.generated_metadata)
        return validation_dataset.metadata.issues
