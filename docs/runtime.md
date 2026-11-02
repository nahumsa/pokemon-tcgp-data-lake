# Runtime paths and migration

Run `make setup`, then `make check` from the repository root. Logic checks use
synthetic inputs and temporary/in-memory databases, not downloaded events.

## Isolate data and state

Defaults live under `<repository>/.data/`. Separate worktrees therefore have
separate runtime paths. Use `make DATA_DIR=/absolute/task/data <target>` to select
another task directory. Both ingestion entry points use `POKEMON_TCG_DB_PATH` and
`POKEMON_TCG_DLT_STATE_DIR` for their database and dlt pipelines directory. MCP and
dbt use the same database variable. Explicit overrides must be absolute paths.
Direct dbt commands should run from `transformations/` or receive the absolute
database environment variable; Make handles this automatically.

```bash
make DATA_DIR=/absolute/task/data ingest-labs INGEST_ARGS="--latest 1 --snapshot /absolute/task/event.json.gz"
make DATA_DIR=/absolute/task/data dbt-build
make DATA_DIR=/absolute/task/data dbt-test
```

The Compose services share a directory mount (`DATA_DIR` or `./.data`) at
`/app/.data`. The dbt `unit` target always uses an in-memory database.

## Existing databases

The old database files at the repository root and under `semantic_layer/` are no
longer tracked. Preserve any database you need before updating a checkout. Back
up the database containing your actual tables, stop writers/MCP, then either set
`POKEMON_TCG_DB_PATH=/absolute/existing.duckdb` or copy it into
`.data/pokemon_tcg_pipeline.duckdb`. Keep the backup until queries are verified.
If retaining prior dlt state, set `POKEMON_TCG_DLT_STATE_DIR` to that pipelines
directory. No automatic data migration or deletion is performed.

Use the repository importer and its snapshot replay for real data. Preserve
snapshots and failed load state when diagnosing errors; do not invent records or
remove another task's state. Path isolation does not claim to fix the previously
observed dlt completed-package directory collision.
