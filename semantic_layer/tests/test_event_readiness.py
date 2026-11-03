"""Readiness is a policy decision independent of source completion."""

from datetime import datetime, timezone
import json
import sys

import duckdb
import pytest

from semantic_layer.readiness import ReadinessPolicy, check_readiness


NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("explicit_database", [False, True])
def test_cli_uses_shared_database_path_and_explicit_override(
    tmp_path, monkeypatch, capsys, complete_event, explicit_database
):
    from semantic_layer import readiness

    database = tmp_path / "task.duckdb"
    duckdb.connect(str(database)).close()
    missing = tmp_path / "wrong.duckdb"
    monkeypatch.setenv(
        "POKEMON_TCG_DB_PATH", str(missing if explicit_database else database)
    )
    now = datetime.now(timezone.utc).isoformat()
    complete_event.update(
        extracted_at=now, last_successful_ingestion_at=now, transformed_at=now
    )

    def read_event(connection, url):
        assert url == "https://example/event"
        assert connection.execute("pragma database_list").fetchone()[2] == str(database)
        return complete_event

    monkeypatch.setattr(readiness, "read_event_coverage", read_event)
    argv = ["readiness", "https://example/event"]
    if explicit_database:
        argv += ["--database", str(database)]
    monkeypatch.setattr(sys, "argv", argv)
    readiness.main()
    assert json.loads(capsys.readouterr().out)["ready"] is True
    assert not missing.exists()


@pytest.fixture
def complete_event():
    return {
        "source_completed": True,
        "latest_extraction_status": "success",
        "latest_load_status": "success",
        "expected_participant_count": 2,
        "observed_participant_count": 2,
        "latest_participant_count": 2,
        "latest_decklist_count": 2,
        "latest_history_participant_count": 2,
        "participant_coverage_pct": 100.0,
        "decklist_coverage_pct": 100.0,
        "history_coverage_pct": 100.0,
        "classification_coverage_pct": 100.0,
        "extracted_at": "2026-10-31T10:00:00+00:00",
        "last_successful_ingestion_at": "2026-10-31T10:01:00+00:00",
        "transformed_at": "2026-10-31T10:02:00+00:00",
    }


def test_complete_fresh_event_is_ready(complete_event):
    assert check_readiness(complete_event, now=NOW) == {"ready": True, "reasons": []}


def test_ingestion_after_the_coverage_build_requires_a_rebuild(complete_event):
    complete_event["latest_load_at"] = "2026-10-31T11:00:00Z"
    assert "transformation_stale" in check_readiness(complete_event, now=NOW)["reasons"]


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("source_completed", False, "event_not_completed"),
        ("source_completed", None, "event_not_completed"),
        ("latest_extraction_status", "failed", "extraction_not_successful"),
        ("latest_load_status", "failed", "load_not_successful"),
        ("expected_participant_count", None, "participant_count_unknown"),
        ("observed_participant_count", 1, "participant_count_mismatch"),
        ("latest_participant_count", 1, "participant_count_mismatch"),
        ("decklist_coverage_pct", 0, "decklist_coverage_below_threshold"),
        ("history_coverage_pct", None, "history_coverage_unknown"),
        ("classification_coverage_pct", 50, "classification_coverage_below_threshold"),
        ("extracted_at", "2026-10-20T10:00:00+00:00", "extraction_stale"),
        ("extracted_at", None, "extraction_time_unknown"),
        ("transformed_at", "2026-10-31T09:00:00+00:00", "transformation_stale"),
    ],
)
def test_incomplete_or_failed_events_explain_why(complete_event, field, value, reason):
    complete_event[field] = value
    result = check_readiness(complete_event, now=NOW)
    assert result["ready"] is False
    assert reason in result["reasons"]


def test_standings_report_can_explicitly_relax_deck_requirements(complete_event):
    complete_event.update(decklist_coverage_pct=0, classification_coverage_pct=0)
    policy = ReadinessPolicy(min_decklist_pct=0, min_classification_pct=0)
    assert check_readiness(complete_event, policy, now=NOW)["ready"] is True


@pytest.mark.parametrize(
    "kwargs", [{"min_decklist_pct": -1}, {"min_history_pct": 101}, {"max_age_hours": 0}]
)
def test_invalid_policy_is_rejected(kwargs):
    with pytest.raises(ValueError):
        ReadinessPolicy(**kwargs)


def test_report_section_discloses_zero_unknown_and_reasons(complete_event):
    from semantic_layer.readiness import coverage_section

    complete_event.update(
        tournament_url="https://labs.limitlesstcg.com/event",
        decklist_coverage_pct=0,
        history_coverage_pct=None,
    )
    section = coverage_section(complete_event, now=NOW)
    assert "Decklists: 0.0%" in section
    assert "History: unavailable" in section
    assert "decklist_coverage_below_threshold" in section
    assert complete_event["tournament_url"] in section
