# Matchup evidence and result provenance

Use `matchup_evidence` for event-level counts and pooled win-rate uncertainty;
use `matchup_results` to inspect contributing source records. Both are registered
in the MCP server. The legacy `archetype_matchups` model remains available with
its original population and fields; it does not provide these evidence controls.
Rebuild dbt and restart MCP before querying the new models.

## Population and metric

The estimate uses **directed player-result observations**, not unique physical
matches or independent pilots. Eligible observations have known primary and
opponent archetypes, different primary archetypes and a WIN, LOSS or TIE result.
`sample_size = wins + losses + ties`; `win_rate = 100 * wins / sample_size`.
Draws count as non-wins. Rates and bounds are null when the denominator is zero.

`matchup_type` retains excluded categories: `mirror`, `bye`,
`unknown_archetype`, `invalid_result` and `missing_history`. The last is one marker
per imported entrant without an own result record; it is not a loss or a played
match. Markers have null `match_id`/`result`. `recorded_results` counts actual
records, while the separate category counters explain exclusions. For mirrors,
inspect `matchup_results` grouped by `result` with `recorded_results` to see W–L–D;
mirror outcomes do not enter the binomial estimate.

Missing histories are not reconstructed from the opponent's perspective.
Neither presence of a history nor source completion proves that every round was
ingested. These models do not estimate how many unobserved rounds are missing.
They retain imported participants and their histories when event metadata exists;
orphan results without an imported participant/event are outside this population.
The coverage/readiness work in #4 is separate.

Current importers support TCG only. `game = PTCG` declares that existing scope;
it is not new raw game metadata or Pocket support. Explicit game identity must
be propagated before enabling another game (#14). Recorded format and the existing
set calendar are retained; neither infers a new legality/rotation calendar.

## Uncertainty

Bounds use the two-sided **95% Wilson score interval** for the binomial event
"win versus loss or draw", as described by
[NIST](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
For `w` wins, `n` observations, `p = w/n` and `z = 1.959963984540054`:

```text
center = (p + z²/(2n)) / (1 + z²/n)
half_width = z * sqrt(p*(1-p)/n + z²/(4n²)) / (1 + z²/n)
bounds_percent = 100 * (center ± half_width)
```

The semantic expressions calculate these from pooled counts after cohort filters,
never by averaging event rates or bounds. Endpoints are clipped to 0–100 and rounded
to ten decimal places to remove floating-point cancellation at zero/all-win samples.

These are **nominal binomial intervals**, assuming independent observations.
Repeated pilots, tournament selection, related player perspectives and incomplete
histories violate that assumption. They are not cluster-adjusted intervals,
causal estimates, multiple-comparison corrections or tournament forecasts. A
minimum sample policy does not establish statistical significance.

## Sample-filtered MCP query

Use `query_matchup_evidence_with_minimum_sample`, rather than applying a generic
`sample_size` filter to `query_model`: the generic semantic library filters rows
before aggregation and would discard small events that together meet the policy.

```json
{
  "dimensions": ["tournament_id", "tournament_url", "tournament_date"],
  "filters": [
    {"field": "game", "operator": "=", "value": "PTCG"},
    {"field": "format", "operator": "=", "value": "STANDARD"},
    {"field": "tournament_date", "operator": ">=", "value": "2026-10-01"},
    {"field": "tournament_date", "operator": "<", "value": "2026-11-01"}
  ],
  "min_sample_size": 10,
  "limit": 100
}
```

The tool always groups by game, format, set period, provider, event setting and
both primary archetypes. Extra dimensions narrow that grain (for example, event
or either sub-archetype). Omit event dimensions to pool compatible events.
Dimension-only filters support event IDs, date windows, format, source, setting,
archetype and variant. Sample thresholds must be positive integers; the output
limit is 1–1,000 and applies **after** pooling and thresholding. Results are ordered
by sample size descending, then cohort dimensions for deterministic ties.
`qualifying_groups` reports the count before the output limit.

To drill down, query `matchup_results` using the same event/date/cohort predicates
and `matchup_type = played`, selecting `match_id`, `participant_id`, `opponent_id`,
`round`, `result`, `tournament_url`, `tournament_date` and optionally `decklist_link`.
Group by `result` and sum `recorded_results` to reconcile W–L–D. Remove the type
filter to inspect excluded categories and missing-history markers. Pagination or
limits on a drilldown must not be interpreted as the full denominator.

## Rebuild and regression checks

After ingestion, from `transformations/`:

```bash
uv run --package pokemon-tcg-transformations dbt run --profiles-dir .
uv run --package pokemon-tcg-transformations dbt test --profiles-dir .
```

From the repository root:

```bash
uv run pytest semantic_layer/tests/test_matchup_evidence.py -q
```

The tests run production SQL and semantic expressions on isolated inputs, check
directed mirrored perspectives, excluded categories, missing histories, provenance,
null/zero/all-win samples, pooled intervals, post-pool thresholds and an actual
in-process MCP tool call. The PR evidence comment records the bounded real-data
ingestion commands, source snapshot hashes and observed outcomes.
