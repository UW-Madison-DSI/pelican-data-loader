"""Read DTOs and wizard state.

Templates render these, never SQLModel instances: `Dataset.creators` is a lazy
relationship, so a template touching an ORM object after its session closed
raises DetachedInstanceError. Building DTOs while the session is open makes that
structurally impossible.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from pelican_data_loader.croissant import CroissantAuthor, CroissantSpec

T = TypeVar("T")

# Most numbered pagination buttons drawn at once. A module constant rather than
# a class attribute: a bare int on a BaseModel would become a pydantic field.
PAGE_WINDOW = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Discover
# --------------------------------------------------------------------------- #


class CreatorOut(BaseModel):
    first_name: str
    last_name: str
    email: str


class DatasetSummary(BaseModel):
    id: int
    name: str
    version: str
    description: str
    license: str
    keywords: list[str] = Field(default_factory=list)
    published_date: str
    creators: list[CreatorOut] = Field(default_factory=list)


class DatasetDetail(DatasetSummary):
    primary_source_url: str = ""
    primary_source_sha256: str = ""
    croissant_jsonld_url: str = ""
    pelican_uri: str = ""
    pelican_http_url: str = ""

    @property
    def file_type(self) -> str:
        """Extension of the Pelican URI, which is what `load_dataset` needs as its builder name."""
        return Path(self.pelican_uri).suffix.removeprefix(".") if self.pelican_uri else ""


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        if self.page_size <= 0:
            return 1
        return max(1, -(-self.total // self.page_size))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def first_index(self) -> int:
        return 0 if not self.total else (self.page - 1) * self.page_size + 1

    @property
    def last_index(self) -> int:
        return min(self.page * self.page_size, self.total)

    @property
    def page_numbers(self) -> list[int]:
        """The numbered buttons to draw, as a contiguous window on the current page.

        Capped at PAGE_WINDOW so a repository with hundreds of pages still
        renders one tidy row; Previous and Next reach everything outside it.
        Deliberately contiguous with no ellipsis — every number drawn is a real
        page, so nothing has to explain itself.
        """
        if self.pages <= PAGE_WINDOW:
            return list(range(1, self.pages + 1))
        half = PAGE_WINDOW // 2
        start = min(max(1, self.page - half), self.pages - PAGE_WINDOW + 1)
        return list(range(start, start + PAGE_WINDOW))


class Facet(BaseModel):
    value: str
    count: int
    label: str = ""

    def display(self) -> str:
        return self.label or self.value


class Facets(BaseModel):
    licenses: list[Facet] = Field(default_factory=list)
    keywords: list[Facet] = Field(default_factory=list)
    keywords_truncated: int = 0


# --------------------------------------------------------------------------- #
# Publish wizard
# --------------------------------------------------------------------------- #


class UploadState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    # A restart killed the upload; the CSV is still on disk so Retry works.
    INTERRUPTED = "interrupted"

    @property
    def is_terminal(self) -> bool:
        return self in (UploadState.DONE, UploadState.ERROR, UploadState.INTERRUPTED)


class ColumnInfo(BaseModel):
    name: str
    dtype: str
    non_null: int
    null_count: int


class DraftAuthor(BaseModel):
    name: str = ""
    email: str = ""


class PublishDraft(BaseModel):
    """The whole wizard, persisted as draft.json next to the uploaded CSV.

    The DataFrame is deliberately absent: it lives on disk as data.csv, which is
    both the file uploaded to S3 and the file that gets hashed, so there is only
    ever one copy of the truth.
    """

    id: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # Step 1
    name: str = ""
    description: str = ""
    version: str = ""
    cite_as: str = ""
    license: str = ""
    keywords: list[str] = Field(default_factory=list)
    authors: list[DraftAuthor] = Field(default_factory=list)

    # Step 2
    source_file_name: str = ""
    row_count: int = 0
    column_count: int = 0
    columns: list[ColumnInfo] = Field(default_factory=list)
    preview_columns: list[str] = Field(default_factory=list)
    preview_rows: list[list[str]] = Field(default_factory=list)

    upload_state: UploadState = UploadState.IDLE
    upload_pct: int = 0
    upload_error: str = ""
    upload_started_at: datetime | None = None

    s3_file_id: str = ""
    s3_file_name: str = ""
    s3_file_url: str = ""
    s3_file_sha256: str = ""
    pelican_uri: str = ""
    pelican_http_url: str = ""

    # Step 3
    has_metadata: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    generate_error: str = ""
    s3_metadata_url: str = ""

    # Step 4
    published_dataset_id: int | None = None

    # -- derived state the templates gate on ------------------------------- #

    @property
    def has_csv(self) -> bool:
        return bool(self.source_file_name)

    @property
    def metadata_complete(self) -> bool:
        return bool(self.name and self.version and self.license)

    @property
    def data_uploaded(self) -> bool:
        return self.upload_state is UploadState.DONE and bool(self.s3_file_url)

    @property
    def can_generate(self) -> bool:
        return self.has_csv and self.metadata_complete and self.data_uploaded

    @property
    def can_publish(self) -> bool:
        return self.has_metadata and not self.validation_errors

    @property
    def metadata_filename(self) -> str:
        """Download name, matching the Streamlit download_button."""
        stem = self.name.lower().replace(" ", "_") or "dataset"
        return f"{stem}_metadata.json"

    @property
    def s3_metadata_object(self) -> str:
        """Key the JSON-LD is stored under: metadata/<csv stem>.json."""
        if not self.s3_file_name:
            return ""
        return f"metadata/{Path(self.s3_file_name).stem}.json"

    def to_croissant_spec(self) -> CroissantSpec:
        return CroissantSpec(
            name=self.name,
            description=self.description,
            version=self.version,
            cite_as=self.cite_as,
            license=self.license,
            keywords=self.keywords,
            authors=[CroissantAuthor(name=a.name, email=a.email) for a in self.authors],
            file_id=self.s3_file_id,
            file_name=self.s3_file_name,
            file_url=self.s3_file_url,
            file_sha256=self.s3_file_sha256,
        )
