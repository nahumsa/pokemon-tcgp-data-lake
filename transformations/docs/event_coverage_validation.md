# Event coverage validation

Observed with live source extraction on 2026-11-02 UTC. The database and source
snapshots are local validation inputs, not committed datasets.

| Source event | Expected / stored entrants | Nonempty lists | Entrants with histories | Unambiguous classifications | Default readiness |
| --- | --- | --- | --- | --- | --- |
| [Puebla, Labs 0078](https://labs.limitlesstcg.com/0078/standings) | 2,234 / 2,234 | 2,222 | 2,234 | 2,222 | Unready: decklists and classification below 100% |
| [Gdańsk, Labs 0079](https://labs.limitlesstcg.com/0079/standings) | 1,739 / 1,739 | 0 | 1,739 | 0 | Unready: decklists and classification below 100% |
| [LUDUSP weekly #4, Play](https://play.limitlesstcg.com/tournament/6add2e2597e21d82e5c6e88b/standings) | 4 / 4 | 0 | 0 | 0 | Unready: lists, histories, and classification below 100% |

Puebla's decklist and classification coverage is 99.46284691136974%. An explicit
99% list/classification policy passes; Gdańsk still fails that policy. All three
events had successful extraction/load audits with zero extraction errors.
The real [Puebla coverage section](examples/puebla_coverage.md) records its exact
extraction, load, and coverage-build timestamps and selected policy.

## Live import and rebuild

Commands were run from the repository root unless a directory change is shown:

```bash
uv sync --all-packages --locked
RUNTIME__DLTHUB_TELEMETRY=false NORMALIZE__WORKERS=1 LOAD__WORKERS=1 \
  uv run --package pokemon-tcg-ingestion python -m ingestion.labs \
  --latest 2 --snapshot data/limitless_labs/issue4_two_events.json.gz
cd transformations
DBT_SEND_ANONYMOUS_USAGE_STATS=false uv run dbt deps
DBT_SEND_ANONYMOUS_USAGE_STATS=false uv run dbt seed --profiles-dir .
DBT_SEND_ANONYMOUS_USAGE_STATS=false uv run dbt run --profiles-dir .
DBT_SEND_ANONYMOUS_USAGE_STATS=false uv run dbt test --profiles-dir .
cd ..
uv run --package pokemon-tcg-semantic-layer python -m semantic_layer.semantic_layer.readiness \
  https://labs.limitlesstcg.com/0078/standings \
  --min-decklist-pct 99 --min-classification-pct 99 --output markdown
```

The first live run also ingested Labs 0079 alone. The second fetched both events,
including all 2,222 published Puebla lists. `--latest` selects current completed
events, so future runs may select different events.

The Play path was exercised through its production extraction functions, choosing
the smallest positive-size event on the first completed-events page:

```python
from ingestion.main import collect_rows, iter_tournaments
from ingestion.labs import load_rows
from ingestion.payload import TournamentPayload

payload = TournamentPayload(
    game="PTCG", format="STANDARD", platform="all", type="online", time="all"
)
batch = next(iter_tournaments(payload, backfill=True))
event = min(
    (event for event in batch if event.data_players and int(event.data_players) > 0),
    key=lambda event: int(event.data_players),
)
rows = collect_rows([event])
load_rows(rows)
```

During validation the extracted Play rows were saved as a local gzip snapshot and
loaded through `ingestion.labs --from-snapshot`, which uses the same `load_rows`
function as the Play command. A subsequent full dbt rebuild/test included all
three events. Future page contents can select a different Play event.

## Replay, stale build, and recovery

```bash
RUNTIME__DLTHUB_TELEMETRY=false NORMALIZE__WORKERS=1 LOAD__WORKERS=1 \
  uv run --package pokemon-tcg-ingestion python -m ingestion.labs \
  --from-snapshot data/limitless_labs/issue4_two_events.json.gz
```

After replay, Puebla changed from ready under the 99% policy to unready with
`transformation_stale`, before any dbt rebuild. Stored entrants remained 3,977
across the three events. Rebuilding `+mart_event_coverage` restored Puebla's ready
result; all 129 dbt checks passed again. Replays created distinct load attempts
while preserving their original extraction timestamps. The semantic MCP model
was loaded and queried against the real database, returning event-level coverage
and event counts.

## Automated checks

```bash
RUNTIME__DLTHUB_TELEMETRY=false uv run pytest \
  ingestion/test_labs.py ingestion/test_coverage.py semantic_layer/tests -q
uv run ruff check .
cd transformations
DBT_SEND_ANONYMOUS_USAGE_STATS=false uv run sqlfluff lint \
  models/staging/stg_ingestion_event_runs.sql models/consumption/mart_event_coverage.sql
DBT_SEND_ANONYMOUS_USAGE_STATS=false uv run dbt test \
  --profiles-dir . --target unit --select test_type:unit
```

Validation passed 84 Python tests, 129 dbt checks on real ingested data
(including 17 native unit tests), Ruff, and SQLFluff on both new SQL models.
The 17 native unit tests also passed against an in-memory database.

Tests exercise unknown versus zero inputs, failed extraction/load attempts,
successful reruns, first-failure initialization in a fresh DuckDB database,
snapshot timestamps, ambiguous classifications, zero denominators, latest-failure
history, live audit freshness, policy validation, and Markdown disclosures.
CI runs ingestion and semantic tests without saved source datasets. The report
section is ready for reuse by #3; integration into that future full-report
generator remains outstanding.
