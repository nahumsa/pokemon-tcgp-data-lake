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
| `matchup_suggestions.avg_win_rate_with_card` | Wins with card | With-card player-result observations, % | Set, source, event type, archetype, opponent archetype, card |
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

The suggestions mart exposes only cohorts/cards passing its existing difficulty,
sample, inclusion, relevance, and top-five filters. Pooled suggestion rates cover
those retained rows, not every historical cohort. They do not establish causality.

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
