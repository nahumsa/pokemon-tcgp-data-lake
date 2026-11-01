# Metric contract

Rates are calculated from summed, unrounded counts at query time, never by
averaging cohort percentages. All exposed rates use **percentages (0–100)**;
rate differences use **percentage points**. A zero or empty denominator returns
null, not zero or infinity. Quantity averages use copies per observation.

| Model / measure | Numerator | Denominator / unit | Stored row grain |
|---|---|---|---|
| `archetype_stats.avg_win_rate` | Wins | Recorded player-results, % | Set, source, event type, archetype, variant |
| `monthly_meta_shifts.avg_win_rate` | Wins | Recorded player-results, % | Month, source, event type, archetype |
| `archetype_matchups.win_no_ties_rate` | Wins | Recorded player-results, % | Set, source, event type, both archetypes and variants |
| `archetype_matchups.win_ties_rate` | Wins + ties | Recorded player-results, % | Same matchup grain |
| `deck_analysis.avg_win_rate` | Wins | Recorded player-results, % | Tournament entry |
| `card_staples.avg_mean_quantity` | Copies in included decks | Included functional-card/deck memberships, copies | Set, source, event type, archetype, card name, card kind |
| `matchup_suggestions.avg_win_rate_with_card` | Wins with card | With-card player-result observations, % | Set, game, format, source, event type, archetype, opponent archetype, card |
| `matchup_suggestions.avg_win_rate_without_card` | Wins without card | Without-card player-result observations, % | Same suggestion grain |
| `matchup_suggestions.avg_relevance_score` | With-card pooled rate minus without-card pooled rate | Percentage points | Same suggestion grain |
| `matchup_suggestions.avg_suggested_quantity` | Copies in winning with-card results | Winning with-card player-results, copies | Same suggestion grain |

The `avg_` names remain for query compatibility; they represent ratios of pooled
counts. For example, 1 win in 1 result and 9 wins in 99 results yield 10%, not the
54.55% unweighted mean of their rates. Ties stay in all win-rate denominators;
only `win_ties_rate` also counts them in the numerator. `win_no_ties_rate` means
win-only numerator, **not** exclusion of ties from the denominator. Recorded
player-results retain the existing facts' treatment of byes and unresolved
opponents; these are not deduplicated physical tournament matches.

## Population shares and distinct counts

- Monthly meta share is `100 * archetype_participants / total_participants`.
  The numerator counts tournament entries in that archetype. The denominator
  includes unclassified entries and lives in `monthly_populations`, once per
  month/source/event type. Count a selected cohort once even if selecting several
  archetypes. To pool months or providers, sum the selected archetype counts and
  divide by the matching population totals. Filtering the numerator to an
  archetype must not shrink the population denominator.
- Card inclusion is `100 * decks_with_card / total_archetype_decks`. The population
  lives in `archetype_deck_populations`, once per set/source/event type/archetype.
  It includes published, classified decks, not all event participants. Filter or
  group the numerator to one functional card before interpreting it as decks.
  When combining cohorts, count each selected population once, not once per card.
- `meta_share` and `inclusion_rate` are cohort-level dimensions, not aggregatable
  measures. Include their complete cohort and category dimensions when displaying
  stored percentages. Never sum or average these values; calculate pooled shares
  from the separate count models. These models have no implicit joins that could
  multiply their denominators.
- `cards_used.decks_containing` is a distinct count of tournament participant IDs
  from deck-card facts. It deduplicates alternate printings and multiple selected
  cards within a deck. `total_used` counts copies and is additive.
- Staple quantities combine alternate printings by name within a deck. Across
  different cards, the resulting quantity is per card/deck membership, not total
  deck size. Suggestion samples similarly count card/result observations when
  several cards are selected. Filter to one card for a matchup population;
  without-card populations overlap across cards and must not be read as unique
  matches. Suggested quantities weight a deck once per winning recorded result.

## Observed card associations

`matchup_suggestions` and its `suggested_` / `avg_relevance_score` names remain
for compatibility. They describe observed associations, not improvements caused
by adding a card. The mart now exposes all observed card/comparison rows,
including missing comparison groups and small samples. Previous difficulty,
staple-inclusion, positive-difference and top-five filters hid that evidence and
have been removed. Existing clients should explicitly select the evidence status
and rank described below rather than assuming every returned row is a suggestion.

