"""The four-step publish wizard.

State lives in a draft on the server (see app/services/drafts.py); the browser
carries only its id in the signed session cookie. Every step response also
re-renders the stepper out-of-band, so progress stays correct without the page
needing to know which step just finished.

Validation failures are returned at HTTP 200 with the form re-rendered: htmx only
swaps 2xx responses, so a 422 would silently discard the error messages.
"""

import asyncio
import logging
from datetime import datetime, timezone

import anyio.to_thread
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlmodel import Session

from app.csrf import require_csrf
from app.deps import get_db
from app.errors import RepositoryUnavailable
from app.schemas import DraftAuthor, PublishDraft, UploadState
from app.services import ingest
from app.services.drafts import DraftNotFound, store
from app.services.licenses import LICENSES
from app.templating import render

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/publish")

SESSION_DRAFT_KEY = "draft_id"

# Strong references to in-flight upload tasks; see start_s3_upload.
_upload_tasks: set[asyncio.Task] = set()


def _get_or_create_draft(request: Request) -> PublishDraft:
    draft = store.load_optional(request.session.get(SESSION_DRAFT_KEY))
    if draft is None:
        draft = store.create()
        request.session[SESSION_DRAFT_KEY] = draft.id
    return draft


def _require_draft(request: Request) -> PublishDraft:
    draft = store.load_optional(request.session.get(SESSION_DRAFT_KEY))
    if draft is None:
        raise DraftNotFound("No active draft")
    return draft


def _draft_lost(request: Request):
    return render(
        request,
        "partials/_alert.html",
        {
            "level": "error",
            "message": "Your draft has expired or was cleared. Reload the page to start again.",
        },
    )


