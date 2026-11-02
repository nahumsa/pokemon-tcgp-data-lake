.DEFAULT_GOAL := help
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DATA_DIR ?= $(ROOT)/.data
export POKEMON_TCG_DB_PATH ?= $(abspath $(DATA_DIR))/pokemon_tcg_pipeline.duckdb
export POKEMON_TCG_DLT_STATE_DIR ?= $(abspath $(DATA_DIR))/dlt/pipelines
export RUNTIME__DLTHUB_TELEMETRY := false
export DBT_SEND_ANONYMOUS_USAGE_STATS := false
UV ?= uv
DBT = $(UV) run --locked --package pokemon-tcg-transformations dbt
SQL_PATHS ?= models

.PHONY: check-paths help setup dbt-deps check lint lint-sql parse test-python test-sql dbt-build dbt-test ingest ingest-labs mcp-check mcp
help:
	@printf '%s\n' 'setup        Install locked workspace and dbt dependencies' 'check        Run the same data-independent checks as CI' 'lint         Check Python with Ruff' 'parse        Validate dbt project configuration' 'lint-sql     Check SQL_PATHS with SQLFluff (default: models)' 'test-python  Test ingestion and semantic Python logic' 'test-sql     Run native dbt unit tests in memory' 'dbt-build    Seed and build models against the configured database' 'dbt-test     Run data tests against a built database' 'ingest       Run the Play importer with optional INGEST_ARGS' 'ingest-labs  Run the Labs importer with optional INGEST_ARGS' 'mcp-check    Check existing database and semantic model readiness' 'mcp          Start the read-only semantic MCP server'

setup:
	cd "$(ROOT)" && $(UV) sync --all-packages --locked
	$(MAKE) -C "$(ROOT)" dbt-deps

dbt-deps:
	cd "$(ROOT)/transformations" && $(DBT) deps

check: check-paths lint parse test-python test-sql

check-paths:
	@case "$$POKEMON_TCG_DB_PATH" in /*) ;; *) printf "%s\n" "POKEMON_TCG_DB_PATH must be absolute" >&2; exit 1;; esac
	@case "$$POKEMON_TCG_DLT_STATE_DIR" in /*) ;; *) printf "%s\n" "POKEMON_TCG_DLT_STATE_DIR must be absolute" >&2; exit 1;; esac

lint:
	cd "$(ROOT)" && $(UV) run --locked ruff check .

lint-sql:
	cd "$(ROOT)/transformations" && $(UV) run --locked sqlfluff lint $(SQL_PATHS)

parse:
	cd "$(ROOT)/transformations" && $(DBT) parse --profiles-dir . --target unit --no-partial-parse

test-python:
	cd "$(ROOT)" && $(UV) run --locked pytest

test-sql:
	cd "$(ROOT)/transformations" && $(DBT) test --profiles-dir . --target unit --select test_type:unit

dbt-build: check-paths
	mkdir -p "$(dir $(POKEMON_TCG_DB_PATH))"
	cd "$(ROOT)/transformations" && $(DBT) seed --profiles-dir .
	cd "$(ROOT)/transformations" && $(DBT) run --profiles-dir .

dbt-test: check-paths
	cd "$(ROOT)/transformations" && $(DBT) test --profiles-dir . --select test_type:data

ingest: check-paths
	cd "$(ROOT)" && $(UV) run --locked --package pokemon-tcg-ingestion python -m ingestion.main $(INGEST_ARGS)

ingest-labs: check-paths
	cd "$(ROOT)" && $(UV) run --locked --package pokemon-tcg-ingestion python -m ingestion.labs $(INGEST_ARGS)

mcp-check: check-paths
	cd "$(ROOT)" && $(UV) run --locked --package pokemon-tcg-semantic-layer python -m semantic_layer.mcp_server --check

mcp: check-paths
	cd "$(ROOT)" && $(UV) run --locked --package pokemon-tcg-semantic-layer python -m semantic_layer.mcp_server
