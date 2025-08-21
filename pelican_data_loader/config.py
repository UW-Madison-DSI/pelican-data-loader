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
    pelican_uri_prefix: str = ""
    pelican_http_url_prefix: str = ""
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = "default"

    @property
    def metadata_db_engine_url(self) -> str:
        """Return the metadata database engine URL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def s3_url(self) -> str:
        return f"{self.s3_endpoint_url}/{self.s3_bucket_name}"

    @property
    def storage_options(self) -> dict[str, Any]:
        """Return storage options for s3fs."""
        return {
            "anon": True,
            "client_kwargs": {"endpoint_url": self.s3_endpoint_url},
        }


SYSTEM_CONFIG = SystemConfig()
