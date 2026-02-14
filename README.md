# Pokemon TCGP Data Lake & AI Analyst

An enterprise-grade data platform for Pokemon TCG Pocket, featuring a component-based monorepo architecture.
This project implements a full ELT (Extract, Load, Transform) pipeline, a semantic layer via MCP (Model Context Protocol), and an AI-powered Analyst CLI using Google's Gemini.

## 🏗 Architecture

The system is designed following the principle of **Separation of Concerns** and **Bounded Contexts**:

1. **Ingestion (`/ingestion`)**: A `dlt` (Data Load Tool) pipeline that scrapes tournament data and participant decklists, loading them into a DuckDB "Bronze/Silver" layer.
2. **Transformations (`/transformations`)**: A `dbt` project that models the raw data into a dimensional "Gold" layer (marts) for analysis.
3. **Semantic Layer (`/semantic_layer`)**: An MCP-compatible server built with `boring-semantic-layer` and `Ibis`. It abstracts complex SQL into semantic entities (Archetypes, Matches, Staples).
4. **AI Analyst CLI (`/pokemon_cli`)**: A Python CLI using the **Gateway** and **Controller** patterns. It integrates with Gemini to allow natural language querying of the semantic layer.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)**: High-performance Python package manager.
- **Docker & Docker Compose** (optional, for containerized execution).
- **Gemini API Key**: Obtain from [Google AI Studio](https://aistudio.google.com/).

### Installation

1. **Clone the repository**:

    ```bash
    git clone <repo-url>
    cd pokemon-tcgp-data-lake
    ```

2. **Set Environment Variables**:

    ```bash
    export GEMINI_API_KEY="your-key-here"
    ```

3. **Synchronize Workspace**:

    ```bash
    uv sync
    ```

---

## 🛠 Operational Guide

### 1. Ingestion (EL)

Extract data from tournament sources and load into DuckDB.

```bash
# Run incremental ingestion (current month)
uv run --package pokemon-tcgp-ingestion python ingestion/main.py

# Run incremental ingestion (for a specific month)
uv run --package pokemon-tcgp-ingestion python ingestion/main.py 2026-01

# Run backfill (could take a while)
uv run --package pokemon-tcgp-ingestion python ingestion/main.py --backfill
```

### 2. Transformations (T)

Model the data using `dbt`.

```bash
cd transformations
uv run dbt deps
uv run dbt run
```

### 3. AI Analyst Chat (The "UI")

Engage with the data using natural language.

```bash
# Run the CLI
uv run --package pokemon-tcgp-cli python -m pokemon_cli.main
```

---

## 📦 Monorepo Workflow

This project uses **uv workspaces** to manage multiple components. When adding dependencies or running commands, you must specify the package name (found in each component's `pyproject.toml`).

### Managing Dependencies

To add a package to a specific component:
```bash
# General syntax
uv add <package-name> --package <internal-package-name>

# Examples
uv add pandas --package pokemon-tcgp-ingestion
uv add rich --package pokemon-tcgp-cli
```

### Running Commands

To run a script or command for a specific component from the root:
```bash
uv run --package <internal-package-name> <command>
```

**Package Reference Table:**
| Component | Directory | Internal Package Name |
|-----------|-----------|-----------------------|
| Ingestion | `ingestion/` | `pokemon-tcgp-ingestion` |
| Semantic Layer | `semantic_layer/` | `pokemon-tcgp-semantic-layer` |
| Analyst CLI | `pokemon_cli/` | `pokemon-tcgp-cli` |
| Transformations | `transformations/` | `pokemon-tcgp-transformations` |

---

## 🐳 Docker Orchestration

The project is fully containerized with optimized multi-stage builds.

```bash
# Build and run the entire stack
docker-compose up -d

# Run the interactive CLI via Docker
docker-compose run cli-chat
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

### Testing

Unit tests are co-located within their respective components.

```bash
# Run CLI unit tests
uv run pytest pokemon_cli/tests/
```

### CI/CD

Our GitHub Actions pipeline (`.github/workflows/ci.yml`) automatically runs SQL linting, Python linting, and unit tests on every push to `main`.

---
