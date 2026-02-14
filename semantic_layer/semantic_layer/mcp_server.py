#!/usr/bin/env python3
"""
MCP Server for the Pokemon TCG Data Lake Semantic Layer.
Exposes semantic models for archetypes, cards, and matches via Model Context Protocol.
"""
import ibis
from pathlib import Path
from typing import Dict, Any
from boring_semantic_layer import MCPSemanticModel, from_yaml

# Define paths
base_dir: Path = Path(__file__).parent
yaml_path: Path = base_dir / "boring.yml"

# Pre-load tables from specific DuckDB schemas
# Boring Semantic Layer uses Ibis under the hood
con: Any = ibis.duckdb.connect(str(base_dir.parent.parent / "pokemon_tcgp_pipeline.duckdb"))
tables: Dict[str, Any] = {
    "mart_archetype_stats": con.table("mart_archetype_stats", database="main_consumption"),
    "dim_cards": con.table("dim_cards", database="main_semantic"),
    "fct_matches": con.table("fct_matches", database="main_semantic"),
    "mart_archetype_card_staples": con.table("mart_archetype_card_staples", database="main_consumption"),
    "mart_archetype_matchups": con.table("mart_archetype_matchups", database="main_consumption"),
}

# Load semantic models from boring.yml
models: Dict[str, Any] = from_yaml(str(yaml_path), tables=tables)

# Create and configure MCP server
server: MCPSemanticModel = MCPSemanticModel(
    models=models,
    name="Pokemon TCG Data Lake Semantic Layer Server",
)

if __name__ == "__main__":
    # Start the MCP server using stdio transport
    server.run()
