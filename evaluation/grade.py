"""Deterministically grade agent outputs against an independent raw-record oracle."""

import math

from .fixture import oracle


def equivalent(actual, expected):
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        return type(actual) is type(expected) and actual == expected
    return (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and math.isfinite(actual)
        and abs(actual - expected) <= 0.011
    )


def grade(question, transcript, expected=None):
    expected = (expected or oracle())[question["id"]]
    final = transcript.get("answer", {})
    if not isinstance(final, dict) or not isinstance(final.get("facts", {}), dict):
        return {
            "id": question["id"],
            "passed": False,
            "failures": ["Invalid answer schema"],
            "tool_calls": len(transcript.get("calls", [])),
            "tool_errors": 0,
        }
    failures = []
    facts = final.get("facts", {})
    for key, value in expected.items():
        if key not in facts or not equivalent(facts[key], value):
            failures.append(f"{key}: expected {value!r}, got {facts.get(key)!r}")
    calls = transcript.get("calls", [])
    if not any(c.get("tool") == "query_model" and not c.get("is_error") for c in calls):
        failures.append("No successful MCP query recorded")
    if (
        not isinstance(final.get("explanation"), str)
        or not final["explanation"].strip()
    ):
        failures.append("Missing explanation")
    checks = final.get("caveats", [])
    if not isinstance(checks, list):
        checks = []
    for caveat in question["required_caveats"]:
        if caveat not in checks:
            failures.append(f"Missing analytical caveat: {caveat}")
    return {
        "id": question["id"],
        "passed": not failures,
        "failures": failures,
        "tool_calls": len(calls),
        "tool_errors": sum(bool(c.get("is_error")) for c in calls),
    }
