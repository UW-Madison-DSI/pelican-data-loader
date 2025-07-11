from .db import DataRepoEngine, HFDataset


def load_uw_data(
    key: str | None = None, croissant_jsonld_url: str | None = None, db: DataRepoEngine | None = None
) -> HFDataset:
    """Thin wrapper to load a dataset from the database."""

    FAKE_INDEX = {"clo36/bird": "https://web.s3.wisc.edu/pelican-data-loader/metadata/bird_migration_data.json"}

    # Check exclusively OR
    if key is None and croissant_jsonld_url is None:
        raise ValueError("Either 'key' or 'croissant_jsonld_url' must be provided.")
    if key is not None and croissant_jsonld_url is not None:
        raise ValueError("Only one of 'key' or 'croissant_jsonld_url' should be provided.")

    if key:
        croissant_jsonld_url = FAKE_INDEX.get(key)

    if not croissant_jsonld_url:
        raise ValueError("No valid URL found for the provided key.")

    if db is None:
        db = DataRepoEngine()

    record = db.get_dataset(croissant_jsonld_url=croissant_jsonld_url)
    if not record:
        raise ValueError(f"No dataset found for URL: {croissant_jsonld_url}")
    return record.pull()
