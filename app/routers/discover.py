"""Browsing, searching, and deleting published datasets.

Handlers are sync `def` because every one of them does blocking database work;
Starlette runs those in a threadpool, whereas `async def` would block the loop.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from app.csrf import require_csrf
from app.deps import get_db
from app.errors import RepositoryUnavailable
from app.schemas import Facets
from app.services import datasets as dataset_service
from app.services.datasets import SORT_OPTIONS
from app.services.licenses import license_label
from app.settings import settings
from app.templating import is_htmx, render

router = APIRouter()


def _listing_url_builder(query: str, licenses: list[str], keywords: list[str], sort: str):
    """Build a /datasets URL that keeps the current filters, changing only what's passed.

    Pagination and facet links need this: dropping a filter because it wasn't
    restated in the link is the classic way faceted search loses its state.
    """

    def build(**overrides) -> str:
        params: list[tuple[str, str]] = []
        text = overrides.get("q", query)
        if text:
            params.append(("q", text))
        for value in overrides.get("license", licenses):
            params.append(("license", value))
        for value in overrides.get("keyword", keywords):
            params.append(("keyword", value))
        chosen_sort = overrides.get("sort", sort)
        if chosen_sort and chosen_sort != "newest":
            params.append(("sort", chosen_sort))
        page = overrides.get("page", 1)
        if page and int(page) > 1:
            params.append(("page", str(page)))
        suffix = urlencode(params)
        return f"/datasets?{suffix}" if suffix else "/datasets"

    return build


def _listing_context(
    session: Session,
    query: str,
    licenses: list[str],
    keywords: list[str],
    sort: str,
    page: int,
) -> dict:
    results = dataset_service.list_datasets(
        session, query=query, licenses=licenses, keywords=keywords, sort=sort, page=page
    )
    facets = dataset_service.get_facets(session)
    sort = sort if sort in SORT_OPTIONS else "newest"
    return {
        "active_nav": "discover",
        "page_obj": results,
        "facets": facets,
        "query": query,
        "selected_licenses": licenses,
        "selected_keywords": keywords,
        "sort": sort,
        "sort_options": SORT_OPTIONS,
        "license_label": license_label,
        "listing_url": _listing_url_builder(query, licenses, keywords, sort),
    }


def _unavailable_context(exc: RepositoryUnavailable, query: str, sort: str) -> dict:
    return {
        "active_nav": "discover",
        "page_obj": None,
        "facets": Facets(),
        "query": query,
        "selected_licenses": [],
        "selected_keywords": [],
        "sort": sort,
        "sort_options": SORT_OPTIONS,
        "license_label": license_label,
        "listing_url": _listing_url_builder(query, [], [], sort),
        "db_error": str(exc),
    }


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: str = "",
    license: list[str] = Query(default=[]),
    keyword: list[str] = Query(default=[]),
    sort: str = "newest",
    page: int = 1,
    session: Session = Depends(get_db),
):
    try:
        context = _listing_context(session, q.strip(), license, keyword, sort, page)
    except RepositoryUnavailable as exc:
        context = _unavailable_context(exc, q.strip(), sort)
    return render(request, "discover/index.html", context)


@router.get("/datasets", response_class=HTMLResponse)
def listing(
    request: Request,
    q: str = "",
    license: list[str] = Query(default=[]),
    keyword: list[str] = Query(default=[]),
    sort: str = "newest",
    page: int = 1,
    session: Session = Depends(get_db),
):
    """The results grid. A partial for htmx, a full page otherwise, so that the
    URLs htmx pushes stay shareable and survive a reload."""
    try:
        context = _listing_context(session, q.strip(), license, keyword, sort, page)
    except RepositoryUnavailable as exc:
        context = _unavailable_context(exc, q.strip(), sort)

    template = "discover/_results.html" if is_htmx(request) else "discover/index.html"
    return render(request, template, context)


@router.get("/datasets/{dataset_id}", response_class=HTMLResponse)
def detail(request: Request, dataset_id: int, session: Session = Depends(get_db)):
    try:
        dataset = dataset_service.get_dataset_detail(session, dataset_id)
    except RepositoryUnavailable as exc:
        return render(request, "errors/unavailable.html", {"db_error": str(exc)})

    if dataset is None:
        return render(request, "errors/404.html", {"detail": f"No dataset with id {dataset_id}."}, status_code=404)

    return render(
        request,
        "discover/detail.html",
        {"dataset": dataset, "license_label": license_label},
    )


@router.get("/datasets/{dataset_id}/delete-confirm", response_class=HTMLResponse)
def delete_confirm(request: Request, dataset_id: int, session: Session = Depends(get_db)):
    dataset = dataset_service.get_dataset_detail(session, dataset_id)
    if dataset is None:
        return render(request, "partials/_alert.html", {"level": "error", "message": "That dataset no longer exists."})
    return render(request, "discover/_delete_confirm.html", {"dataset": dataset})


@router.get("/datasets/{dataset_id}/delete-cancel", response_class=HTMLResponse)
def delete_cancel(request: Request, dataset_id: int):
    return render(request, "discover/_delete_button.html", {"dataset_id": dataset_id})


@router.delete("/datasets/{dataset_id}", dependencies=[Depends(require_csrf)])
def delete(request: Request, dataset_id: int, session: Session = Depends(get_db)):
    """Delete the dataset, then send the browser back to the listing.

    Failures render an alert at 200 rather than a 4xx/5xx, because htmx does not
    swap error responses and the user would otherwise see nothing happen.
    """
    try:
        name, warnings = dataset_service.delete_dataset(session, dataset_id)
    except LookupError:
        return render(request, "partials/_alert.html", {"level": "error", "message": "That dataset no longer exists."})
    except RepositoryUnavailable as exc:
        return render(
            request,
            "partials/_alert.html",
            {"level": "error", "message": f"Could not delete the dataset record: {exc}"},
        )

    request.session["flash"] = {
        "level": "warning" if warnings else "success",
        "message": f"Deleted {name}." + ("" if not warnings else " " + " ".join(warnings)),
    }
    return Response(status_code=200, headers={"HX-Redirect": "/"})


@router.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return render(request, "about.html", {"page_size": settings.page_size})
