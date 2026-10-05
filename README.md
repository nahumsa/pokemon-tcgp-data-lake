# Pokemon TCG Data Lake

A component-based data platform for Pokemon tournament analytics.
This project implements an ELT (Extract, Load, Transform) pipeline and exposes its analytical models through an MCP-compatible semantic layer. The agent-facing application layer is intentionally not included while it is being redesigned.

## 🏗 Architecture

The system is designed following the principle of **Separation of Concerns** and **Bounded Contexts**:

1. **Ingestion (`/ingestion`)**: A `dlt` (Data Load Tool) pipeline that scrapes tournament data and participant decklists, loading them into a DuckDB "Bronze/Silver" layer.
2. **Transformations (`/transformations`)**: A `dbt` project that models the raw data into a dimensional "Gold" layer (marts) for analysis.
3. **Semantic Layer (`/semantic_layer`)**: An MCP-compatible server built with `boring-semantic-layer` and `Ibis`. It abstracts complex SQL into semantic entities (Archetypes, Matches, Staples).

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)**: High-performance Python package manager.
- **Docker & Docker Compose** (optional, for containerized execution).

### Installation

1. **Clone the repository**:

    ```bash
    git clone <repo-url>
    cd pokemon-tcg-data-lake
    ```

2. **Synchronize Workspace**:

    ```bash
    uv sync --all-packages --locked
    ```

---

## 🛠 Operational Guide

### 1. Ingestion (EL)

Extract data from tournament sources and load into DuckDB.

```bash
# Run incremental ingestion (current month)
uv run --package pokemon-tcg-ingestion python -m ingestion.main

# Run incremental ingestion (for a specific month)
uv run --package pokemon-tcg-ingestion python -m ingestion.main --month 2026-01

# Run backfill (could take a while)
uv run --package pokemon-tcg-ingestion python -m ingestion.main --backfill
```

### 2. Transformations (T)

Model the data using `dbt`.

```bash
cd transformations
uv run dbt deps
uv run dbt run
```

### Limitless Labs regional and international events

The Labs importer adds the latest three **completed Masters TCG events** to the
same raw tables used by the Limitless Play pipeline. It fetches full standings,
all rounds, and every published decklist. Live events are excluded. Missing
decklists do not exclude players from the participant dimension.

```bash
# Fetch, save a reproducible snapshot, and merge into the local DuckDB database
uv run --package pokemon-tcg-ingestion python -m ingestion.labs --latest 3 --snapshot data/limitless_labs/latest.json.gz

# Reload the checked-in snapshot without fetching from Labs
uv run --package pokemon-tcg-ingestion python -m ingestion.labs --from-snapshot data/limitless_labs/latest.json.gz

cd transformations
uv run dbt deps
uv run dbt seed --profiles-dir .
uv run dbt run --profiles-dir .
uv run dbt test --profiles-dir .
```

Labs URLs identify events separately from Play URLs, so rerunning an import merges
the same event without overwriting Play records. Duplicate player names within an
event receive a `[Labs <participant id>]` suffix in the existing name-based keys;
their original names and source IDs remain in the raw standings table. Pairings
use `0` for ties and `-1` for double losses. Tournament dates use the local calendar
date shown by Labs. The snapshot contains public tournament player names and results.
Labs standings are calculated outside official tournament software and can contain
errors. Labs events use their published archetype labels, including newer decks
absent from the `meta_decks` seed, using the full source label in both archetype
fields because Labs does not publish the seed's parent/variant hierarchy.
Other events continue to use the existing
card-based archetype classifier. Events without published decks have no archetype
data until Labs publishes it. The local dbt profile does not install network
extensions; these transformations operate entirely on the local DuckDB tables.

## 📦 Monorepo Workflow

### Tournament source and event setting

`dim_tournaments`, `mart_tournament_analysis`, and `mart_deck_analysis` expose two
independent attributes. Both are also filterable dimensions in the semantic
layer's `tournament_analysis` and `deck_analysis` models:

| Attribute | Current Play imports | Labs championship imports | Unrecognized legacy URLs |
|-----------|----------------------|---------------------------|--------------------------|
| `source` | `limitless_play` | `limitless_labs` | `unknown` |
| `event_type` | `online` | `in_person` | `unknown` |

New imports record these attributes explicitly. Existing snapshots and raw tables
without the new columns are supported: staging uses known URL prefixes as legacy
defaults, reflecting the current online-only Play importer and Labs championship
scope. Explicit metadata takes precedence, so a future in-person Play event can
still have `source = 'limitless_play'` and `event_type = 'in_person'`.

```sql
select tournament_name, tournament_date, player_count
from main_consumption.mart_tournament_analysis
where source = 'limitless_labs' and event_type = 'in_person';
```

For match-level modeling, join `fct_matches` to `dim_tournaments` on
`tournament_id` and group/filter using these attributes. Existing aggregate
archetype marts retain their current grain and combine sources; filtering those
requires rebuilding the aggregation from the facts with the tournament dimension.

This project uses **uv workspaces** to manage multiple components. When adding dependencies or running commands, you must specify the package name (found in each component's `pyproject.toml`).

### Managing Dependencies

To add a package to a specific component:

```bash
# General syntax
uv add <package-name> --package <internal-package-name>

# Examples
uv add pandas --package pokemon-tcg-ingestion
uv add ibis-framework --package pokemon-tcg-semantic-layer
```

### Running Commands

To run a script or command for a specific component from the root:

```bash
uv run --package <internal-package-name> <command>
```

**Package Reference Table:**

| Component | Directory | Internal Package Name |
|-----------|-----------|-----------------------|
| Ingestion | `ingestion/` | `pokemon-tcg-ingestion` |
| Semantic Layer | `semantic_layer/` | `pokemon-tcg-semantic-layer` |
| Transformations | `transformations/` | `pokemon-tcg-transformations` |

---

## 🐳 Docker Orchestration

The project is fully containerized with optimized multi-stage builds.

```bash
# Build and run the entire stack
docker-compose up -d
```

---

## 🧪 Quality & Standards

### Linting

We use **Ruff** for high-performance Python linting and formatting, and **SQLFluff** for dbt models.

```bash
# Lint Python code
uv run ruff check .

# Lint SQL models
cd transformations
uv run sqlfluff lint models
```

### CI/CD

Our GitHub Actions pipeline (`.github/workflows/ci.yml`) automatically runs SQL and Python linting on every push to `main`.

---
