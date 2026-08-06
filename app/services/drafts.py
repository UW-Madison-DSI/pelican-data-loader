"""Server-side storage for in-progress publish drafts.

htmx keeps no client state and the publish flow spans four steps carrying a
DataFrame, so the draft lives on the server: the browser holds only an opaque id
in a signed cookie, and everything else is a directory on disk.

    {draft_dir}/{draft_id}/draft.json      the PublishDraft model
                          /data.csv        the sanitized CSV
                          /metadata.json   the generated Croissant document

data.csv is the durable artifact rather than a temp file because it is
simultaneously what gets uploaded to S3, what gets hashed, and what the metadata
generator reads — keeping one copy means those three can never disagree.
"""

import logging
import re
import secrets
import shutil
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.schemas import PublishDraft, UploadState
from app.settings import settings

logger = logging.getLogger(__name__)

# A draft id reaches us from a cookie and is joined onto a filesystem path, so it
# is validated rather than trusted. token_urlsafe(16) is always 22 chars.
DRAFT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22}$")

# An upload still "running" this long after it started cannot be alive.
STALE_UPLOAD_AFTER = timedelta(minutes=60)

_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_locks_guard = threading.Lock()


class DraftNotFound(Exception):
    """No draft with that id, or its directory was swept."""


def _lock_for(draft_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks[draft_id]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DraftStore:
    """The only thing that turns a draft id into a path."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or settings.draft_dir)

    # -- paths ------------------------------------------------------------- #

    def _dir(self, draft_id: str) -> Path:
        if not DRAFT_ID_PATTERN.match(draft_id):
            raise DraftNotFound(f"Malformed draft id: {draft_id!r}")
        return self.root / draft_id

    def csv_path(self, draft_id: str) -> Path:
        return self._dir(draft_id) / "data.csv"

    def metadata_path(self, draft_id: str) -> Path:
        return self._dir(draft_id) / "metadata.json"

    def upload_temp_path(self, draft_id: str) -> Path:
        return self._dir(draft_id) / "upload.csv"

    def _json_path(self, draft_id: str) -> Path:
        return self._dir(draft_id) / "draft.json"

    # -- lifecycle --------------------------------------------------------- #

    def create(self) -> PublishDraft:
        draft_id = secrets.token_urlsafe(16)
        self._dir(draft_id).mkdir(parents=True, exist_ok=True)
        draft = PublishDraft(id=draft_id)
        self._write(draft)
        return draft

    def load(self, draft_id: str) -> PublishDraft:
        path = self._json_path(draft_id)
        if not path.exists():
            raise DraftNotFound(draft_id)
        draft = PublishDraft.model_validate_json(path.read_text())
        return self._mark_stale_upload(draft)

    def load_optional(self, draft_id: str | None) -> PublishDraft | None:
        if not draft_id:
            return None
        try:
            return self.load(draft_id)
        except (DraftNotFound, ValueError) as exc:
            logger.info("Ignoring unusable draft %r: %s", draft_id, exc)
            return None

    def _write(self, draft: PublishDraft) -> None:
        draft.updated_at = _utcnow()
        path = self._json_path(draft.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a crash mid-write cannot leave truncated JSON that
        # would make the draft unloadable and lose the user's whole form.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(draft.model_dump_json(indent=2))
        tmp.replace(path)

    def save(self, draft: PublishDraft) -> PublishDraft:
        with _lock_for(draft.id):
            self._write(draft)
        return draft

    def update(self, draft_id: str, **changes) -> PublishDraft:
        """Read-modify-write under the draft's lock.

        Two tabs on one draft are still last-write-wins per field; the lock only
        guarantees a concurrent write cannot interleave and lose unrelated fields.
        """
        with _lock_for(draft_id):
            draft = self.load(draft_id)
            for key, value in changes.items():
                setattr(draft, key, value)
            self._write(draft)
            return draft

    def discard(self, draft_id: str) -> None:
        try:
            shutil.rmtree(self._dir(draft_id), ignore_errors=True)
        except DraftNotFound:
            return

    # -- maintenance ------------------------------------------------------- #

    def _mark_stale_upload(self, draft: PublishDraft) -> PublishDraft:
        """Flip an upload that cannot still be running to `interrupted`.

        Covers both a container restart (see `reconcile`) and an upload whose
        thread died without recording anything, so the UI offers Retry instead of
        polling a status that will never change.
        """
        if draft.upload_state is not UploadState.RUNNING:
            return draft
        started = draft.upload_started_at
        if started is None or _utcnow() - started > STALE_UPLOAD_AFTER:
            draft.upload_state = UploadState.INTERRUPTED
            draft.upload_error = "The upload stopped unexpectedly. The file is still here, so you can retry."
            self._write(draft)
        return draft

    def reconcile(self) -> int:
        """At startup, no upload can still be in flight. Mark them interrupted."""
        count = 0
        for path in self._iter_draft_json():
            try:
                draft = PublishDraft.model_validate_json(path.read_text())
            except ValueError:
                continue
            if draft.upload_state is UploadState.RUNNING:
                draft.upload_state = UploadState.INTERRUPTED
                draft.upload_error = "The server restarted during the upload. The file is still here, so you can retry."
                self._write(draft)
                count += 1
        return count

    def sweep(self) -> tuple[int, int]:
        """Delete drafts untouched for longer than the TTL.

        Returns (drafts removed, bytes remaining) so the caller can log growth.
        """
        cutoff = _utcnow() - timedelta(seconds=settings.draft_ttl_seconds)
        removed = 0
        remaining_bytes = 0

        for path in self._iter_draft_json():
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                shutil.rmtree(path.parent, ignore_errors=True)
                removed += 1
            else:
                remaining_bytes += sum(f.stat().st_size for f in path.parent.rglob("*") if f.is_file())

        return removed, remaining_bytes

    def _iter_draft_json(self):
        if not self.root.exists():
            return
        for child in self.root.iterdir():
            if child.is_dir() and (child / "draft.json").exists():
                yield child / "draft.json"


store = DraftStore()
