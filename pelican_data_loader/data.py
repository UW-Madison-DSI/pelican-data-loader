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


def delete_from_s3(object_name: str, bucket_name: str | None = None, client: minio.Minio | None = None) -> None:
    """Remove an object from an S3 bucket.

    Removing a key that does not exist is not an error, so callers can retry a
    partially completed cleanup safely.
    """
    if client is None:
        client = get_default_s3_client()

    if not bucket_name:
        bucket_name = SYSTEM_CONFIG.s3_bucket_name

    client.remove_object(bucket_name, object_name)


def s3_object_name_from_url(url: str) -> str | None:
    """Recover the object name from a URL produced against the configured bucket.

    Returns None for an empty URL or one that does not point at this bucket, so
    callers can skip it instead of guessing a key and deleting the wrong object.
    """
    if not url:
        return None

    prefix = f"{SYSTEM_CONFIG.s3_url}/"
    if not url.startswith(prefix):
        return None

    return url.removeprefix(prefix) or None
