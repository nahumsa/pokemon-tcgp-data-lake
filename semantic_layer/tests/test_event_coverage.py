"""Execute the production coverage model against small independent inputs."""

from pathlib import Path

import duckdb
import pytest
from jinja2 import Environment, StrictUndefined


@pytest.fixture
def coverage_db():
    with duckdb.connect() as con:
        con.execute("""
            create table dim_tournaments as select 'e1' tournament_id, 'labs/event' tournament_url,
                'Event' tournament_name, date '2026-10-31' tournament_date,
                'limitless_labs' source, 'in_person' event_type, 'STANDARD' format, 2 player_count;
            create table dim_participants(tournament_id varchar, participant_id varchar);
            insert into dim_participants values ('e1', 'p1'), ('e1', 'p2');
            create table dim_deck_classification(participant_id varchar, classification_status varchar);
            insert into dim_deck_classification values ('p1', 'matched'), ('p2', 'ambiguous');
            create table stg_ingestion_event_runs(
                tournament_url varchar, attempt_id varchar, source_completed boolean,
                expected_participant_count bigint, participant_count bigint, decklist_count bigint,
                history_participant_count bigint, extraction_status varchar, load_status varchar,
                participant_error_count bigint, decklist_error_count bigint, history_error_count bigint,
                extraction_error_count bigint, source_updated_at varchar,
                extracted_at timestamptz, loaded_at timestamptz
            );
            insert into stg_ingestion_event_runs values (
                'labs/event', 'run1', true, 2, 2, 1, 2, 'success', 'success', 0, 0, 0, 0, null,
                '2026-10-31T10:00:00Z', '2026-10-31T10:01:00Z'
            );
        """)
        yield con


def coverage(con):
    query = (
        Path(__file__).resolve().parents[2]
        / "transformations/models/consumption/mart_event_coverage.sql"
    ).read_text()
    sql = (
        Environment(undefined=StrictUndefined)
        .from_string(query)
        .render(ref=lambda name: name, run_started_at="2026-10-31T11:00:00+00:00")
    )
    result = con.execute(sql)
    return dict(zip([col[0] for col in result.description], result.fetchone()))


def test_coverage_denominators_and_ambiguous_classification(coverage_db):
    event = coverage(coverage_db)
    assert event["observed_participant_count"] == 2
    assert event["participant_coverage_pct"] == event["history_coverage_pct"] == 100
    assert event["decklist_coverage_pct"] == event["classification_coverage_pct"] == 50
    assert event["ambiguous_participant_count"] == 1


def test_latest_failure_keeps_previous_success_visible(coverage_db):
    coverage_db.execute("""
        insert into stg_ingestion_event_runs
        select tournament_url, 'run2', source_completed, expected_participant_count,
            null, null, null, 'failed', 'success', 1, 0, 0, 1, null,
            timestamptz '2026-10-31T10:30:00Z', timestamptz '2026-10-31T10:31:00Z'
        from stg_ingestion_event_runs
    """)
    event = coverage(coverage_db)
    assert event["latest_extraction_status"] == "failed"
    assert event["latest_participant_count"] is None
    assert event["decklist_coverage_pct"] is None
    assert event["last_successful_ingestion_at"].hour == 10
    assert event["last_successful_ingestion_at"].minute == 1


def test_legacy_and_empty_events_have_unknown_extraction_coverage(coverage_db):
    coverage_db.execute(
        "delete from stg_ingestion_event_runs; delete from dim_participants"
    )
    event = coverage(coverage_db)
    assert event["observed_participant_count"] == 0
    assert event["decklist_coverage_pct"] is None
    assert event["classification_coverage_pct"] is None
    assert event["last_successful_ingestion_at"] is None
