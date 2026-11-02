"""Reviewable evidence gate for an analytical answer, independent of data quality.

Usage: uv run python scripts/validate_analysis.py analysis.json
This checks structured claims, not whether natural-language prose is truthful.
"""

import argparse
import json
from pathlib import Path


REQUIRED_CONTEXT = (
    "question",
    "population",
    "period",
    "sources",
    "event_types",
    "grain",
    "exclusions",
    "limitations",
    "queries",
    "claims",
)


def validate(report):
    errors = []
    for field in REQUIRED_CONTEXT:
        if field not in report:
            errors.append(f"Missing analysis context: {field}")
    for field in (
        "question",
        "population",
        "period",
        "sources",
        "event_types",
        "grain",
    ):
        if not report.get(field):
            errors.append(f"Empty analysis context: {field}")
    queries = report.get("queries", {})
    for query_id, evidence in queries.items():
        for field in ("sql", "database_revision", "result", "result_grain"):
            if not evidence.get(field):
                errors.append(f"{query_id}: missing evidence field {field}")
    claims = report.get("claims", [])
    if not claims:
        errors.append("No claims supplied for review")
    for index, claim in enumerate(claims):
        label = f"claim[{index}]"
        if not claim.get("text"):
            errors.append(f"{label}: missing claim text")
        if claim.get("kind") not in ("descriptive", "association"):
            errors.append(
                f"{label}: unsupported causal/predictive claim; needs separate evaluation"
            )
        if not claim.get("evidence") or any(
            q not in queries for q in claim["evidence"]
        ):
            errors.append(f"{label}: claim must reference recorded query evidence")
        if not claim.get("caveats"):
            errors.append(f"{label}: disclose uncertainty and coverage limitations")
        if claim.get("kind") == "association" and not claim.get("confounders"):
            errors.append(
                f"{label}: association requires confounders and selection-bias review"
            )
        if "rate" not in claim:
            continue
        rate = claim["rate"]
        for field in (
            "numerator",
            "denominator",
            "value",
            "unit",
            "population",
            "tie_policy",
            "aggregation",
            "evidence",
        ):
            if field not in rate:
                errors.append(f"{label}: missing rate field {field}")
        if any(field not in rate for field in ("numerator", "denominator", "value")):
            continue
        n, d, value = rate["numerator"], rate["denominator"], rate["value"]
        if (
            not isinstance(n, (int, float))
            or isinstance(n, bool)
            or not isinstance(d, (int, float))
            or isinstance(d, bool)
            or n < 0
            or d < 0
            or n > d
        ):
            errors.append(f"{label}: invalid numerator/denominator counts")
            continue
        if rate.get("aggregation") != "ratio_of_sums":
            errors.append(f"{label}: pool counts rather than averaging cohort rates")
        if rate.get("unit") != "percent":
            errors.append(f"{label}: rate unit must be percent")
        expected = n * 100 / d if d else None
        if expected is None:
            if value is not None:
                errors.append(f"{label}: zero denominator must produce null")
        elif (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not abs(value - expected) <= 0.011
        ):
            errors.append(f"{label}: rate disagrees with counts (expected {expected})")
        # Counts must occur in an identified result row, not only in claim prose.
        evidence = queries.get(rate.get("evidence"), {})
        rows = evidence.get("result", [])
        if not any(
            isinstance(row, dict)
            and row.get("numerator") == n
            and row.get("denominator") == d
            for row in rows
        ):
            errors.append(f"{label}: rate counts are not traceable to a query result")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    args = parser.parse_args()
    report = json.loads(args.analysis.read_text())
    errors = validate(report)
    print(
        json.dumps({"status": "fail" if errors else "pass", "errors": errors}, indent=2)
    )
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
