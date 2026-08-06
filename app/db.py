"""One engine and one session factory for the whole process.

The Streamlit app cached a single `Session` and shared it across every user and
rerun, which meant one failed transaction poisoned every later query. Here each
request gets its own session from a pooled engine instead.
"""

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from app.settings import settings
from pelican_data_loader.config import SYSTEM_CONFIG

DATABASE_URL = settings.database_url or SYSTEM_CONFIG.metadata_db_engine_url

# create_engine does not connect, so an unreachable database cannot break startup
# or the build-time smoke test. pool_pre_ping matters because this is a
# long-lived single replica against a Postgres that gets restarted underneath it.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
    echo=False,
)

# expire_on_commit=False: publish and delete both read attributes off an
# instance after committing, and the default would re-fetch a row that may be gone.
SessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, autoflush=False)
