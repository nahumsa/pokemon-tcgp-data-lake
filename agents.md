# Agents Guide

This document is designed to assist AI Agents and Developers in understanding the architectural roles, specialized contexts, and operational guidelines for this repository. Remember that after every change, run the linter and fix the code accordingly.

## Project Context

This is a **Pokemon TCG / TCG Pocket Data Lake** containing:

1. **Ingestion Layer**: Python scripts using `dlt` to scrape Limitless TCG.
2. **Storage Layer**: Local `DuckDB` database (`pokemon_tcgp_pipeline.duckdb`).
3. **Transformation Layer**: A `dbt` project for cleaning and modeling data.

## Specialized Agent Roles

When working on this codebase, assume one of the following roles based on the task:

### 1. Ingestion Specialist

**Focus**: Data scraping, HTML parsing, and pipeline stability.

- **Directory**: `ingestion/`
- **Key Libraries**: `dlt`, `requests`, `selectolax`, `pydantic`.
- **Core Components**:
  - `extractors.py`: Contains specific scraping logic. **Critical**: Handles HTML parsing (CSS selectors) and data cleaning.
  - `models.py`: Pydantic models (`Participant`, `Deck`, `Match`) defining the schema.
  - `main.py`: The entry point for the `dlt` pipeline.
- **Guidelines**:
  - Always use `HEADERS` from `constants.py` to avoid anti-bot blocks.
  - Handle missing data gracefully (e.g., missing decklists or match history).
  - Respect the `dlt` resource/transformer patterns.

### 2. Analytics Engineer

**Focus**: Data modeling, SQL transformations, and data quality.

- **Directory**: `transformations/`
- **Key Tools**: `dbt`, `DuckDB`, `SQL`.
- **Architecture**:
  - **Staging (`models/staging`)**: Raw views. **Must** perform deduplication using `qualify row_number()` on `_dlt_load_id` to handle append-only ingestion.
  - **Semantic (`models/semantic`)**: The "business logic" layer. Joins `tournaments`, `participants`, and `cards`.
  - **Consumption (`models/consumption`)**: Final marts for reporting. Aggregated stats (win rates, card usage).
- **Guidelines**:
  - Run `uv run dbt test --profiles-dir .` after *any* SQL change.
  - Use `dbt_utils.generate_surrogate_key` for primary keys.
  - Materialize Semantic and Consumption models as `table`.

### 3. Data Analyst

**Focus**: Querying insights and verifying results.

- **Target**: `pokemon_tcgp_pipeline.duckdb`
- **Key Schema**: `consumption` (via dbt) or `pokemon_tcgp_data` (raw).
- **Guidelines**:
  - Query the `consumption` layer for reliable metrics (`mart_deck_analysis`, `mart_cards_used`).
  - Use `duckdb` CLI or Python `duckdb.connect()` for exploration.

## Operational Commands

### Package Management (UV)

- Add dependency: `uv add <package>`
- Run script: `uv run <script.py>`

### Ingestion

- Full Run: `uv run -m ingestion.main`

### Transformation

- Run Models: `cd transformations && uv run dbt run --profiles-dir .`
- Test Models: `cd transformations && uv run dbt test --profiles-dir .`

### Lint

- Fix Models: `cd transformations && uv run sqlfluff fix models`
- Lint Models: `cd transformations && uv run sqlfluff lint models`
