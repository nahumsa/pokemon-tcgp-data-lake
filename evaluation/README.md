# Evaluate analytical answers through the real MCP server

This benchmark assesses a candidate's complete workflow: read a question, discover
semantic models, choose MCP queries, inspect evidence, calculate an answer, and
state its limits. It uses the production stdio server and production dbt models.

## First assessed run

The ChatGPT Work assistant answered **12/12** questions correctly using **27 actual
MCP calls**, with no tool errors. The [per-question report](baselines/assistant-first/report.md)
and JSON transcripts include the questions, discovered tools, actual arguments,
returned rows, explanations, structured facts, dataset fingerprint, and scores.

The same assistant authored the fixture and answered the questions with shared
context. The prompts also supplied scope guidance and caveat labels. This was a
**guided, non-blinded self-evaluation**. It verifies these answers and the working
MCP path; 12/12 is not a general estimate of an independent model's accuracy.
Expected numeric answers were not injected by the runner or generated from the
semantic measures being tested. They are independently calculated from raw Python
fixture records.

| Question | Correct reference answer |
|---|---|
| Imported tournament entries | 11 entries; not 11 distinct lifetime people |
| Online entries | 7 |
| January match activity | 4 observed pairings, 9 player records, 1 bye |
| Alice's January win-only rate | 1 win / 3 results = 33.33%; ties remain in the denominator |
| Dragapult online pooled win rate | 4 / 7 = 57.14% |
| Dragapult online pooled meta share | 3 / 7 = 42.86%; includes unclassified entrants in population |
| Dragapult ex across online published classified decks | 3 decks, 12 copies; alternate printings deduplicated |
| Missing's February history | 0 recorded observations, undefined win rate |
| Entries missing decklists | 3; still present in participant population |
| Tech in January Dragapult mirrors | 2 vs 2 results, 0% vs 50%, -50 percentage points; insufficient_matches, null rank, no causal proof |
| Next tournament's winning archetype | Cannot determine from historical data alone |
| Labs entries | 4; provider and setting are independent dimensions |

## Build and start MCP

```bash
uv sync --all-packages --locked
uv run python -m evaluation.run build --work evaluation-results/run-001
uv run python semantic_layer/semantic_layer/mcp_server.py \
  --database evaluation-results/run-001/benchmark.duckdb
```

The last command serves MCP over stdio; clients must perform the MCP handshake.
It is not an HTTP server. `--database` overrides `PTCG_DATABASE_PATH`; otherwise
the repository's `pokemon_tcg_pipeline.duckdb` is used. The server opens an
existing warehouse read-only and fails clearly if it is missing. Importing the
module does not open a database. All table registrations are loaded from the
production semantic YAML, avoiding a separate hardcoded registry.

The build creates 3 synthetic events, raw ingestion tables, a full dbt rebuild,
107 passing dbt data checks, and a database fingerprint. Synthetic decks are
minimal analytical fixtures, not legal 60-card decks. Use a new directory for
each fixture build. No tournament scraping or saved production database is used.

## Run a fresh candidate

```bash
uv run python -m evaluation.run run \
  --work evaluation-results/run-001 \
  --run-id candidate-001 \
  --candidate 'your-agent / exact model and prompt version' \
  --candidate-command 'python /path/to/your_agent_adapter.py'
uv run python -m evaluation.report evaluation-results/run-001/candidate-001
```

The adapter is the analytics agent being tested, not a scripted reference-answer
solver. No model API credentials are needed for MCP or grading. An API-backed
candidate supplies its own configured provider credentials. This repository does
not silently choose or fund a model, and no unattended model endpoint was
available for the first run.

The runner starts the real MCP server, verifies the fixture fingerprint, and
launches a fresh candidate subprocess per question. Every exchange is one JSON
object per line on stdin/stdout; diagnostics go to stderr:

1. The candidate receives `event: question`, the question, answer field names,
   guidance, and actual MCP tool schemas. It never receives oracle values.
2. To query, emit `{"action":"call","tool":"query_model","arguments":{...}}`.
3. Read `event: tool_result`, then choose another call or produce an answer.
4. Finish with `{"action":"answer","facts":{...},"explanation":"...","caveats":[...]}`.

`list_models` and `get_model` support exploration. The runner executes chosen
calls; it does not prescribe a query plan. Set `get_chart: false` when only rows
are needed. The budget is 20 calls per question, 60 seconds per tool call, and
180 seconds waiting for each candidate action. Timeout/invalid/missing answers
fail rather than becoming a success. Candidate commands are trusted local
processes; filesystem/answer secrecy is a protocol boundary, not a hostile-agent
sandbox.

