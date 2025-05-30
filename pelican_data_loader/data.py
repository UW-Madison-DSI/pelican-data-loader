import os

import minio
from dotenv import load_dotenv


def get_default_s3_client() -> minio.Minio:
    """Get a MinIO client instance from environment variables."""

    load_dotenv()

    # Check if the environment variables are set
    if not (s3_endpoint_url := os.getenv("S3_ENDPOINT_URL")):
        raise ValueError("S3_ENDPOINT_URL environment variable is not set.")
    if not (s3_access_key_id := os.getenv("S3_ACCESS_KEY_ID")):
        raise ValueError("S3_ACCESS_KEY_ID environment variable is not set.")
    if not (s3_secret_access_key := os.getenv("S3_SECRET_ACCESS_KEY")):
        raise ValueError("S3_SECRET_ACCESS_KEY environment variable is not set.")

    return minio.Minio(
        endpoint=s3_endpoint_url,
        access_key=s3_access_key_id,
        secret_key=s3_secret_access_key,
    )
