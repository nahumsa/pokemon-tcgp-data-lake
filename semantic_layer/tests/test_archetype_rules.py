"""Run the production seed validation query against deliberately invalid rules."""

from pathlib import Path

import duckdb
import pytest
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def validation_sql():
    query = (
        ROOT / "transformations/tests/assert_archetype_rules_valid.sql"
    ).read_text()
    return (
        Environment(undefined=StrictUndefined)
        .from_string(query)
        .render(ref=lambda _: "main.rules")
    )


@pytest.mark.parametrize(
    "rules,expected",
    [
        ("('r1', 0, 'A', null, 'Deck', 'Deck')", 0),
        # A duplicate cannot inflate candidate counts, even with a different ID.
        (
            "('r1', 0, 'A', null, 'Deck', 'Deck'), "
            "('r2', 0, 'A', null, 'Deck', 'Deck')",
            1,
        ),
        # Card order does not make conflicting equal-priority rules distinct.
        (
            "('r1', 0, 'A', 'B', 'Alpha', 'Alpha'), "
            "('r2', 0, 'B', 'A', 'Zulu', 'Zulu')",
            1,
        ),
        (
            "('r1', 0, 'A', 'B', 'Alpha', 'Alpha'), "
            "('r2', 10, 'B', 'A', 'Zulu', 'Zulu')",
            0,
        ),
        (
            "('r1', 0, 'A', null, 'Alpha', 'Alpha'), "
            "('r1', 0, 'B', null, 'Zulu', 'Zulu')",
            1,
        ),
        ("('r1', null, 'A', null, 'Deck', 'Deck')", 1),
        ("('', 0, 'A', null, 'Deck', 'Deck')", 1),
        ("('r1', 0, '', null, 'Deck', 'Deck')", 1),
    ],
)
def test_seed_validation_rejects_duplicates_conflicts_and_missing_metadata(
    rules, expected, validation_sql
):
    with duckdb.connect() as con:
        con.execute(f"""
            create table rules as select rule_id, rule_priority, card_name_1,
                cast(card_name_2 as varchar) as card_name_2, archetype, sub_archetype
            from (values {rules})
                m(rule_id, rule_priority, card_name_1, card_name_2, archetype, sub_archetype)
        """)
        assert len(con.execute(validation_sql).fetchall()) == expected


def test_committed_seed_satisfies_the_production_validation(validation_sql):
    with duckdb.connect() as con:
        con.execute(
            "create table rules as select * from read_csv_auto(?)",
            [str(ROOT / "transformations/seeds/meta_decks.csv")],
        )
        assert con.execute(validation_sql).fetchall() == []
