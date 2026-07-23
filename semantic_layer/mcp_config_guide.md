# How to use the Pokemon TCG Semantic Layer MCP Server

This server allows an LLM (like Claude) to query the Pokemon TCG Data Lake using a semantic layer.

## 1. Local Configuration for Claude Desktop

Add the following to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pokemon-tcg-semantic": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/pokemon-tcg-data-lake",
        "python",
        "/path/to/pokemon-tcg-data-lake/semantic_layer/semantic_layer/mcp_server.py"
      ]
    }
  }
}
```

Replace `/path/to/pokemon-tcg-data-lake` with the absolute path to this repository.

## 2. Available Tools

The MCP server provides the following tools to the LLM:

- `list_models`: List available semantic models (`archetype_stats`, `cards`, `matches`, `card_staples`).
- `get_model`: Get the schema (dimensions and measures) of a specific model.
- `query_model`: Execute a semantic query.

## 3. Example Queries

You can ask the LLM things like:

- "What are the top 5 archetypes by win rate in the current set?"
- "Compare the win rates of Charizard and Dragapult decks."
- "What cards are most commonly used in Gholdengo decks?"
- "Show me the match results for the 'Gardevoir' archetype in the last tournament."

## 4. Technical Details

- **Database**: DuckDB (`pokemon_tcg_pipeline.duckdb`)
- **Engine**: Ibis + Boring Semantic Layer
- **Transport**: stdio
