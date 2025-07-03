import os
from pathlib import Path
from typing import Optional

import fsspec
import httpx
import minio
import pandas as pd
from dotenv import load_dotenv
from sqlmodel import Session, create_engine, select

from .config import SystemConfig
from .db import Dataset

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    raise ImportError(
        "beautifulsoup4 is required for license pulling functionality. Install it with: pip install beautifulsoup4"
    )


def pull_license(output_path: Optional[str | Path] = None) -> pd.DataFrame:
    """
    Pull license information from SPDX.org and return as DataFrame.

    Args:
        output_path: Optional path to save the data as JSONL. If None, data is not saved.

    Returns:
        DataFrame containing license information with columns:
        - identifier: SPDX license identifier
        - full_name: Full license name
        - url: URL to license details
        - fsf_free_libre: Boolean indicating if FSF Free/Libre
        - osi_approved: Boolean indicating if OSI approved
    """
    url = "https://spdx.org/licenses/"
    response = httpx.get(url)
    page = BeautifulSoup(response.text, "html.parser")
    table = page.find("table")

    if not table or not isinstance(table, Tag):
        raise ValueError("Could not find license table on SPDX page")

    # Deal with the headers
    thead = table.find("thead")
    if not thead or not isinstance(thead, Tag):
        raise ValueError("Could not find table header")

    headers = [th.get_text(strip=True) for th in thead.find_all("th")]
    # rename to more pythonic names
    columns_mapping = {
        "Full name": "full_name",
        "Identifier": "identifier",
        "FSF Free/Libre?": "fsf_free_libre",
        "OSI Approved?": "osi_approved",
    }
    columns = [columns_mapping.get(h, h) for h in headers]

    # Deal with data rows
    rows = []
    base_url = "https://spdx.org/licenses/"

    for tr in table.select("tbody tr"):
        if not isinstance(tr, Tag):
            continue

        row = [td.get_text(strip=True) for td in tr.find_all("td")]
        a_tag = tr.find("a", href=True)

        link = None
        if a_tag and isinstance(a_tag, Tag):
            href = a_tag.get("href")
            if href:
                link = str(href).lstrip("./")
                link = base_url + link if not link.startswith("http") else link

        row.append(link or "")
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns + ["url"])

    # Cast fsf_free_libre and osi_approved to boolean
    df["fsf_free_libre"] = df["fsf_free_libre"].apply(lambda x: x == "Y")
    df["osi_approved"] = df["osi_approved"].apply(lambda x: x == "Y")

    # Reorder columns
    df = df[["identifier", "full_name", "url", "fsf_free_libre", "osi_approved"]]

    # Save to file if output_path is provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_json(output_path, orient="records", lines=True)

    return df


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


def upload_to_s3(file_path: str | Path, bucket_name: str, object_name: Optional[str] = None) -> None:
    """Upload a file to an S3 bucket."""
    client = get_default_s3_client()
    file_path = Path(file_path)
    if not object_name:
        object_name = file_path.name
    client.fput_object(bucket_name, object_name, str(file_path))


def get_s3_filesystem(config: SystemConfig) -> fsspec.AbstractFileSystem:
    return fsspec.filesystem(
        "s3",
        key=config.s3_access_key_id,
        secret=config.s3_secret_access_key,
        client_kwargs={
            "endpoint_url": config.s3_url,
        },
    )


class DatasetEngine:
    """A class to handle metadata operations using SQLModel."""

    def __init__(self, config: SystemConfig):
        self.engine = create_engine(config.metadata_db_engine_url)

    def get_session(self) -> Session:
        """Create a new SQLModel session."""
        return Session(self.engine)

    def list_datasets(self) -> list[Dataset]:
        """List all datasets in the metadata database."""
        with self.get_session() as session:
            statement = select(Dataset)
            return list(session.exec(statement).all())
