"""Health checks and error pages."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlmodel import Session, text

from app.deps import get_db

router = APIRouter()


@router.get("/healthz", include_in_schema=False)
async def healthz() -> JSONResponse:
    """Liveness. Deliberately does not touch the database.

    The container healthcheck calls this, and a Postgres blip must not make
    Docker restart an app that is serving pages perfectly well.
    """
    return JSONResponse({"status": "ok"})


@router.get("/readyz", include_in_schema=False)
def readyz(session: Session = Depends(get_db)) -> JSONResponse:
    """Readiness, including the database. Not used by the container healthcheck."""
    try:
        session.exec(text("SELECT 1"))  # type: ignore[call-overload]
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "unavailable", "detail": str(exc)}, status_code=503)
    return JSONResponse({"status": "ok"})
