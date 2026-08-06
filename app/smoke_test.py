"""Render the app once and fail on anything broken.

Run at image build time so an app that cannot start — bad imports, a Jinja syntax
error in a partial, a stylesheet that was never built — fails the build instead of
being deployed. A container healthcheck cannot catch any of these: /healthz keeps
returning "ok" while every page 500s.

Needs no database and no S3 credentials. Database outages surface as an in-page
alert at HTTP 200, which is exactly what the checks below assert.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.licenses import LICENSES
from app.templating import STATIC_DIR, templates

CSS_PATH = STATIC_DIR / "css" / "app.css"
HTMX_PATH = STATIC_DIR / "js" / "htmx.min.js"
MIN_CSS_BYTES = 5_000

failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)
    print(f"FAIL: {message}", file=sys.stderr)


def check_templates_compile() -> int:
    """Compile every template, not just the ones a smoke request reaches.

    A typo in a partial that only renders on an error path would otherwise ship.
    """
    names = templates.env.list_templates()
    for name in names:
        try:
            templates.env.get_template(name)
        except Exception as exc:  # noqa: BLE001
            fail(f"template {name} does not compile: {exc}")
    return len(names)


def check_assets() -> None:
    """Prove the Tailwind build ran and actually scanned the templates.

    Tailwind 4 roots its source detection at the input CSS file's directory, so a
    wrong `@source` in app/static/src/app.css produces a valid stylesheet with no
    component classes in it — a silent, total loss of styling.
    """
    if not CSS_PATH.exists():
        fail(f"{CSS_PATH} is missing — run `bun install && bun run build`")
        return

    size = CSS_PATH.stat().st_size
    if size < MIN_CSS_BYTES:
        fail(f"{CSS_PATH} is only {size} bytes; the Tailwind build looks empty")

    css = CSS_PATH.read_text()
    for selector in (".btn", ".card", ".steps"):
        if selector not in css:
            fail(f"{CSS_PATH} has no `{selector}` rule — check the @source paths in app/static/src/app.css")

    if not HTMX_PATH.exists():
        fail(f"{HTMX_PATH} is missing — run `bun run vendor:js`")


def main() -> int:
    template_count = check_templates_compile()
    check_assets()

    with TestClient(app) as client:
        response = client.get("/healthz")
        if response.status_code != 200 or response.json().get("status") != "ok":
            fail(f"GET /healthz returned {response.status_code} {response.text[:200]}")

        response = client.get("/")
        if response.status_code != 200:
            fail(f"GET / returned {response.status_code}")
        elif "UW–Madison Dataset Repository" not in response.text:
            fail("GET / did not render the site title")
        elif 'id="results"' not in response.text:
            fail("GET / did not render the results container")

        # htmx requests must get a fragment, not a whole document.
        response = client.get("/datasets", headers={"HX-Request": "true"})
        if response.status_code != 200:
            fail(f"GET /datasets (htmx) returned {response.status_code}")
        elif "<html" in response.text:
            fail("GET /datasets (htmx) returned a full page instead of a partial")

        response = client.get("/publish")
        if response.status_code != 200:
            fail(f"GET /publish returned {response.status_code}")
        else:
            if 'id="stepper"' not in response.text:
                fail("GET /publish did not render the stepper")
            missing = [url for url in LICENSES if f'value="{url}"' not in response.text]
            if missing:
                fail(f"GET /publish is missing {len(missing)} license option(s): {missing}")

            token = _extract_csrf(response.text)
            if not token:
                fail("GET /publish did not emit a CSRF token")
            else:
                # Proves the out-of-band stepper contract still holds, which is
                # what keeps wizard progress correct across every step.
                result = client.post(
                    "/publish/step1",
                    data={
                        "csrf_token": token,
                        "name": "Smoke test",
                        "version": "0.0.1",
                        "license": next(iter(LICENSES)),
                    },
                )
                if result.status_code != 200:
                    fail(f"POST /publish/step1 returned {result.status_code}")
                elif "hx-swap-oob" not in result.text:
                    fail("POST /publish/step1 did not emit an out-of-band update")

        response = client.get("/about")
        if response.status_code != 200:
            fail(f"GET /about returned {response.status_code}")

        response = client.get("/datasets/0")
        if response.status_code not in (200, 404):
            fail(f"GET /datasets/0 returned {response.status_code}")

    if failures:
        print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
        return 1

    print(f"OK: {template_count} templates compile, {CSS_PATH.stat().st_size // 1024} KB of CSS, all routes render")
    return 0


def _extract_csrf(html: str) -> str | None:
    import re

    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else None


if __name__ == "__main__":
    # Keep drafts created by the smoke test out of the real draft directory.
    import tempfile

    from app.services.drafts import store

    store.root = Path(tempfile.mkdtemp(prefix="smoke-drafts-"))
    sys.exit(main())
