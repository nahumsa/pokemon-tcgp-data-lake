# MCP analytical evaluation

Answers are compared against the reference dataset selected for this run. See the snapshot manifest for scope.

| Question | Verdict | Tool calls |
|---|---|---|
| real_entries | PASS | 3 |
| real_records | PASS | 2 |
| real_latest_matches | PASS | 2 |
| real_byes | PASS | 1 |
| real_classification | PASS | 2 |
| real_dragapult_share | PASS | 3 |
| real_dragapult_rate | PASS | 2 |
| real_card | PASS | 2 |
| real_player | PASS | 2 |
| real_association | PASS | 2 |
| real_online | PASS | 1 |
| real_forecast | PASS | 1 |

## real_entries

How many imported tournament entries are in this real-data snapshot? Distinguish entries from lifetime people.

Expected: `{"entries": 3973}`

Answer: The population measure reports 3,973 imported tournament entries across the snapshot. The same person can enter more than one event, so this is not a lifetime distinct-person count.

Trace: [real_entries.json](real_entries.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| entries | 3973 | 3973 | yes |

## real_records

How many player-result records exist across the snapshot? These are not unique physical matches.

Expected: `{"player_records": 33027}`

Answer: The player-perspective fact contains 33,027 result records, including bye or unresolved histories. A pairing may contribute a history for each player, so this count cannot be reported as unique played matches.

Trace: [real_records.json](real_records.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| player_records | 33027 | 33027 | yes |

## real_latest_matches

For Regional Championship Gdańsk, report observed unique played pairings and player-result records.

Expected: `{"played_pairings": 7112, "player_records": 14239}`

Answer: For Gdańsk the tournament model reports 7,112 observed played pairings and 14,239 player-result records. The latter includes 15 bye records; twice 7,112 plus 15 equals 14,239. These are imported observations, not a guarantee of complete source coverage.

Trace: [real_latest_matches.json](real_latest_matches.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| played_pairings | 7112 | 7112 | yes |
| player_records | 14239 | 14239 | yes |

## real_byes

How many bye records are represented across the snapshot? Do not count them as played pairings.

Expected: `{"byes": 69}`

Answer: There are 69 bye records across the imported events. They contribute player histories but are excluded from the unique played-pairing count.

Trace: [real_byes.json](real_byes.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| byes | 69 | 69 | yes |

## real_classification

How many imported entries have no published decklist or source archetype label? Are they still included in the overall population?

Expected: `{"missing_entries": 1751}`

Answer: The classification diagnostics show 1,751 missing_decklist entries. The remaining 2,222 have source labels, including 1,022 labels not mapped by the seed. The diagnostic population totals 3,973, so missing decklists do not remove entrants from the overall population. Analyses restricted to classified entries cover a different population.

Trace: [real_classification.json](real_classification.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| missing_entries | 1751 | 1751 | yes |

## real_dragapult_share

Across these imported events, what share of all entries are classified as Dragapult? Include every entrant in the population and disclose classification coverage.

Expected: `{"archetype_entries": 649, "all_entries": 3973, "meta_share": 16.335263025421597}`

Answer: The MCP numerator is 649 classified Dragapult entries, against all 3,973 imported entries, so the observed classified share is 16.34%. Unclassified entrants remain in the denominator. This is not an estimate of the true Dragapult share among entrants whose deck information is missing; unmapped source labels can also fragment parent archetypes.

Trace: [real_dragapult_share.json](real_dragapult_share.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| archetype_entries | 649 | 649 | yes |
| all_entries | 3973 | 3973 | yes |
| meta_share | 16.335263025421597 | 16.335263025421597 | yes |

## real_dragapult_rate

What is the pooled recorded-result win rate of classified Dragapult entries? Report wins, results, and percentage; preserve ties in the denominator.

Expected: `{"wins": 2285, "results": 5507, "win_rate": 41.49264572362448}`

Answer: Classified Dragapult entries have 2,285 wins across 5,507 recorded results, giving a pooled win-only rate of 41.49%. Its 1,048 ties remain in the denominator. The returned scope is Limitless Labs in-person events in the 30th Celebration period. This covers known classified entries, not the missing-deck population, and seed-unmapped variants may be separate categories.

Trace: [real_dragapult_rate.json](real_dragapult_rate.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| wins | 2285 | 2285 | yes |
| results | 5507 | 5507 | yes |
| win_rate | 41.4926457236 | 41.49264572362448 | yes |

## real_card

How many published classified decks contain Dreepy, and how many copies are recorded? Combine printings for deck counts.

Expected: `{"decks": 712, "copies": 2788}`

Answer: The functional-card query reports Dreepy in 712 distinct published classified deck entries, with 2,788 copies. The distinct participant count combines alternate printings without counting the same deck twice. Missing and unpublished lists are outside this card-usage population.

Trace: [real_card.json](real_card.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| decks | 712 | 712 | yes |
| copies | 2788 | 2788 | yes |

## real_player

For Aarni Karjala at Regional Championship Gdańsk, report recorded wins, ties, result count, and win-only percentage.

Expected: `{"wins": 14, "ties": 2, "results": 17, "win_rate": 82.3529411764706}`

Answer: Aarni Karjala has 14 recorded wins and 2 ties from 17 results in the Gdańsk event URL ending /0079/standings. The win-only rate is 14/17 = 82.35%; ties remain in the denominator rather than being removed or treated as wins.

Trace: [real_player.json](real_player.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| wins | 14 | 14 | yes |
| ties | 2 | 2 | yes |
| results | 17 | 17 | yes |
| win_rate | 82.3529411765 | 82.3529411764706 | yes |

## real_association

For Dusknoir in Dragapult mirror comparisons in this snapshot, report with-card/without-card counts and win rates, percentage-point difference, evidence status, and whether the comparison proves a causal effect.

Expected: `{"with_results": 297, "without_results": 1257, "with_rate": 35.01683501683502, "without_rate": 41.84566428003182, "difference_pp": -6.828829263196802, "evidence_status": "meets_sample_thresholds", "causal": false}`

Answer: For the returned Standard, in-person Labs cohort, Dusknoir has 297 with-card results at 35.02% wins versus 1,257 without-card results at 41.85%, an observed difference of -6.83 percentage points. There are 116 versus 473 distinct tournament entries. Both groups pass the configured sample gates, but passing thresholds is not statistical significance or proof that Dusknoir causes the difference; pilot strength, variants, repeated results and event selection remain confounders.

Trace: [real_association.json](real_association.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| with_results | 297 | 297 | yes |
| without_results | 1257 | 1257 | yes |
| with_rate | 35.0168350168 | 35.01683501683502 | yes |
| without_rate | 41.84566428 | 41.84566428003182 | yes |
| difference_pp | -6.8288292632 | -6.828829263196802 | yes |
| evidence_status | "meets_sample_thresholds" | "meets_sample_thresholds" | yes |
| causal | false | false | yes |

## real_online

How many imported entries in this snapshot belong to online events? Do not mistake absence of online records for poor online performance.

Expected: `{"entries": 0}`

Answer: The complete population grouping contains only in_person/limitless_labs, with 3,973 entries. There are therefore zero imported online entries in this snapshot. This describes the selected dataset only and says nothing about online deck performance.

Trace: [real_online.json](real_online.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| entries | 0 | 0 | yes |

## real_forecast

Can this snapshot determine the winning archetype of the next tournament?

Expected: `{"answerable": false}`

Answer: The returned tournaments are historical Gdańsk and Puebla events starting October 31 and October 24, 2026. Those observations cannot determine the next tournament winner. Missing deck coverage further limits extrapolation, and no validated predictive evaluation is exposed by these tools.

Trace: [real_forecast.json](real_forecast.json)

| Fact | Agent answer | Independent reference | Match |
|---|---|---|---|
| answerable | false | false | yes |