Each row compares **the same game, recorded format, set period, provider, event
setting, primary archetype and opponent archetype**. Unknown periods/formats and
unrecognized outcomes are excluded. Both current importers support Pokemon TCG
only (`GameEnum.TCG` and the Labs `/tcg` endpoint), so `game = 'PTCG'` declares the
supported importer scope, not newly observed raw game metadata. Pocket is not
supported by this model; explicit game identity must be propagated before any
additional game's ingestion is enabled. Set periods retain the existing calendar
assignment; this change does not implement a new legality calendar.

Only results with known own/opponent classifications enter the recorded matchup
population. A result needs published own-card rows to enter either comparison
group. Missing own lists are **not** evidence that a card was absent. Mirrored
player perspectives retain their directed matchup meaning; these counts are not
independent physical matches. Alternate printings are combined by existing card
names within a deck, preserving the current functional-card convention.

The row exposes with/without wins, losses, draws, player-result denominators and
distinct tournament-entry counts. `sample_size` is the with-card denominator;
`matches_without_card` is the without-card denominator. Both win rates are
`100 * wins / (wins + losses + draws)`. Empty denominators and the resulting
rate difference are null, not zero. `decklist_match_coverage` is
`100 * matches_with_decklists / recorded_match_count`; its denominator excludes
unclassified/unknown-opponent results, so it is not overall event completeness.
Coverage totals repeat across cards: filter one card and cohort before using them.

### Evidence policy and ranking

The default policy requires **10 recorded results and 3 distinct tournament
entries in each comparison group**. Entries are not resolved lifetime player
identities; one pilot can appear at multiple events. Repeated results from one
entry do not satisfy the three-entry gate.

| `evidence_status` | Meaning | `association_rank` |
|---|---|---|
| `missing_comparison_group` | No without-card observations | null |
| `insufficient_matches` | Either group has fewer than the configured results | null |
| `insufficient_decks` | Both result counts pass, but either entry count is too small | null |
| `meets_sample_thresholds` | Both configured sample gates pass | Descriptive within-cohort rank |

Ranks order the observed percentage-point difference descending, then with-card
sample size descending, then card name for a stable tie-break. All qualified
associations, including zero/negative differences, remain available. Filter
`evidence_status = 'meets_sample_thresholds'` and `association_rank <= 5` for a
five-row view within one compatible cohort. Do not combine different formats or
periods before interpreting a comparison, or aggregate stored ranks/coverage.
The pooled rate aliases remain available; filter compatible cohorts and one card
before interpreting their results.

Configure the policy with positive integer dbt variables; the active thresholds
are also exposed in every result and in the semantic dimensions. Restart the
semantic server after rebuilding so it loads the new fields:

```bash
# From transformations/
uv run dbt run --profiles-dir . --select mart_archetype_matchup_suggestions \
  --vars '{"association_min_matches": 20, "association_min_decks": 5}'
```

Meeting these policy thresholds is **not** statistical significance, a confidence
interval or proof of causation. Pilot strength, deck variants, event selection,
correlated card choices and missing lists can all explain differences. Suggested
quantities describe card copies in observed lists, weighted once per recorded
win; they are not an optimized prescription. Null quantity means no observed
with-card wins, not a recommendation to play zero copies.

## Migration and validation

`deck_analysis.avg_win_rate` and `mart_deck_analysis.win_rate` now use 0–100 rather
than 0–1. Remove any extra multiplication by 100 in clients. Missing deck match
history now yields a null mart rate. All other rate names retain their units.
The MCP measure descriptions carry these formulas and null behavior. No generated
report component currently exists in this repository.

Run the isolated regression checks (no saved database or network data required):

```bash
uv run --package pokemon-tcg-semantic-layer pytest semantic_layer/tests -q
```

These execute production YAML expressions through the semantic query engine and
render the production population/staple/deck SQL against synthetic inputs. They
cover uneven samples, combined periods/archetypes, provider filters, ties, empty
and zero denominators, absent comparison groups, unclassified entrants, repeated
population denominators, and alternate card printings.
