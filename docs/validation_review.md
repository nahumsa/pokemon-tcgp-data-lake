# Validation review and improvements

Reviewed repository snapshot: `2538b625569a3cffc2cd64e0aa8e3f26f58cad81`.
Scope: definitions, synthetic execution, and analytical methodology. No claims
about the completeness of live tournament data are made by this review.

## Verified results

`uv run python scripts/validate.py --analysis docs/analysis_example.json` passed
all six stages locally: Ruff, dbt dependencies, dbt parsing, 90 Python tests,
17 native dbt unit tests, and the example evidence gate. The Python integration
fixture also built all production models and passed 107 dbt data tests in a
disposable warehouse. All 14 semantic models had every dimension and measure
queried against the production dbt output.

The analysis benchmark demonstrates a pooled ranking reversal: A beats B in
both online and in-person strata, yet B beats A in the pooled rate. Eight negative
evidence cases check that the gate rejects averaging percentages, turning an
empty population into 0%, unsupported causal claims, missing query references,
incorrect arithmetic, absent population scope, untraceable counts, and absent
caveats. The example query result is independently replayed in DuckDB.

## Findings addressed

- The `fct_matches.result` accepted-values contract rejected `BYE`, although the
  production reconciliation deliberately preserves bye records. The integration
  fixture reproduced this failure; the contract now allows `BYE`. No results or
  win-rate formulas were rewritten.
- `dim_tournaments` documented `name`, `date`, `players`, and `winner`, whereas
  built output uses `tournament_name`, `tournament_date`, `player_count`, and
  `winner_name`. Corrected these names and added a regression for all documented
  model columns.
- Removed the unsupported `asyncio_mode` pytest setting, which produced a warning
  without a pytest-asyncio plugin.
- Added a common local/CI routine, retained logs/JUnit results, and an explicit
  assistant workflow for checking analysis claims before answering.

## Remaining improvements, in priority order

| Priority | Improvement | Reason and acceptance criterion |
|---|---|---|
| High | Replay actual analysis evidence against a pinned, read-only snapshot | The JSON gate currently checks recorded evidence and arithmetic; it cannot authenticate saved results. Add a runner that verifies dataset identity, reruns approved queries, and compares typed results. |
| High | Expand question-to-query benchmarks | Add real user questions with independently specified cohort, SQL answer, expected conclusion, and misleading alternatives. Score wrong scope, denominators, rankings, and unsupported statements separately. Current reference tests validate known failure modes rather than arbitrary prose. |
| High | Require a sensitivity appendix for comparative conclusions | Show counts and coverage by source, setting, period, and classification status. A pooled ranking can reverse within every stratum; the new benchmark proves why stratification matters. |
| High | Separate observational card signals from demonstrated improvements | Upstream now exposes both comparison groups, coverage, and explicit result/entry sample thresholds. Passing those thresholds is not significance or causality. Require independent/held-out evaluation before making predictive or causal claims. |
| Medium | Make sample uncertainty and dependence explicit | Repeated results from one deck/player are correlated. Define the estimand and clustering unit before adding confidence intervals or hypothesis tests; disclose low sample sizes and multiple comparisons. |
| Medium | Define legality periods separately from release periods | `int_tournament_context` chooses the latest release date, and multiple sets can share a date. Define deterministic ties and source/format legality policies before calling those periods legal metagames. Do not silently change historical cohort assignments. |
| Medium | Add coverage reporting and identity contracts | Lifetime stats group on player names; monthly populations count entries; missing decklists affect classification populations. Surface these limits alongside conclusions rather than implying unique people or complete deck coverage. |
| Low | Upgrade the ingestion stack in a separate compatibility change | The passing suite emits 4,918 upstream deprecation warnings, chiefly from dlt/threading and pkg_resources. Upgrade with regression checks; do not hide all warnings or change the lockfile as part of this methodology task. |

A green routine establishes that the tested definitions and reference scenarios
behave as expected. It does not establish that a new natural-language conclusion
is correct, causal, representative, or predictive. Follow the analysis workflow
and retain its evidence for each actual answer.

Upstream card-association changes were incorporated before the final rerun. Their
new explicit evidence policy addresses the previous hidden heuristic filtering;
this report treats independent evaluation as the remaining improvement.
