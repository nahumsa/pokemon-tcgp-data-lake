# Archetype classification contract

`main_semantic.dim_deck_classification` has one row per imported participant,
including entrants without published cards. `dim_deck_archetypes` retains its
existing five columns and classified-only population for downstream analytics.
MCP exposes the full diagnostic table as `deck_classification`; group by
`classification_status` with the `participants` measure to inspect coverage.
Join `participant_id` to `dim_participants` for event and decklist provenance.

## Precedence and provenance

1. The latest Labs standing's non-null label overrides card rules. A label maps
   to a shared parent only if the seed maps it to exactly one distinct parent.
   Unknown or ambiguous labels retain their original text as the parent and
   variant. A newer null label does not resurrect an older label. If load IDs tie,
   null labels sort first (a withdrawal wins); otherwise the alphabetically first
   label wins. This deterministic fallback does not identify which equally fresh
   conflicting record is the provider's authoritative update.
2. For card rules, both required cards must exist. Matching two-card variants
   beat one-card base rules, regardless of priority. Reprints/repeated card rows
   cannot multiply a rule match.
3. Among equally specific rules, larger `rule_priority` wins. Remaining ties
   resolve by ascending permanent `rule_id`, independent of input order.
4. Distinct parent/variant pairs tied on specificity and priority produce
   `ambiguous`, even though a deterministic winner is retained. Lower precedence
   base rules do not make a winning variant ambiguous.

`selected_rule_id`, `selected_match_score`, and `selected_rule_priority` describe
an applied card rule, and are null when a source label wins. `matched_rule_ids`
contains all matching rules; `top_rule_ids` contains only highest specificity and
priority matches. Both are sorted comma-separated IDs that join back to
`meta_decks`. Their counts remain available even when a source label wins, for
comparing the provider's label with card-rule evidence.

| Status | Meaning |
| --- | --- |
| `matched` | One winning card-based parent/variant |
| `ambiguous` | Multiple top card-based parent/variant candidates |
| `unmatched` | Published card rows exist, but no seed rule matches |
| `missing_decklist` | No published card rows or usable provider label |
| `source_label_mapped` | Labs label maps to exactly one seed parent |
| `source_label_unmapped` | Labs label has no seed mapping |
| `source_label_ambiguous` | Labs label maps to multiple seed parents |

A source label may classify a participant without any published cards. Thus these
statuses measure classification coverage, not complete decklist coverage. For a
source-labelled row, `top_candidate_count > 1` describes competing **card** rules;
the status continues to describe the overriding label.

## Rule maintenance and historical reports

Do not renumber or reuse `rule_id` values. Add new IDs for new rules and retain
IDs when correcting a rule's content. The ruleset version combines the algorithm
prefix (currently `v2:`) with a fingerprint of the complete seed, including
priorities, in stable ID order. Content changes alter
the fingerprint; input order alone does not. Bump the algorithm prefix when
changing classification policy. Git history preserves prior rulesets; rebuilding
tables reclassifies historical events with the current seed, so archive the
ruleset version with exported reports. This is not a historical snapshot store.

The initial migration removes five exact duplicate seed rows. All priorities
start at zero except two reversed-card conflicting rules, which receive `-10`
so their previous alphabetical winner remains preferred. IDs initially follow
the old alphabetical parent/variant ordering to preserve other equal-score
winners. This migration documents precedence; it does not adjudicate whether the
existing archetype labels are correct.

`assert_archetype_rules_valid` rejects missing metadata, fractional priorities,
reused IDs, duplicate card-requirement/target definitions, and conflicting targets
for the same unordered card requirements at equal priority. The Python CI tests
execute that production SQL against both invalid examples and the committed CSV.

After editing the seed, run from `transformations/`:

```bash
uv run dbt seed --profiles-dir . --full-refresh
uv run dbt run --profiles-dir .
uv run dbt test --profiles-dir .
```

Full refresh is required when upgrading the seed's columns. Restart the MCP
server after rebuilding so it loads the new diagnostic table.

