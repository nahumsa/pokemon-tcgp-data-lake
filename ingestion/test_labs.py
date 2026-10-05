import pytest

from ingestion.labs import deck_row, latest_completed, match_rows


def test_play_ingestion_records_source_and_requested_event_type(monkeypatch):
    from ingestion import main
    from ingestion.models import Tournament
    from ingestion.payload import TournamentPayload

    event = Tournament(
        tournament_page="https://play.limitlesstcg.com/tournament/example"
    )
    monkeypatch.setattr(main, "get", lambda *args, **kwargs: object())
    monkeypatch.setattr(main, "extract_tournaments", lambda response: [event])
    payload = TournamentPayload(
        game="PTCG", format="STANDARD", platform="all", type="online", time="all"
    )
    rows = list(main.iter_tournaments(payload, backfill=True))
    assert rows[0][0].model_dump()["source"] == "limitless_play"
    assert rows[0][0].model_dump()["event_type"] == "online"


def test_latest_excludes_live_events_and_orders_by_start():
    events = [
        {"id": 1, "utc_start": "2026-09-01", "completed": 1},
        {"id": 3, "utc_start": "2026-10-01", "completed": 0},
        {"id": 2, "utc_start": "2026-09-20", "completed": 1},
    ]
    assert [e["id"] for e in latest_completed(events, 1)] == [2]


@pytest.mark.parametrize(
    "winner,results",
    [(1, ["WIN", "LOSS"]), (0, ["TIE", "TIE"]), (-1, ["LOSS", "LOSS"])],
)
def test_pairings_keep_player_perspectives_and_duplicate_name_identity(winner, results):
    pairings = [
        {
            "completed": 1,
            "player1": 1,
            "player2": 2,
            "winner": winner,
            "p1_name": "Alex",
            "p2_name": "Alex",
        }
    ]
    rows = match_rows(
        pairings, 3, "labs/event", {1: "Alex [Labs 1]", 2: "Alex [Labs 2]"}
    )
    assert [r["Result"] for r in rows] == results
    assert rows[0]["P1"] == rows[1]["P2"] == "Alex [Labs 1]"
    assert rows[0]["P2"] == rows[1]["P1"] == "Alex [Labs 2]"
    assert all(r["Round"] == "3" for r in rows)


def test_unfinished_pairings_fail_instead_of_becoming_losses():
    with pytest.raises(ValueError, match="Unfinished"):
        match_rows([{"completed": 0}], 1, "labs/event")


def test_bye_does_not_create_a_phantom_participant():
    rows = match_rows(
        [
            {
                "completed": 1,
                "player1": 1,
                "player2": None,
                "winner": 1,
                "p1_name": "Alex",
                "p2_name": None,
            }
        ],
        1,
        "labs/event",
    )
    assert len(rows) == 1
    assert rows[0]["P2"] == "BYE"
    assert rows[0]["Result"] == "WIN"


def test_deck_preserves_unicode_and_card_codes_and_rejects_incomplete_lists():
    player = {"name": "José", "tp_id": 12}
    cards = {
        "pokemon": [{"name": "Farfetch’d", "set": "MEG", "number": "12", "count": 4}],
        "energy": [
            {"name": "Psychic Energy", "set": "MEE", "number": "5", "count": 56}
        ],
    }
    row = deck_row(player, cards, "0074", "labs/event")
    assert row["decklist"][0]["code"] == "MEG-12"
    assert row["player"] == "José"
    assert row["decklist"][0]["name"] == "Farfetch’d"
    with pytest.raises(ValueError, match="deck size"):
        deck_row(player, {}, "0074", "labs/event")
