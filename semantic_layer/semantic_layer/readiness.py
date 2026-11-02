"""Evaluate event report requirements without changing or publishing data."""

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ReadinessPolicy:
    min_decklist_pct: float = 100
    min_history_pct: float = 100
    min_classification_pct: float = 100
    max_age_hours: float = 24

    def __post_init__(self):
        for value in (
            self.min_decklist_pct,
            self.min_history_pct,
            self.min_classification_pct,
        ):
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError("Coverage thresholds must be between 0 and 100")
        if not math.isfinite(self.max_age_hours) or self.max_age_hours <= 0:
            raise ValueError("Maximum age must be positive")


def timestamp(value):
    if value is None:
        return None
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    # Never assume a timezone for legacy timestamps.
    return result if result.tzinfo is not None else None


def check_readiness(event, policy=None, *, now=None):
    policy = policy or ReadinessPolicy()
    now = now or datetime.now(timezone.utc)
    reasons = []
    if event.get("source_completed") is not True:
        reasons.append("event_not_completed")
    if event.get("latest_extraction_status") != "success":
        reasons.append("extraction_not_successful")
    if event.get("latest_load_status") != "success":
        reasons.append("load_not_successful")
    expected = event.get("expected_participant_count")
    if expected is None or expected <= 0:
        reasons.append("participant_count_unknown")
    elif any(
        event.get(field) != expected
        for field in ("observed_participant_count", "latest_participant_count")
    ):
        reasons.append("participant_count_mismatch")
    for name, minimum in (
        ("decklist", policy.min_decklist_pct),
        ("history", policy.min_history_pct),
        ("classification", policy.min_classification_pct),
    ):
        value = event.get(f"{name}_coverage_pct")
        if value is None or not math.isfinite(value):
            reasons.append(f"{name}_coverage_unknown")
        elif value < minimum or value > 100:
            reasons.append(f"{name}_coverage_below_threshold")
    extracted = timestamp(event.get("extracted_at"))
    loaded = timestamp(event.get("last_successful_ingestion_at"))
    transformed = timestamp(event.get("transformed_at"))
    latest_load = timestamp(event.get("latest_load_at"))
    if extracted is None:
        reasons.append("extraction_time_unknown")
    elif not 0 <= (now - extracted).total_seconds() <= policy.max_age_hours * 3600:
        reasons.append("extraction_stale")
    if loaded is None:
        reasons.append("ingestion_time_unknown")
    if (
        transformed is None
        or loaded is None
        or transformed < loaded
        or (latest_load is not None and transformed < latest_load)
    ):
        reasons.append("transformation_stale")
    return {"ready": not reasons, "reasons": reasons}


def read_event_coverage(con, tournament_url):
    """Check the live audit head as well as the last successful dbt model build."""
    result = con.execute(
        "select * from main_consumption.mart_event_coverage where tournament_url = ?",
        [tournament_url],
    )
    row = result.fetchone()
    if row is None:
        return None
    event = dict(zip([column[0] for column in result.description], row))
    has_audits = con.execute("""
        select count(*) from information_schema.tables
        where table_schema = 'pokemon_tcg_data' and table_name = 'ingestion_event_runs'
    """).fetchone()[0]
    if has_audits:
        latest = con.execute(
            """
            select loaded_at::timestamptz from pokemon_tcg_data.ingestion_event_runs
            where tournament_url = ? order by loaded_at desc, attempt_id desc limit 1
        """,
            [tournament_url],
        ).fetchone()
        if latest:
            event["latest_load_at"] = latest[0]
    return event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tournament_url")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "pokemon_tcg_pipeline.duckdb",
    )
    parser.add_argument("--min-decklist-pct", type=float, default=100)
    parser.add_argument("--min-history-pct", type=float, default=100)
    parser.add_argument("--min-classification-pct", type=float, default=100)
    parser.add_argument("--max-age-hours", type=float, default=24)
    args = parser.parse_args()
    try:
        policy = ReadinessPolicy(
            args.min_decklist_pct,
            args.min_history_pct,
            args.min_classification_pct,
            args.max_age_hours,
        )
    except ValueError as exc:
        parser.error(str(exc))
    import duckdb

    with duckdb.connect(str(args.database), read_only=True) as con:
        con.execute("set timezone = 'UTC'")
        con.begin()
        event = read_event_coverage(con, args.tournament_url)
        con.commit()
        if event is None:
            parser.error(
                "Event has no coverage model row; ingest and transform it first"
            )
    print(
        json.dumps(
            {
                "coverage": event,
                "policy": vars(policy),
                **check_readiness(event, policy),
            },
            default=str,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
