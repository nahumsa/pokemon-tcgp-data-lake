"""Regressions using mixed providers, unequal samples and alternate card printings."""

from pathlib import Path

import duckdb
import ibis
import pytest
import yaml
from boring_semantic_layer import from_config
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "transformations/models"


def render_model(name):
    path = next(MODELS.rglob(name + ".sql"))
    env = Environment(undefined=StrictUndefined)
    env.globals["ref"] = lambda value: value
    env.globals["source"] = lambda _source, table: table
    env.globals["dbt_utils"] = {
        "generate_surrogate_key": lambda columns: "md5(concat_ws('|', "
        + ", ".join(columns)
        + "))"
    }
    return env.from_string(path.read_text()).render()


def build_model(con, name):
    con.execute(f"create table {name} as " + render_model(name))


@pytest.fixture
def analytics():
    con = duckdb.connect(":memory:")
    con.execute("""create table dim_tournaments (
        tournament_id varchar, tournament_date date, source varchar, event_type varchar)""")
    con.execute("""insert into dim_tournaments values
        ('lab', '2026-09-26', 'limitless_labs', 'in_person'),
        ('play', '2026-09-26', 'limitless_play', 'online'),
        ('lab_oct', '2026-10-03', 'limitless_labs', 'in_person')""")
    con.execute(
        "create table int_tournament_context as select *, 'Example period' as set_name from dim_tournaments"
    )
    con.execute(
        "create table dim_participants (participant_id varchar, tournament_id varchar)"
    )
    con.executemany(
        "insert into dim_participants values (?, ?)",
        [
            ("a1", "lab"),
            ("a2", "lab"),
            ("a3", "lab"),
            ("b", "lab"),
            ("p", "play"),
            *[(f"o{i}", "lab_oct") for i in range(4)],
        ],
    )
    con.execute(
        "create table dim_deck_archetypes (participant_id varchar, archetype varchar, sub_archetype varchar)"
    )
    con.executemany(
        "insert into dim_deck_archetypes values (?, ?, ?)",
        [
            ("a1", "A", "A variant"),
            ("a2", "A", "A variant"),
            ("a3", "A", "A variant"),
            ("b", "B", "B variant"),
            ("p", "A", "A variant"),
        ],
    )
    con.execute("""create table fct_deck_composition (
        participant_id varchar, card_entry_id varchar, card_name varchar,
        card_code varchar, card_kind varchar, quantity integer)""")
    cards = [
        (p, p + "-base", "Base", "SET-1", "pokemon", 2)
        for p in ["a1", "a2", "a3", "b", "p"]
    ]
    cards += [
        ("a1", "tech1", "Tech", "SET-2", "pokemon", 1),
        ("a1", "tech2", "Tech", "SET-3", "pokemon", 1),
    ]
    con.executemany("insert into fct_deck_composition values (?, ?, ?, ?, ?, ?)", cards)
    con.execute("""create table fct_matches (
        match_id varchar, participant_id varchar, opponent_id varchar, tournament_id varchar, result varchar)""")
    matches = [
        (f"l{i}", "a1" if i < 4 else "a2", "b", "lab", "WIN" if i < 3 else "LOSS")
        for i in range(10)
    ]
    matches += [
        (f"p{i}", "p", "p", "play", "WIN" if i < 18 else "LOSS") for i in range(20)
    ]
    con.executemany("insert into fct_matches values (?, ?, ?, ?, ?)", matches)
    for name in [
        "int_classified_deck_cards",
        "mart_archetype_deck_populations",
        "mart_monthly_populations",
        "mart_archetype_stats",
        "mart_archetype_matchups",
        "mart_cards_used",
        "mart_archetype_card_staples",
        "mart_monthly_meta_shifts",
        "mart_archetype_matchup_suggestions",
    ]:
        build_model(con, name)
    yield con
    con.close()


def semantic_models(con, *names):
    config = yaml.safe_load(
        (ROOT / "semantic_layer/semantic_layer/boring.yml").read_text()
    )
    backend = ibis.duckdb.from_connection(con)
    selected = {
        name: {k: v for k, v in config[name].items() if k != "database"}
        for name in names
    }
    tables = {
        definition["table"]: backend.table(definition["table"])
        for definition in selected.values()
    }
    return from_config(selected, tables=tables)


def test_sources_and_settings_remain_separate_in_every_aggregate(analytics):
    for name in [
        "mart_archetype_stats",
        "mart_archetype_matchups",
        "mart_cards_used",
        "mart_archetype_card_staples",
        "mart_monthly_meta_shifts",
    ]:
        providers = analytics.execute(
            f"select distinct source, event_type from {name}"
        ).fetchall()
        assert set(providers) == {
            ("limitless_labs", "in_person"),
            ("limitless_play", "online"),
        }
    rates = analytics.execute(
        "select source, win_rate from mart_archetype_stats where archetype='A'"
    ).fetchall()
    assert dict(rates) == {"limitless_labs": 30.0, "limitless_play": 90.0}


