"""Generate a question-by-question review from saved real MCP traces."""

import argparse
import json
from pathlib import Path

from .fixture import ROOT, oracle
from .grade import equivalent, grade


def report(run, questions_path=None, expected_path=None):
    questions = json.loads(
        (questions_path or ROOT / "evaluation/questions.json").read_text()
    )
    expected = json.loads(expected_path.read_text()) if expected_path else oracle()
    lines = [
        "# MCP analytical evaluation",
        "",
        "Answers are compared against the reference dataset selected for this run. See the snapshot manifest for scope.",
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
        answer = record.get("answer")
        answer = answer if isinstance(answer, dict) else {}
        facts = answer.get("facts")
        facts = facts if isinstance(facts, dict) else {}
        explanation = answer.get("explanation")
        explanation = explanation if isinstance(explanation, str) else "No final answer"
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
            "Answer: " + explanation,
            "",
            "Trace: [" + path.name + "](" + path.name + ")",
        ]
        details += [
            "",
            "| Fact | Agent answer | Independent reference | Match |",
            "|---|---|---|---|",
        ]
        for key, reference in expected[question["id"]].items():
            actual = facts.get(key)

            def display(value):
                return json.dumps(value, ensure_ascii=False)

            match = "yes" if equivalent(actual, reference) else "NO"
            details.append(
                f"| {key} | {display(actual)} | {display(reference)} | {match} |"
            )
        if result["failures"]:
            details += ["", "Failures: " + "; ".join(result["failures"])]
    return "\n".join(lines + details) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--expected", type=Path)
    args = parser.parse_args()
    destination = args.run / "report.md"
    destination.write_text(report(args.run, args.questions, args.expected))
    print(destination)


if __name__ == "__main__":
    main()
