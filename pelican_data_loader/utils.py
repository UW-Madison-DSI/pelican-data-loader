import hashlib
import logging
from pathlib import Path

import mlcroissant as mlc
import pandas as pd


def get_sha256(path: Path) -> str:
    """Calculate the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_sha256_from_bytes(content: bytes) -> str:
    """Calculate the SHA256 hash of bytes."""
    return hashlib.sha256(content).hexdigest()


def sanitize_name(name: str) -> str:
    """Sanitize a name to be a valid identifier."""
    # Guard: handle empty input early
    if not name:
        return "_"

    # Replace unsafe characters with safe alternatives
    SAFE_MAPPING = {
        "%": "pc",
    }
    for unsafe, safe in SAFE_MAPPING.items():
        name = name.replace(unsafe, safe)

    # Remove invalid characters and replace spaces with underscores
    sanitized_name = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    if name != sanitized_name:
        logging.warning(f"Sanitizing name: '{name}' -> '{sanitized_name}'")
    # Ensure the name starts with a letter or underscore
    if not sanitized_name:
        # In case everything was filtered out
        return "_"
    if not sanitized_name[0].isalpha() and sanitized_name[0] != "_":
        sanitized_name = "_" + sanitized_name
    return sanitized_name


def parse_col(col: pd.Series, parent_id: str) -> mlc.Field:
    """Parse a column of the DataFrame into a Field object."""

    PD_DTYPE_TO_MLC_DTYPE = {
        "bool": mlc.DataType.BOOL,
        "int": mlc.DataType.INTEGER,
        "int8": mlc.DataType.INT8,
        "int16": mlc.DataType.INT16,
        "int32": mlc.DataType.INT32,
        "int64": mlc.DataType.INT64,
        "uint8": mlc.DataType.UINT8,
        "uint16": mlc.DataType.UINT16,
        "uint32": mlc.DataType.UINT32,
        "uint64": mlc.DataType.UINT64,
        "float": mlc.DataType.FLOAT,
        "float16": mlc.DataType.FLOAT16,
        "float32": mlc.DataType.FLOAT32,
        "float64": mlc.DataType.FLOAT64,
        "string": mlc.DataType.TEXT,
        "datetime64[ns]": mlc.DataType.DATE,
        "category": mlc.DataType.TEXT,
        "object": mlc.DataType.TEXT,  # TODO: May need better type for missing values
    }
    col_name = sanitize_name(str(col.name))
    # Normalize pandas dtype string and map with safe fallback
    dtype_str = str(col.dtype).lower()
    mlc_dtype = PD_DTYPE_TO_MLC_DTYPE.get(dtype_str)
    if mlc_dtype is None:
        logging.warning(
            "Unrecognized pandas dtype '%s' for column '%s'; defaulting to TEXT",
            col.dtype,
            col_name,
        )
        mlc_dtype = mlc.DataType.TEXT
    return mlc.Field(
        id=f"{parent_id}/{col_name}",
        name=col_name,
        data_types=[mlc_dtype],
        source=mlc.Source(
            file_object=parent_id,
            extract=mlc.Extract(column=col_name),
        ),
    )
