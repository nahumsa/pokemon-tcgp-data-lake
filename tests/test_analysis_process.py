"""Challenge analysis choices, not just the validity of stored rows."""

from copy import deepcopy
import json
from pathlib import Path

import duckdb
import ibis
import pytest
from boring_semantic_layer import from_config
import yaml

from scripts.validate_analysis import validate

ROOT = Path(__file__).resolve().parents[1]


def test_pooled_ranking_can_reverse_every_cohort_ranking():
    # A wins within both settings; B wins the pooled comparison because its
    # population is concentrated in the easier setting. Both claims need scope.
    config = yaml.safe_load(
        (ROOT / "semantic_layer/semantic_layer/boring.yml").read_text()
    )
    con = ibis.duckdb.connect()
    try:
        con.raw_sql("create schema main_consumption; set schema=main_consumption")
        con.raw_sql("""
            create table mart_archetype_stats as select * from (values
                ('A', 'online', 81, 87), ('B', 'online', 234, 270),
                ('A', 'in_person', 192, 263), ('B', 'in_person', 55, 80)
            ) t(archetype, event_type, wins, total_matches)
        """)
        definition = config["archetype_stats"]
        model = from_config(
            {"performance": definition},
            tables={definition["table"]: con.table("mart_archetype_stats")},
        )["performance"]
        pooled = model.query(
            dimensions=["archetype"], measures=["avg_win_rate"]
        ).execute()
        rates = dict(zip(pooled.archetype, pooled.avg_win_rate))
        assert rates["B"] > rates["A"]
        for setting in ("online", "in_person"):
            grouped = model.query(
                dimensions=["archetype"],
                measures=["avg_win_rate"],
                filters=[lambda t, s=setting: t.event_type == s],
            ).execute()
            rates = dict(zip(grouped.archetype, grouped.avg_win_rate))
            assert rates["A"] > rates["B"]

    finally:
        con.disconnect()


@pytest.fixture
def analysis():
    return json.loads((ROOT / "docs/analysis_example.json").read_text())


def test_complete_evidence_record_passes(analysis):
    assert validate(analysis) == []


@pytest.mark.parametrize(
    "mistake",
    [
        "average_rates",
        "zero_as_zero",
        "causality",
        "missing_evidence",
        "incorrect_percentage",
        "missing_scope",
        "missing_counts",
        "missing_caveats",
    ],
)
def test_evidence_gate_rejects_known_analysis_failures(analysis, mistake):
    report = deepcopy(analysis)
    claim = report["claims"][0]
    if mistake == "average_rates":
        claim["rate"]["aggregation"] = "mean_of_percentages"
    elif mistake == "zero_as_zero":
        claim["rate"].update(numerator=0, denominator=0, value=0)
    elif mistake == "causality":
        claim["kind"] = "causal"
    elif mistake == "missing_evidence":
        claim["evidence"] = ["nonexistent"]
    elif mistake == "incorrect_percentage":
        claim["rate"]["value"] = 54.55
    elif mistake == "missing_scope":
        del report["population"]
    elif mistake == "missing_counts":
        report["queries"]["q1"]["result"] = [{"win_rate": 10}]
    else:
        claim["caveats"] = []
    assert validate(report), mistake


def test_reference_evidence_replays_independently(analysis):
    query = analysis["queries"]["q1"]
    with duckdb.connect() as con:
        cursor = con.execute(query["sql"])
        names = [c[0] for c in cursor.description]
        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
    assert rows == query["result"]
