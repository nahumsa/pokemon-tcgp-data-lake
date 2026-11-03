# Real-data MCP answer comparison

**Result: 11/11 quantitative questions matched independent reference SQL.** The
12th question, predicting the next tournament's winner from this snapshot alone,
was correctly declined. There were **23 actual MCP calls and zero tool errors**.

[Detailed comparison](report.md) includes agent answers and independent reference
values side by side, with complete query/tool traces. [Reference SQL](references.json)
is committed separately. The [snapshot manifest](manifest.json) identifies the
source records and dataset fingerprints.

## Scope and source

The frozen public Limitless Labs Masters TCG snapshot contains:

| Event | Dates | Imported entries | Published decklists |
|---|---|---:|---:|
| [Gdańsk](https://labs.limitlesstcg.com/0079/standings) | October 31–November 1, 2026 | 1,739 | 0 |
| [Puebla](https://labs.limitlesstcg.com/0078/standings) | October 24–25, 2026 | 2,234 | 2,222 |
| Total | | 3,973 | 2,222 |

There are 33,027 imported player-result records. The catalogue, standings,
metadata, all 34 pairing-round responses and every published decklist were saved
from `https://mew.limitlesstcg.com/labs/data/tcg`. No invented tournament results
or synthetic decklists were added. Technical load keys are derived locally to
connect real parent/child records.

The repository's committed database had no tables. The production importer
successfully downloaded real data, but dlt's loader failed on its local pipeline
state. An explicit adapter loaded the frozen importer JSON into isolated raw
tables, then all 26 production dbt models rebuilt and all 107 data tests passed.
This run assesses analytics and MCP, not successful dlt loading.

## Comparison design

The candidate answered through the actual read-only stdio MCP server. Reference
SQL ran in a separate DuckDB connection over original API standings, pairings and
decklist records; it never read dbt marts or MCP results. The reference identified
players by source IDs, while production models use their documented name-based
keys and duplicate-name suffixes. No duplicate source player/round records were
found. The archetype seed mapping is shared domain-contract input.

The same assistant constructed the questions and answered them, with visible
scope/caveat guidance. This is a guided self-evaluation on **real records**, not a
blinded independent-model benchmark. Quantitative results use an absolute 0.011
comparison tolerance. Causal and predictive limitations also require reviewing
the explanation, not just matching a boolean. The first answers are retained;
they were not edited to make the reference check pass.

## Notable matching results

| Analysis | MCP/agent answer | Independent reference |
|---|---:|---:|
| Imported entries | 3,973 | 3,973 |
| Player-result records | 33,027 | 33,027 |
| Gdańsk observed pairings | 7,112 | 7,112 |
| Gdańsk player-result records | 14,239 | 14,239 |
| Bye records across both events | 69 | 69 |
| Entries without deck information | 1,751 | 1,751 |
| Classified Dragapult entries | 649 | 649 |
| Observed classified Dragapult share of all entries | 16.335263% | 16.335263% |
| Classified Dragapult win-only rate | 2,285 / 5,507 = 41.492646% | 2,285 / 5,507 = 41.492646% |
| Published classified decks containing Dreepy | 712 | 712 |
| Dreepy copies | 2,788 | 2,788 |
| Aarni Karjala at Gdańsk | 14 wins, 2 ties / 17 results = 82.352941% | Same |
| Dusknoir in Dragapult mirrors | 297 with-card results vs 1,257 without | Same |
| Dusknoir observed win-rate difference | -6.828829 percentage points | -6.828829 percentage points |

The Dusknoir comparison passes the configured sample gates but does not prove a
causal effect or statistical significance. Repeated player/deck observations,
variants and pilot differences remain confounders.

## What the real-data assessment exposed

1. **Coverage dominates interpretation.** All 1,739 Gdańsk entrants and 12 Puebla
   entrants lack deck information in this snapshot. Do not describe the
   classified win rate as performance across all entrants, or the observed
   classified share as the unknown true deck share of missing entries.
2. **The seed mapping is incomplete.** 1,022 published source labels are unmapped;
   1,200 map to seed parents. Unmapped labels are retained as their own categories.
   This preserves information but may fragment a parent archetype across variants.
   Report source labels and mapping coverage, and review seed changes explicitly.
3. **Availability differs by event.** Gdańsk has results but no published decks.
   Event-specific classification/deck-coverage dimensions would make it harder
   for an agent to extrapolate Puebla deck analytics to Gdańsk.
4. **Real-data loading needs a separate fix.** The snapshot adapter allowed the
   analysis to proceed without changing tournament facts. Repair and validate
   the dlt pipeline-state failure before calling ingestion healthy.
5. **Agreement is scoped.** The reference checks agree with the published snapshot
   and contract. Labs itself can contain errors; this is not verification against
   official tournament software. The snapshot contains only in-person Labs events,
   so it does not establish online-event accuracy or predictive performance.
