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

# Reload a snapshot you previously saved locally without fetching from Labs
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
date shown by Labs. Locally saved snapshots contain public tournament player names
and results and are not committed to the repository.
Labs standings are calculated outside official tournament software and can contain
errors. Labs events use their published archetype labels, including newer decks
absent from the `meta_decks` seed. Unambiguous seed labels map to the shared
parent archetype.
`sub_archetype` and `source_archetype_label` preserve the published label;
unknown labels remain their own parent. `classification_method` records whether
the label was mapped, unmapped, or classified from card rules.
Other events continue to use the existing
card-based archetype classifier. Events without published decks have no archetype
data until Labs publishes it. The local dbt profile does not install network
extensions; these transformations operate entirely on the local DuckDB tables.

### CI validation

CI tests ingestion logic with mocked requests, small synthetic inputs, and
isolated temporary DuckDB databases. The tests are independent of saved tournament
snapshots and existing pipeline databases. Native dbt unit tests validate match reconciliation and event counts with mocked
parent models in an in-memory DuckDB database. Ruff and dbt parsing check code
and project configuration without loading tournament data.

To validate a real-data analytics rebuild, fetch the latest events or reload a
locally saved snapshot, then run the dbt commands above. This workflow is separate
from the CI ingestion tests.

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
`tournament_id` and group/filter using these attributes. Aggregate archetype, matchup, card, and monthly marts include `source` and
`event_type` in their grain. Their semantic models expose both dimensions, so
online and in-person populations can be filtered separately or deliberately pooled.
Win rates pool wins and match counts instead of averaging subgroup percentages.

### Archetype classification

See the [classification contract](transformations/docs/archetype_classification.md)
for rule precedence, stable IDs, ruleset versions, and classification coverage.
The `deck_classification` semantic model includes ambiguous and unclassified
entrants; existing archetype analytics retain their classified-only population.

### Tournament match counts

Use `tournament_analysis.unique_match_count` for observed played pairings and
`perspective_record_count` for player-result records. Mirrored histories count as
one pairing; one-sided histories remain countable when both players and the round
are known. Byes and unresolved pairings are disclosed separately. Event totals
also expose duplicate records and conflicting/incomplete outcomes. These are
observed counts, not a guarantee that all event histories were imported.

See the [match-count contract](transformations/docs/match_counts.md) for identity,
normalization, coverage, compatibility aliases, and rebuild instructions.

### Semantic query migration

See the [metric contract](semantic_layer/docs/metrics.md) for formulas, aggregation
grains, denominator populations, draw treatment, and regression checks. All exposed
rates now use percentages (0–100), including `deck_analysis.avg_win_rate` (previously
0–1). Zero denominators return null. Existing `avg_` names denote pooled count
ratios, not averages of percentages.

Population totals now have dedicated models: `monthly_populations.total_participants`
and `archetype_deck_populations.total_archetype_decks`. These count each cohort once,
including unclassified entrants in monthly populations. The corresponding repeated
denominator measures were removed from `monthly_meta_shifts` and `card_staples`.
Monthly `meta_share` and staple `inclusion_rate` are dimensions valid at their full
cohort/category grain; recompute a share from counts when combining cohorts.

Staples and suggestions combine alternate printings by card name within each deck,
and suggestions are unique per source, event type, period, and matchup/card.
`card_staples.card_code` was removed; printing-level analysis remains available in
`cards_used`, whose deck count uses distinct participant IDs. Deck-card membership
and suggestion sample counts are additive observations across cards, not unique
decks or matches: filter to one card when interpreting them as population counts.

This change preserves the existing set-period assignments and player-perspective
match facts. Legality periods, deck coverage reporting, and lifetime player
identities remain separate modeling work. Unique played-match identity and reconciliation coverage
are documented in the match-count contract above.

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

Our GitHub Actions pipeline (`.github/workflows/ci.yml`) runs Ruff, dbt project parsing, ingestion tests, and native dbt unit tests on pull requests and pushes to `main`.

---

