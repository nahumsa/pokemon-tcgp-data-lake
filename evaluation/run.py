"""Run a candidate agent through a real MCP server; save and grade every answer.

bridge: JSONL stdin/stdout for a human or this assistant to act as the candidate.
run: one fresh candidate subprocess per question, using the same JSONL protocol.
The candidate receives only the question, output schema, and discovered MCP tools.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .fixture import ROOT, build
from .grade import grade

QUESTIONS = ROOT / "evaluation/questions.json"


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, default=str, allow_nan=False) + "\n"
    )


def decode(result):
    blocks = [c.text for c in result.content if c.type == "text"]
    values = []
    for block in blocks:
        try:
            values.append(json.loads(block))
        except json.JSONDecodeError:
            values.append(block)
    return values[0] if len(values) == 1 else values


def prompt(question, tools):
    return {
        "event": "question",
        "id": question["id"],
        "question": question["question"],
        "instructions": "Answer by choosing and calling the available MCP tools. Do not access local files, oracle answers, or external sources. Return a factual explanation grounded in tool results. Percentages use 0-100. Report missing values as null.",
        "answer_schema": {
            "action": "answer",
            "facts": question["facts"],
            "explanation": "Your reasoning and conclusion",
            "caveats": question["required_caveats"],
        },
        "protocol": {
            "tool_call": {"action": "call", "tool": "tool_name", "arguments": {}},
            "final": {
                "action": "answer",
                "facts": {},
                "explanation": "...",
                "caveats": [],
            },
        },
        "tools": [t.model_dump(mode="json") for t in tools],
    }


async def drive(session, question, tools, read, send, max_calls=20):
    start = time.monotonic()
    transcript = {
        "id": question["id"],
        "question": question["question"],
        "calls": [],
        "candidate_input": prompt(question, tools),
    }
    await send(prompt(question, tools))
    names = {t.name for t in tools}
    for _ in range(max_calls + 1):
        try:
            line = await asyncio.wait_for(read(), timeout=180)
        except (asyncio.TimeoutError, OSError) as exc:
            transcript["error"] = f"Candidate read failed: {type(exc).__name__}"
            break
        if not line:
            transcript["error"] = "Candidate ended without an answer"
            break
        try:
            action = json.loads(line)
        except (ValueError, TypeError):
            await send(
                {"event": "error", "message": "Expected one JSON action per line"}
            )
            continue
        if not isinstance(action, dict):
            await send({"event": "error", "message": "Action must be a JSON object"})
            continue
        if action.get("action") == "answer":
            transcript["answer"] = {k: v for k, v in action.items() if k != "action"}
            break
        if action.get("action") != "call" or action.get("tool") not in names:
            await send({"event": "error", "message": "Unknown action/tool"})
            continue
        if len(transcript["calls"]) >= max_calls:
            transcript["error"] = "Tool budget exhausted"
            break
        call = {"tool": action["tool"], "arguments": action.get("arguments", {})}
        try:
            result = await asyncio.wait_for(
                session.call_tool(call["tool"], call["arguments"]), timeout=60
            )
            call.update(result=decode(result), is_error=bool(result.isError))
        except Exception as exc:
            call.update(result=str(exc), is_error=True)
        transcript["calls"].append(call)
        await send(
            {"event": "tool_result", "call_index": len(transcript["calls"]) - 1, **call}
        )
    if "answer" not in transcript:
        transcript.setdefault("error", "Candidate produced no final answer")
    transcript["seconds"] = round(time.monotonic() - start, 3)
    return transcript


async def evaluate(args):
    work = args.work.resolve()
    database = work / "benchmark.duckdb"
    if not database.is_file():
        raise FileNotFoundError("Run build first; no evaluation database exists")
    manifest = json.loads((work / "manifest.json").read_text())
    if hashlib.sha256(database.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("Benchmark database differs from its manifest")
    question_path = args.questions or (
        work / "questions.json" if not manifest.get("synthetic", True) else QUESTIONS
    )
    questions = json.loads(question_path.read_text())
    expected_path = args.expected or work / "expected.json"
    expected = json.loads(expected_path.read_text()) if expected_path.exists() else None
    if not manifest.get("synthetic", True) and expected is None:
        raise ValueError("Real-data evaluation requires independent expected answers")
    if args.question:
        questions = [q for q in questions if q["id"] == args.question]
        if not questions:
            raise ValueError(f"Unknown question: {args.question}")
    output = work / args.run_id
    if output.exists():
        raise FileExistsError(f"Run already exists: {output}; choose a new --run-id")
    output.mkdir()
    env = {
        **os.environ,
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "RUNTIME__DLTHUB_TELEMETRY": "false",
    }
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            str(ROOT / "semantic_layer/semantic_layer/mcp_server.py"),
            "--database",
            str(database),
        ],
        env=env,
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            write_json(
                output / "tools.json", [t.model_dump(mode="json") for t in tools]
            )
            results = []
            for question in questions:
                process = None
                if args.mode == "run":
                    process = await asyncio.create_subprocess_exec(
                        *shlex.split(args.candidate_command),
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=(output / f"{question['id']}.stderr.log").open("w"),
                        cwd=ROOT,
                        env=env,
                    )
                    read = process.stdout.readline

                    async def send(value):
                        process.stdin.write(
                            (json.dumps(value, default=str) + "\n").encode()
                        )
                        await process.stdin.drain()
                else:

                    async def read():
                        return await asyncio.to_thread(sys.stdin.readline)

                    async def send(value):
                        print(json.dumps(value, default=str), flush=True)

                try:
                    transcript = await drive(session, question, tools, read, send)
                except Exception as exc:
                    transcript = {"id": question["id"], "calls": [], "error": str(exc)}
                finally:
                    if process and process.returncode is None:
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.wait()
                transcript.update(
                    candidate=args.candidate,
                    fixture_sha256=manifest["sha256"],
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                write_json(output / f"{question['id']}.json", transcript)
                result = grade(question, transcript, expected)
                results.append(result)
                print(json.dumps({"event": "graded", **result}), flush=True)
    summary = {
        "candidate": args.candidate,
        "fixture_sha256": manifest["sha256"],
        "passed": sum(r["passed"] for r in results),
        "total": len(results),
        "results": results,
        "scope": (
            "Controlled synthetic benchmark"
            if manifest.get("synthetic", True)
            else "Frozen real public tournament snapshot"
        )
        + "; facts and declared caveats are scored. Free-text explanation still needs review.",
        "synthetic": manifest.get("synthetic", True),
        "questions_sha256": hashlib.sha256(question_path.read_bytes()).hexdigest(),
    }
    write_json(output / "summary.json", summary)
    return 0 if summary["passed"] == summary["total"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--work", type=Path, required=True)
    for mode in ("bridge", "run"):
        command = sub.add_parser(mode)
        command.add_argument("--work", type=Path, required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--candidate", required=True)
        command.add_argument("--question")
        command.add_argument("--questions", type=Path)
        command.add_argument("--expected", type=Path)
        if mode == "run":
            command.add_argument("--candidate-command", required=True)
    args = parser.parse_args()
    if args.mode == "build":
        print(build(args.work))
        return 0
    return asyncio.run(evaluate(args))


if __name__ == "__main__":
    raise SystemExit(main())
