"""Small, serializable extraction summaries shared by both ingestion commands."""

from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

AUDIT_TABLE = "ingestion_event_runs"


def build_audit(tournament, *, participants=None, decks=None, matches=None, errors=()):
    """Preserve unknown inputs as null; an empty fetched collection is a real zero."""
    try:
        expected = int(tournament.get("data_players"))
        if expected < 0:
            expected = None
    except (TypeError, ValueError):
        expected = None
    failures = Counter(errors)
    status = "success"
    if any(value is None for value in (participants, decks, matches)):
        status = "incomplete"
    if failures:
        status = "failed"
    return {
        "tournament_url": tournament["tournament_page"],
        "source_completed": tournament.get("completed"),
        "expected_participant_count": expected,
        "participant_count": None
        if participants is None
        else len({p["name"] for p in participants}),
        "decklist_count": None
        if decks is None
        else len({d["player"] for d in decks if d.get("decklist")}),
        "history_participant_count": None
        if matches is None
        else len({m["P1"] for m in matches}),
        "participant_error_count": failures["participants"],
        "decklist_error_count": failures["decks"],
        "history_error_count": failures["matches"],
        "extraction_error_count": sum(failures.values()),
        "source_updated_at": tournament.get("source_updated_at"),
        "extraction_status": status,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }


def load_audits(pipeline, audits, *, load_status):
    """Write after data loads; reloading a snapshot is a new load, not a new scrape."""
    if not audits:
        return
    loaded_at = datetime.now(timezone.utc).isoformat()
    rows = [
        dict(
            audit, attempt_id=uuid4().hex, load_status=load_status, loaded_at=loaded_at
        )
        for audit in audits
    ]
    # Failed/empty events may contain only null values for these fields.
    columns = {
        "source_completed": {"data_type": "bool"},
        "source_updated_at": {"data_type": "text"},
        **{
            name: {"data_type": "bigint"}
            for name in (
                "expected_participant_count",
                "participant_count",
                "decklist_count",
                "history_participant_count",
            )
        },
    }
    pipeline.run(
        rows,
        table_name=AUDIT_TABLE,
        write_disposition="merge",
        primary_key=["tournament_url", "attempt_id"],
        columns=columns,
        loader_file_format="jsonl",
    )
