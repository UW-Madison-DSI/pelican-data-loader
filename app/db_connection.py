from pathlib import Path

import streamlit as st
from sqlmodel import Session

from pelican_data_loader.config import SystemConfig
from pelican_data_loader.db import get_session


@st.cache_resource
def get_cached_db_session(metadata_db_engine_url: str | Path | None = None) -> Session:
    """Create and cache a database session.

    Falls back to the system configuration when no URL is given. The default is
    resolved lazily so importing this module does not touch st.session_state,
    which is unavailable outside a script run context.
    """
    if metadata_db_engine_url is None:
        metadata_db_engine_url = SystemConfig().metadata_db_engine_url
    return get_session(metadata_db_engine_url)
