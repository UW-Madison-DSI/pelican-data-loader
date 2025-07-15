from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class SystemConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")
    s3_endpoint_url: str = ""
    s3_bucket_name: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    wisc_oauth_url: str = ""
    wisc_client_id: str = ""
    wisc_client_secret: str = ""
    metadata_db_engine_url: str = ""

    @property
    def s3_url(self) -> str:
        return f"{self.s3_endpoint_url}/{self.s3_bucket_name}"

    @property
    def metadata_db_path(self) -> Path:
        return Path(self.metadata_db_engine_url.removeprefix("sqlite:///"))

    @property
    def storage_options(self) -> dict[str, Any]:
        """Return storage options for s3fs."""
        return {
            "anon": True,
            "client_kwargs": {"endpoint_url": self.s3_endpoint_url},
        }


SYSTEM_CONFIG = SystemConfig()
