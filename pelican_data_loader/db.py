import json
from pathlib import Path

from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select


def initialize_database(path: Path, wipe: bool = False) -> None:
    """Initialize the SQLite database and create the Dataset table."""

    if wipe and path.exists():
        path.unlink()
    engine = create_engine(f"sqlite:///{path}", echo=True)
    SQLModel.metadata.create_all(engine)


def guess_primary_url(jsonld: dict, extension_priority: list[str] | None = None) -> dict[str, str]:
    """Guess the primary source URL and checksum from a JSON-LD document."""

    def _sort_distributions(distributions: dict, extension_priority: list[str]) -> list[dict]:
        """Sort the distribution list in a JSON-LD document by file extension priority."""
        priority = {ext: rank for rank, ext in enumerate(extension_priority)}

        def get_priority(item):
            url = item.get("contentUrl", "")
            for ext, rank in priority.items():
                if url.endswith(ext):
                    return rank
            return max(priority.values()) + 1  # Last priority for unknown extensions

        return sorted(distributions, key=get_priority)

    if extension_priority is None:
        extension_priority = [".csv", ".parquet"]

    distributions = jsonld.get("distribution")
    if not distributions:
        return {"content_url": "", "sha256": ""}

    distributions = _sort_distributions(distributions, extension_priority)
    primary_distribution = distributions[0]
    return {
        "content_url": primary_distribution.get("contentUrl", ""),
        "sha256": primary_distribution.get("sha256", ""),
    }


def parse_creators(jsonld: dict, session: Session | None = None) -> list["Person"]:
    """Parse creators from a JSON-LD document into Person objects."""
    creators_data = jsonld.get("creator", [])
    if isinstance(creators_data, dict):
        creators_data = [creators_data]

    persons = []
    for creator_data in creators_data:
        name = creator_data.get("name", "")
        email = creator_data.get("email", "")
        if not name or not email:
            continue

        if session:
            statement = select(Person).where(Person.email == email)
            result = session.exec(statement)
            person = result.first()
            if person:
                persons.append(person)
                continue

        parts = name.split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        persons.append(Person(first_name=first_name, last_name=last_name, email=email))
    return persons


class PersonDatasetLink(SQLModel, table=True):
    """Link between Dataset and Person (creator)."""

    dataset_id: int = Field(foreign_key="dataset.id", primary_key=True)
    person_id: int = Field(foreign_key="person.id", primary_key=True)


class Dataset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    version: str
    published_date: str  # ISO 8601 format, e.g., "2023-10-01"
    primary_source_url: str
    primary_source_sha256: str
    license: str
    keywords: str = ""  # comma-separated
    croissant_jsonld: str | None = None  # JSON-LD document as a string
    creators: list["Person"] = Relationship(back_populates="datasets", link_model=PersonDatasetLink)

    @classmethod
    def from_jsonld(cls, jsonld: dict, session: Session | None = None) -> "Dataset":
        """Create a Dataset instance from a JSON-LD document."""

        source_info = guess_primary_url(jsonld, extension_priority=[".csv", ".parquet"])
        creators = parse_creators(jsonld, session=session)

        return cls(
            name=jsonld.get("name", ""),
            description=jsonld.get("description", ""),
            version=jsonld.get("version", ""),
            published_date=jsonld.get("datePublished", ""),
            license=jsonld.get("license", ""),
            keywords=", ".join(jsonld.get("keywords", [])),
            croissant_jsonld=json.dumps(jsonld),
            primary_source_url=source_info["content_url"],
            primary_source_sha256=source_info["sha256"],
            creators=creators,
        )

    def __str__(self) -> str:
        """String representation of the Dataset."""
        return f"Dataset(id={self.id}, name={self.name}, version={self.version}, published_date={self.published_date})"


class Person(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    email: str = Field(index=True, unique=True)
    datasets: list["Dataset"] = Relationship(back_populates="creators", link_model=PersonDatasetLink)
