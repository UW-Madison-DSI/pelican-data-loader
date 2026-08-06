"""Settings for the demo web app, separate from the library's SystemConfig.

Everything here is `APP_`-prefixed so it cannot collide with the library's
env vars. `database_url` exists because `SystemConfig.metadata_db_engine_url` is
a computed property built from POSTGRES_* — a `METADATA_DB_ENGINE_URL` in .env is
accepted by `extra="allow"` and then silently ignored. Set `APP_DATABASE_URL` to
point the app somewhere else (e.g. sqlite for local development).
"""

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="APP_", extra="ignore")

    # Signs the session cookie. Without a stable value every restart invalidates
    # in-progress drafts, so main.py warns loudly when this was generated.
    secret_key: str = ""

    database_url: str = ""

    draft_dir: Path = REPO_ROOT / "var" / "drafts"
    draft_ttl_seconds: int = 86_400
    draft_sweep_interval_seconds: int = 900

    page_size: int = 12
    max_facet_keywords: int = 30
    max_upload_mb: int = 512

    # Set behind a TLS-terminating proxy so the session cookie gets Secure.
    https_only: bool = False

    # Skips the real S3 call and emits synthetic progress, for developing the
    # upload state machine without credentials.
    fake_s3: bool = False

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = AppSettings()

SECRET_KEY_WAS_GENERATED = not settings.secret_key
if SECRET_KEY_WAS_GENERATED:
    settings.secret_key = secrets.token_urlsafe(32)
