"""Exercise actual MCP transport and ensure the evaluator can fail bad agents."""

import asyncio
from copy import deepcopy
import json
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from evaluation.fixture import ROOT, build, oracle
from evaluation.grade import equivalent, grade
from evaluation.run import decode

QUESTIONS = json.loads((ROOT / "evaluation/questions.json").read_text())
BASELINE = ROOT / "evaluation/baselines/assistant-first"


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    return build(tmp_path_factory.mktemp("mcp") / "fixture")


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda q: q["id"])
def test_recorded_assistant_answer_matches_independent_oracle(question):
    transcript = json.loads((BASELINE / f"{question['id']}.json").read_text())
    assert grade(question, transcript)["passed"]


@pytest.mark.parametrize(
    "mistake",
    ["wrong_number", "no_query", "tool_error", "no_explanation", "missing_caveat"],
)
def test_evaluator_rejects_bad_answers(mistake):
    question = QUESTIONS[0]
    transcript = deepcopy(json.loads((BASELINE / "entries.json").read_text()))
    if mistake == "wrong_number":
        transcript["answer"]["facts"]["entries"] = 999
    elif mistake == "no_query":
        transcript["calls"] = []
    elif mistake == "tool_error":
        for call in transcript["calls"]:
            call["is_error"] = True
    elif mistake == "no_explanation":
        transcript["answer"]["explanation"] = ""
    else:
        transcript["answer"]["caveats"] = []
    assert not grade(question, transcript)["passed"]


def test_numeric_grading_rejects_nan_and_boolean_counts():
    assert not equivalent(float("nan"), 11)
    assert not equivalent(True, 1)
    assert not equivalent(0, None)
    assert equivalent(33.33, 100 / 3)


def test_oracle_counts_population_and_nulls_independently():
    answers = oracle()
    assert answers["entries"]["entries"] == 11
    assert answers["unique_matches"] == {
        "played_pairings": 4,
        "player_records": 9,
        "byes": 1,
    }
    assert answers["missing_results"]["win_rate"] is None


def test_real_stdio_server_and_tool_errors(warehouse):
    async def check():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                str(ROOT / "semantic_layer/semantic_layer/mcp_server.py"),
                "--database",
                str(warehouse),
            ],
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                assert {
                    "list_models",
                    "get_model",
                    "query_model",
                    "get_time_range",
                } <= names
                result = await client.call_tool(
                    "query_model",
                    {
                        "model_name": "monthly_populations",
                        "measures": ["total_participants"],
                        "get_chart": False,
                    },
                )
                assert not result.isError
                assert decode(result)["records"] == [{"total_participants": 11}]
                invalid = await client.call_tool(
                    "query_model", {"model_name": "does_not_exist", "get_chart": False}
                )
                assert invalid.isError

    asyncio.run(check())


def test_server_is_read_only_and_import_has_no_db_side_effects(warehouse):
    from semantic_layer.semantic_layer.mcp_server import create_server

    server = create_server(warehouse)
    try:
        with pytest.raises(Exception, match="read-only"):
            server.warehouse_connection.raw_sql(
                "create table should_not_exist(i integer)"
            )
    finally:
        server.warehouse_connection.disconnect()
    with pytest.raises(FileNotFoundError):
        create_server(warehouse.with_name("missing.duckdb"))
    assert not warehouse.with_name("missing.duckdb").exists()


def test_external_candidate_queries_mcp_but_wrong_answer_fails(warehouse, tmp_path):
    candidate = tmp_path / "wrong_agent.py"
    candidate.write_text("""import json,sys
json.loads(sys.stdin.readline())
print(json.dumps({"action":"call","tool":"query_model","arguments":{"model_name":"monthly_populations","measures":["total_participants"],"get_chart":False}}),flush=True)
evidence=json.loads(sys.stdin.readline())
assert evidence["result"]["records"][0]["total_participants"] == 11
print(json.dumps({"action":"answer","facts":{"entries":999},"explanation":"Deliberately incorrect","caveats":["entries_not_people"]}),flush=True)
""")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation.run",
            "run",
            "--work",
            str(warehouse.parent),
            "--run-id",
            "negative-control",
            "--candidate",
            "deliberately wrong test process",
            "--question",
            "entries",
            "--candidate-command",
            f"{sys.executable} {candidate}",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )
    assert result.returncode == 1, result.stdout
    summary = json.loads(
        (warehouse.parent / "negative-control/summary.json").read_text()
    )
    assert summary["passed"] == 0
    transcript = json.loads(
        (warehouse.parent / "negative-control/entries.json").read_text()
    )
    assert transcript["calls"][0]["result"]["records"] == [{"total_participants": 11}]
    assert "999" in summary["results"][0]["failures"][0]


def test_candidate_eof_and_invalid_json_are_failed_not_passed():
    from evaluation.run import drive

    async def check():
        lines = iter(["[]\n", "not-json\n", ""])
        messages = []

        async def read():
            return next(lines)

        async def send(message):
            messages.append(message)

        transcript = await drive(None, QUESTIONS[0], [], read, send)
        assert transcript["error"] == "Candidate ended without an answer"
        assert "candidate_input" in transcript
        assert len([m for m in messages if m["event"] == "error"]) == 2
        assert not grade(QUESTIONS[0], transcript)["passed"]

    asyncio.run(check())
