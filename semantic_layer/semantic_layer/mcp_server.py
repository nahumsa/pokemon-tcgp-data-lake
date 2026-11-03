"""Serve semantic models, or check readiness without starting MCP."""

import argparse
import json
import sys
from pathlib import Path

from boring_semantic_layer import MCPSemanticModel

from semantic_layer.runtime import ReadinessError, open_models


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, help="Override the configured warehouse for this run."
    )
    parser.add_argument(
        "--check", action="store_true", help="Check database/model readiness and exit."
    )
    args = parser.parse_args(argv)
    try:
        loader = open_models(args.database) if args.database is not None else open_models()
        with loader as (path, models):
            if args.check:
                print(
                    json.dumps(
                        {
                            "database": str(path),
                            "read_only": True,
                            "models": sorted(models),
                        }
                    )
                )
            else:
                server = MCPSemanticModel(
                    models=models, name="Pokemon TCG Data Lake Semantic Layer Server"
                )
                server.run(transport="stdio", show_banner=False)
    except ReadinessError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
