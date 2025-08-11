import logging
from pathlib import Path

from datasets import Dataset as HFBaseDataset
from datasets import DatasetDict, IterableDataset, IterableDatasetDict, load_dataset
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select

from pelican_data_loader.config import SystemConfig

CONFIG = SystemConfig()
HFDataset = IterableDataset | HFBaseDataset | DatasetDict | IterableDatasetDict


def initialize_database(path: str = CONFIG.metadata_db_engine_url, wipe: bool = False) -> None:
    """Initialize the SQLite database and create the Dataset table."""

    engine = create_engine(path, echo=True)

    if wipe:
        SQLModel.metadata.drop_all(engine)

    SQLModel.metadata.create_all(engine)


def get_session(metadata_db_engine_url: str | Path = CONFIG.metadata_db_engine_url) -> Session:
    """Create a new SQLModel session."""
    engine = create_engine(str(metadata_db_engine_url), echo=False)
    return Session(engine)


def guess_primary_url(jsonld: dict, extension_priority: list[str] | None = None) -> dict[str, str]:
    """Guess the primary source URL and checksum from a JSON-LD document."""

    def _sort_distributions(distributions: list[dict], extension_priority: list[str]) -> list[dict]:
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
    should_close_session = False
    if not session:
        logging.warning("No session provided, creating a new one with system defaults.")
        session = Session(create_engine(CONFIG.metadata_db_engine_url, echo=True))
        should_close_session = True

    creators_data = jsonld.get("creator", [])
    if isinstance(creators_data, dict):
        creators_data = [creators_data]

    persons = []
    try:
        for creator_data in creators_data:
            name = creator_data.get("name", "")
            email = creator_data.get("email", "")
            if not name or not email:
                continue

            # Use the existing static method for consistency
            existing_person = Person.find_person_by_email(email, session)

            if existing_person:
                # Reuse existing Person record
                persons.append(existing_person)
            else:
                # Create new Person object
                parts = name.split()
                first_name = parts[0] if parts else ""
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                new_person = Person(first_name=first_name, last_name=last_name, email=email)
                persons.append(new_person)
    finally:
        if should_close_session:
            session.close()

    return persons


class PersonDatasetLink(SQLModel, table=True):
    """Link between Dataset and Person (creator)."""

    dataset_id: int = Field(foreign_key="dataset.id", primary_key=True)
    person_id: int = Field(foreign_key="person.id", primary_key=True)


class Dataset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)  # Ensure non-empty name
    description: str = ""
    version: str = Field(min_length=1)  # Ensure non-empty version
    published_date: str  # ISO 8601 format, e.g., "2023-10-01"
    primary_source_url: str
    primary_source_sha256: str
    license: str = Field(min_length=1)  # Ensure non-empty license
    keywords: str = ""  # comma-separated
    croissant_jsonld_url: str | None = None
    pelican_uri: str = ""
    pelican_http_url: str = ""
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
            primary_source_url=source_info["content_url"],
            primary_source_sha256=source_info["sha256"],
            creators=creators,
        )

    def __str__(self) -> str:
        """String representation of the Dataset."""
        return f"Dataset(id={self.id}, name={self.name}, version={self.version}, published_date={self.published_date})"

    def pull(self) -> HFDataset:
        """Pull the dataset from the primary source URL."""
        if not self.primary_source_url:
            raise ValueError("Primary source URL is not set for this dataset.")

        s3_url = self.primary_source_url.replace(CONFIG.s3_endpoint_url, "s3://")

        # Use the datasets library to load the dataset
        return load_dataset(
            "csv",
            data_files={"train": s3_url},
            storage_options=CONFIG.storage_options,
        )


class Person(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    first_name: str = Field(min_length=1)  # Ensure non-empty first name
    last_name: str = Field(min_length=1)  # Ensure non-empty last name
    email: str = Field(index=True, unique=True, min_length=1)  # Ensure non-empty email
    datasets: list["Dataset"] = Relationship(back_populates="creators", link_model=PersonDatasetLink)

    @staticmethod
    def find_person_by_email(email: str, session: Session) -> "Person | None":
        """Find an existing Person in the database by email.

        Args:
            email: Email address to search for
            session: Database session

        Returns:
            Person: Existing Person record if found, None otherwise
        """
        statement = select(Person).where(Person.email == email)
        result = session.exec(statement)
        return result.first()

    def __str__(self) -> str:
        """String representation of the Person."""
        return f"Person(id={self.id}, name={self.first_name} {self.last_name}, email={self.email})"


class DataRepoEngine:
    """A class to handle metadata operations using SQLModel."""

    def __init__(self, metadata_db_engine_url: str | None = None):
        if metadata_db_engine_url is None:
            metadata_db_engine_url = SystemConfig().metadata_db_engine_url
        self.engine = create_engine(metadata_db_engine_url)

    def get_session(self) -> Session:
        """Create a new SQLModel session."""
        return Session(self.engine)

    def list_datasets(self) -> list[Dataset]:
        """List all datasets in the metadata database."""
        with self.get_session() as session:
            statement = select(Dataset)
            return list(session.exec(statement).all())

    def search_datasets(self, query: str) -> list[Dataset]:
        """Search datasets by name or description."""

        if not query:
            raise ValueError("Query string cannot be empty")

        with self.get_session() as session:
            statement = select(Dataset).where(
                Dataset.name.ilike(f"%{query}%") | Dataset.description.ilike(f"%{query}%")  # type: ignore
            )
            results = session.exec(statement).all()
            if not results:
                raise ValueError(f"No datasets found matching query: {query}")
            return list(results)

    def get_dataset(self, name: str | None = None, id: int | None = None, croissant_jsonld_url: str | None = None) -> Dataset | None:
        """Get a dataset by name or ID."""

        if not name and not id and not croissant_jsonld_url:
            raise ValueError("Either name, id or croissant_jsonld_url must be provided")

        with self.get_session() as session:
            statement = select(Dataset).where((Dataset.name == name) | (Dataset.id == id) | (Dataset.croissant_jsonld_url == croissant_jsonld_url))
            return session.exec(statement).first()

    def delete_dataset(self, id: int) -> None:
        """Delete a dataset from the metadata database."""
        with self.get_session() as session:
            statement = select(Dataset).where(Dataset.id == id)
            dataset = session.exec(statement).first()
            if dataset:
                session.delete(dataset)
                session.commit()
            else:
                raise ValueError(f"Dataset with id {id} not found")
