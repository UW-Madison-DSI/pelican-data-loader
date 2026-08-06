"""UW-Madison Dataset Repository demo.

FastAPI + Jinja2 + htmx, styled with Tailwind 4 / daisyUI 5. Replaces the earlier
Streamlit app; the library it drives (`pelican_data_loader`) is unchanged.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.errors import RepositoryUnavailable
from app.routers import discover, pages, publish
from app.services.drafts import store
from app.settings import SECRET_KEY_WAS_GENERATED, settings
from app.templating import STATIC_DIR, render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CSS_PATH = STATIC_DIR / "css" / "app.css"


async def _sweep_drafts_forever() -> None:
    """Delete expired drafts so abandoned CSVs cannot fill the disk."""
    while True:
        try:
            removed, remaining = store.sweep()
            if removed:
                logger.info("Swept %d expired draft(s); %.1f MB of drafts remain", removed, remaining / 1e6)
        except Exception:  # noqa: BLE001 - a sweep failure must not kill the loop
            logger.exception("Draft sweep failed")
        await asyncio.sleep(settings.draft_sweep_interval_seconds)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if SECRET_KEY_WAS_GENERATED:
        logger.warning(
            "APP_SECRET_KEY is not set, so a random key was generated. "
            "Every restart will invalidate in-progress publish drafts. Set it in .env."
        )
    if not CSS_PATH.exists():
        logger.warning("%s is missing — run `bun install && bun run build`. The app will render unstyled.", CSS_PATH)

    settings.draft_dir.mkdir(parents=True, exist_ok=True)
    # Nothing can still be uploading across a restart, so clear those flags before
    # serving; otherwise the UI polls a status that will never change.
    interrupted = store.reconcile()
    if interrupted:
        logger.warning("Marked %d in-flight upload(s) as interrupted after restart", interrupted)

    sweeper = asyncio.create_task(_sweep_drafts_forever())
    try:
        yield
    finally:
        sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweeper


app = FastAPI(title="UW-Madison Dataset Repository", lifespan=lifespan, docs_url=None, redoc_url=None)

# Holds only the draft id, the CSRF token, and one-shot flash messages.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="uwdf_session",
    same_site="lax",
    https_only=settings.https_only,
    max_age=settings.draft_ttl_seconds,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(pages.router)
app.include_router(publish.router)
# Last, because it owns "/" and the /datasets/{id} paths.
app.include_router(discover.router)


@app.exception_handler(RepositoryUnavailable)
async def repository_unavailable_handler(request: Request, exc: RepositoryUnavailable) -> HTMLResponse:
    """Show the outage in the page instead of returning an error status.

    htmx does not swap 4xx/5xx responses, so a 503 here would look like a dead
    button. Rendering at 200 also lets the build-time smoke test pass with no
    database available.
    """
    return render(request, "errors/unavailable.html", {"db_error": str(exc)})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> HTMLResponse:
    if exc.status_code == 404:
        return render(request, "errors/404.html", {"detail": exc.detail}, status_code=404)
    return render(
        request,
        "errors/500.html",
        {"detail": exc.detail, "status_code": exc.status_code},
        status_code=exc.status_code,
    )


@app.middleware("http")
async def add_no_store_to_partials(request: Request, call_next):
    """Keep htmx partials out of the browser cache.

    A cached fragment would show a stale upload percentage or a stale result grid
    after a back-navigation.
    """
    response = await call_next(request)
    if request.headers.get("HX-Request") == "true":
        response.headers["Cache-Control"] = "no-store"
    return response
