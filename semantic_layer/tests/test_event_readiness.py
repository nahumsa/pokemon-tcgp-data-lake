"""Readiness is a policy decision independent of source completion."""

from datetime import datetime, timezone

import pytest

from semantic_layer.semantic_layer.readiness import ReadinessPolicy, check_readiness


NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


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
