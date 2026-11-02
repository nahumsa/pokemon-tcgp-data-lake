"""Freeze public Limitless Labs responses and rebuild an isolated real warehouse."""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
import yaml

from ingestion import labs
from .fixture import ROOT


def stage_snapshot(rows, database):
    """Normalize saved importer JSON to dbt's raw contract, without dlt runtime state."""
    with duckdb.connect(str(database)) as con:
        con.execute(
            "begin; create schema if not exists pokemon_tcg_data; set schema=pokemon_tcg_data"
        )
        con.execute("""
            create or replace table tournaments(tournament_page varchar,data_date varchar,data_name varchar,
                data_organizer varchar,data_format varchar,data_players varchar,data_winner varchar,
                source varchar,event_type varchar,_dlt_load_id varchar);
            create or replace table tournament_participants(tournament_link varchar,name varchar,deck varchar,_dlt_load_id varchar);
            create or replace table participant_deck(_dlt_id varchar,player varchar,tournament varchar,decklist_link varchar,_dlt_load_id varchar);
            create or replace table participant_deck__decklist(_dlt_parent_id varchar,name varchar,code varchar,quantity bigint,kind varchar);
            create or replace table participant_matches(tournament varchar,round varchar,p1 varchar,p2 varchar,result varchar,_dlt_load_id varchar);
        """)
        columns = [
            "tournament_page",
            "data_date",
            "data_name",
            "data_organizer",
            "data_format",
            "data_players",
            "data_winner",
            "source",
            "event_type",
        ]
        con.executemany(
            "insert into tournaments values (?,?,?,?,?,?,?,?,?,?)",
            [[*[r.get(c) for c in columns], "snapshot"] for r in rows["tournaments"]],
        )
        con.executemany(
            "insert into tournament_participants values (?,?,?,?)",
            [
                [r["tournament_link"], r["name"], r.get("deck"), "snapshot"]
                for r in rows["tournament_participants"]
            ],
        )
        parents, children = [], []
        for r in rows["participant_deck"]:
            key = hashlib.sha256(
                json.dumps([r["tournament"], r["player"]]).encode()
            ).hexdigest()
            parents.append(
                [key, r["player"], r["tournament"], r.get("decklist_link"), "snapshot"]
            )
            children.extend(
                [key, c["name"], c.get("code"), c["quantity"], c["kind"]]
                for c in r["decklist"]
            )
        if parents:
            con.executemany("insert into participant_deck values (?,?,?,?,?)", parents)
        if children:
            con.executemany(
                "insert into participant_deck__decklist values (?,?,?,?,?)", children
            )
        con.executemany(
            "insert into participant_matches values (?,?,?,?,?,?)",
            [
                [r["tournament"], r["Round"], r["P1"], r["P2"], r["Result"], "snapshot"]
                for r in rows["participant_matches"]
            ],
        )

        con.commit()


def prepare(output, latest=2):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache = output / "api"
    cache.mkdir(exist_ok=True)
    original_api = labs.api

    def cached_api(resource, **params):
        key = json.dumps([resource, params], sort_keys=True)
        path = cache / (
            resource + "-" + hashlib.sha256(key.encode()).hexdigest()[:16] + ".json"
        )
        if path.exists():
            return json.loads(path.read_text())["response"]
        response = original_api(resource, **params)
        record = {
            "resource": resource,
            "params": params,
            "url": f"{labs.API_URL}/{resource}",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "response": response,
        }
        path.write_text(json.dumps(record, ensure_ascii=False))
        return response

    labs.api = cached_api
    snapshot = output / "rows.json.gz"
    if not snapshot.exists():
        rows = labs.extract_events(latest, workers=4)
        with gzip.open(snapshot, "wt", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False)
    else:
        with gzip.open(snapshot, "rt", encoding="utf-8") as handle:
            rows = json.load(handle)
    database = output / "benchmark.duckdb"
    stage_snapshot(rows, database)
    project = output / "transformations"
    if not project.exists():
        shutil.copytree(
            ROOT / "transformations",
            project,
            ignore=shutil.ignore_patterns("target", "logs", "*.duckdb*"),
        )
    (project / "profiles.yml").write_text(
        yaml.safe_dump(
            {
                "pokemon_tcg_transform": {
                    "target": "real_evaluation",
                    "outputs": {
                        "real_evaluation": {
                            "type": "duckdb",
                            "path": str(database),
                            "threads": 1,
                        }
                    },
                }
            }
        )
    )
    env = {**os.environ, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    for action in ("deps", "seed", "run", "test"):
        command = [
            str(Path(sys.executable).with_name("dbt")),
            action,
            "--profiles-dir",
            ".",
        ]
        if action == "test":
            command += ["--select", "test_type:data"]
        result = subprocess.run(
            command,
            cwd=project,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=600,
        )
        (output / f"dbt-{action}.log").write_text(result.stdout)
        print(f"dbt {action}: exit {result.returncode}", flush=True)
        if result.returncode and action != "test":
            raise RuntimeError(f"dbt {action} failed; see logs")
    manifest = {
        "synthetic": False,
        "source": "Limitless Labs public Masters TCG API",
        "staging": "Explicit normalization of saved production-importer JSON to raw dbt tables; dlt runtime excluded",
        "database": str(database),
        "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "events": rows["tournaments"],
        "row_counts": {k: len(v) for k, v in rows.items()},
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "api_cache_files": len(list(cache.glob("*.json"))),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {"database": str(database), "row_counts": manifest["row_counts"]}, indent=2
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--latest", type=int, default=2)
    args = parser.parse_args()
    prepare(args.work, args.latest)
