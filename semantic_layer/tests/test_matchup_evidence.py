"""Regression checks for matchup evidence, provenance and pooled uncertainty."""

import asyncio
from pathlib import Path

import duckdb
import ibis
import pandas as pd
import pytest
import yaml
from boring_semantic_layer import MCPSemanticModel, from_config
from fastmcp import Client
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]


def build(con, name, layer):
    sql = (ROOT / f"transformations/models/{layer}/{name}.sql").read_text()
    con.execute(
        f"create table {name} as "
        + Environment(undefined=StrictUndefined)
        .from_string(sql)
        .render(ref=lambda n: n)
    )


@pytest.fixture
def observations():
    with duckdb.connect() as con:
        con.execute("""
            create table dim_participants as select * from (values
                ('p1', 'e1', 'One'), ('p2', 'e1', 'Two'),
                ('p3', 'e1', 'No history'), ('p4', 'e1', 'Unclassified'),
                ('p5', 'e2', 'Elsewhere')
            ) t(participant_id, tournament_id, player_name);
            alter table dim_participants add column decklist_link varchar;
            create table dim_deck_archetypes as select * from (values
                ('p1', 'A', 'A1'), ('p2', 'B', 'B1'),
                ('p3', 'A', 'A1'), ('p5', 'A', 'A1')
            ) t(participant_id, archetype, sub_archetype);
            create table int_tournament_context as select * from (values
                ('e1', 'Event 1', 'https://example/e1', date '2026-10-01',
                 'STANDARD', 'Set', 'limitless_labs', 'in_person'),
                ('e2', 'Event 2', 'https://example/e2', date '2026-10-02',
                 'EXPANDED', 'Set', 'limitless_play', 'online')
            ) t(tournament_id, tournament_name, tournament_url, tournament_date,
                format, set_name, source, event_type);
            create table fct_matches as select * from (values
                ('m1', 'e1', 'p1', 'p2', 'Two', '1', 'WIN'),
                ('m2', 'e1', 'p2', 'p1', 'One', '1', 'LOSS'),
                ('m3', 'e1', 'p1', 'p2', 'Two', '2', 'TIE'),
                ('m4', 'e1', 'p1', 'bye', 'BYE', '3', 'WIN'),
                ('m5', 'e1', 'p1', 'p4', 'Unclassified', '4', 'LOSS'),
                ('m6', 'e1', 'p1', 'p3', 'No history', '5', 'WIN'),
                ('m7', 'e1', 'p1', 'p2', 'Two', '6', 'PENDING'),
                ('m8', 'e2', 'p5', 'outside', 'Outside', '1', 'WIN')
            ) t(match_id, tournament_id, participant_id, opponent_id,
                opponent_name, round, result);
        """)
        build(con, "fct_matchup_results", "semantic")
        build(con, "mart_matchup_evidence", "consumption")
        yield con


def test_counts_exclude_byes_unknowns_mirrors_and_invalid_results(observations):
    assert observations.execute("""
        select sum(sample_size), sum(wins), sum(losses), sum(ties),
            sum(bye_results), sum(unknown_archetype_results), sum(mirror_results),
            sum(invalid_results), sum(participants_without_history)
        from mart_matchup_evidence
    """).fetchone() == (3, 1, 1, 1, 1, 2, 1, 1, 2)


def test_mirrored_perspectives_are_directed_not_deduplicated(observations):
    assert observations.execute("""
        select p1_archetype, p2_archetype, sample_size, wins, losses, ties
        from mart_matchup_evidence where matchup_type='played'
        order by p1_archetype
    """).fetchall() == [("A", "B", 2, 1, 0, 1), ("B", "A", 1, 0, 1, 0)]


def test_result_drilldown_preserves_event_and_record_provenance(observations):
    assert observations.execute("""
        select tournament_url, tournament_date, game, format,
            match_id, participant_id, opponent_id, round, result
        from fct_matchup_results where match_id='m3'
    """).fetchone() == (
        "https://example/e1",
        pd.Timestamp("2026-10-01").date(),
        "PTCG",
        "STANDARD",
        "m3",
        "p1",
        "p2",
        "2",
        "TIE",
    )
    assert (
        observations.execute("""
        select count(*) from mart_matchup_evidence
        where tournament_id='e2' and format='EXPANDED' and source='limitless_play'
    """).fetchone()[0]
        == 1
    )


def test_missing_history_is_not_a_loss_or_zero_percent(observations):
    assert observations.execute("""
        select sample_size, wins, losses, ties, participants_without_history
        from mart_matchup_evidence where tournament_id='e1' and matchup_type='missing_history'
        and p1_archetype='A'
    """).fetchone() == (0, 0, 0, 0, 1)


