FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Enable bytecode compilation and use copy mode for links
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first for caching
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=ingestion/pyproject.toml,target=ingestion/pyproject.toml \
  uv sync --frozen --no-install-project --no-dev --package pokemon-tcgp-ingestion

# Add the rest of the project
ADD ingestion /app/ingestion

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=ingestion/pyproject.toml,target=ingestion/pyproject.toml \
  uv sync --frozen --no-dev --package pokemon-tcgp-ingestion

# Final Stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the environment from the builder
COPY --from=builder /app /app

# Set PATH to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Default command runs the ingestion main as a module
ENTRYPOINT ["python", "-m", "ingestion.main"]
