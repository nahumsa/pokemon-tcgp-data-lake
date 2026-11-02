# MCP analytical evaluation

This is a controlled synthetic benchmark, not a live tournament report.

| Question | Verdict | Tool calls |
|---|---|---|
| entries | PASS | 3 |
| online_entries | PASS | 2 |
| unique_matches | PASS | 2 |
| ties | PASS | 2 |
| pooled_rate | PASS | 2 |
| meta_share | PASS | 3 |
| printings | PASS | 2 |
| missing_results | PASS | 2 |
| classification | PASS | 2 |
| association | PASS | 3 |
| future | PASS | 2 |
| source_scope | PASS | 2 |

## entries

Across all available fixture tournaments, how many tournament entries were imported? Do not interpret the total as distinct lifetime people.

Expected: `{"entries": 11}`

Answer: The population measure sums to 11 tournament entries across all cohorts. A person entering two tournaments contributes two entries, so this does not establish 11 distinct people.

Trace: [entries.json](entries.json)

## online_entries

How many imported tournament entries belong to online events only?

Expected: `{"entries": 7}`

Answer: Filtering the population model by event_type online gives 7 imported entries. This includes every archetype and unclassified entry in that setting.

Trace: [online_entries.json](online_entries.json)

## unique_matches

In January Play, how many observed played pairings, player-result records, and bye records exist? Explain why the first two counts differ.

Expected: `{"played_pairings": 4, "player_records": 9, "byes": 1}`

Answer: January Play has 4 observed pairings: 3 mirrored and 1 one-sided. Its 9 player-result records comprise 6 mirrored histories, 1 one-sided history, 1 bye and 1 unresolved record. These are observed counts, not proof the event import is complete.

Trace: [unique_matches.json](unique_matches.json)

## ties

For Alice in January Play, report wins, recorded results, and win-only percentage. How do ties affect that percentage?

Expected: `{"wins": 1, "results": 3, "win_rate": 33.333333333333336}`

Answer: The January Play entry has 1 win among 3 recorded results, including 1 tie. Its win-only rate is 1/3 = 33.33%; the tie stays in the denominator and is not counted as a win. The separate Labs entry is excluded.

Trace: [ties.json](ties.json)

## pooled_rate

Across online events, what is Dragapult's pooled recorded-result win percentage? Report wins and results too. Do not average event or period percentages.

Expected: `{"wins": 4, "results": 7, "win_rate": 57.142857142857146}`

Answer: Within online events, Dragapult has 4 wins from 7 recorded player results, giving 57.14%. This pools the counts across periods rather than averaging their percentages; in-person results are excluded.

Trace: [pooled_rate.json](pooled_rate.json)

## meta_share

Across online events pooled together, what percentage of all imported tournament entries used Dragapult? Include unclassified entrants in the population and report numerator and denominator.

Expected: `{"archetype_entries": 3, "all_entries": 7, "meta_share": 42.857142857142854}`

Answer: The online Dragapult numerator is 3 entries. The separately queried online population is 7 entries, including unclassified entrants. The pooled share is 3/7 times 100 = 42.86%; filtering the population to Dragapult would incorrectly shrink the denominator.

Trace: [meta_share.json](meta_share.json)

## printings

Across online events, how many published classified decks contain Dragapult ex, and how many copies are recorded? Combine alternate printings for deck counts.

Expected: `{"decks": 3, "copies": 12}`

Answer: Grouping by functional card name across online events gives 3 distinct deck entries containing Dragapult ex and 12 copies. The distinct deck measure avoids counting an entry twice when it includes alternate printings. This population covers published classified decks, not every entrant.

Trace: [printings.json](printings.json)

## missing_results

What are Missing's recorded-result count and win percentage in February Play? If no results are recorded, explain what can be concluded.

Expected: `{"results": 0, "win_rate": null}`

Answer: Missing has an imported February Play entry, but the MCP returns null for its joined result count and win percentage, indicating no recorded match history. I interpret the absent history as 0 recorded observations; the win rate remains undefined, not 0% performance. A null count is an interface ambiguity worth making explicit.

Trace: [missing_results.json](missing_results.json)

## classification

How many imported entries have classification_status missing_decklist? Is their absence from classified archetype performance the same as absence from the participant population?

Expected: `{"entries": 3}`

Answer: The classification diagnostic counts 3 entries with missing_decklist and 8 matched entries. The diagnostic includes imported unclassified entries, so missing decklists exclude them from classified performance but not from the overall participant population.

Trace: [classification.json](classification.json)

## association

For Tech in Dragapult mirror matches in January Play, report with-card and without-card result counts, win percentages, the percentage-point difference, evidence status, and rank. Does this prove Tech causally changes the outcome?

Expected: `{"with_results": 2, "without_results": 2, "with_rate": 0.0, "without_rate": 50.0, "difference_pp": -50.0, "evidence_status": "insufficient_matches", "rank": null, "causal": false}`

Answer: The returned online Play mirror comparison has 2 with-card results at 0% and 2 without-card results at 50%, a -50 percentage-point association. The tournament query maps its Phantasmal Flames cohort to January Play in this fixture. The evidence status is insufficient_matches and rank is null. These tiny, observational, player-result samples do not prove a causal effect; repeated players, card choices and pilot strength can confound the comparison.

Trace: [association.json](association.json)

## future

Using this dataset alone, can you determine which archetype will win the next tournament? Give a supported answer rather than a fabricated prediction.

Expected: `{"answerable": false}`

Answer: The latest returned event is February Play on 2026-02-16. These are historical observations, not the result of the next tournament or a validated predictive model. The dataset alone cannot determine the next winning archetype, so I will not name a winner.

Trace: [future.json](future.json)

## source_scope

How many imported tournament entries come from limitless_labs? Keep provider and event setting conceptually separate.

Expected: `{"entries": 4}`

Answer: Filtering the population by provider source limitless_labs yields 4 imported entries. The returned setting is in_person in this fixture, but provider and setting are independent dimensions; the filter used the provider rather than assuming all in-person events are Labs.

Trace: [source_scope.json](source_scope.json)
