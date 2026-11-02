"""Explicit, task-local paths for both ingestion entry points."""

import os
from pathlib import Path

import dlt

ROOT = Path(__file__).resolve().parents[1]


def configured_path(variable: str, default: Path) -> Path:
    value = Path(os.environ.get(variable, str(default))).expanduser()
    if not value.is_absolute():
        raise ValueError(f"{variable} must be an absolute path: {value}")
    return value.resolve()


def pipeline_options() -> dict:
    """Select the destination and state without depending on the caller's cwd."""
    database = configured_path(
        "POKEMON_TCG_DB_PATH", ROOT / ".data" / "pokemon_tcg_pipeline.duckdb"
    )
    state = configured_path(
        "POKEMON_TCG_DLT_STATE_DIR", ROOT / ".data" / "dlt" / "pipelines"
    )
    database.parent.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    return {
        "destination": dlt.destinations.duckdb(str(database)),
        "pipelines_dir": str(state),
    }
