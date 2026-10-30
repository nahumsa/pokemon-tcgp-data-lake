# Player records and observed tournament matches

`fct_matches` remains one player/event/raw-round result per staged identity.
Its `match_id` is a **perspective record ID**, not a physical-match ID. Two
players' histories can describe the same played match; one history may be missing.
Player and archetype performance calculations continue to use these original
records and outcomes.

`fct_tournament_matches` reconciles those facts into observed pairing groups.
`mart_tournament_analysis` and the `tournament_analysis` semantic model expose:

| Count | Meaning |
|---|---|
| `perspective_record_count` | All staged player records, including byes and unresolved records |
| `unique_match_count` | Observed played pairings with known players and normalized rounds |
| `mirrored_match_count` | Identified pairings with records for both players |
| `one_sided_match_count` | Identified pairings with only one player's history |
| `bye_record_count` | Explicit BYE records, excluded from played matches |
| `unresolved_perspective_record_count` | Records without a reliable pairing identity, excluded from played matches |
| `duplicate_perspective_record_count` | Extra records for one player within a reconciliation group |
| `conflicting_outcome_match_count` | Identified pairings with contradictory outcomes; included in unique matches |
| `incomplete_outcome_match_count` | Identified pairings with missing/unrecognized outcomes; included in unique matches |

`unique_match_count = mirrored_match_count + one_sided_match_count`. No count is
estimated by dividing perspective rows by two. An event without imported histories
has zero observed matches; zero does not establish that no matches were played.
Even a fully mirrored dataset does not prove that every event round was imported.
Missing/unresolved data is disclosed, not filled with inferred matches.

## Identity and reconciliation

A canonical identity is `match:` plus the MD5 of a JSON array containing the
tournament ID, normalized round, and the two participant IDs in sorted order.
JSON encoding keeps the key components unambiguous. The ID is independent of
which history arrives first and does not depend on outcomes. Participant IDs
must resolve in `dim_participants` for the same event; display names are not
fuzzily matched. Identity therefore retains the source/name-based participant
limitations of the existing ingestion pipeline.

Round labels are lowercased, trimmed, and have whitespace collapsed. Positive
numeric labels lose leading zeros, and `Round 01` matches `1`. Named phase labels
remain distinct: `Swiss 1` and `Top 1` are different rounds. Missing/placeholder
labels and zero rounds are unresolved. The model does not guess equivalences
between other source phase names.

Both ends of every known pairing are checked for multiple opponents in the same
event/round, including reverse edges inferred from one-sided histories. Conflicting
pairings, self-pairings, unknown players/opponents, and missing rounds receive a
null `canonical_match_id`. Explicit `BYE` opponent labels also receive no played
match ID. Every such record remains in a reconciliation group with an explicit
`resolution_reason`; no source result is discarded or changed.

The group has `history_status` (`mirrored`, `one_sided`, `bye`, or `unresolved`)
and `outcome_status`. Complementary wins/losses and two ties are consistent. Two
losses are retained as `double_loss`, as supported by the Labs importer. Two
wins, incompatible mirrored results, or contradictory results for one player are
flagged `conflicting`. Missing/unrecognized outcomes are flagged `incomplete`.
Known pairings remain counted even if their outcomes are problematic; the outcome
counts expose that distinction. One-sided histories do not invent a second result.

Staging still keeps its latest record per existing raw identity. Extra facts that
normalize to the same player/pair/round do not inflate unique matches. The new
fact stores the contributing `perspective_record_ids` for SQL drilldown into
`fct_matches`. Conflicting candidate pairs retain their pair-based group key but have a null
canonical ID. Other unresolved records and byes use `record:` plus the original
`match_id` as a fallback group key; this fallback is never treated as a
played-match identity.

## Queries and compatibility

Use `tournament_analysis.unique_match_count` for observed event match totals, and
show its coverage counters alongside it. The `tournament_matches` semantic model
supports round, player, resolution, history, and outcome drilldowns. For example:

```sql
select resolution_reason, history_status, outcome_status,
       count(canonical_match_id) as unique_match_count,
       sum(perspective_record_count) as perspective_record_count
from main_semantic.fct_tournament_matches
where tournament_id = 'selected-event-id'
group by 1, 2, 3;
```

`mart_tournament_analysis.total_matches`, its semantic measure, and
`matches.match_count` are retained as compatibility aliases for **player record
counts**, with corrected descriptions. New callers should use the explicit
`perspective_record_count` or `unique_match_count` measures. Existing player and
archetype marts and their rates keep their perspective unit.

Rebuild the new fact and the event mart before starting the MCP server:

```bash
cd transformations
uv run dbt build --profiles-dir . --select fct_tournament_matches mart_tournament_analysis
```

CI runs native dbt unit tests with static SQL fixtures for every parent model.
The reconciliation tests mock `fct_matches` and `dim_participants`; the event-mart
tests independently mock `fct_tournament_matches`, `dim_tournaments`, and
`dim_pokemon_sets`. Tests compare model outputs with fixed expected rows; they do
not run ingestion, chain model materializations, or exercise the semantic server.

The `unit` target uses an in-memory DuckDB database. SQL fixtures supply their own
column types, so neither saved tournament data nor prebuilt parent tables are
required:

```bash
cd transformations
uv run --package pokemon-tcg-transformations dbt test --profiles-dir . --target unit --select test_type:unit
```

This work supplies match-count coverage, not overall ingestion freshness or report
readiness (issue #4).