@pytest.fixture
def semantic():
    config = yaml.safe_load(
        (ROOT / "semantic_layer/semantic_layer/boring.yml").read_text()
    )["matchup_evidence"]
    con = ibis.duckdb.connect()
    con.raw_sql("create schema main_consumption; set schema=main_consumption")
    con.raw_sql("""
        create table mart_matchup_evidence as select *, 'Set' as set_name,
            'labs' as source, 'in_person' as event_type,
            'A' as p1_archetype, 'B' as p2_archetype from (values
            ('e1', 'PTCG', 'STANDARD', date '2026-10-01', 'played', 1, 1, 0, 0),
            ('e2', 'PTCG', 'STANDARD', date '2026-10-02', 'played', 9, 0, 5, 4),
            ('e3', 'PTCG', 'EXPANDED', date '2026-10-03', 'played', 90, 90, 0, 0),
            ('e4', 'PTCG', 'STANDARD', date '2026-10-04', 'missing_history', 0, 0, 0, 0)
        ) t(tournament_id, game, format, tournament_date, matchup_type,
            sample_size, wins, losses, ties)
    """)
    yield from_config(
        {"matchup_evidence": config},
        tables={config["table"]: con.table(config["table"])},
    )["matchup_evidence"]
    con.disconnect()


def test_wilson_interval_uses_pooled_counts_and_ties_as_nonwins(semantic):
    row = (
        semantic.query(
            measures=[
                "sample_size",
                "win_rate",
                "win_rate_lower_95",
                "win_rate_upper_95",
            ],
            filters=[lambda t: t.format == "STANDARD"],
        )
        .execute()
        .iloc[0]
    )
    assert row["sample_size"] == 10
    assert row["win_rate"] == 10
    assert row["win_rate_lower_95"] == pytest.approx(1.7876, abs=0.001)
    assert row["win_rate_upper_95"] == pytest.approx(40.4150, abs=0.001)


@pytest.mark.parametrize("event", ["e1", "e2"])
def test_small_all_win_and_no_win_samples_have_bounded_intervals(semantic, event):
    row = (
        semantic.query(
            measures=["win_rate", "win_rate_lower_95", "win_rate_upper_95"],
            filters=[lambda t: t.tournament_id == event],
        )
        .execute()
        .iloc[0]
    )
    assert 0 <= row["win_rate_lower_95"] <= row["win_rate"]
    assert row["win_rate"] <= row["win_rate_upper_95"] <= 100


def test_zero_samples_return_null_rates_and_intervals(semantic):
    row = (
        semantic.query(
            measures=["win_rate", "win_rate_lower_95", "win_rate_upper_95"],
            filters=[lambda t: t.tournament_id == "e4"],
        )
        .execute()
        .iloc[0]
    )
    assert row.isna().all()


def test_minimum_sample_filter_applies_to_pooled_groups(semantic):
    from semantic_layer.matchups import query_matchup_evidence

    output = query_matchup_evidence(semantic, min_sample_size=10)
    assert sorted(row["sample_size"] for row in output["rows"]) == [10, 90]
    assert output["qualifying_groups"] == 2


@pytest.mark.parametrize("minimum", [0, -1, 1.5, True])
def test_sample_filter_rejects_invalid_thresholds(semantic, minimum):
    from semantic_layer.matchups import query_matchup_evidence

    with pytest.raises(ValueError, match="positive integer"):
        query_matchup_evidence(semantic, min_sample_size=minimum)


def test_sample_filter_does_not_mix_formats_or_apply_limit_before_threshold(semantic):
    from semantic_layer.matchups import query_matchup_evidence

    output = query_matchup_evidence(semantic, min_sample_size=10, limit=1)
    assert output["qualifying_groups"] == 2
    assert output["rows"][0]["format"] == "EXPANDED"
    assert output["rows"][0]["sample_size"] == 90
    output = query_matchup_evidence(
        semantic,
        min_sample_size=11,
        filters=[{"field": "format", "operator": "=", "value": "STANDARD"}],
    )
    assert output["rows"] == []


def test_mcp_tool_exposes_post_pool_sample_filter(semantic):
    from semantic_layer.matchups import register_matchup_tools

    server = MCPSemanticModel(models={"matchup_evidence": semantic})
    register_matchup_tools(server, {"matchup_evidence": semantic})

    async def call():
        async with Client(server) as client:
            return await client.call_tool(
                "query_matchup_evidence_with_minimum_sample", {"min_sample_size": 10}
            )

    result = asyncio.run(call())
    assert result.data["qualifying_groups"] == 2


def test_sample_measure_cannot_be_misused_as_a_pre_pool_filter(semantic):
    from semantic_layer.matchups import query_matchup_evidence

    with pytest.raises(ValueError, match="dimension"):
        query_matchup_evidence(
            semantic, filters=[{"field": "sample_size", "operator": ">=", "value": 10}]
        )
