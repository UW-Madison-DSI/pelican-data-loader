"""The publish pipeline: CSV in, S3 objects and a database row out.

Everything here blocks (pandas, minio, mlcroissant, psycopg2), so callers must be
sync `def` handlers that Starlette runs in a threadpool, never `async def`.

mlcroissant and datasets are imported at module load on purpose: they are slow to
import, and paying that at startup means the first user request is not the one
that waits, and the build-time smoke test exercises it.
"""

import json
import logging
import time
from pathlib import Path

import pandas as pd
from sqlmodel import Session

from app.schemas import ColumnInfo, PublishDraft, UploadState
from app.services.drafts import DraftStore
from app.settings import settings
from pelican_data_loader.config import SYSTEM_CONFIG
from pelican_data_loader.croissant import build_croissant_metadata, validate_croissant
from pelican_data_loader.data import upload_to_s3
from pelican_data_loader.db import Dataset
from pelican_data_loader.utils import get_sha256, sanitize_name

logger = logging.getLogger(__name__)

PREVIEW_ROWS = 10
CHUNK_SIZE = 1024 * 1024


class UploadTooLarge(Exception):
    """The uploaded file exceeded APP_MAX_UPLOAD_MB."""


class CsvError(Exception):
    """The uploaded file could not be parsed as CSV."""


# --------------------------------------------------------------------------- #
# Step 2: receive the CSV
# --------------------------------------------------------------------------- #


def save_uploaded_csv(store: DraftStore, draft: PublishDraft, file_name: str, stream) -> PublishDraft:
    """Stream an upload to disk, parse it, and record shape/preview/column info.

    The file is streamed in chunks and never held in memory: a multi-hundred-MB
    CSV read whole would take the container down.
    """
    temp_path = store.upload_temp_path(draft.id)
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    try:
        with temp_path.open("wb") as out:
            while chunk := stream.read(CHUNK_SIZE):
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise UploadTooLarge(f"The file is larger than {settings.max_upload_mb} MB.")
                out.write(chunk)

        try:
            frame = pd.read_csv(temp_path)
        except Exception as exc:  # noqa: BLE001 - pandas raises a wide variety here
            raise CsvError(str(exc)) from exc

        if frame.empty and not len(frame.columns):
            raise CsvError("The file contains no columns.")

        # Column names become Croissant field ids, which must be valid identifiers.
        frame.columns = [sanitize_name(str(col)) for col in frame.columns]

        csv_path = store.csv_path(draft.id)
        frame.to_csv(csv_path, index=False)

        preview = frame.head(PREVIEW_ROWS)
        draft.source_file_name = Path(file_name).name
        draft.row_count = int(frame.shape[0])
        draft.column_count = int(frame.shape[1])
        draft.columns = [
            ColumnInfo(
                name=str(name),
                dtype=str(frame[name].dtype),
                non_null=int(frame[name].count()),
                null_count=int(frame[name].isnull().sum()),
            )
            for name in frame.columns
        ]
        draft.preview_columns = [str(c) for c in preview.columns]
        draft.preview_rows = [["" if pd.isna(v) else str(v) for v in row] for row in preview.itertuples(index=False)]

        # Replacing the data invalidates everything downstream of it.
        draft.upload_state = UploadState.IDLE
        draft.upload_pct = 0
        draft.upload_error = ""
        draft.s3_file_id = ""
        draft.s3_file_name = ""
        draft.s3_file_url = ""
        draft.s3_file_sha256 = ""
        draft.pelican_uri = ""
        draft.pelican_http_url = ""
        draft.has_metadata = False
        draft.s3_metadata_url = ""
        draft.validation_errors = []
        draft.validation_warnings = []
        draft.generate_error = ""

        del frame
        return store.save(draft)
    finally:
        temp_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Step 2: push it to S3
# --------------------------------------------------------------------------- #


class DraftProgress:
    """minio progress sink that records percentage onto the draft.

    Throttled: minio calls update() once per part, and rewriting draft.json on
    every call would cost more than the upload.
    """

    MIN_INTERVAL_SECONDS = 0.5

    def __init__(self, store: DraftStore, draft_id: str):
        self.store = store
        self.draft_id = draft_id
        self.total = 0
        self.sent = 0
        self.last_pct = 0
        self.last_write = 0.0

    def set_meta(self, object_name: str, total_length: int) -> None:
        self.total = total_length

    def update(self, length: int) -> None:
        self.sent += length
        if not self.total:
            return
        pct = min(99, int(self.sent * 100 / self.total))
        now = time.monotonic()
        if pct > self.last_pct and now - self.last_write >= self.MIN_INTERVAL_SECONDS:
            self.last_pct = pct
            self.last_write = now
            try:
                self.store.update(self.draft_id, upload_pct=pct)
            except Exception as exc:  # noqa: BLE001 - progress must never fail an upload
                logger.debug("Could not record upload progress: %s", exc)


