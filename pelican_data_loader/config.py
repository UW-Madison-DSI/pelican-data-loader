from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class SystemConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    s3_endpoint_url: str
    s3_bucket_name: str
    s3_access_key_id: str
    s3_secret_access_key: str
    mlc_s3_bucket_name: str  # for mlc metadata
    metadata_db_engine_url: str
    wisc_oauth_url: str
    wisc_client_id: str
    wisc_client_secret: str

    @property
    def s3_url(self) -> str:
        return f"https://{self.s3_endpoint_url}/{self.s3_bucket_name}"

    @property
    def metadata_db_path(self) -> Path:
        return Path(self.metadata_db_engine_url.removeprefix("sqlite:///"))
