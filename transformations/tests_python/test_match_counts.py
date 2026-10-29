"""Exercise production SQL and semantic counts without a saved pipeline database."""

from pathlib import Path

import ibis
import pytest
import yaml
from boring_semantic_layer import from_config
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def con():
    connection = ibis.duckdb.connect()
    connection.raw_sql("""
        create schema main_semantic;
        create schema main_consumption;
        set schema=main_semantic;
        create table fct_matches (
            match_id varchar, tournament_id varchar, participant_id varchar,
            opponent_id varchar, round varchar, opponent_name varchar, result varchar
        );
        create table dim_participants as select * from (values
            ('a', 't1'), ('b', 't1'), ('c', 't1'), ('d', 't1'), ('e', 't1'),
            ('x', 't2'), ('y', 't2')
        ) p(participant_id, tournament_id);
        create table dim_tournaments as select *, 'play' as source,
            'online' as event_type, 'Event' as tournament_name,
            'STANDARD' as format, 'Winner' as winner_name, 5 as player_count
        from (values ('t1', date '2026-01-01'), ('t2', date '2026-02-01'))
            t(tournament_id, tournament_date);
        create table dim_pokemon_sets as select 'Set' as set_name,
            date '2025-12-01' as release_date
    """)
    yield connection
    connection.disconnect()


def record(
    mid, player="a", opponent="b", round_label="1", result="WIN", name="Bob", event="t1"
):
    return (mid, event, player, opponent, round_label, name, result)


def insert(con, *records):
    con.con.executemany(
        "insert into main_semantic.fct_matches values (?, ?, ?, ?, ?, ?, ?)",
        list(records),
    )


def ref(name):
    schema = (
        "main_consumption" if name == "mart_tournament_analysis" else "main_semantic"
    )
    return f"{schema}.{name}"


def render(path):
    return (
        Environment(undefined=StrictUndefined)
        .from_string(path.read_text())
        .render(ref=ref)
    )


def build(con, name="fct_tournament_matches"):
    layer = "consumption" if name.startswith("mart_") else "semantic"
    path = ROOT / f"transformations/models/{layer}/{name}.sql"
    con.raw_sql(f"create or replace table {ref(name)} as {render(path)}")


def rows(con, table="fct_tournament_matches"):
    cursor = con.raw_sql(
        f"select * from {ref(table)} order by tournament_id, match_group_id"
        if table == "fct_tournament_matches"
        else f"select * from {ref(table)} order by tournament_id"
    )
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


@pytest.mark.parametrize(
    "a,b,status",
    [
        ("WIN", "LOSS", "consistent"),
        ("LOSS", "WIN", "consistent"),
        ("TIE", "TIE", "consistent"),
        ("LOSS", "LOSS", "double_loss"),
        ("WIN", "WIN", "conflicting"),
        ("TIE", "LOSS", "conflicting"),
        (None, "LOSS", "incomplete"),
        ("PENDING", "LOSS", "incomplete"),
    ],
)
def test_mirrored_histories_keep_one_pairing_and_both_outcomes(con, a, b, status):
    insert(con, record("a1", result=a), record("b1", "b", "a", result=b, name="Alice"))
    build(con)
    (match,) = rows(con)
    assert match["canonical_match_id"] is not None
    assert match["perspective_record_count"] == 2
    assert match["perspective_record_ids"] == ["a1", "b1"]
    assert match["history_status"] == "mirrored"
    assert match["outcome_status"] == status
    assert con.raw_sql(
        "select result from fct_matches order by match_id"
    ).fetchall() == [(a,), (b,)]


def test_one_sided_pairing_keeps_stable_id_when_mirror_arrives(con):
    insert(con, record("a1", round_label=" Round 001 "))
    build(con)
    (first,) = rows(con)
    assert first["history_status"] == "one_sided"
    assert first["canonical_match_id"] is not None
    assert first["round_key"] == "1"
    insert(con, record("b1", "b", "a", round_label="1", result="LOSS", name="Alice"))
    build(con)
    (mirrored,) = rows(con)
    assert mirrored["canonical_match_id"] == first["canonical_match_id"]
    assert mirrored["history_status"] == "mirrored"


@pytest.mark.parametrize(
    "duplicate_id,duplicate_result,outcome",
    [
        ("a1", "WIN", "consistent"),
        ("a01", "WIN", "consistent"),
        ("a01", "LOSS", "conflicting"),
    ],
)
def test_duplicates_do_not_inflate_unique_counts(
    con, duplicate_id, duplicate_result, outcome
):
    insert(
        con,
        record("a1"),
        record("b1", "b", "a", result="LOSS"),
        record(duplicate_id, round_label="01", result=duplicate_result),
    )
    build(con)
    (match,) = rows(con)
    assert match["canonical_match_id"] is not None
    assert match["perspective_record_count"] == 3
    assert match["duplicate_perspective_record_count"] == 1
    assert match["outcome_status"] == outcome
    if outcome == "conflicting":
        assert match["low_player_result"] is None


