# Pokemon TCGP Data Lake & Analytics

A data lake and analytics platform for Pokemon TCG and Pokemon TCG Pocket tournaments, built with `dlt`, `dbt`, and `DuckDB`.

## Features

- **Automated Ingestion**: Scrapes tournament, participant, decklist, and match data from Limitless TCG.
- **Robust Transformation**: Multi-layer dbt project for cleaning, modeling, and analyzing data.
- **DuckDB Powered**: High-performance local analytical database.
- **UV Managed**: Modern Python package management.

## Getting Started

1.  **Install UV**: Ensure you have [uv](https://github.com/astral-sh/uv) installed.
2.  **Sync Dependencies**:
    ```bash
    uv sync
    ```

## Ingestion Pipeline

The ingestion pipeline is built with `dlt` and fetches data directly into DuckDB.

To run the full ingestion:
```bash
uv run -m ingestion.main
```

This will populate the `pokemon_tcgp_data` schema in `pokemon_tcgp_pipeline.duckdb`.

## Transformations (dbt)

Transfomations are located in the `transformations/` directory and use the `dbt-duckdb` adapter.

### Data Layers

- **Staging**: Proper casting, surrogate key generation, and deduplication (using `qualify row_number()`).
- **Semantic**: Dimensional modeling with Facts (`fct_matches`, `fct_deck_composition`) and Dimensions (`dim_tournaments`, `dim_participants`, `dim_cards`).
- **Consumption**: Analytical marts for business-level insights:
    - `mart_tournament_analysis`: Aggregated tournament metrics.
    - `mart_deck_analysis`: Player performance and win rate statistics.
    - `mart_cards_used`: Card frequency and usage analysis across decks.

### Running Transformations

Navigate to the `transformations` directory:
```bash
cd transformations
uv run dbt run --profiles-dir .
uv run dbt test --profiles-dir .
```

## Data Exploration

You can query the results directly using the DuckDB CLI (if installed) or via Python:

```bash
# Example: Check top 5 players by win rate
uv run python -c "import duckdb; print(duckdb.connect('pokemon_tcgp_pipeline.duckdb').sql('SELECT * FROM consumption.mart_deck_analysis LIMIT 5').fetchall())"
```