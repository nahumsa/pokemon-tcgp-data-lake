"""Recheck committed real-data comparisons without fetching live tournament data."""

import json

import pytest

from evaluation.fixture import ROOT
from evaluation.grade import grade

BASELINE = ROOT / "evaluation/baselines/real-labs"
QUESTIONS = json.loads((BASELINE / "questions.json").read_text())
EXPECTED = json.loads((BASELINE / "expected.json").read_text())


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda question: question["id"])
def test_real_answer_matches_independent_snapshot_reference(question):
    trace = json.loads((BASELINE / f"{question['id']}.json").read_text())
    assert grade(question, trace, EXPECTED)["passed"]


def test_reference_sql_does_not_read_production_marts():
    reference = json.loads((BASELINE / "references.json").read_text())
    assert set(reference) == {q["id"] for q in QUESTIONS}
    for entry in reference.values():
        assert "main_consumption" not in entry["sql"]
        assert "mart_" not in entry["sql"]
        assert "main_semantic" not in entry["sql"]
    assert EXPECTED["real_entries"]["entries"] == 3973
    assert EXPECTED["real_records"]["player_records"] == 33027


def test_real_manifest_is_not_marked_synthetic():
    manifest = json.loads((BASELINE / "manifest.json").read_text())
    summary = json.loads((BASELINE / "summary.json").read_text())
    assert manifest["synthetic"] is False
    assert summary["synthetic"] is False
    assert len(manifest["events"]) == 2
    assert summary["passed"] == summary["total"] == 12
