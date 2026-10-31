"""Verify classification evidence using a hash-identified snapshot and a rebuilt DB.

This reads the database and Git history without changing either. Temporary tables
isolate the original rules, reversed rules, card-only inputs and priority mutation.
The JSON output contains aggregate results only, never player names or decklists.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import subprocess
from pathlib import Path

import duckdb
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "tournaments",
    "tournament_participants",
    "participant_deck",
    "participant_matches",
)
LEGACY_COLUMNS = "participant_id, archetype, sub_archetype, source_archetype_label, classification_method"
BASELINE = "11863bd8085c80a76753131268aa072ef1d801a9"


def load_snapshot(path, expected_sha256):
    data = gzip.decompress(path.read_bytes())
    observed = hashlib.sha256(data).hexdigest()
    if observed != expected_sha256:
        raise ValueError(
            f"Snapshot SHA-256 mismatch: expected {expected_sha256}, got {observed}"
        )
    return json.loads(data)


def snapshot_counts(path, expected_sha256):
    rows = load_snapshot(path, expected_sha256)
    return {table: len(rows[table]) for table in TABLES}


def difference_count(con, left, right, columns="*"):
    # EXCEPT ALL detects changed multiplicities as well as changed values.
    return con.execute(f"""
        select count(*) from (
            (select {columns} from {left} except all select {columns} from {right})
            union all
            (select {columns} from {right} except all select {columns} from {left})
        )
    """).fetchone()[0]


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def verify_records(con, records, relation):
    """Compare every supplied scalar field, including duplicate multiplicities."""
    if not records:
        require(
            con.execute(f"select count(*) from {relation}").fetchone()[0] == 0,
            f"Snapshot contents differ: {relation}",
        )
        return
    keys = sorted({key for row in records for key in row})
    columns = ", ".join(quote_identifier(key.lower()) for key in keys)
    con.execute(
        f"create or replace temp table audit_expected as select {columns} from {relation} where false"
    )
    placeholders = ", ".join("?" for _ in keys)
    con.executemany(
        f"insert into audit_expected values ({placeholders})",
        [[row.get(key) for key in keys] for row in records],
    )
    require(
        difference_count(con, "audit_expected", relation, columns) == 0,
        f"Snapshot contents differ: {relation}",
    )


def verify_snapshot_contents(con, rows):
    for table in TABLES:
        scalars = [
            {key: value for key, value in row.items() if key != "decklist"}
            for row in rows[table]
        ]
        verify_records(con, scalars, f"pokemon_tcg_data.{table}")
    cards = [
        dict(card, player=deck["player"], tournament=deck["tournament"])
        for deck in rows["participant_deck"]
        for card in deck["decklist"]
    ]
    con.execute("""create temp table audit_raw_cards as
        select p.player, p.tournament, c.name, c.code, c.quantity, c.kind
        from pokemon_tcg_data.participant_deck p
        join pokemon_tcg_data.participant_deck__decklist c on p._dlt_id=c._dlt_parent_id
    """)
    verify_records(con, cards, "audit_raw_cards")
    require(
        con.execute(
            "select count(*) from pokemon_tcg_data.participant_deck__decklist"
        ).fetchone()[0]
        == len(cards),
        "Snapshot deck-card count differs, including orphan rows",
    )


def verify_rebuilt_inputs(con):
    """Recompute the classifier's semantic inputs from the verified raw tables."""
    refs = {}
    for folder, model in (
        ("staging", "stg_participants"),
        ("staging", "stg_deck_cards"),
        ("semantic", "fct_deck_composition"),
    ):
        sql = (ROOT / f"transformations/models/{folder}/{model}.sql").read_text()
        table = f"audit_{model}"
        con.execute(f"create temp table {table} as " + render(sql, refs=refs))
        refs[model] = table
    for expected, actual in (
        ("audit_stg_participants", "dim_participants"),
        ("audit_fct_deck_composition", "fct_deck_composition"),
    ):
        require(
            difference_count(con, expected, f"main_semantic.{actual}") == 0,
            f"Rebuilt classifier input differs: {actual}",
        )


