# Adversarial evidence review of PR #18

Reviewed on 2026-10-31 against original head
`343db4a7ebf149067e2bc671854b8236023346da`.
This follow-up is stacked on PR #18, not on `main`.

Two subagents started with fresh context, without the author's conversation
history. Both were instructed to challenge the claims, use read-only inspection
and isolated experiments, and report findings without editing or posting. The
first audited the original PR and its evidence. The second challenged the proposed
fix and evidence verifier. The implementation author reproduced the source-label
failure, applied the corrections, and reran validation.

## Findings and disposition

### P2: equally fresh source labels were order-dependent — fixed

The original classifier ordered Labs standings only by `_dlt_load_id`. The first
reviewer inserted isolated `Dragapult`/`Gardevoir` labels for the same real
participant and load ID. Reversing those input rows changed the selected label.
The source-consistency data test copied the same incomplete ordering.
Therefore reversing **seed rules** did not support an unrestricted claim that
all repeated classification builds were deterministic.

The stacked fix orders by load ID descending, then label ascending with nulls
first, in both the classifier and source assertion. A withdrawal wins tied loads;
otherwise the alphabetically first label wins. This is a deterministic conflict
policy, not evidence of which conflicting source row is authoritative. The
algorithm prefix changes to `v2:`; the seed content hash does not change.

New forward/reversed fixtures contain both conflicting labels and a null/non-null
tie. Before the fix, the forward fixture failed and the reversed fixture passed;
after the fix both pass. The original real snapshot has no equal-load duplicate
participant groups, so it cannot by itself demonstrate this correction.

### Evidence reproduction was incomplete — verification command added

The original PR described baseline, rule-order and fingerprint experiments but
did not commit their executable checks. The new
[`verify_archetype_evidence.py`](../analysis/verify_archetype_evidence.py) loads
production SQL and the exact original SQL/seed from the baseline commit. It checks
full multiset differences, not just distinct values.

The second reviewer found that an early draft of this verifier accepted fabricated
semantic participants against an empty, correctly hashed snapshot. Counts alone
were insufficient; trusting loaded semantic inputs and seed was also insufficient.
That draft was strengthened before publication. It now compares scalar snapshot
contents and nested card rows to raw tables, checks for orphan card rows, rebuilds
the classifier's staging/fact inputs from production SQL, and compares the loaded
seed with the checkout before running the classification experiments.

The second reviewer executed the final verifier on real data and separately
altered five isolated databases. All five substitutions were rejected:

| Substitution | Observed rejection |
| --- | --- |
| Same-count raw participant name change | Snapshot contents differ: tournament participants |
| Nested deck-card quantity change | Snapshot contents differ: deck cards |
| Semantic participant identifier change | Rebuilt classifier input differs |
| Loaded seed priority change | Loaded seed differs from checkout |
| Empty raw tables/empty snapshot with fabricated semantic participant | Rebuilt classifier input differs |

The hash identifies the snapshot artifact; it does not authenticate the live
provider. Replaying the exact data still requires the local, uncommitted snapshot.
The verifier does not establish universal correctness outside the tested inputs.

### A fresh Python rerun failed — retained as a limitation

The first reviewer observed 31 passed and one failure in the pre-existing
`test_repeated_deck_imports_are_idempotent_and_replace_only_the_matching_deck`.
One execution saw six parent rows where three were expected; an isolated execution
also saw extra child-card rows. Neither ingestion implementation nor ingestion
tests changed in PR #18 or this stack. The cause remains unproven; this is not an
established regression introduced by these changes.

The original GitHub CI job independently records **32 passed**, and its 15 dbt
unit tests passed: [original CI run](https://github.com/nahumsa/pokemon-tcgp-data-lake/actions/runs/41210297579).
Thus the historical pass is supported, but was not reproduced in every local
execution. The implementation author's final run used a new explicit pytest
temporary directory and passed **36 tests** (the original 32 plus four verifier
checks). Both observations are retained rather than attributing a cause without
evidence.

## Supported real-data evidence

The first reviewer independently matched the decompressed snapshot hash, all four
raw counts, production status counts and the original ruleset fingerprint. They
reran production and card-only classifications with the original SQL **and original
seed**, baseline multiset comparisons, reversed rule order, and priority mutation.
The second reviewer independently ran the strengthened verifier after the fix.

The aggregate [verification output](pr18_evidence_verification.json) records:

- One Puebla event, 2,234 participants, 2,222 decks and 18,788 result records.
- Production: 1,200 mapped, 1,022 unmapped and 12 missing lists.
- Card-only validation: 1,229 matched, 437 ambiguous, 556 unmatched and 12 missing.
- Zero legacy, repeated-build, reversed-rule and persisted-diagnostic differences.
- Matching snapshot/raw contents, rebuilt classifier inputs and checkout seed.
- A changed priority changes the ruleset fingerprint.

The implementation author also replayed all four snapshot tables through the
unmodified ingestion CLI into a new isolated database, one table per process with
separate dlt state directories. All 26 models rebuilt and all **97 data tests +
17 unit tests** passed. Ruff, changed-SQL SQLFluff and dbt parsing passed.
The first two historical regression tests were independently replayed from remote
commit `da20aa4fd26db6486c62e7748cf7f9ef700a29b2`; both failed as originally reported.

## Reproduction and CI scope

The [classification contract](archetype_classification.md#reproducing-the-adversarial-evidence-checks)
contains the verifier command and exact snapshot hash. For the one-table ingestion
workaround used in this runtime, create replay files in an isolated checkout:

```python
import gzip
import json
from pathlib import Path

source = Path("data/limitless_labs/issue7.json.gz")
rows = json.loads(gzip.decompress(source.read_bytes()))
for table in rows:
    subset = {key: rows[key] if key == table else [] for key in rows}
    target = source.with_name(f"issue7-{table}.json.gz")
    target.write_bytes(gzip.compress(json.dumps(subset).encode()))
```

Run from that isolated checkout's root:

```bash
for table in tournaments tournament_participants participant_deck participant_matches; do
  DLT_DATA_DIR="$(pwd)/data/limitless_labs/state-$table" \
    uv run --package pokemon-tcg-ingestion python -m ingestion.labs \
    --from-snapshot "data/limitless_labs/issue7-$table.json.gz" || exit 1
done
```

Then run the seed/rebuild/test and verifier commands. The usual combined snapshot
reload remains the normal workflow; this workaround does not change ingestion
code. GitHub CI runs Ruff, dbt parsing, Python logic/ingestion tests and dbt unit
tests without saved datasets. It does **not** run the real-data replay, 26-model
rebuild, full data tests or snapshot-dependent verifier. Those are local checks,
and a green CI result alone does not substantiate them.
