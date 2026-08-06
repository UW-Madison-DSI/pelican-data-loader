"""CSRF tokens backed by the signed session cookie.

Streamlit had XSRF protection enabled; a plain form app has none, so every unsafe
method needs a token. The token lives in the session (which the client cannot
forge), and is presented either as a hidden form field or as the X-CSRF-Token
header that htmx sends from `hx-headers` on <body>.
"""

import secrets

from fastapi import HTTPException, Request, status

SESSION_KEY = "csrf_token"
FORM_FIELD = "csrf_token"
HEADER_NAME = "X-CSRF-Token"


def get_csrf_token(request: Request) -> str:
    """Return this session's token, minting one on first use."""
    token = request.session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = token
    return token


async def require_csrf(request: Request) -> None:
    """Reject an unsafe request whose token does not match the session."""
    if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
        return

    expected = request.session.get(SESSION_KEY)
    provided = request.headers.get(HEADER_NAME)

    if not provided:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
            form = await request.form()
            value = form.get(FORM_FIELD)
            provided = value if isinstance(value, str) else None

    if not expected or not provided or not secrets.compare_digest(expected, provided):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid. Reload the page and try again.")
