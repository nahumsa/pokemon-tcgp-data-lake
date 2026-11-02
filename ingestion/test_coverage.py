"""Coverage records must describe an extraction attempt, including unavailable data."""

from ingestion.coverage import build_audit


EVENT = {"tournament_page": "labs/event", "data_players": "2", "completed": True}


def test_missing_inputs_are_unknown_instead_of_zero():
    audit = build_audit(EVENT)
    assert audit["participant_count"] is None
    assert audit["decklist_count"] is None
    assert audit["history_participant_count"] is None
    assert audit["extraction_status"] == "incomplete"


def test_successful_extraction_can_have_no_published_decks():
    audit = build_audit(EVENT, participants=[{"name": "A"}, {"name": "B"}], decks=[], matches=[])
    assert audit["expected_participant_count"] == 2
    assert audit["participant_count"] == 2
    assert audit["decklist_count"] == audit["history_participant_count"] == 0
    assert audit["source_completed"] is True
    assert audit["extraction_status"] == "success"


def test_history_counts_players_once_and_empty_decks_do_not_count():
    audit = build_audit(
        EVENT,
        participants=[{"name": "A"}, {"name": "B"}],
        decks=[{"player": "A", "decklist": [{"name": "Card"}]} , {"player": "B", "decklist": []}],
        matches=[{"P1": "A", "Round": "1"}, {"P1": "A", "Round": "2"}],
    )
    assert audit["decklist_count"] == audit["history_participant_count"] == 1


def test_failed_attempt_does_not_claim_success_and_rerun_clears_errors():
    failed = build_audit(EVENT, participants=[], decks=[], matches=[], errors=["participants", "decks", "decks"])
    assert failed["extraction_status"] == "failed"
    assert failed["participant_error_count"] == 1
    assert failed["decklist_error_count"] == 2
    rerun = build_audit(EVENT, participants=[], decks=[], matches=[])
    assert rerun["extraction_status"] == "success"
    assert rerun["participant_error_count"] == rerun["decklist_error_count"] == 0


def test_unknown_source_metadata_stays_unknown():
    audit = build_audit({"tournament_page": "legacy", "data_players": "unavailable"})
    assert audit["expected_participant_count"] is None
    assert audit["source_completed"] is None