def run_data_upload(store: DraftStore, draft_id: str) -> None:
    """Upload data.csv to S3 and record the derived URLs. Runs in a worker thread.

    Never raises: the outcome is written to the draft, which is what the polling
    status endpoint reads.
    """
    try:
        draft = store.load(draft_id)
        csv_path = store.csv_path(draft_id)
        if not csv_path.exists():
            raise FileNotFoundError("The uploaded CSV is no longer on disk. Upload it again.")

        object_name = draft.source_file_name

        if settings.fake_s3:
            # Exercises the state machine (and the progress bar) with no credentials.
            for pct in range(0, 100, 10):
                store.update(draft_id, upload_pct=pct)
                time.sleep(0.8)
        else:
            upload_to_s3(
                file_path=csv_path,
                bucket_name=SYSTEM_CONFIG.s3_bucket_name,
                object_name=object_name,
                progress=DraftProgress(store, draft_id),
            )

        # Hash the file that was actually uploaded, so the recorded checksum
        # always describes the bytes in the bucket.
        sha256 = get_sha256(csv_path)

        store.update(
            draft_id,
            upload_state=UploadState.DONE,
            upload_pct=100,
            upload_error="",
            s3_file_id=Path(object_name).stem,
            s3_file_name=object_name,
            s3_file_url=f"{SYSTEM_CONFIG.s3_url}/{object_name}",
            s3_file_sha256=sha256,
            pelican_uri=f"{SYSTEM_CONFIG.pelican_uri_prefix}/{object_name}",
            pelican_http_url=f"{SYSTEM_CONFIG.pelican_http_url_prefix}/{object_name}",
        )
    except Exception as exc:  # noqa: BLE001 - reported through the draft, not raised
        logger.exception("S3 upload failed for draft %s", draft_id)
        try:
            store.update(draft_id, upload_state=UploadState.ERROR, upload_error=str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("Could not record the upload failure for draft %s", draft_id)


# --------------------------------------------------------------------------- #
# Step 3: Croissant metadata
# --------------------------------------------------------------------------- #


def generate_metadata(store: DraftStore, draft: PublishDraft) -> PublishDraft:
    """Generate and validate the Croissant document, storing it beside the CSV."""
    csv_path = store.csv_path(draft.id)
    if not csv_path.exists():
        draft.generate_error = "The uploaded CSV is no longer on disk. Upload it again."
        draft.has_metadata = False
        return store.save(draft)

    try:
        # Read the whole file, not a sample: dtype inference decides the Croissant
        # field types, and inferring from the first N rows would emit different types.
        frame = pd.read_csv(csv_path)
        jsonld = build_croissant_metadata(frame, draft.to_croissant_spec())
        del frame
    except Exception as exc:  # noqa: BLE001
        logger.exception("Croissant generation failed for draft %s", draft.id)
        draft.generate_error = str(exc)
        draft.has_metadata = False
        draft.validation_errors = []
        draft.validation_warnings = []
        return store.save(draft)

    store.metadata_path(draft.id).write_text(json.dumps(jsonld, indent=2))
    draft.has_metadata = True
    draft.generate_error = ""

    try:
        issues = validate_croissant(jsonld)
        draft.validation_errors = [str(e) for e in issues.errors]
        draft.validation_warnings = [str(w) for w in issues.warnings]
    except Exception as exc:  # noqa: BLE001 - validation failing is not generation failing
        logger.warning("Croissant validation failed for draft %s: %s", draft.id, exc)
        draft.validation_errors = [f"Validation could not run: {exc}"]
        draft.validation_warnings = []

    return store.save(draft)


def load_metadata(store: DraftStore, draft: PublishDraft) -> dict:
    path = store.metadata_path(draft.id)
    if not path.exists():
        raise FileNotFoundError("No generated metadata for this draft.")
    return json.loads(path.read_text())


def upload_metadata(store: DraftStore, draft: PublishDraft) -> PublishDraft:
    """Upload the JSON-LD to S3 under metadata/<csv stem>.json.

    Synchronous, unlike the data upload: this is a few kilobytes and finishes
    inside one request, so a background task and a polling endpoint would be
    machinery for nothing.
    """
    object_name = draft.s3_metadata_object
    if not object_name:
        raise ValueError("Upload the data file first — the metadata key is derived from its name.")

    path = store.metadata_path(draft.id)
    if not path.exists():
        raise FileNotFoundError("No generated metadata for this draft.")

    if not settings.fake_s3:
        upload_to_s3(file_path=path, bucket_name=SYSTEM_CONFIG.s3_bucket_name, object_name=object_name)

    draft.s3_metadata_url = f"{SYSTEM_CONFIG.s3_url}/{object_name}"
    return store.save(draft)


# --------------------------------------------------------------------------- #
# Step 4: publish
# --------------------------------------------------------------------------- #


def build_pending_dataset(session: Session, store: DraftStore, draft: PublishDraft) -> Dataset:
    """The row that would be inserted, for review before committing.

    The session is passed through to `from_jsonld` so `parse_creators` reuses
    existing Person rows via this transaction. Omitting it makes the library open
    its own connection, which returns detached objects and inserts duplicate
    people — a unique-constraint violation on republish.
    """
    jsonld = load_metadata(store, draft)
    dataset = Dataset.from_jsonld(jsonld, session=session)

    # Not part of the Croissant document, so they have to be attached here.
    dataset.pelican_uri = draft.pelican_uri
    dataset.pelican_http_url = draft.pelican_http_url
    dataset.croissant_jsonld_url = draft.s3_metadata_url or None
    return dataset


def publish_draft(session: Session, store: DraftStore, draft: PublishDraft) -> int:
    """Insert the dataset and return its new id."""
    dataset = build_pending_dataset(session, store, draft)
    session.add(dataset)
    session.commit()

    dataset_id = dataset.id
    if dataset_id is None:  # pragma: no cover - the insert would have raised
        raise RuntimeError("The dataset was committed without an id.")

    draft.published_dataset_id = dataset_id
    store.save(draft)
    return dataset_id