def _parse_keywords(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _step_context(draft: PublishDraft, **extra) -> dict:
    context = {"draft": draft, "licenses": LICENSES}
    context.update(extra)
    return context


# --------------------------------------------------------------------------- #
# The page
# --------------------------------------------------------------------------- #


@router.get("", response_class=HTMLResponse)
def index(request: Request):
    """Resume wherever the draft left off, or start a fresh one."""
    draft = _get_or_create_draft(request)
    return render(request, "publish/index.html", _step_context(draft))


@router.delete("/draft", dependencies=[Depends(require_csrf)])
def discard(request: Request):
    draft_id = request.session.pop(SESSION_DRAFT_KEY, None)
    if draft_id:
        store.discard(draft_id)
    return Response(status_code=200, headers={"HX-Redirect": "/publish"})


# --------------------------------------------------------------------------- #
# Step 1: metadata
# --------------------------------------------------------------------------- #


@router.post("/step1", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
def save_metadata(
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    version: str = Form(""),
    cite_as: str = Form(""),
    license: str = Form(""),
    keywords: str = Form(""),
):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    errors: dict[str, str] = {}
    if not name.strip():
        errors["name"] = "A dataset name is required."
    if not version.strip():
        errors["version"] = "A version is required."
    if not license:
        errors["license"] = "Choose a license."

    draft.name = name.strip()
    draft.description = description.strip()
    draft.version = version.strip()
    draft.cite_as = cite_as.strip()
    draft.license = license
    draft.keywords = _parse_keywords(keywords)
    store.save(draft)

    return render(
        request,
        "publish/_step1_result.html",
        _step_context(draft, errors=errors, saved=not errors),
    )


@router.post("/authors", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
def add_author(request: Request, author_name: str = Form(""), author_email: str = Form("")):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    error = ""
    if not author_name.strip() or not author_email.strip():
        error = "Please provide both name and email."
    elif any(a.email.lower() == author_email.strip().lower() for a in draft.authors):
        error = "That email is already listed."
    else:
        draft.authors.append(DraftAuthor(name=author_name.strip(), email=author_email.strip()))
        store.save(draft)

    return render(request, "publish/_authors.html", _step_context(draft, author_error=error))


@router.delete("/authors/{index}", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
def remove_author(request: Request, index: int):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    if 0 <= index < len(draft.authors):
        draft.authors.pop(index)
        store.save(draft)

    return render(request, "publish/_authors.html", _step_context(draft))


# --------------------------------------------------------------------------- #
# Step 2: the CSV, then S3
# --------------------------------------------------------------------------- #


@router.post("/upload", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
def upload_csv(request: Request, file: UploadFile):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    if not file.filename:
        return render(request, "publish/_step2_result.html", _step_context(draft, upload_error="Choose a file first."))

    try:
        # file.file is a spooled sync stream; save_uploaded_csv reads it in chunks
        # rather than pulling the whole upload into memory.
        draft = ingest.save_uploaded_csv(store, draft, file.filename, file.file)
    except (ingest.UploadTooLarge, ingest.CsvError) as exc:
        return render(request, "publish/_step2_result.html", _step_context(draft, upload_error=str(exc)))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected failure reading the uploaded CSV")
        return render(
            request, "publish/_step2_result.html", _step_context(draft, upload_error=f"Could not read the file: {exc}")
        )

    return render(request, "publish/_step2_result.html", _step_context(draft))


@router.post("/s3-upload", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
async def start_s3_upload(request: Request):
    """Kick off the upload and return immediately.

    A large file takes minutes, and holding the HTTP connection open that long
    means Traefik idle timeouts and a lost outcome if the tab reloads. Progress
    goes onto the draft instead, where the status endpoint (and any other tab) can
    read it.

    Deliberately not a FastAPI BackgroundTask: Starlette awaits those before the
    ASGI call completes, which would keep the connection occupied for the whole
    upload. A detached task cuts that tie entirely.
    """
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    if not draft.has_csv:
        return render(
            request, "publish/_s3_status_result.html", _step_context(draft, message="Upload a CSV file first.")
        )

    if draft.upload_state is UploadState.RUNNING:
        return render(request, "publish/_s3_status_result.html", _step_context(draft))

    draft = store.update(
        draft.id,
        upload_state=UploadState.RUNNING,
        upload_pct=0,
        upload_error="",
        upload_started_at=datetime.now(timezone.utc),
    )

    # run_data_upload blocks, so it goes to a worker thread. The reference is kept
    # because asyncio only holds a weak one and the task could be collected mid-upload.
    task = asyncio.create_task(anyio.to_thread.run_sync(ingest.run_data_upload, store, draft.id))
    _upload_tasks.add(task)
    task.add_done_callback(_upload_tasks.discard)

    return render(request, "publish/_s3_status_result.html", _step_context(draft))


@router.get("/s3-upload/status", response_class=HTMLResponse)
def s3_upload_status(request: Request):
    """Current upload state. The terminal render drops the polling trigger, so
    the client stops asking on its own."""
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)
    return render(request, "publish/_s3_status_result.html", _step_context(draft))


# --------------------------------------------------------------------------- #
# Step 3: Croissant metadata
# --------------------------------------------------------------------------- #


@router.post("/generate", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
def generate(request: Request):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    if not draft.can_generate:
        return render(
            request,
            "publish/_step3_result.html",
            _step_context(draft, message="Finish steps 1 and 2 before generating metadata."),
        )

    draft = ingest.generate_metadata(store, draft)
    return render(request, "publish/_step3_result.html", _step_context(draft))


@router.get("/metadata.json")
def download_metadata(request: Request):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return RedirectResponse("/publish", status_code=303)

    path = store.metadata_path(draft.id)
    if not path.exists():
        return RedirectResponse("/publish", status_code=303)

    return FileResponse(path, media_type="application/json", filename=draft.metadata_filename)


@router.post("/metadata-upload", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
def upload_metadata(request: Request):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    try:
        draft = ingest.upload_metadata(store, draft)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Metadata upload failed for draft %s", draft.id)
        return render(
            request,
            "publish/_step3_result.html",
            _step_context(draft, metadata_upload_error=str(exc)),
        )

    return render(request, "publish/_step3_result.html", _step_context(draft))


# --------------------------------------------------------------------------- #
# Step 4: publish
# --------------------------------------------------------------------------- #


@router.get("/step4", response_class=HTMLResponse)
def step4(request: Request, session: Session = Depends(get_db)):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    pending = None
    error = ""
    if draft.can_publish:
        try:
            pending = ingest.build_pending_dataset(session, store, draft).model_dump(exclude={"id"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Could not build the pending dataset for draft %s", draft.id)
            error = str(exc)

    return render(request, "publish/_step4_result.html", _step_context(draft, pending=pending, publish_error=error))


@router.post("/publish", response_class=HTMLResponse, dependencies=[Depends(require_csrf)])
def publish(request: Request, session: Session = Depends(get_db)):
    try:
        draft = _require_draft(request)
    except DraftNotFound:
        return _draft_lost(request)

    if not draft.can_publish:
        return render(
            request,
            "publish/_step4_result.html",
            _step_context(draft, publish_error="Generate valid metadata before publishing."),
        )

    try:
        dataset_id = ingest.publish_draft(session, store, draft)
    except RepositoryUnavailable as exc:
        return render(request, "publish/_step4_result.html", _step_context(draft, publish_error=str(exc)))
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.exception("Publishing draft %s failed", draft.id)
        return render(request, "publish/_step4_result.html", _step_context(draft, publish_error=str(exc)))

    # The draft has served its purpose; keeping it would offer a stale wizard on
    # the next visit and leave the CSV on disk.
    store.discard(draft.id)
    request.session.pop(SESSION_DRAFT_KEY, None)
    request.session["flash"] = {"level": "success", "message": f"Published {draft.name}."}
    return Response(status_code=200, headers={"HX-Redirect": f"/datasets/{dataset_id}"})
