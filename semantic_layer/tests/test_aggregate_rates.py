"""Execute the production semantic definitions against isolated synthetic cohorts."""

from pathlib import Path

import ibis
import pandas as pd
import pytest
import yaml
from boring_semantic_layer import from_config
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
CONFIG = yaml.safe_load((ROOT / "semantic_layer/semantic_layer/boring.yml").read_text())


@pytest.fixture
def con():
    connection = ibis.duckdb.connect()
    connection.raw_sql("create schema main_consumption; set schema=main_consumption")
    yield connection
    connection.disconnect()


def model(con, name, sql):
    config = CONFIG[name]
    table = config["table"]
    con.raw_sql(f"create or replace table {table} as {sql}")
    return from_config({name: config}, tables={table: con.table(table)})[name]


def value(semantic_model, measure, **kwargs):
    return semantic_model.query(measures=[measure], **kwargs).execute().iloc[0][measure]


@pytest.mark.parametrize(
    "name,measure,expected",
    [
        ("archetype_stats", "avg_win_rate", 10),
        ("monthly_meta_shifts", "avg_win_rate", 10),
        ("archetype_matchups", "win_no_ties_rate", 10),
        ("archetype_matchups", "win_ties_rate", 30),
        ("deck_analysis", "avg_win_rate", 10),
    ],
)
def test_rates_pool_unequal_samples_across_periods_and_archetypes(
    con, name, measure, expected
):
    semantic_model = model(
        con,
        name,
        """
        select *, archetype as p1_archetype, 'Opponent' as p2_archetype,
            'Variant' as sub_archetype, 'Variant' as p1_sub_archetype,
            'Variant' as p2_sub_archetype, 'Player' as player_name,
            'event' as tournament_url, wins as archetype_participants,
            10.0 as meta_share
        from (values
            ('Set A', date '2026-01-01', 'Deck A', 'play', 'online', 1, 1, 0, 0),
            ('Set B', date '2026-02-01', 'Deck B', 'labs', 'in_person', 99, 9, 70, 20)
        ) t(set_name, tournament_month, archetype, source, event_type,
            total_matches, wins, losses, ties)
    """,
    )
    assert value(semantic_model, measure) == pytest.approx(expected)
    assert value(semantic_model, measure, filters=[lambda t: t.source == "play"]) == 100
    by_source = semantic_model.query(
        dimensions=["source"], measures=[measure]
    ).execute()
    assert len(by_source) == 2
    assert by_source.loc[by_source.source == "labs", measure].iloc[0] == pytest.approx(
        (29 if measure == "win_ties_rate" else 9) * 100 / 99
    )
    con.raw_sql(f"update {CONFIG[name]['table']} set wins=0, ties=0, total_matches=0")
    assert pd.isna(value(semantic_model, measure))
    con.raw_sql(f"delete from {CONFIG[name]['table']}")
    assert pd.isna(value(semantic_model, measure))


def test_suggestions_pool_counts_and_return_null_for_missing_comparison_groups(con):
    semantic_model = model(
        con,
        "matchup_suggestions",
        """
        select *, 'Deck' as archetype, 'Opponent' as opponent_archetype,
            'Tech' as suggested_card, 'trainer' as card_kind,
            'play' as source, 'online' as event_type
        from (values
            ('Set A', 1, 1, 4, 1, 1),
            ('Set B', 99, 9, 16, 3, 90)
        ) t(set_name, sample_size, wins_with_card, matches_without_card,
            wins_without_card, quantity_in_wins)
    """,
    )
    assert value(semantic_model, "avg_win_rate_with_card") == pytest.approx(10)
    assert value(semantic_model, "avg_win_rate_without_card") == pytest.approx(20)
    assert value(semantic_model, "avg_relevance_score") == pytest.approx(-10)
    assert value(semantic_model, "avg_suggested_quantity") == pytest.approx(9.1)
    con.raw_sql("""
        update mart_archetype_matchup_suggestions
        set matches_without_card=0, wins_without_card=0, wins_with_card=0,
            quantity_in_wins=0
    """)
    assert value(semantic_model, "avg_win_rate_with_card") == 0
    for measure in (
        "avg_win_rate_without_card",
        "avg_relevance_score",
        "avg_suggested_quantity",
    ):
        assert pd.isna(value(semantic_model, measure))
    con.raw_sql("update mart_archetype_matchup_suggestions set sample_size=0")
    assert pd.isna(value(semantic_model, "avg_win_rate_with_card"))


