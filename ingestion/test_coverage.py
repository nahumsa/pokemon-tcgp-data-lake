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
    audit = build_audit(
        EVENT, participants=[{"name": "A"}, {"name": "B"}], decks=[], matches=[]
    )
    assert audit["expected_participant_count"] == 2
    assert audit["participant_count"] == 2
    assert audit["decklist_count"] == audit["history_participant_count"] == 0
    assert audit["source_completed"] is True
    assert audit["extraction_status"] == "success"


def test_history_counts_players_once_and_empty_decks_do_not_count():
    audit = build_audit(
        EVENT,
        participants=[{"name": "A"}, {"name": "B"}],
        decks=[
            {"player": "A", "decklist": [{"name": "Card"}]},
            {"player": "B", "decklist": []},
        ],
        matches=[{"P1": "A", "Round": "1"}, {"P1": "A", "Round": "2"}],
    )
    assert audit["decklist_count"] == audit["history_participant_count"] == 1


def test_failed_attempt_does_not_claim_success_and_rerun_clears_errors():
    failed = build_audit(
        EVENT,
        participants=[],
        decks=[],
        matches=[],
        errors=["participants", "decks", "decks"],
    )
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


def test_labs_records_failed_event_and_a_successful_rerun(monkeypatch):
    from ingestion import labs
    from ingestion.coverage import AUDIT_TABLE

    event = {
        "id": 1,
        "completed": 1,
        "utc_start": "2026-10-01",
        "date": "October 1, 2026",
    }
    responses = {
        "tournaments": [event],
        "tournament": {
            "completed": 1,
            "players": 1,
            "round": 0,
            "updated_at": "2026-10-01",
            "name": "Event",
        },
        "standings": [
            {
                "name": "A",
                "tp_id": 1,
                "placement": 1,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "points": 0,
            }
        ],
    }

    def broken_api(resource, **kwargs):
        if resource == "standings":
            raise ValueError("Unavailable standings")
        return responses[resource]

    monkeypatch.setattr(labs, "api", broken_api)
    failed = labs.extract_events(1)
    assert failed[AUDIT_TABLE][0]["extraction_status"] == "failed"
    assert failed[labs.TOURNAMENT_PARTICIPANTS_TABLE] == []
    monkeypatch.setattr(labs, "api", lambda resource, **kwargs: responses[resource])
    rerun = labs.extract_events(1)
    assert rerun[AUDIT_TABLE][0]["extraction_status"] == "success"
    assert rerun[AUDIT_TABLE][0]["participant_count"] == 1
    assert rerun[AUDIT_TABLE][0]["decklist_count"] == 0


def test_play_captures_detail_failures_without_losing_standings(monkeypatch):
    from types import SimpleNamespace

    from ingestion import main
    from ingestion.coverage import AUDIT_TABLE
    from ingestion.models import Tournament

    participant = SimpleNamespace(
        name="A", model_dump=lambda: {"name": "A", "tournament_link": "play/event"}
    )
    monkeypatch.setattr(main, "extract_participants", lambda url: [participant])
    monkeypatch.setattr(
        main,
        "get_deck",
        lambda player: (_ for _ in ()).throw(ValueError("Failed request")),
    )
    monkeypatch.setattr(main, "extract_matches", lambda player: [])
    rows = main.collect_rows(
        [
            Tournament(
                tournament_page="play/event", **{"data-players": "1", "completed": True}
            )
        ]
    )
    audit = rows[AUDIT_TABLE][0]
    assert len(rows[main.TOURNAMENT_PARTICIPANTS_TABLE]) == 1
    assert audit["decklist_error_count"] == 1
    assert audit["extraction_status"] == "failed"
