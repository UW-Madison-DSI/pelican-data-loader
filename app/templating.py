"""Jinja environment, template filters, and the htmx-aware render helper."""

import json
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.csrf import get_csrf_token
from app.settings import settings

APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def short_sha(value: str | None, length: int = 16) -> str:
    if not value:
        return ""
    return value[:length]


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)


templates.env.filters["short_sha"] = short_sha
templates.env.filters["pretty_json"] = pretty_json
templates.env.globals["settings"] = settings


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def render(request: Request, template: str, context: dict[str, Any] | None = None, status_code: int = 200):
    """Render `template` with the CSRF token and request always available."""
    ctx: dict[str, Any] = {"csrf_token": get_csrf_token(request)}
    if context:
        ctx.update(context)
    return templates.TemplateResponse(request=request, name=template, context=ctx, status_code=status_code)
