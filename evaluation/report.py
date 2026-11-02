"""Generate a question-by-question review from saved real MCP traces."""

import argparse
import json
from pathlib import Path

from .fixture import ROOT, oracle
from .grade import grade


def report(run):
    questions = json.loads((ROOT / "evaluation/questions.json").read_text())
    expected = oracle()
    lines = [
        "# MCP analytical evaluation",
        "",
        "This is a controlled synthetic benchmark, not a live tournament report.",
        "",
        "| Question | Verdict | Tool calls |",
        "|---|---|---|",
    ]
    details = []
    for question in questions:
        path = run / f"{question['id']}.json"
        if not path.exists():
            continue
        record = json.loads(path.read_text())
        result = grade(question, record, expected)
        verdict = "PASS" if result["passed"] else "FAIL"
        lines.append(f"| {question['id']} | {verdict} | {result['tool_calls']} |")
        details += [
            "",
            f"## {question['id']}",
            "",
            question["question"],
            "",
            "Expected: `" + json.dumps(expected[question["id"]]) + "`",
            "",
            "Answer: " + record.get("answer", {}).get("explanation", "No final answer"),
            "",
            "Trace: [" + path.name + "](" + path.name + ")",
        ]
        if result["failures"]:
            details += ["", "Failures: " + "; ".join(result["failures"])]
    return "\n".join(lines + details) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    destination = args.run / "report.md"
    destination.write_text(report(args.run))
    print(destination)


if __name__ == "__main__":
    main()
