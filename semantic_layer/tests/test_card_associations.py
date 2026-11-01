"""Exercise the production association SQL and semantic definitions on isolated cohorts."""

from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def con():
    with duckdb.connect() as connection:
        connection.execute("""
            create table int_tournament_context(
                tournament_id varchar, set_name varchar, source varchar,
                event_type varchar, format varchar
            );
            create table dim_deck_archetypes(participant_id varchar, archetype varchar);
            create table fct_matches(
                match_id varchar, participant_id varchar, opponent_id varchar,
                tournament_id varchar, result varchar
            );
            create table fct_deck_composition(
                participant_id varchar, card_name varchar, card_kind varchar, quantity int
            );
            create table int_classified_deck_cards(
                participant_id varchar, card_name varchar, card_kind varchar, quantity int,
                set_name varchar, source varchar, event_type varchar
            );
            create table mart_archetype_card_staples(
                set_name varchar, source varchar, event_type varchar,
                archetype varchar, card_name varchar, card_kind varchar, inclusion_rate double
            )
        """)
        yield connection


def entry(con, name, results, tech=False, published=True, **cohort):
    values = dict(
        set_name="Set A",
        source="limitless_labs",
        event_type="in_person",
        format="STANDARD",
    )
    values.update(cohort)
    con.execute(
        "insert into int_tournament_context values (?, ?, ?, ?, ?)",
        [name, *values.values()],
    )
    con.execute(
        "insert into dim_deck_archetypes values (?, 'Deck'), (?, 'Opponent')",
        [name, name + "-opponent"],
    )
    for index, result in enumerate(results):
        con.execute(
            "insert into fct_matches values (?, ?, ?, ?, ?)",
            [f"{name}-{index}", name, name + "-opponent", name, result],
        )
    if published:
        cards = [("Anchor", 1)] + ([("Tech", 1), ("Tech", 3)] if tech else [])
        for card, quantity in cards:
            con.execute(
                "insert into fct_deck_composition values (?, ?, 'trainer', ?)",
                [name, card, quantity],
            )
            con.execute(
                "insert into int_classified_deck_cards values (?, ?, 'trainer', ?, ?, ?, ?)",
                [
                    name,
                    card,
                    quantity,
                    values["set_name"],
                    values["source"],
                    values["event_type"],
                ],
            )


def build(con, **variables):
    def fail(message):
        raise ValueError(message)

    sql = (
        ROOT
        / "transformations/models/consumption/mart_archetype_matchup_suggestions.sql"
    ).read_text()
    rendered = (
        Environment(undefined=StrictUndefined)
        .from_string(sql)
        .render(
            ref=lambda name: name,
            var=lambda name, default: variables.get(name, default),
            exceptions=SimpleNamespace(raise_compiler_error=fail),
        )
    )
    con.execute("create or replace table associations as " + rendered)


def tech(con):
    result = con.execute("select * from associations where suggested_card='Tech'")
    names = [column[0] for column in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def test_tiny_samples_remain_visible_but_unranked(con):
    entry(con, "with", ["WIN"], tech=True)
    entry(con, "without", ["LOSS"])
    build(con)
    rows = tech(con)
    assert len(rows) == 1
    row = rows[0]
    assert (row["sample_size"], row["matches_without_card"]) == (1, 1)
    assert row["evidence_status"] == "insufficient_matches"
    assert row["association_rank"] is None
    assert (row["min_matches_per_group"], row["min_decks_per_group"]) == (10, 3)


def test_absent_comparison_group_has_null_rate_and_difference(con):
    entry(con, "with", ["TIE"], tech=True)
    build(con)
    row = tech(con)[0]
    assert row["matches_without_card"] == 0
    assert row["win_rate_with_card"] == 0
    assert row["win_rate_without_card"] is None
    assert row["relevance_score"] is None
    assert row["evidence_status"] == "missing_comparison_group"
    assert row["association_rank"] is None


def test_unpublished_lists_are_not_without_card_evidence(con):
    entry(con, "with", ["WIN"], tech=True)
    entry(con, "without", ["LOSS"])
    entry(con, "unpublished", ["WIN"], published=False)
    build(con)
    row = tech(con)[0]
    assert row["matches_without_card"] == 1
    assert row["recorded_match_count"] == 3
    assert row["matches_with_decklists"] == 2
    assert row["decklist_match_coverage"] == pytest.approx(200 / 3)


def test_repeated_results_do_not_replace_deck_sample_threshold(con):
    entry(con, "with", ["WIN"] * 10, tech=True)
    entry(con, "without", ["LOSS"] * 10)
    build(con)
    row = tech(con)[0]
    assert (row["decks_with_card"], row["decks_without_card"]) == (1, 1)
    assert row["evidence_status"] == "insufficient_decks"
    assert row["association_rank"] is None


def test_adequate_samples_expose_outcomes_and_descriptive_ranking(con):
    for index in range(3):
        entry(con, f"with-{index}", ["WIN", "WIN", "LOSS", "TIE"], tech=True)
        entry(con, f"without-{index}", ["WIN", "LOSS", "LOSS", "LOSS"])
    build(con)
    row = tech(con)[0]
    assert (row["sample_size"], row["matches_without_card"]) == (12, 12)
    assert (row["wins_with_card"], row["losses_with_card"], row["ties_with_card"]) == (
        6,
        3,
        3,
    )
    assert (
        row["wins_without_card"],
        row["losses_without_card"],
        row["ties_without_card"],
    ) == (3, 9, 0)
    assert (row["decks_with_card"], row["decks_without_card"]) == (3, 3)
    assert (
        row["win_rate_with_card"],
        row["win_rate_without_card"],
        row["relevance_score"],
    ) == (50, 25, 25)
    assert row["suggested_quantity"] == 4
    assert row["evidence_status"] == "meets_sample_thresholds"
    assert row["association_rank"] == 1


@pytest.mark.parametrize(
    "dimension,value",
    [
        ("set_name", "Set B"),
        ("source", "limitless_play"),
        ("event_type", "online"),
        ("format", "EXPANDED"),
    ],
)
def test_incompatible_cohorts_are_not_comparison_groups(con, dimension, value):
    entry(con, "with", ["WIN"], tech=True)
    entry(con, "elsewhere", ["LOSS"], **{dimension: value})
    build(con)
    row = tech(con)[0]
    assert row["matches_without_card"] == 0
    assert row["game"] == "PTCG"
    assert row["format"] == "STANDARD"


def test_threshold_configuration_is_applied_before_ranking(con):
    entry(con, "with", ["WIN"], tech=True)
    entry(con, "without", ["LOSS"])
    build(con, association_min_matches=1, association_min_decks=1)
    assert tech(con)[0]["evidence_status"] == "meets_sample_thresholds"


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_invalid_thresholds_are_rejected(con, value):
    with pytest.raises(ValueError, match="positive integers"):
        build(con, association_min_matches=value)


def test_no_results_do_not_invent_associations(con):
    entry(con, "no-history", [], tech=True)
    build(con)
    assert con.execute("select count(*) from associations").fetchone()[0] == 0