For an assistant in this conversation or another interactive controller:

```bash
uv run python -m evaluation.run bridge \
  --work evaluation-results/run-001 \
  --run-id interactive-001 --candidate 'assistant identity'
```

This uses the identical JSONL protocol on the terminal. Reuse of conversation
context must be disclosed, as in the initial run.

## Scoring and repeated evaluation

The independent `fixture.oracle()` computes reference facts directly from raw
records, without calling production SQL/YAML. The grader checks numbers (0.011
absolute tolerance), exact null/boolean/status behavior, declared caveat labels,
a nonempty explanation, and at least one successful real MCP query per answer.
Wrong values or missing evidence fail the run with a nonzero exit code. A negative
control deliberately queries the correct MCP result then answers 999; the harness
must reject it.

The automatic score does not establish that the prose follows the evidence. A
reviewer must inspect query scope, provenance, reasoning, and causal language;
a successful unrelated query is insufficient support even if fact values happen
to match. Caveat labels are declarations, not proof that the explanation respects
them. The initial saved explanations were also reviewed against their tool rows.

CI runs real MCP transport, fixture builds, negative controls, and grading tests.
It rechecks the archived answers but does **not** count this as a new agent run.
For periodic agent evaluation, invoke `evaluation.run run` from a scheduler with
a configured candidate adapter and a distinct run ID; retain each report and
compare per-question failures on the same fixture/version. No periodic model job
has been enabled or claimed to run. Add held-out questions and independently
run candidates before using the score for model comparisons.

## Improvements exposed by this assessment

- `deck_analysis.total_matches` returns null for an imported entrant with no
  history. The evaluated answer explicitly interpreted absent history as zero
  observed results while retaining a null win rate. Expose a zero observation
  count or a history-availability field to avoid implicit interpretation.
- Temporal dimensions are returned with `is_time_dimension: false`. Agents can
  query dates directly, but coverage discovery should have explicit time metadata.
- Participant names/event dates are not consistently exposed across semantic
  models. Alice's event had to be identified through `tournament_url`, while
  association periods were cross-checked against the tournament model. Add
  provenance dimensions or supported joins to make event-specific questions less
  dependent on matching period labels.
- Provider and setting are distinct fields but correlated in this fixture. Add
  cross-cutting providers/settings, altered cohort sizes, unseen questions, and
  repeated independent runs before asserting robust analytical performance.
- Add a separate independent interpretation review and trace-grounding scorer;
  deterministic numeric correctness alone cannot assess arbitrary analytical prose.

## Completed comparison on real tournament data

The [real-data assessment](baselines/real-labs/README.md) uses a frozen public
Limitless Labs snapshot of Gdańsk and Puebla: 3,973 entries, 2,222 published decks,
and 33,027 player-result records. Eleven quantitative questions matched
independent SQL over original API records; a future-winner question was correctly
declined. The run used 23 actual MCP calls. See the comparison for coverage limits.

To create another reproducible real-data comparison:

```bash
uv run python -m evaluation.real_data --work evaluation-results/real-data --latest 2
uv run python -m evaluation.real_reference --work evaluation-results/real-data
uv run python -m evaluation.run bridge --work evaluation-results/real-data \
  --run-id actual-agent-001 --candidate 'assistant identity / real data'
uv run python -m evaluation.report evaluation-results/real-data/actual-agent-001 \
  --questions evaluation-results/real-data/questions.json \
  --expected evaluation-results/real-data/expected.json
```

`real_data` caches the original API responses and normalized importer JSON. It
loads those real records through an explicit raw-table adapter and runs the
production dbt project. This isolates analytical validation from dlt runtime
state; it does not validate the dlt loader. `real_reference` creates separate
reference tables directly from API standings, pairings and decklists, then
executes independent SQL without querying production marts or semantic measures.
The classification contract's seed mapping is shared domain input, not a claim
of independent archetype taxonomy. Current reference questions concern Labs
Masters TCG events and the chosen entities (Dragapult, Dreepy and Dusknoir), so
check applicability when selecting other events.

Real-data runs require a custom question set and independent expected answers.
The runner picks `questions.json` and `expected.json` beside a real-data manifest
or accepts explicit `--questions`/`--expected` arguments. Raw source snapshots and
full entrant rosters remain outside git; committed transcripts use aggregates
and one explicitly requested public player example. No scheduled model job is
implied by a stored successful run.
