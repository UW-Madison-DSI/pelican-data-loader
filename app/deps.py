"""FastAPI dependencies."""

from collections.abc import Iterator

from sqlmodel import Session

from app.db import SessionFactory


def get_db() -> Iterator[Session]:
    """A session per request, rolled back if the handler raises."""
    with SessionFactory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
