# Event coverage and report readiness

`mart_event_coverage` and the MCP `event_coverage` model contain one row per
stored or audited event, including an event whose first extraction failed.
`tournament_url` links every row to its source. Both ingestion commands retain
extraction summaries in `pokemon_tcg_data.ingestion_event_runs`.

## Denominators

All rates are percentages at the **single-event grain**. Do not average them
across events; pool the corresponding counts instead.

| Field | Numerator | Denominator |
| --- | --- | --- |
| `participant_coverage_pct` | Stored distinct event entrants | Source-reported expected entrants |
| `decklist_coverage_pct` | Latest extracted entrants with a nonempty list | Latest extracted entrants |
| `history_coverage_pct` | Latest extracted entrants with at least one result | Latest extracted entrants |
| `classification_coverage_pct` | Stored entrants with unambiguous classification | Stored entrants |

Ambiguous card-rule and source-label classifications are disclosed separately
and excluded from the classified numerator. Unmapped but unambiguous source
labels count as classified, following the existing classification contract.
History coverage does **not** establish that every round was imported. Byes
count as an available player history, following the existing result ingestion.

Unfetched inputs and zero denominators yield null. An extraction that fetched
standings but found no published lists has a known list count of zero. Databases
and snapshots without audits remain compatible, but their extraction coverage,
completion, and freshness stay unknown; rebuilding does not invent them.

## Attempts and freshness

Each load gets a distinct attempt ID. Snapshot replay preserves `extracted_at`
and records a new `loaded_at`; replaying old source data cannot refresh its age.
The latest attempt's status and error counts remain visible alongside the last
successful extraction/load time. A failed raw load is recorded and re-raised.
If storage itself is unavailable, the command fails and may also be unable to
persist its audit; callers must require a successful ingestion command.

Labs imports discard a failed event's extracted rows as a unit, retain a failed
event audit, and continue other events. Event-level errors are included in
`extraction_error_count`; their per-resource error counts may remain zero.
Play retains successfully extracted rows and records participant, list, and
history failures separately. Either command exits unsuccessfully when an event
fails extraction. Missing published lists/history alone are not request errors.

`transformed_at` identifies the dbt invocation that successfully built the
coverage table and its parent models. It is not a claim that unrelated models
or the whole dbt invocation succeeded. Report orchestration must also require
the full transformation and validation commands to succeed. The readiness CLI
checks the live raw audit head, preventing a coverage table built before a later
load from passing. MCP timestamps describe the last materialized build; use the
CLI/live audit check as a publication gate.

Raw data uses existing merge behavior, which can retain older deck rows. Latest
list/history coverage uses the latest extraction summary, so retained rows cannot
make those coverage percentages appear complete. Classification describes the
stored analytical population. Participant count mismatches block readiness.

## Checks and reusable report section

Run from the repository root after ingestion and a successful dbt rebuild:

```bash
uv run --package pokemon-tcg-semantic-layer python -m semantic_layer.semantic_layer.readiness \
  https://labs.limitlesstcg.com/0078/standings
```

The default policy requires a completed source event, successful extraction/load,
matching positive expected/stored/latest participant counts, 100% decklist,
history, and unambiguous classification coverage, and extraction within 24 hours.
The JSON output includes all coverage fields, the policy, and machine-readable
failure reasons. Exit status is 0 for ready, 1 for unready, and 2 for invalid
arguments or an event absent from the coverage table.

Choose lower thresholds explicitly for reports that disclose partial coverage:

```bash
uv run --package pokemon-tcg-semantic-layer python -m semantic_layer.semantic_layer.readiness \
  https://labs.limitlesstcg.com/0078/standings \
  --min-decklist-pct 99 --min-classification-pct 99 --max-age-hours 24 \
  --output markdown
```

`--min-history-pct` is also configurable. `--database` selects a different local
database. Thresholds must be finite percentages in [0, 100], and maximum age
must be finite and positive. Unknown coverage still fails when a threshold is
zero; a known zero can pass a deliberately disabled requirement.

`read_event_coverage`, `check_readiness`, and `coverage_section` are reusable by
the report component from #3. The Markdown section includes source provenance,
counts, coverage, timestamps, policy, and reasons. Integration into a full event
recap remains part of #3, whose report generator does not exist yet. This change
does not publish reports or add delivery credentials.

See [the real-data validation record](event_coverage_validation.md) for commands
and observed outcomes.