@pytest.mark.parametrize(
    "round_label", [None, "", "  ", "?", "unknown", "0", "Round 0", "-1", "Round -1"]
)
def test_missing_or_invalid_round_is_unresolved(con, round_label):
    insert(con, record("a1", round_label=round_label))
    build(con)
    (match,) = rows(con)
    assert match["canonical_match_id"] is None
    assert match["resolution_reason"] == "missing_round"


@pytest.mark.parametrize(
    "player,opponent,name,reason",
    [
        ("a", "unknown", "Unknown", "unknown_opponent"),
        ("a", "x", "Known in another event", "unknown_opponent"),
        ("missing", "b", "Bob", "unknown_player"),
        ("a", "a", "Alice", "self_pairing"),
        ("a", "bye-id", " bye ", "bye"),
        ("a", None, None, "unknown_opponent"),
    ],
)
def test_byes_and_unresolved_records_are_not_played_matches(
    con, player, opponent, name, reason
):
    insert(con, record("a1", player, opponent, name=name))
    build(con)
    (match,) = rows(con)
    assert match["canonical_match_id"] is None
    assert match["resolution_reason"] == reason
    assert match["history_status"] == ("bye" if reason == "bye" else "unresolved")
    assert match["perspective_record_ids"] == ["a1"]


def test_distinct_rounds_phases_and_events_remain_distinct(con):
    insert(
        con,
        record("a1"),
        record("a2", round_label="2"),
        record("as1", round_label="Swiss 1"),
        record("at1", round_label="Top 1"),
        record("xs1", "x", "y", event="t2"),
    )
    build(con)
    matches = rows(con)
    assert len(matches) == 5
    assert len({m["canonical_match_id"] for m in matches}) == 5


def test_named_round_labels_normalize_case_and_whitespace(con):
    insert(
        con,
        record("a1", round_label=" Top   8 "),
        record("b1", "b", "a", round_label="top 8", result="LOSS"),
    )
    build(con)
    (match,) = rows(con)
    assert match["round_key"] == "top 8"
    assert match["history_status"] == "mirrored"


def test_conflicting_pairings_are_unresolved_including_inferred_reverse_edges(con):
    insert(
        con, record("ab"), record("bc", "b", "c", result="LOSS"), record("de", "d", "e")
    )
    build(con)
    matches = rows(con)
    resolved = [m for m in matches if m["canonical_match_id"] is not None]
    assert len(resolved) == 1
    assert resolved[0]["player_low_id"] == "d"
    assert (
        sum(
            m["perspective_record_count"]
            for m in matches
            if m["resolution_reason"] == "conflicting_pairing"
        )
        == 2
    )


def test_event_totals_and_semantic_models_expose_reconciliation_coverage(con):
    insert(
        con,
        record("a1"),
        record("a1"),
        record("b1", "b", "a", result="LOSS"),
        record("a2", round_label="2", result="TIE"),
        record("bye", opponent="bye-id", round_label="3", name="BYE"),
        record("unknown", opponent="missing", round_label="4", name="Unknown"),
        record("a5", round_label="5"),
        record("b5", "b", "a", "5", "WIN"),
        record("a6", round_label="6", result=None),
        record("b6", "b", "a", "6", "LOSS"),
    )
    build(con)
    build(con, "mart_tournament_analysis")
    populated, empty = rows(con, "mart_tournament_analysis")
    expected = {
        "total_matches": 10,
        "perspective_record_count": 10,
        "unique_match_count": 4,
        "mirrored_match_count": 3,
        "one_sided_match_count": 1,
        "bye_record_count": 1,
        "unresolved_perspective_record_count": 1,
        "duplicate_perspective_record_count": 1,
        "conflicting_outcome_match_count": 1,
        "incomplete_outcome_match_count": 1,
    }
    for name, count in expected.items():
        assert populated[name] == count
        assert empty[name] == 0
    # Execute the dbt coverage invariant against the same adversarial fixture.
    assert (
        con.raw_sql(
            render(
                ROOT / "transformations/tests/assert_match_reconciliation_counts.sql"
            )
        ).fetchall()
        == []
    )
    config = yaml.safe_load(
        (ROOT / "semantic_layer/semantic_layer/boring.yml").read_text()
    )
    names = ("tournament_analysis", "tournament_matches", "matches")
    tables = {
        config[name]["table"]: con.table(
            config[name]["table"], database=config[name]["database"]
        )
        for name in names
    }
    models = from_config({name: config[name] for name in names}, tables=tables)
    for model_name in ("tournament_analysis", "tournament_matches"):
        result = (
            models[model_name]
            .query(measures=["unique_match_count", "perspective_record_count"])
            .execute()
            .iloc[0]
        )
        assert result["unique_match_count"] == 4
        assert result["perspective_record_count"] == 10
    assert (
        models["matches"]
        .query(measures=["perspective_record_count"])
        .execute()
        .iloc[0]["perspective_record_count"]
        == 10
    )


def test_empty_histories_do_not_invent_matches(con):
    build(con)
    assert rows(con) == []
    build(con, "mart_tournament_analysis")
    assert all(
        row["unique_match_count"] == row["perspective_record_count"] == 0
        for row in rows(con, "mart_tournament_analysis")
    )
