# Pokemon TCGP AI Analyst CLI

This is a standalone CLI component for analyzing Pokemon TCGP data using the Gemini LLM and an MCP Semantic Layer (from `semantic_layer/` folder on this project).

## Setup

1. Ensure you have `uv` installed.
2. Set your `GEMINI_API_KEY` environment variable.

## Running

From this directory:

```bash
uv run python main.py
```

Or from the root:

```bash
uv run --package pokemon-tcgp-cli python -m pokemon_cli.main
```

## Testing

```bash
uv run pytest tests/
```
