# Pokemon TCG Semantic Layer MCP

Run `make setup`, ingest or reload the intended data, then run `make dbt-build`
and `make mcp-check` from the repository root. To select another database, set
`POKEMON_TCG_DB_PATH` to its absolute path. MCP opens that existing file read-only.
Missing tables/columns produce an actionable startup error rather than an empty
new database. See the [runtime runbook](../docs/runtime.md).

## Client configuration

For a stdio MCP client such as Claude Desktop:

```json
{
  "mcpServers": {
    "pokemon-tcg-semantic": {
      "command": "uv",
      "args": [
        "run", "--locked", "--project", "/absolute/pokemon-tcgp-data-lake",
        "--package", "pokemon-tcg-semantic-layer",
        "python", "-m", "semantic_layer.mcp_server"
      ],
      "env": {
        "POKEMON_TCG_DB_PATH": "/absolute/task/data/pokemon_tcg_pipeline.duckdb"
      }
    }
  }
}
```

Replace both absolute paths with your checkout and intended database. The module
entry point works outside the checkout after `make setup`. To preflight directly,
use the same arguments plus `--check` after the module name; it exits nonzero on
failure and does not start the MCP transport.

## Discover before querying

Use `list_models`, then `get_model` to inspect available dimensions/measures before
calling `query_model`. `semantic_layer/boring.yml` is the single model registry,
including table names and schemas. Do not maintain another table map in a client.

Follow the [metric contract](docs/metrics.md),
[match-count contract](../transformations/docs/match_counts.md), and
[component agent instructions](AGENTS.md). For analytical answers:

- Identify game/source, event or period, actual supported filters, and units.
- Include supporting player/deck/match sample counts and provenance links.
- Disclose missing coverage or freshness information; unknown does not mean zero.
- Keep player-result counts separate from unique played pairings.
- Use pooled counts for rates; card comparisons describe observed associations.

MCP preflight validates tables and expressions, not the completeness of an event.
The retired `test_queries.py` script is removed; use `make test-python` for semantic
runtime/expression tests and `make mcp-check` for a selected built database.