def test_printings_do_not_duplicate_suggestions_or_card_membership(analytics):
    suggestions = analytics.execute("""select source,suggested_card,sample_size,suggested_quantity
        from mart_archetype_matchup_suggestions""").fetchall()
    assert suggestions == [("limitless_labs", "Tech", 4, 2.0)]
    inclusion = analytics.execute("""select decks_with_card,total_archetype_decks,mean_quantity
        from mart_archetype_card_staples where card_name='Tech' """).fetchone()
    assert inclusion == (1, 3, 2.0)
    models = semantic_models(analytics, "cards_used")
    data = (
        models["cards_used"]
        .query(
            dimensions=["card_name"],
            measures=["decks_containing", "total_used"],
            filters=[lambda t: t.card_name == "Tech"],
        )
        .execute()
    )
    assert data["decks_containing"].iloc[0] == 1
    assert data["total_used"].iloc[0] == 2


def test_population_measures_are_counted_once_across_categories_and_equal_sized_cohorts(
    analytics,
):
    models = semantic_models(
        analytics, "monthly_populations", "archetype_deck_populations"
    )
    monthly = (
        models["monthly_populations"]
        .query(
            dimensions=["tournament_month"],
            measures=["total_participants"],
        )
        .execute()
        .sort_values("tournament_month")
    )
    assert monthly["total_participants"].tolist() == [5, 4]
    labs = (
        models["monthly_populations"]
        .query(
            measures=["total_participants"],
            filters=[lambda t: t.source == "limitless_labs"],
        )
        .execute()
    )
    assert labs["total_participants"].iloc[0] == 8
    populations = (
        models["archetype_deck_populations"]
        .query(
            dimensions=["archetype"],
            measures=["total_archetype_decks"],
        )
        .execute()
    )
    assert dict(
        zip(populations["archetype"], populations["total_archetype_decks"])
    ) == {"A": 4, "B": 1}


def test_semantic_win_rates_pool_counts_and_respect_source_filters(analytics):
    models = semantic_models(analytics, "archetype_stats")
    pooled = models["archetype_stats"].query(measures=["avg_win_rate"]).execute()
    assert pooled["avg_win_rate"].iloc[0] == pytest.approx(70.0)
    labs = (
        models["archetype_stats"]
        .query(
            measures=["avg_win_rate"],
            filters=[lambda t: t.source == "limitless_labs"],
        )
        .execute()
    )
    assert labs["avg_win_rate"].iloc[0] == pytest.approx(30.0)


def test_known_source_labels_share_parent_taxonomy_and_unknown_labels_are_preserved():
    con = duckdb.connect(":memory:")
    con.execute("""create table meta_decks (
        card_name_1 varchar, card_name_2 varchar, archetype varchar, sub_archetype varchar)""")
    con.execute(
        "insert into meta_decks values ('Dragapult ex','Dusknoir','Dragapult','Dragapult Dusknoir')"
    )
    con.execute("""create table tournament_participants (
        name varchar, tournament_link varchar, deck varchar, _dlt_load_id varchar)""")
    con.execute("""insert into tournament_participants values
        ('Labs', 'https://labs.limitlesstcg.com/0074/standings', 'Dragapult Dusknoir', '1'),
        ('New', 'https://labs.limitlesstcg.com/0074/standings', 'Unmapped New Deck', '1')""")
    con.execute(
        "create table fct_deck_composition (participant_id varchar,card_name varchar)"
    )
    con.execute(
        "insert into fct_deck_composition values ('play-id','Dragapult ex'),('play-id','Dusknoir')"
    )
    build_model(con, "dim_deck_archetypes")
    parents = con.execute(
        "select archetype from dim_deck_archetypes where sub_archetype='Dragapult Dusknoir'"
    ).fetchall()
    assert parents == [("Dragapult",), ("Dragapult",)]
    unknown = con.execute(
        "select archetype,source_archetype_label from dim_deck_archetypes where classification_method='source_label_unmapped'"
    ).fetchall()
    assert unknown == [("Unmapped New Deck", "Unmapped New Deck")]
    con.close()


def test_suggestion_semantic_measures_load_and_pool_counts(analytics):
    model = semantic_models(analytics, "matchup_suggestions")["matchup_suggestions"]
    result = (
        model.query(
            measures=[
                "avg_win_rate_with_card",
                "avg_win_rate_without_card",
                "avg_relevance_score",
                "avg_suggested_quantity",
            ]
        )
        .execute()
        .iloc[0]
    )
    assert result["avg_win_rate_with_card"] == 75.0
    assert result["avg_win_rate_without_card"] == 0.0
    assert result["avg_relevance_score"] == 75.0
    assert result["avg_suggested_quantity"] == 2.0
