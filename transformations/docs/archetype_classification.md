# Archetype classification contract

`main_semantic.dim_deck_classification` has one row per imported participant,
including entrants without published cards. `dim_deck_archetypes` retains its
existing five columns and classified-only population for downstream analytics.
MCP exposes the full diagnostic table as `deck_classification`; group by
`classification_status` with the `participants` measure to inspect coverage.
Join `participant_id` to `dim_participants` for event and decklist provenance.

## Precedence and provenance

1. The latest Labs standing's non-null label overrides card rules. A label maps
   through `limitless_archetypes.csv`, independently of the card-rule seed.
   Unknown or ambiguous labels retain their original text as the parent and
   variant. A newer null label does not resurrect an older label. Equal load IDs
   resolve by label ascending with nulls first, so a withdrawal wins a tie. This
   fallback is deterministic; it does not identify the authoritative source row.
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

## Published main archetypes and shared engines

`limitless_archetypes.csv` copies the published `identifier`/`name` to
`sup_identifier`/`sup_name` relationships from the Limitless Labs Masters deck
endpoints for [Louisville](https://mew.limitlesstcg.com/labs/data/tcg/decks?tournamentId=0076&division=MA),
[Nice](https://mew.limitlesstcg.com/labs/data/tcg/decks?tournamentId=0077&division=MA),
and [Puebla](https://mew.limitlesstcg.com/labs/data/tcg/decks?tournamentId=0078&division=MA),
retrieved on 2026-10-31. The 113 rows include canonical main entries and cover
82 main archetypes. They reproduce all 7,470 labelled entrants' grouped totals
on those events' published metagame pages. This is a checked-in mapping snapshot;
new provider labels need an explicit update, not a card-rule-based parent guess.
Provider IDs are retained in the seed; legacy ingested rows join by source label.

`deck_engine_rules.csv` separately describes shared engines. Its initial rule
requires both `Teal Mask Ogerpon ex` and `Meganium`. The diagnostic/MCP dimension
`deck_engines` contains the sorted, comma-separated matching engine names, or
null when no configured engine matches. Duplicate card rows do not repeat a tag.
Multiple engines may coexist; these tags do not replace the published archetype
or imply complete engine coverage.

For example, a published `Mega Venusaur` list stays in that main archetype while
receiving the `Ogerpon Meganium` engine tag if both cards are present. A source
label alone cannot establish an engine: missing lists and Venusaur builds without
Meganium receive no such tag. Engine tags are available through
`deck_classification`; existing classified-only analytical models keep their
five-column contract.

## Rule maintenance and historical reports

Do not renumber or reuse `rule_id` values. Add new IDs for new rules and retain
IDs when correcting a rule's content. The `v1:` ruleset version fingerprints the
card rules, published label mappings and engine rules in stable ID order.
Content changes alter
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

## Real-data verification (2026-10-31)

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

The original full dataset was imported through the ingestion program. During
mapping validation, a fresh full replay hit malformed intermediate JSON in dlt's
child-card load. Validation reused that previously verified full database and
successfully replayed the 15 real Mega Venusaur decklists through the unmodified
ingestion CLI into an isolated copy. The complete raw deck-card multiset still
matched the saved snapshot afterward. No synthetic event rows were substituted.

All 26 models rebuilt and 110 data tests plus 19 unit tests passed; the Python
suite passed 34 tests. All 2,222 published labels now map to the provider's main
archetypes, with 12 entrants still missing lists/labels. Puebla's grouped counts
include 171 Alakazam, 93 Mega Lucario, 39 Mega Lopunny, 94 Ogerpon Meganium and
15 Mega Venusaur, matching Limitless's grouped page. The classified population
remains 2,222; changing the parent groups is intentional.

The shared Ogerpon Meganium engine matches 72 Hydrapple lists, 22 Arboliva lists
and 14 of the 15 Mega Venusaur lists. The remaining Venusaur list lacks Meganium
and is not tagged. The ruleset remains `v1`, with content fingerprint
`abb27c5c36f75bff56e766405f747f11`.
