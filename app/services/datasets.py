"""Reads and deletes against the published-dataset table.

Deliberately does not use `DataRepoEngine`: its `search_datasets` raises on zero
results (fatal for live search) and its `get_dataset` ORs unset arguments into
`IS NULL`, which can return an unrelated row.
"""

import logging
from collections import Counter

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from app.errors import RepositoryUnavailable
from app.schemas import CreatorOut, DatasetDetail, DatasetSummary, Facet, Facets, Page
from app.services.licenses import license_label
from app.settings import settings
from pelican_data_loader.data import delete_from_s3, s3_object_name_from_url
from pelican_data_loader.db import Dataset

logger = logging.getLogger(__name__)

SORT_OPTIONS = {
    "newest": "Newest first",
    "oldest": "Oldest first",
    "name": "Name A-Z",
}


def _split_keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _to_summary(dataset: Dataset) -> DatasetSummary:
    return DatasetSummary(
        id=dataset.id or 0,
        name=dataset.name,
        version=dataset.version,
        description=dataset.description,
        license=dataset.license,
        keywords=_split_keywords(dataset.keywords),
        published_date=dataset.published_date,
        creators=[CreatorOut(first_name=c.first_name, last_name=c.last_name, email=c.email) for c in dataset.creators],
    )


def _to_detail(dataset: Dataset) -> DatasetDetail:
    return DatasetDetail(
        **_to_summary(dataset).model_dump(),
        primary_source_url=dataset.primary_source_url,
        primary_source_sha256=dataset.primary_source_sha256,
        croissant_jsonld_url=dataset.croissant_jsonld_url or "",
        pelican_uri=dataset.pelican_uri,
        pelican_http_url=dataset.pelican_http_url,
    )


def _filters(query: str, licenses: list[str], keywords: list[str]):
    clauses = []
    if query:
        like = f"%{query}%"
        clauses.append(
            or_(
                col(Dataset.name).ilike(like),
                col(Dataset.description).ilike(like),
                col(Dataset.keywords).ilike(like),
            )
        )
    if licenses:
        clauses.append(col(Dataset.license).in_(licenses))
    # AND across selected keywords: picking two narrows, it does not widen.
    for keyword in keywords:
        clauses.append(col(Dataset.keywords).ilike(f"%{keyword}%"))
    return clauses


def list_datasets(
    session: Session,
    query: str = "",
    licenses: list[str] | None = None,
    keywords: list[str] | None = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int | None = None,
) -> Page[DatasetSummary]:
    """One page of datasets matching the filters, newest first by default."""
    page_size = page_size or settings.page_size
    page = max(1, page)
    clauses = _filters(query, licenses or [], keywords or [])

    # published_date is a zero-padded YYYY-MM-DD string column, so lexicographic
    # ordering is chronological. The id tiebreaker keeps pagination stable when
    # several datasets share a publication date.
    ordering = {
        "name": (col(Dataset.name).asc(), col(Dataset.id).asc()),
        "oldest": (col(Dataset.published_date).asc(), col(Dataset.id).asc()),
    }.get(sort, (col(Dataset.published_date).desc(), col(Dataset.id).desc()))

    try:
        total = session.exec(select(func.count()).select_from(Dataset).where(*clauses)).one()
        rows = session.exec(
            select(Dataset)
            # Eager-load creators: the cards show author names, and without this
            # a grid of N datasets costs N+1 queries.
            .options(selectinload(Dataset.creators))  # type: ignore[arg-type]
            .where(*clauses)
            .order_by(*ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    except SQLAlchemyError as exc:
        logger.warning("Dataset listing failed: %s", exc)
        raise RepositoryUnavailable(str(exc)) from exc

    return Page[DatasetSummary](
        items=[_to_summary(row) for row in rows],
        total=int(total),
        page=page,
        page_size=page_size,
    )


def get_facets(session: Session) -> Facets:
    """License and keyword counts over the whole table.

    Unfiltered on purpose, so a user can always widen a selection rather than
    watching the options they might want disappear. Counted in Python because the
    row count is tiny and it stays portable to SQLite for local development; past
    ~10k rows this becomes
    `SELECT trim(kw), count(*) FROM dataset, unnest(string_to_array(keywords, ',')) kw GROUP BY 1`.
    """
    try:
        rows = session.exec(select(Dataset.license, Dataset.keywords)).all()
    except SQLAlchemyError as exc:
        logger.warning("Facet query failed: %s", exc)
        raise RepositoryUnavailable(str(exc)) from exc

    license_counts: Counter[str] = Counter()
    keyword_counts: Counter[str] = Counter()
    for license_url, keywords in rows:
        if license_url:
            license_counts[license_url] += 1
        for keyword in _split_keywords(keywords):
            keyword_counts[keyword] += 1

    licenses = [
        Facet(value=value, count=count, label=license_label(value))
        for value, count in sorted(license_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    ranked_keywords = sorted(keyword_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_keywords = ranked_keywords[: settings.max_facet_keywords]

    return Facets(
        licenses=licenses,
        keywords=[Facet(value=value, count=count) for value, count in top_keywords],
        keywords_truncated=max(0, len(ranked_keywords) - len(top_keywords)),
    )


def get_dataset_detail(session: Session, dataset_id: int) -> DatasetDetail | None:
    try:
        dataset = session.exec(
            select(Dataset)
            .options(selectinload(Dataset.creators))  # type: ignore[arg-type]
            .where(Dataset.id == dataset_id)
        ).first()
    except SQLAlchemyError as exc:
        logger.warning("Dataset lookup failed: %s", exc)
        raise RepositoryUnavailable(str(exc)) from exc

    return _to_detail(dataset) if dataset else None


def delete_dataset(session: Session, dataset_id: int) -> tuple[str, list[str]]:
    """Delete a dataset's S3 objects and then its row.

    S3 first: removing an object is idempotent, so if the row delete fails the
    whole operation can be retried without leaving orphans behind. A file that
    cannot be removed is reported rather than aborting, because a dataset whose
    files are already gone must still be deletable.

    Returns the dataset name and any warnings to show the user.
    """
    dataset = session.exec(select(Dataset).where(Dataset.id == dataset_id)).first()
    if dataset is None:
        raise LookupError(f"Dataset {dataset_id} not found")

    name = dataset.name
    warnings: list[str] = []

    for label, url in (
        ("data file", dataset.primary_source_url),
        ("metadata file", dataset.croissant_jsonld_url or ""),
    ):
        object_name = s3_object_name_from_url(url)
        if object_name is None:
            warnings.append(f"Skipped the {label}: {url or 'no URL recorded'} is not in the configured S3 bucket.")
            continue
        if settings.fake_s3:
            # Local development must not reach into the real bucket.
            logger.info("APP_FAKE_S3 is set; not deleting %s from S3", object_name)
            continue
        try:
            delete_from_s3(object_name)
        except Exception as exc:  # noqa: BLE001 - any S3 failure is reported, not fatal
            warnings.append(f"Could not delete the {label} ({object_name}) from S3: {exc}")

    try:
        session.delete(dataset)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.warning("Dataset delete failed: %s", exc)
        raise RepositoryUnavailable(str(exc)) from exc

    return name, warnings
