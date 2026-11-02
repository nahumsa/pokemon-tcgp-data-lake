"""Run the repeatable repository validation routine and retain reviewable logs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--analysis", type=Path, help="Also validate an analysis evidence record"
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "validation-results")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "RUNTIME__DLTHUB_TELEMETRY": "false",
    }
    bin_dir = Path(sys.executable).parent
    stages = [
        ("lint", [str(bin_dir / "ruff"), "check", "."], ROOT),
        (
            "dbt-deps",
            [str(bin_dir / "dbt"), "deps", "--profiles-dir", "."],
            ROOT / "transformations",
        ),
        (
            "dbt-parse",
            [
                str(bin_dir / "dbt"),
                "parse",
                "--profiles-dir",
                ".",
                "--no-partial-parse",
            ],
            ROOT / "transformations",
        ),
        (
            "regressions",
            [
                sys.executable,
                "-m",
                "pytest",
                "ingestion/test_labs.py",
                "semantic_layer/tests",
                "tests",
                "-q",
                f"--junitxml={output / 'tests.xml'}",
            ],
            ROOT,
        ),
        (
            "dbt-unit",
            [
                str(bin_dir / "dbt"),
                "test",
                "--profiles-dir",
                ".",
                "--target",
                "unit",
                "--select",
                "test_type:unit",
            ],
            ROOT / "transformations",
        ),
    ]
    if args.analysis:
        stages.append(
            (
                "analysis-evidence",
                [
                    sys.executable,
                    "scripts/validate_analysis.py",
                    str(args.analysis.resolve()),
                ],
                ROOT,
            )
        )
    results = []
    for name, command, cwd in stages:
        print(f"Running {name}...", flush=True)
        start = time.monotonic()
        try:
            run = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=600,
            )
            code, log = run.returncode, run.stdout
        except (OSError, subprocess.TimeoutExpired) as exc:
            code, log = 1, str(exc)
        (output / f"{name}.log").write_text(log)
        results.append(
            {
                "stage": name,
                "status": "pass" if code == 0 else "fail",
                "exit_code": code,
                "seconds": round(time.monotonic() - start, 2),
            }
        )
        print(f"{name}: {results[-1]['status']}", flush=True)
    failed = any(result["status"] == "fail" for result in results)
    (output / "summary.json").write_text(
        json.dumps(
            {
                "status": "fail" if failed else "pass",
                "stages": results,
                "scope": "Synthetic regressions and analysis evidence; no live-data completeness guarantee",
            },
            indent=2,
        )
        + "\n"
    )
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
