from pathlib import Path

import streamlit as st
from sqlmodel import Session

from app.state import TypedSessionState
from pelican_data_loader.db import get_session

typed_state = TypedSessionState.get_or_create()
DEFAULT_DB_URL = typed_state.system_config.metadata_db_engine_url


@st.cache_resource
def get_cached_db_session(metadata_db_engine_url: str | Path = DEFAULT_DB_URL) -> Session:
    """Create and cache database session."""
    return get_session(metadata_db_engine_url)
