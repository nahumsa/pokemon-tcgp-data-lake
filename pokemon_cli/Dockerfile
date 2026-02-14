FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# The CLI container needs the semantic_layer project definition to resolve workspace dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=pokemon_cli/pyproject.toml,target=pokemon_cli/pyproject.toml \
  --mount=type=bind,source=semantic_layer/pyproject.toml,target=semantic_layer/pyproject.toml \
  --mount=type=bind,source=ingestion/pyproject.toml,target=ingestion/pyproject.toml \
  uv sync --frozen --no-install-project --no-dev --package pokemon-tcgp-cli

ADD pokemon_cli /app/pokemon_cli
ADD semantic_layer /app/semantic_layer

RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=pokemon_cli/pyproject.toml,target=pokemon_cli/pyproject.toml \
  --mount=type=bind,source=semantic_layer/pyproject.toml,target=semantic_layer/pyproject.toml \
  --mount=type=bind,source=ingestion/pyproject.toml,target=ingestion/pyproject.toml \
  uv sync --frozen --no-dev --package pokemon-tcgp-cli

FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# CLI is interactive, so we set it up for a shell-like experience
ENTRYPOINT ["python", "-m", "pokemon_cli.main"]