def test_staple_quantity_is_weighted_by_included_decks(con):
    semantic_model = model(
        con,
        "card_staples",
        """
        select *, 'Deck' as archetype, 'Tech' as card_name, 'trainer' as card_kind,
            'play' as source, 'online' as event_type, 10.0 as inclusion_rate
        from (values ('A', 1, 4), ('B', 9, 9))
            t(set_name, decks_with_card, total_quantity_when_included)
    """,
    )
    assert value(semantic_model, "avg_mean_quantity") == pytest.approx(1.3)
    con.raw_sql("update mart_archetype_card_staples set decks_with_card=0")
    assert pd.isna(value(semantic_model, "avg_mean_quantity"))


def build(con, name):
    sql = (ROOT / f"transformations/models/consumption/{name}.sql").read_text()
    rendered = (
        Environment(undefined=StrictUndefined).from_string(sql).render(ref=lambda x: x)
    )
    con.raw_sql(f"create table {name} as {rendered}")


def test_population_totals_are_not_repeated_across_categories(con):
    # Three January entrants and five February entrants, one unclassified each.
    # Only January has published cards: two decks, two cards, and two printings
    # of Tech in the first deck. Membership must count that deck only once.
    con.raw_sql("""
        create table dim_participants as select * from (values
            ('p1', 'e1'), ('p2', 'e1'), ('p3', 'e1'),
            ('p4', 'e2'), ('p5', 'e2'), ('p6', 'e2'), ('p7', 'e2'), ('p8', 'e2')
        ) t(participant_id, tournament_id);
        create table dim_tournaments as select *, 'play' as source, 'online' as event_type
        from (values ('e1', date '2026-01-01'), ('e2', date '2026-02-01'))
            t(tournament_id, tournament_date);
        create table dim_deck_archetypes as select * from (values
            ('p1', 'Deck A'), ('p2', 'Deck B'), ('p4', 'Deck A'),
            ('p5', 'Deck A'), ('p6', 'Deck B'), ('p7', 'Deck B')
        ) t(participant_id, archetype);
        create table fct_matches as select 'p1' as participant_id,
            'e1' as tournament_id, 'WIN' as result;
        create table int_classified_deck_cards as select *, 'Set' as set_name,
            'play' as source, 'online' as event_type, 'trainer' as card_kind
        from (values
            ('p1', 'Deck A', 'Tech', 1), ('p1', 'Deck A', 'Tech', 2),
            ('p1', 'Deck A', 'Other', 1), ('p2', 'Deck B', 'Tech', 1)
        ) t(participant_id, archetype, card_name, quantity)
    """)
    for name in (
        "mart_monthly_populations",
        "mart_monthly_meta_shifts",
        "mart_archetype_deck_populations",
        "mart_archetype_card_staples",
    ):
        build(con, name)
    for name, measure, expected in (
        ("monthly_populations", "total_participants", 8),
        ("archetype_deck_populations", "total_archetype_decks", 2),
    ):
        config = CONFIG[name]
        semantic_model = from_config(
            {name: config}, tables={config["table"]: con.table(config["table"])}
        )[name]
        assert value(semantic_model, measure) == expected
    assert con.raw_sql("""
        select strftime(tournament_month, '%Y-%m'), total_participants
        from mart_monthly_populations order by tournament_month
    """).fetchall() == [("2026-01", 3), ("2026-02", 5)]
    assert con.raw_sql("""
        select strftime(tournament_month, '%Y-%m'), archetype,
            archetype_participants, meta_share
        from mart_monthly_meta_shifts order by tournament_month, archetype
    """).fetchall() == [
        ("2026-01", "Deck A", 1, 33.33),
        ("2026-01", "Deck B", 1, 33.33),
        ("2026-02", "Deck A", 2, 40.0),
        ("2026-02", "Deck B", 2, 40.0),
    ]
    # Pool counts across months; do not average monthly percentages or repeat
    # the population once for each archetype.
    assert con.raw_sql("""
        select 100.0 * (
            select sum(archetype_participants) from mart_monthly_meta_shifts
            where archetype = 'Deck A'
        ) / (select sum(total_participants) from mart_monthly_populations)
    """).fetchone()[0] == pytest.approx(37.5)
    assert con.raw_sql("""
        select decks_with_card, total_quantity_when_included, inclusion_rate
        from mart_archetype_card_staples where archetype='Deck A' and card_name='Tech'
    """).fetchone() == (1, 3, 100.0)
    # Repeated denominators and non-additive percentages are not exposed as measures.
    for name, forbidden in (
        ("monthly_meta_shifts", ("total_participants", "meta_share")),
        ("card_staples", ("total_archetype_decks", "inclusion_rate")),
    ):
        for measure in forbidden:
            assert measure not in CONFIG[name]["measures"]


