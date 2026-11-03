"""Load the YAML model registry against an existing, read-only database."""

from contextlib import contextmanager
import os
from pathlib import Path

import ibis
from boring_semantic_layer import from_config
import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL_CONFIG = Path(__file__).with_name("boring.yml")


class ReadinessError(RuntimeError):
    """The configured database cannot serve the semantic models yet."""


def database_path() -> Path:
    path = Path(
        os.environ.get(
            "POKEMON_TCG_DB_PATH", str(ROOT / ".data" / "pokemon_tcg_pipeline.duckdb")
        )
    ).expanduser()
    if not path.is_absolute():
        raise ReadinessError("POKEMON_TCG_DB_PATH must be an absolute path.")
    return path.resolve()


@contextmanager
def open_models(path: Path | None = None, config_path: Path = MODEL_CONFIG):
    """Keep one registry in YAML and close the connection on every exit path."""
    path = path.resolve() if path is not None else database_path()
    recovery = (
        f"Database: {path}. Set POKEMON_TCG_DB_PATH to the intended absolute path. "
        "From the repository root, ingest with make ingest or make ingest-labs "
        "(or reload an existing snapshot), then run make dbt-build. "
        "Recheck with make mcp-check."
    )
    if not path.is_file():
        raise ReadinessError(f"Database file does not exist. {recovery}")
    try:
        connection = ibis.duckdb.connect(str(path), read_only=True)
    except Exception as exc:
        raise ReadinessError(
            f"Cannot open database read-only: {exc}. {recovery}"
        ) from exc
    try:
        with config_path.open() as handle:
            config = yaml.safe_load(handle)
        tables = {}
        missing = []
        for spec in config.values():
            name, schema = spec["table"], spec["database"]
            try:
                tables[name] = connection.table(name, database=schema)
            except ibis.common.exceptions.TableNotFound:
                missing.append(f"{schema}.{name}")
        if missing:
            raise ReadinessError(
                f"Missing model tables: {', '.join(sorted(set(missing)))}. {recovery}"
            )
        try:
            models = from_config(config, tables=tables)
            # Validate expressions against the current columns without reading rows.
            for name, model in models.items():
                spec = config[name]
                model.query(
                    dimensions=list(spec.get("dimensions", {})),
                    measures=list(spec.get("measures", {})),
                    limit=0,
                ).execute()
        except Exception as exc:
            raise ReadinessError(
                f"Semantic definitions could not load: {exc}. {recovery}"
            ) from exc
        yield path, models
    finally:
        connection.disconnect()
