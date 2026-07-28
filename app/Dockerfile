FROM ghcr.io/astral-sh/uv:python3.12-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Make the synced venv the default interpreter and put the repo root on the
# import path, so `app.*` and `pelican_data_loader.*` resolve regardless of cwd.
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY pelican_data_loader ./pelican_data_loader
RUN uv sync --frozen --no-dev

# App sources change most often, so copy them after dependencies are installed
COPY app ./app

# Fail the build instead of the deployment if the app cannot render
RUN python app/smoke_test.py

EXPOSE 8501

# Run the Streamlit app from the pre-built venv. Invoking `uv run` here would
# re-resolve dependencies (including the dev group) on every container start.
CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
