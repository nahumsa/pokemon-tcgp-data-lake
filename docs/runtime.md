# Reproducible agent workflow

Run `make setup`, then `make check` from the repository root. Setup installs the
locked workspace packages and dbt packages. Subsequent logic checks use installed
packages, synthetic inputs, and temporary databases; they never ingest data.

| Task | Command | Requires tournament data? |
|---|---|---|
| Python lint | `make lint` | No |
| dbt configuration | `make parse` | No |
| Python logic tests | `make test-python` | No |
| Native dbt SQL logic tests | `make test-sql` | No |
| All CI checks | `make check` | No |
| SQL lint | `make lint-sql SQL_PATHS="models/path.sql"` | dbt templating can require upstream schemas |
| Seed and transform imported data | `make dbt-build` | Yes |
| Existing dataset data tests | `make dbt-test` | Yes |
| Semantic readiness | `make mcp-check` | Yes |
| Start MCP | `make mcp` | Yes |

SQL_PATHS are relative to `transformations/`. Logic tests are different from data
tests: native dbt unit tests mock every parent; data tests inspect built tables.
The existing Python tests of semantic expressions and legacy SQL assertions remain
available. Add new SQL model logic tests as native dbt unit tests.

## Isolate each task's data and state

The default is `<repository>/.data/`, so separate worktrees have separate data.
`DATA_DIR` sets both paths for every Make target:

```bash
make DATA_DIR=/absolute/task/data ingest-labs INGEST_ARGS="--latest 1 --snapshot /absolute/task/event.json.gz"
make DATA_DIR=/absolute/task/data dbt-build
make DATA_DIR=/absolute/task/data mcp-check
```

| Variable | Default when using Make | Used by |
|---|---|---|
| `POKEMON_TCG_DB_PATH` | `DATA_DIR/pokemon_tcg_pipeline.duckdb` | Ingestion, dbt, MCP |
| `POKEMON_TCG_DLT_STATE_DIR` | `DATA_DIR/dlt/pipelines` | Both ingestion entry points |

Explicit path overrides must be absolute. The Python entry points default to
`.data/` under their source checkout, independently of the caller's cwd. Direct
dbt commands should be run from `transformations/`, or receive the absolute
database environment variable; Make handles this automatically. The native dbt
`unit` target always uses `:memory:` instead of the persistent database.

For an MCP client launched outside Make, supply `POKEMON_TCG_DB_PATH` explicitly;
see [MCP configuration](../semantic_layer/mcp_config_guide.md). There is one model
registry (`boring.yml`) and no separate MCP database profile. The Compose services
mount the same data directory (`DATA_DIR` or `./.data`) at `/app/.data`.

## Existing database migration

Database files formerly tracked at the repository root and under `semantic_layer/`
are now ignored. Preserve any existing database you need before updating a
checkout. Choose the one containing your actual imported/transformed tables;
do not blindly select an empty file by its name. Make a backup first, then either:

- Keep its current location and export `POKEMON_TCG_DB_PATH=/absolute/existing.duckdb`.
- Copy that database into `.data/pokemon_tcg_pipeline.duckdb` while all writers and
  MCP are stopped. Keep the original backup until queries have been verified.

If retaining an older dlt pipeline directory, set `POKEMON_TCG_DLT_STATE_DIR` to
that directory rather than silently mixing old and new task state. No automatic
migration, deletion, or data download occurs in `make setup` or `make check`.

## MCP preflight

`make mcp-check` opens the selected database read-only, checks the tables listed
in `boring.yml`, and validates model expressions with zero-row queries. Success
prints the database path and model names as JSON. It does not establish coverage,
freshness, or completeness of the underlying event data.

A missing file is an error, not a newly created empty database. Missing tables
are listed together. Load an existing snapshot or ingest using the repository
CLI, run `make dbt-build`, and recheck. A DuckDB lock/read-only configuration error
may require stopping an ingestion/dbt writer before opening MCP. The server closes
its connection after a failed preflight or when serving ends.

## Ingestion failure and replay

Fetches and successful table loads are separate stages. Save snapshots with the
Labs CLI and keep the original failure, load ID, database path, and state directory
when reporting a load error. Never delete task state or fabricate replacement
records to make a run appear successful.

A prior managed-environment run hit `OSError: [Errno 39] Directory not empty` while
dlt moved a completed load package. The underlying cause is still unconfirmed;
path isolation is not claimed to fix that error. Preserve the snapshot and failed
state before diagnosing it. Replaying the saved snapshot through the same CLI in
fresh per-table sessions succeeded in that run, but is not an automatic recovery
policy. Do not download the event again merely to retry a load.

Record exact commands, source/event links, imported row counts, successful/failed
stages, and any recovery steps in the PR. Unit tests remain data-independent;
manual real-data checks are reported separately.
