"""Regression coverage for failed builds, sparse inputs, and invalid answers."""

import asyncio
import gzip
import json
import subprocess

import duckdb
import pytest

from evaluation import real_data
from evaluation.fixture import ROOT
from evaluation.real_reference import make_reference
from evaluation.report import report
from evaluation.run import drive, write_json


@pytest.mark.parametrize("existing_manifest", [False, True])
@pytest.mark.parametrize("test_exit_code", [0, 1])
def test_data_tests_control_success_manifest(
    tmp_path, monkeypatch, existing_manifest, test_exit_code
):
    rows = {name: [] for name in real_data.labs.TABLE_KEYS}
    with gzip.open(tmp_path / "rows.json.gz", "wt", encoding="utf-8") as handle:
        json.dump(rows, handle)
    (tmp_path / "transformations").mkdir()
    if existing_manifest:
        (tmp_path / "manifest.json").write_text('{"synthetic": false}')
    monkeypatch.setattr(
        real_data.labs, "api", lambda *args, **kwargs: pytest.fail("No fetch expected")
    )
    monkeypatch.setattr(
        real_data, "stage_snapshot", lambda rows, path: path.write_bytes(b"warehouse")
    )
    actions = []

    def run(command, **kwargs):
        actions.append(command[1])
        return subprocess.CompletedProcess(
            command, test_exit_code if command[1] == "test" else 0, "dbt output"
        )

    monkeypatch.setattr(real_data.subprocess, "run", run)
    if test_exit_code:
        with pytest.raises(RuntimeError, match="dbt test failed"):
            real_data.prepare(tmp_path)
        assert not (tmp_path / "manifest.json").exists()
    else:
        real_data.prepare(tmp_path)
        manifest = json.loads((tmp_path / "manifest.json").read_text())
        assert manifest["synthetic"] is False
        assert manifest["row_counts"] == {name: 0 for name in rows}
    assert actions == ["deps", "seed", "run", "test"]
    assert (tmp_path / "dbt-test.log").read_text() == "dbt output"


@pytest.mark.parametrize("empty", ["cards", "results", "both"])
def test_reference_build_handles_empty_input_tables(tmp_path, empty):
    cache = tmp_path / "api"
    cache.mkdir()
    (tmp_path / "manifest.json").write_text("{}")
    packets = [
        {
            "resource": "tournaments",
            "params": {},
            "response": [{"id": 1, "utc_start": "2026-10-31", "city": "Gdańsk"}],
        },
        {
            "resource": "standings",
            "params": {"tournamentId": "0001"},
            "response": [
                {
                    "tp_id": 1,
                    "name": "One",
                    "placement": 1,
                    "deck_name": "Dragapult",
                    "decklist": False,
                },
                {
                    "tp_id": 2,
                    "name": "Two",
                    "placement": 2,
                    "deck_name": "Gholdengo",
                    "decklist": False,
                },
            ],
        },
    ]
    if empty == "cards":
        packets.append(
            {
                "resource": "pairings",
                "params": {"tournamentId": "0001", "round": 1},
                "response": [
                    {
                        "player1": 1,
                        "player2": 2,
                        "p1_name": "One",
                        "p2_name": "Two",
                        "winner": 1,
                    },
                ],
            }
        )
    elif empty == "results":
        packets.append(
            {
                "resource": "decklist",
                "params": {"tournamentId": "0001", "playerId": "0001"},
                "response": {
                    "pokemon": [{"name": "Dreepy", "count": 4}],
                },
            }
        )
    for index, packet in enumerate(packets):
        (cache / f"{index}.json").write_text(json.dumps(packet))
    make_reference(tmp_path)
    expected = json.loads((tmp_path / "expected.json").read_text())
    assert expected["real_entries"] == {"entries": 2}
    assert expected["real_records"]["player_records"] == (2 if empty == "cards" else 0)
    assert expected["real_card"] == (
        {"decks": 1, "copies": 4}
        if empty == "results"
        else {"decks": 0, "copies": None}
    )
    with duckdb.connect() as con:
        for table in ("cards", "results", "pairings"):
            path = str(tmp_path / "reference-tables" / f"{table}.parquet")
            # Even an empty exported reference has its complete typed schema.
            columns = con.execute(
                "describe select * from read_parquet(?)", [path]
            ).fetchall()
            assert len(columns) >= 5


@pytest.mark.parametrize(
    "answer",
    [
        None,
        [],
        {"facts": None},
        {"facts": []},
        {"facts": {}, "explanation": None},
        {"facts": {}, "explanation": 42},
    ],
)
def test_report_discloses_malformed_answers_without_crashing(tmp_path, answer):
    questions = tmp_path / "questions.json"
    expected = tmp_path / "expected.json"
    questions.write_text(
        json.dumps([{"id": "q1", "question": "Count?", "required_caveats": []}])
    )
    expected.write_text(json.dumps({"q1": {"count": 1}}))
    (tmp_path / "q1.json").write_text(json.dumps({"answer": answer, "calls": []}))
    output = report(tmp_path, questions, expected)
    assert "| q1 | FAIL |" in output
    assert "Answer: No final answer" in output
    assert "| count | null | 1 | NO |" in output
    assert "Failures:" in output


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_candidate_json_is_rejected_then_run_continues(tmp_path, constant):
    question = {
        "id": "q1",
        "question": "Count?",
        "facts": ["count"],
        "required_caveats": [],
    }

    async def check():
        lines = iter(
            [
                '{"action":"answer","facts":{"count":' + constant + "}}",
                '{"action":"answer","facts":{"count":1},"explanation":"One","caveats":[]}',
            ]
        )
        messages = []

        async def read():
            return next(lines)

        async def send(message):
            messages.append(message)

        transcript = await drive(None, question, [], read, send)
        assert len([m for m in messages if m["event"] == "error"]) == 1
        assert transcript["answer"]["facts"] == {"count": 1}
        write_json(tmp_path / "q1.json", transcript)
        assert json.loads((tmp_path / "q1.json").read_text())["answer"]["facts"] == {
            "count": 1
        }

    asyncio.run(check())


def test_archived_assistant_report_matches_saved_transcripts():
    baseline = ROOT / "evaluation/baselines/assistant-first"
    assert (baseline / "report.md").read_text() == report(baseline)
