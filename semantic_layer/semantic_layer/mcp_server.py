#!/usr/bin/env python3
"""Serve production semantic models over MCP against an explicit read-only database."""

import argparse
import os
from pathlib import Path

import ibis
import yaml
from boring_semantic_layer import MCPSemanticModel, from_yaml

CONFIG = Path(__file__).with_name("boring.yml")
DEFAULT_DATABASE = Path(__file__).resolve().parents[2] / "pokemon_tcg_pipeline.duckdb"


def create_server(database, config_path=CONFIG):
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError(
            f"Warehouse does not exist: {database}; build dbt models first"
        )
    definitions = yaml.safe_load(Path(config_path).read_text())
    connection = ibis.duckdb.connect(str(database), read_only=True)
    try:
        tables = {
            item["table"]: connection.table(item["table"], database=item["database"])
            for item in definitions.values()
        }
        models = from_yaml(str(config_path), tables=tables)
        server = MCPSemanticModel(
            models=models, name="Pokemon TCG Data Lake Semantic Layer"
        )
        server.warehouse_connection = connection
        return server
    except Exception:
        connection.disconnect()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=os.environ.get("PTCG_DATABASE_PATH", DEFAULT_DATABASE),
    )
    args = parser.parse_args()
    server = create_server(args.database)
    try:
        server.run(transport="stdio", show_banner=False)
    finally:
        server.warehouse_connection.disconnect()


if __name__ == "__main__":
    main()
