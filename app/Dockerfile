FROM ghcr.io/astral-sh/uv:python3.12-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY pelican_data_loader ./pelican_data_loader
COPY app ./app
RUN uv sync --frozen

EXPOSE 8501

# Run the Streamlit app
CMD ["uv", "run", "streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]

