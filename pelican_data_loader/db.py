import json
from pathlib import Path

from sqlmodel import Field, SQLModel, create_engine


def sort_distributions(distributions: dict, extension_priority: list[str]) -> list[dict]:
    """Sort the distribution list in a JSON-LD document by file extension priority."""

    priority = {ext: rank for rank, ext in enumerate(extension_priority)}

    def get_priority(item):
        url = item.get("contentUrl", "")
        for ext, rank in priority.items():
            if url.endswith(ext):
                return rank
        return max(priority.values()) + 1  # Default to a high rank if no extension matches

    return sorted(distributions, key=get_priority)


def guess_primary_url(jsonld: dict, extension_priority: list[str] | None = None) -> dict[str, str]:
    """Guess the primary source URL and checksum from a JSON-LD document."""

    if extension_priority is None:
        extension_priority = [".csv", ".parquet"]

    distributions = jsonld.get("distribution", [])
    if not distributions:
        return {"content_url": "", "sha256": ""}

    distributions = sort_distributions(distributions, extension_priority)
    primary_distribution = distributions[0]
    return {
        "content_url": primary_distribution.get("contentUrl", ""),
        "sha256": primary_distribution.get("sha256", ""),
    }


class Dataset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    version: str
    published_date: str  # ISO 8601 format, e.g., "2023-10-01"
    primary_creator: str
    primary_creator_email: str
    primary_source_url: str
    primary_source_sha256: str
    license: str
    keywords: str = ""  # comma-separated
    croissant_jsonld: str | None = None  # JSON-LD document as a string

    @classmethod
    def from_jsonld(cls, jsonld: dict) -> "Dataset":
        """Create a Dataset instance from a JSON-LD document."""

        source_info = guess_primary_url(jsonld, extension_priority=[".csv", ".parquet"])

        return cls(
            name=jsonld.get("name", ""),
            description=jsonld.get("description", ""),
            version=jsonld.get("version", ""),
            published_date=jsonld.get("datePublished", ""),
            primary_creator=jsonld.get("creator", {}).get("name", ""),
            primary_creator_email=jsonld.get("creator", {}).get("email", ""),
            license=jsonld.get("license", ""),
            keywords=", ".join(jsonld.get("keywords", [])),
            croissant_jsonld=json.dumps(jsonld),
            primary_source_url=source_info["content_url"],
            primary_source_sha256=source_info["sha256"],
        )

    def __str__(self) -> str:
        """String representation of the Dataset."""
        return f"Dataset(id={self.id}, name={self.name}, version={self.version}, published_date={self.published_date})"


def initialize_database(path: Path, wipe: bool = False) -> None:
    """Initialize the SQLite database and create the Dataset table."""

    if wipe and path.exists():
        path.unlink()
    engine = create_engine(f"sqlite:///{path}", echo=True)
    SQLModel.metadata.create_all(engine)
