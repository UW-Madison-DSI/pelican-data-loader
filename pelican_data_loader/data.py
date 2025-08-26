from pathlib import Path

import minio

from .config import SYSTEM_CONFIG


def get_default_s3_client() -> minio.Minio:
    """Get a MinIO client instance from environment variables."""

    endpoint = SYSTEM_CONFIG.s3_endpoint_url.split("://")[-1]
    return minio.Minio(
        endpoint=endpoint,
        access_key=SYSTEM_CONFIG.s3_access_key_id,
        secret_key=SYSTEM_CONFIG.s3_secret_access_key,
    )


def upload_to_s3(file_path: str | Path, bucket_name: str | None = None, object_name: str | None = None, client: minio.Minio | None = None) -> None:
    """Upload a file to an S3 bucket."""
    if client is None:
        client = get_default_s3_client()
    file_path = Path(file_path)
    if not object_name:
        object_name = file_path.name

    if not bucket_name:
        bucket_name = SYSTEM_CONFIG.s3_bucket_name

    client.fput_object(bucket_name, object_name, str(file_path))