## Original PR #18 real-data verification (2026-10-31)

Fetched the latest completed Masters event with:

```bash
uv run --package pokemon-tcg-ingestion python -m ingestion.labs --latest 1 --workers 4 --snapshot data/limitless_labs/issue7.json.gz
```

The snapshot identifies [Regional Championship Puebla](https://labs.limitlesstcg.com/0078/standings),
2026-10-24: 2,234 entrants, 2,222 published lists, and 18,788 player-result rows.
The raw JSON SHA-256 is
`7b44c7252554cb61e0d4dec57983db3e0d49b1cb56e30ffb31c3ed9c24c8d89f`.
The snapshot is local and is not committed. `--latest 1` will select a different
event after newer events complete; a saved snapshot is needed for exact replay.

This environment's combined dlt load hit a directory-rename error after the first
load. Validation used the **unmodified ingestion CLI** to replay the fetched
snapshot one table per process with separate local dlt state directories. Each
replay snapshot retained all four table keys, with only its selected table
populated. No synthetic tournament rows were substituted. A normal environment
can reload the original snapshot with `--from-snapshot` instead.

All 26 models rebuilt. The diagnostic table contains 1,200 mapped labels, 1,022
unmapped labels, and 12 missing lists; the existing classified table still has
2,222 rows. Comparing all five legacy columns against the pre-change classifier
on this same data found zero differences.

A separate validation-only execution suppressed provider labels to exercise card
rules on the same real decks: 1,229 matched, 437 ambiguous, 556 unmatched, and 12
missing lists. It also preserved every pre-change classified result. These are
card-rule diagnostics, not the event's authoritative published classifications.
Reversing seed order produced zero diagnostic differences in both modes, and
editing a priority changed the fingerprint. The original PR #18 ruleset was
`v1:344e2a634e798296850a99b98eb8465a`.

The full dbt suite passed 97 data tests and 15 unit tests. The Python ingestion and
semantic suite passed 32 tests. Ruff, SQLFluff on changed SQL, and dbt parsing
passed. Unit fixtures cover priority, ID tie-breaking, variant precedence,
repeated card rows, source overrides, ambiguous/unmapped labels, removal of an
old label, unmatched decks, and missing lists. The two initial priority/ID tests
were first observed failing against the original classifier.


## Reproducing the adversarial evidence checks

The [fresh-context review](pr18_adversarial_review.md) records the limitations of
those original observations and the follow-up correction. Algorithm `v2` adds
source-label tie handling; the seed fingerprint itself is unchanged.

After ingesting the saved snapshot into an isolated database, running the dbt
seed/rebuild/test commands above, and fetching the baseline commit if necessary:

```bash
uv run python transformations/analysis/verify_archetype_evidence.py \
  --database pokemon_tcg_pipeline.duckdb \
  --snapshot data/limitless_labs/issue7.json.gz \
  --expected-snapshot-sha256 7b44c7252554cb61e0d4dec57983db3e0d49b1cb56e30ffb31c3ed9c24c8d89f
```

Run from the repository root. The default baseline is the exact pre-PR commit
`11863bd8085c80a76753131268aa072ef1d801a9`. This read-only database check uses
temporary tables to compare snapshot scalar contents and nested card multisets,
recompute the classifier's staging/fact inputs from raw production SQL, and
compare the loaded seed to the checkout. It then checks the original SQL/seed
baseline, repeat and reversed-rule executions, persisted diagnostics, and a
priority mutation. Changed row multiplicities are checked with `EXCEPT ALL`.
The [recorded aggregate output](pr18_evidence_verification.json) contains the
observed counts and checks, without player records.

The exact snapshot is still required and is not distributed with the code. Its
hash identifies the saved input; it does not independently authenticate the
remote provider. The verifier does not replace ingestion execution, dbt tests,
or a live provider audit. GitHub CI runs unit/logic checks without that dataset;
the full real-data rebuild and this verifier are separate local checks.
