# ---------------------------------------------------------------------------
# Stage 1: front-end assets.
#
# Tailwind scans the templates for class names, so they have to be present here
# even though nothing in this stage runs them. Only two built files are carried
# into the runtime image; the whole JS toolchain is discarded.
#
# Debian-based rather than alpine: bun.lock resolves Tailwind's native oxide
# binary for glibc, which is what the lockfile was generated against.
# ---------------------------------------------------------------------------
FROM oven/bun:1 AS assets
WORKDIR /assets

# --frozen-lockfile so the image can never silently drift from bun.lock; the
# pinned daisyUI and Tailwind versions are the point of committing it.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY app/templates ./app/templates
COPY app/static/src ./app/static/src
RUN bun run build


# ---------------------------------------------------------------------------
# Stage 2: runtime.
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Make the synced venv the default interpreter and put the repo root on the
# import path, so `app.*` and `pelican_data_loader.*` resolve regardless of cwd.
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV APP_DRAFT_DIR="/app/var/drafts"

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY pelican_data_loader ./pelican_data_loader
RUN uv sync --frozen --no-dev --group demo

# App sources change most often, so copy them after dependencies are installed
COPY app ./app
COPY --from=assets /assets/app/static/css/app.css ./app/static/css/app.css
COPY --from=assets /assets/app/static/js/htmx.min.js ./app/static/js/htmx.min.js
RUN mkdir -p /app/var/drafts

# Fail the build instead of the deployment if the app cannot render. Also asserts
# the stylesheet above was actually built and picked up the templates.
RUN python app/smoke_test.py

EXPOSE 8000

# Run from the pre-built venv. Invoking `uv run` here would re-resolve
# dependencies (including the dev group) on every container start.
# --proxy-headers so url_for emits https:// behind Traefik and the session
# cookie's Secure flag is meaningful.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
