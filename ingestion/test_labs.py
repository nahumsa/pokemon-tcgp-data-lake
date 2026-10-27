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


@pytest.fixture
def labs_pipeline(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    import dlt

    from ingestion import labs

    pipeline = SimpleNamespace(
        default_schema=dlt.Schema("labs_test"),
        run=Mock(return_value="Loaded fixture"),
        sync_schema=Mock(),
    )
    monkeypatch.setattr(
        labs, "dlt", SimpleNamespace(pipeline=lambda **kwargs: pipeline)
    )
    return pipeline


def no_deck_rows():
    from ingestion import labs

    rows = {table: [] for table in labs.TABLE_KEYS}
    rows[labs.TOURNAMENT_PARTICIPANTS_TABLE] = [
        {"name": "Alex", "tournament_link": "labs/event", "deck": None}
    ]
    return rows


def test_no_deck_import_declares_empty_deck_sources_and_nullable_labels(labs_pipeline):
    from ingestion import labs

    rows = no_deck_rows()
    labs.load_rows(rows)

    # Only real standings are loaded; no placeholder deck or card is inserted.
    labs_pipeline.run.assert_called_once()
    call = labs_pipeline.run.call_args
    assert call.args[0] == rows[labs.TOURNAMENT_PARTICIPANTS_TABLE]
    assert call.kwargs["columns"] == {"deck": {"data_type": "text"}}
    assert call.kwargs["write_disposition"] == "merge"
    parent = labs_pipeline.default_schema.tables[labs.PARTICIPANT_DECK_TABLE]
    cards = labs_pipeline.default_schema.tables["participant_deck__decklist"]
    assert {
        "player",
        "tournament",
        "decklist_link",
        "_dlt_id",
        "_dlt_load_id",
    } <= parent["columns"].keys()
    assert {"name", "code", "kind", "quantity", "_dlt_parent_id", "_dlt_id"} <= cards[
        "columns"
    ].keys()
    assert cards["parent"] == labs.PARTICIPANT_DECK_TABLE
    # These hints let subsequently published cards merge with their deck.
    assert parent["columns"]["_dlt_id"]["unique"] is True
    assert parent["columns"]["player"]["primary_key"] is True
    assert parent["columns"]["tournament"]["primary_key"] is True
    assert cards["columns"]["_dlt_root_id"]["root_key"] is True
    assert cards["columns"]["_dlt_parent_id"]["foreign_key"] is True
    labs_pipeline.sync_schema.assert_called_once()


def test_no_deck_import_preserves_existing_source_schemas(labs_pipeline):
    from copy import deepcopy

    from dlt.common.schema.utils import new_table

    from ingestion import labs

    schema = labs_pipeline.default_schema
    schema.update_table(
        new_table(
            labs.PARTICIPANT_DECK_TABLE,
            columns=[{"name": "existing_field", "data_type": "text"}],
        )
    )
    schema.update_table(
        new_table(
            "participant_deck__decklist",
            parent_table_name=labs.PARTICIPANT_DECK_TABLE,
            columns=[{"name": "existing_card_field", "data_type": "text"}],
        )
    )
    before = deepcopy(schema.tables)
    labs.load_rows(no_deck_rows())
    assert schema.tables == before


def test_published_deck_import_keeps_merge_keys_without_empty_schema_setup(
    labs_pipeline,
):
    from ingestion import labs

    rows = {table: [] for table in labs.TABLE_KEYS}
    rows[labs.PARTICIPANT_DECK_TABLE] = [
        deck_row(
            {"name": "Alex", "tp_id": 1},
            {
                "energy": [
                    {"name": "Psychic Energy", "set": "MEE", "number": "5", "count": 60}
                ]
            },
            "0001",
            "labs/event",
        )
    ]
    labs.load_rows(rows)
    call = labs_pipeline.run.call_args
    assert call.args[0] == rows[labs.PARTICIPANT_DECK_TABLE]
    assert call.kwargs["table_name"] == labs.PARTICIPANT_DECK_TABLE
    assert call.kwargs["primary_key"] == ["tournament", "player"]
    assert call.kwargs["write_disposition"] == "merge"
    labs_pipeline.sync_schema.assert_not_called()


def test_empty_snapshot_does_not_create_sources(labs_pipeline):
    from ingestion import labs

    labs.load_rows({table: [] for table in labs.TABLE_KEYS})
    labs_pipeline.run.assert_not_called()
    labs_pipeline.sync_schema.assert_not_called()