def git_text(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def surrogate_key(columns):
    # Rendering adapter for dbt_utils.generate_surrogate_key in these two models.
    # The classifier SQL itself is loaded from source, not reimplemented here.
    parts = [
        f"coalesce(cast({column} as varchar), '_dbt_utils_surrogate_key_null_')"
        for column in columns
    ]
    return "md5(" + " || '-' || ".join(parts) + ")"


def render(sql, rules="audit_rules", card_only=False, refs=None):
    return (
        Environment(undefined=StrictUndefined)
        .from_string(sql)
        .render(
            ref=lambda name: (refs or {}).get(
                name, rules if name == "meta_decks" else f"main_semantic.{name}"
            ),
            source=lambda _, name: "audit_empty_labels"
            if card_only and name == "tournament_participants"
            else f"pokemon_tcg_data.{name}",
            dbt_utils={"generate_surrogate_key": surrogate_key},
        )
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(database, snapshot, expected_sha256, baseline_ref):
    snapshot_rows = load_snapshot(snapshot, expected_sha256)
    counts = {table: len(snapshot_rows[table]) for table in TABLES}
    baseline = git_text("rev-parse", "--verify", f"{baseline_ref}^{{commit}}")
    old_sql = git_text(
        "show", f"{baseline}:transformations/models/semantic/dim_deck_archetypes.sql"
    )
    old_seed = git_text("show", f"{baseline}:transformations/seeds/meta_decks.csv")
    sql = (
        ROOT / "transformations/models/semantic/dim_deck_classification.sql"
    ).read_text()
    report = {
        "snapshot_sha256": expected_sha256,
        "snapshot_rows": counts,
        "baseline_commit": baseline,
    }
    with duckdb.connect(str(database), read_only=True) as con:
        con.begin()  # Keep bulk temporary inserts in one transaction.
        observed_counts = {
            table: con.execute(
                f"select count(*) from pokemon_tcg_data.{table}"
            ).fetchone()[0]
            for table in TABLES
        }
        require(
            observed_counts == counts,
            f"Database raw row counts differ from snapshot: {observed_counts}",
        )
        verify_snapshot_contents(con, snapshot_rows)
        verify_rebuilt_inputs(con)
        committed_rules = list(
            csv.DictReader((ROOT / "transformations/seeds/meta_decks.csv").open())
        )
        committed_rules = [
            {key: value or None for key, value in row.items()}
            for row in committed_rules
        ]
        verify_records(con, committed_rules, "main.meta_decks")
        report["snapshot_contents_match_raw"] = True
        report["classifier_inputs_match_rebuild"] = True
        report["seed_matches_checkout"] = True
        con.execute("create temp table audit_rules as select * from main.meta_decks")
        con.execute(
            "create temp table audit_empty_labels as select * from pokemon_tcg_data.tournament_participants where false"
        )
        con.execute(
            "create temp table audit_original_rules(card_name_1 varchar, card_name_2 varchar, archetype varchar, sub_archetype varchar)"
        )
        seed_rows = [
            [
                row[key] or None
                for key in ("card_name_1", "card_name_2", "archetype", "sub_archetype")
            ]
            for row in csv.DictReader(io.StringIO(old_seed))
        ]
        con.executemany(
            "insert into audit_original_rules values (?, ?, ?, ?)", seed_rows
        )
        con.execute(
            "create temp table audit_reversed_rules as select * from audit_rules order by rule_id desc"
        )
        con.execute(
            "create temp table audit_mutated_rules as select * from audit_rules"
        )
        con.execute(
            "update audit_mutated_rules set rule_priority=rule_priority+1 where rule_id=(select min(rule_id) from audit_rules)"
        )
        for card_only in (False, True):
            mode = "card_only" if card_only else "production"
            con.execute(
                "create or replace temp table audit_new as "
                + render(sql, card_only=card_only)
            )
            con.execute(
                "create or replace temp table audit_old as "
                + render(old_sql, "audit_original_rules", card_only)
            )
            con.execute(
                "create or replace temp table audit_classified as select * from audit_new where archetype is not null"
            )
            baseline_diff = difference_count(
                con, "audit_classified", "audit_old", LEGACY_COLUMNS
            )
            require(
                baseline_diff == 0,
                f"{mode}: legacy classification changed ({baseline_diff} rows)",
            )
            con.execute(
                "create or replace temp table audit_repeat as "
                + render(sql, card_only=card_only)
            )
            repeat_diff = difference_count(con, "audit_new", "audit_repeat")
            con.execute(
                "create or replace temp table audit_reversed as "
                + render(sql, "audit_reversed_rules", card_only)
            )
            reversed_diff = difference_count(con, "audit_new", "audit_reversed")
            require(
                repeat_diff == reversed_diff == 0,
                f"{mode}: diagnostics are not reproducible",
            )
            con.execute(
                "create or replace temp table audit_mutated as "
                + render(sql, "audit_mutated_rules", card_only)
            )
            versions = con.execute(
                "select distinct ruleset_version from audit_new"
            ).fetchall()
            mutated_versions = con.execute(
                "select distinct ruleset_version from audit_mutated"
            ).fetchall()
            require(
                len(versions) == 1 and versions != mutated_versions,
                f"{mode}: priority edit did not change version",
            )
            statuses = dict(
                con.execute(
                    "select classification_status, count(*) from audit_new group by 1"
                ).fetchall()
            )
            report[mode] = dict(
                status_counts=statuses,
                legacy_difference_rows=baseline_diff,
                repeat_difference_rows=repeat_diff,
                reversed_rule_difference_rows=reversed_diff,
                ruleset_version=versions[0][0],
                priority_changes_version=True,
            )
            if not card_only:
                persisted_diff = difference_count(
                    con, "audit_new", "main_semantic.dim_deck_classification"
                )
                require(
                    persisted_diff == 0,
                    "Persisted diagnostics differ from production SQL; rebuild first",
                )
                report[mode]["persisted_difference_rows"] = persisted_diff
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--expected-snapshot-sha256", required=True)
    parser.add_argument("--baseline-ref", default=BASELINE)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(
                args.database,
                args.snapshot,
                args.expected_snapshot_sha256,
                args.baseline_ref,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
