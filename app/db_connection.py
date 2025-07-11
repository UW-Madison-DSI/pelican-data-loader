from pathlib import Path

import streamlit as st
from sqlmodel import Session, create_engine

from app.state import TypedSessionState

typed_state = TypedSessionState.get_or_create()
DEFAULT_DB_URL = typed_state.system_config.metadata_db_engine_url


@st.cache_resource
def get_database_session(metadata_db_engine_url: str | Path = DEFAULT_DB_URL) -> Session:
    """Create and cache database session."""
    engine = create_engine(str(metadata_db_engine_url), echo=False)
    return Session(engine)
