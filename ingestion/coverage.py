"""Small, serializable extraction summaries shared by both ingestion commands."""

from collections import Counter
from datetime import datetime, timezone

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
        "extraction_status": status,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