def test_deck_mart_uses_percentage_and_preserves_missing_results(con):
    con.raw_sql("""
        create table dim_participants as select * from (values
            ('p1', 'e1', 'Alex', 'event'), ('p2', 'e1', 'Sam', 'event')
        ) t(participant_id, tournament_id, player_name, tournament_url);
        create table dim_tournaments as select 'e1' as tournament_id,
            date '2026-01-01' as tournament_date, 'play' as source, 'online' as event_type;
        create table dim_pokemon_sets as select 'Set' as set_name,
            date '2025-12-01' as release_date;
        create table fct_matches as select * from (values ('p1', 'WIN'), ('p1', 'TIE'))
            t(participant_id, result)
    """)
    build(con, "mart_deck_analysis")
    rows = dict(
        con.raw_sql("select player_name, win_rate from mart_deck_analysis").fetchall()
    )
    assert rows == {"Alex": 50.0, "Sam": None}


def test_card_deck_count_deduplicates_printings_and_card_selections(con):
    con.raw_sql("create schema main_semantic")
    config = CONFIG["cards_used"]
    con.raw_sql("""
        create table main_semantic.int_classified_deck_cards as select *,
            'Set' as set_name, 'trainer' as card_kind, 'play' as source,
            'online' as event_type
        from (values ('p1', 'Tech', 'A', 1), ('p1', 'Tech', 'B', 2),
            ('p1', 'Other', 'C', 1), ('p2', 'Tech', 'A', 1))
            t(participant_id, card_name, card_code, quantity)
    """)
    semantic_model = from_config(
        {"cards_used": config},
        tables={config["table"]: con.table(config["table"], database="main_semantic")},
    )["cards_used"]
    assert value(semantic_model, "decks_containing") == 2
    assert (
        value(
            semantic_model,
            "decks_containing",
            filters=[lambda t: t.card_name == "Tech"],
        )
        == 2
    )
    assert (
        value(semantic_model, "total_used", filters=[lambda t: t.card_name == "Tech"])
        == 4
    )


def test_classification_diagnostics_count_every_status(con):
    con.raw_sql("create schema main_semantic; set schema=main_semantic")
    semantic_model = model(
        con,
        "deck_classification",
        """
        select * from (values
            ('p1', 'ambiguous'), ('p2', 'unmatched'), ('p3', 'missing_decklist')
        ) t(participant_id, classification_status)
        """,
    )
    assert value(semantic_model, "participants") == 3
    rows = semantic_model.query(
        dimensions=["classification_status"], measures=["participants"]
    ).execute()
    assert dict(zip(rows.classification_status, rows.participants)) == {
        "ambiguous": 1,
        "unmatched": 1,
        "missing_decklist": 1,
    }
