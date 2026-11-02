# Semantic layer and analytical agents

- `semantic_layer/boring.yml` is the model/table/measure registry. `runtime.py`
  loads it once; avoid adding a second hand-maintained table map.
- MCP uses an existing database in read-only mode. Importing the server must not
  connect to DuckDB or require populated tables. Preserve actionable startup
  failures and run `make mcp-check` against a deliberately selected built database.
- Test Python runtime and Ibis/semantic-expression behavior with temporary fixture
  databases via `make test-python`; SQL transformations use dbt unit tests.
- Before answering analytical questions, inspect available models/dimensions,
  choose compatible cohorts, and use recorded counts for denominators. Explain
  missing coverage, sample size, date/source, and metric units. Do not invent
  filters, treat aliases as new metrics, or describe associations as causation.
- Link [metrics](docs/metrics.md) and
  [match counts](../transformations/docs/match_counts.md) for definitions. Keep
  provider/event provenance with reported results. See root `AGENTS.md` for the
  full analytical and handoff requirements.
