"""Build and validate Croissant (JSON-LD) metadata for a tabular dataset.

The library could already *read* Croissant (`Dataset.from_jsonld`) but not write
it, so every consumer had to reimplement the generator. This module closes that
gap, including the `datePublished` workaround below, which is knowledge about
mlcroissant rather than about any one application.
"""

from datetime import datetime
from typing import Any

import mlcroissant as mlc
import pandas as pd
from pydantic import BaseModel, Field

from pelican_data_loader.utils import parse_col


class CroissantAuthor(BaseModel):
    """An author/creator of a dataset."""

    name: str = ""
    email: str = ""

    def to_mlc_person(self) -> mlc.Person:
        return mlc.Person(name=self.name or None, email=self.email or None)


class CroissantSpec(BaseModel):
    """Everything needed to describe a single-file tabular dataset in Croissant.

    The `file_*` fields describe the already-uploaded data file: Croissant records
    where the data lives, so the file has to exist before metadata can point at it.
    """

    name: str = ""
    description: str = ""
    version: str = ""
    cite_as: str = ""
    license: str = ""
    keywords: list[str] = Field(default_factory=list)
    authors: list[CroissantAuthor] = Field(default_factory=list)
    encoding_formats: list[str] = Field(default_factory=lambda: [mlc.EncodingFormat.CSV])

    file_id: str = ""
    file_name: str = ""
    file_url: str = ""
    file_sha256: str = ""

    def to_mlc_file_object(self) -> mlc.FileObject:
        return mlc.FileObject(
            id=self.file_id,
            name=self.file_name,
            sha256=self.file_sha256,
            content_url=self.file_url,
            encoding_formats=self.encoding_formats,
        )


def build_croissant_metadata(dataframe: pd.DataFrame, spec: CroissantSpec) -> dict[str, Any]:
    """Generate Croissant JSON-LD describing `dataframe` as published per `spec`.

    One record set with one field per column; column types come from the pandas
    dtypes via `parse_col`, so the frame must be the same one that was uploaded.
    """

    distribution = [spec.to_mlc_file_object()]

    record_set = mlc.RecordSet(
        id=f"{spec.file_id}_record_set",
        name=spec.name,
        fields=[parse_col(dataframe[col], parent_id=distribution[0].id) for col in dataframe.columns],
    )

    metadata = mlc.Metadata(
        name=spec.name,
        description=spec.description,
        version=spec.version,
        distribution=distribution,  # type: ignore[arg-type]
        record_sets=[record_set],
        cite_as=spec.cite_as,
        license=[spec.license],
        date_published=datetime.now(),
        creators=[author.to_mlc_person() for author in spec.authors],
        keywords=spec.keywords,
    )

    jsonld = metadata.to_json()

    # mlcroissant serializes date_published as a full datetime, which its own
    # validator then rejects. Overwrite with a plain ISO date. `Dataset.published_date`
    # is a string column that gets sorted lexicographically, so zero-padding matters.
    jsonld["datePublished"] = datetime.now().strftime("%Y-%m-%d")

    return jsonld


def validate_croissant(jsonld: dict[str, Any]) -> mlc.Issues:
    """Validate a Croissant document, returning its `.errors` and `.warnings`."""
    return mlc.Dataset(jsonld=jsonld).metadata.issues
