# Validate the analysis process

The goal is to test the route from a question to a supported conclusion, as well
as the data and metric definitions underneath it. A clean database does not make
an analytical conclusion valid.

## Routine

```bash
uv sync --all-packages --locked
uv run python scripts/validate.py
# Include the evidence record for a specific analysis:
uv run python scripts/validate.py --analysis docs/analysis_example.json
```

The example is a synthetic, independently replayed reference, not a tournament
report. Copy its structure for actual analyses. Logs, a stage summary, and JUnit
results are written to `validation-results/`. Failure in any stage produces a
nonzero exit code. Dependency retrieval needs network access; the analytical
fixtures use temporary warehouses, no saved tournament database, and no scraping.

The routine runs lint, dbt dependency installation and parsing, ingestion and
semantic regressions, definition checks, analytical benchmarks, and dbt unit
tests. The definition tests build all production models from synthetic raw
sources, run dbt data tests, and execute every exposed dimension and measure.
They check server registration, YAML duplicate keys, and documented columns too.

## Required analysis workflow

1. **Specify the question before querying.** State whether the question concerns
   popularity, performance, coverage, or an association. Define “best”, “current”,
   and the comparison baseline explicitly. Do not quietly substitute a different
   question because a convenient mart exists.
2. **Declare the population and estimand.** Record the period, sources, settings,
   format, classification policy, exclusions, row grain, outcome, denominator,
   and tie/bye policy. Tournament entries are not lifetime people;
   player-perspective results are not unique played pairings. State which is used.
3. **Design the query using the metric contract.** Filter numerator and population
   to matching cohorts. Preserve unclassified entrants for meta-share populations.
   Recompute pooled shares from counts; do not average stored percentages or
   multiply population totals by joining cards/archetypes to them.
4. **Retain reproducible evidence.** Save SQL, dataset revision/snapshot identifier,
   result grain, and result rows. Link each material claim to query IDs. Rerun the
   SQL against that exact revision and compare results before treating it as
   evidence. The evidence gate checks the record, not a live SQL replay.
5. **Try to disprove the conclusion.** Compare pooled and source/setting/period
   strata, disclose reversals, inspect sample sizes and coverage, and verify
   surprising results using an independent count calculation. Test empty and
   missing populations. A ranking without a stated population is incomplete.
6. **Limit inference.** Card comparisons are observational; filter compatible cohorts and
   inspect the exposed evidence status, group sizes, and coverage. A percentage-point difference is not proof of improvement or
   statistical significance. Repeated matches from one player/deck are dependent;
   any interval/test must respect that dependency and disclose its assumptions.
   Without a suitable evaluation, present an association or decline the claim.
7. **Review the answer against the evidence.** Verify that every number, scope,
   direction of comparison, unit, and caveat matches the saved results. Run the
   evidence gate. Publish only after the judgment checks above are satisfied;
   a passing JSON record alone does not approve an answer.

## What is automated, and what still requires judgment?

| Check | Mechanism | Limit |
|---|---|---|
| Formulas, pooling, ties, nulls, alternate printings, population denominators | Production SQL/YAML regressions | Reference cases do not cover all possible questions |
| Misleading pooled ranking | Simpson reversal benchmark using the production semantic measure | Detecting a reversal in a real analysis still requires stratified queries |
| Claims have scope and query evidence | Structured evidence gate | Cannot determine whether SQL answers the question or prose matches evidence |
| Rate arithmetic and zero-denominator handling | Recompute from saved numerator/denominator | Does not independently authenticate saved evidence |
| Causal overstatement | Reject unsupported causal/predictive claim types; require association caveats/confounders | Cannot detect a causal assertion disguised as descriptive prose |
| Definitions agree across layers | Full synthetic dbt build and all-field execution | Execution is not proof of correct scientific interpretation |

Before returning an analytical answer, the assistant must complete both the
mechanical checks and the judgment review. Record failed checks and unresolved
limitations rather than silently treating missing evidence as a pass.
