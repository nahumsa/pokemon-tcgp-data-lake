"""Build a small raw-to-dbt benchmark warehouse; never use production data."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]


def raw_records():
    events = [
        (
            "jan",
            "2026-01-15",
            "January Play",
            "limitless_play",
            "online",
            ["Alice", "Bob", "Carol", "Dana"],
        ),
        (
            "labs",
            "2026-02-15",
            "February Labs",
            "limitless_labs",
            "in_person",
            ["Alice", "Bob", "Eli", "No list"],
        ),
        (
            "feb",
            "2026-02-16",
            "February Play",
            "limitless_play",
            "online",
            ["Ada", "Bea", "Missing"],
        ),
    ]
    matches = [
        ("jan", "Alice", "Bob", "1", "WIN"),
        ("jan", "Bob", "Alice", "1", "LOSS"),
        ("jan", "Alice", "Carol", "2", "TIE"),
        ("jan", "Carol", "Alice", "2", "TIE"),
        ("jan", "Alice", "Carol", "3", "LOSS"),
        ("jan", "Carol", "Alice", "3", "WIN"),
        ("jan", "Dana", "BYE", "1", "BYE"),
        ("jan", "Bob", "Mystery", "2", "LOSS"),
        ("jan", "Bob", "Carol", "4", "WIN"),
        ("labs", "Alice", "Bob", "1", "WIN"),
        ("labs", "Bob", "Alice", "1", "LOSS"),
        ("labs", "Eli", "No list", "1", "TIE"),
        ("labs", "No list", "Eli", "1", "TIE"),
        ("feb", "Ada", "Bea", "1", "WIN"),
        ("feb", "Bea", "Ada", "1", "LOSS"),
        ("feb", "Ada", "Bea", "2", "WIN"),
        ("feb", "Bea", "Ada", "2", "LOSS"),
    ]
    decks = {
        ("jan", "Alice"): [
            ("Dragapult ex", "TWM-130", 2, "pokemon"),
            ("Dragapult ex", "PRE-073", 2, "pokemon"),
            ("Tech", None, 3, "trainer"),
        ],
        ("jan", "Bob"): [("Charizard ex", "OBF-125", 4, "pokemon")],
        ("jan", "Carol"): [("Dragapult ex", "TWM-130", 4, "pokemon")],
        ("labs", "Alice"): [("Dragapult ex", "TWM-130", 4, "pokemon")],
        ("labs", "Bob"): [("Charizard ex", "OBF-125", 4, "pokemon")],
        ("labs", "Eli"): [("Charizard ex", "OBF-125", 4, "pokemon")],
        ("feb", "Ada"): [("Dragapult ex", "TWM-130", 4, "pokemon")],
        ("feb", "Bea"): [("Charizard ex", "OBF-125", 4, "pokemon")],
    }
    return events, matches, decks


def oracle():
    """Calculate answers from raw Python records, without SQL or semantic measures."""
    events, matches, decks = raw_records()
    online = {e[0] for e in events if e[4] == "online"}
    dragon = {
        key
        for key, cards in decks.items()
        if any(c[0] == "Dragapult ex" for c in cards)
    }
    dragon_results = [m for m in matches if m[0] in online and m[:2] in dragon]
    january = [m for m in matches if m[0] == "jan"]
    names = set(events[0][5])
    pairings = {
        (m[3], tuple(sorted(m[1:3])))
        for m in january
        if m[1] in names and m[2] in names and m[4] != "BYE"
    }
    alice = [m for m in january if m[1] == "Alice"]
    tech_with = [m for m in january if m[1] == "Alice" and (m[0], m[2]) in dragon]
    tech_without = [m for m in january if m[1] == "Carol" and (m[0], m[2]) in dragon]

    def pct(rows):
        return 100 * sum(m[4] == "WIN" for m in rows) / len(rows) if rows else None

    return {
        "entries": {"entries": sum(len(e[5]) for e in events)},
        "online_entries": {"entries": sum(len(e[5]) for e in events if e[0] in online)},
        "unique_matches": {
            "played_pairings": len(pairings),
            "player_records": len(january),
            "byes": sum(m[4] == "BYE" for m in january),
        },
        "ties": {
            "wins": sum(m[4] == "WIN" for m in alice),
            "results": len(alice),
            "win_rate": pct(alice),
        },
        "pooled_rate": {
            "wins": sum(m[4] == "WIN" for m in dragon_results),
            "results": len(dragon_results),
            "win_rate": pct(dragon_results),
        },
        "meta_share": {
            "archetype_entries": sum(k[0] in online for k in dragon),
            "all_entries": sum(len(e[5]) for e in events if e[0] in online),
            "meta_share": 100
            * sum(k[0] in online for k in dragon)
            / sum(len(e[5]) for e in events if e[0] in online),
        },
        "printings": {
            "decks": sum(k[0] in online for k in dragon),
            "copies": sum(
                c[2]
                for k, cards in decks.items()
                if k[0] in online
                for c in cards
                if c[0] == "Dragapult ex"
            ),
        },
        "missing_results": {"results": 0, "win_rate": None},
        "classification": {"entries": sum(len(e[5]) for e in events) - len(decks)},
        "association": {
            "with_results": len(tech_with),
            "without_results": len(tech_without),
            "with_rate": pct(tech_with),
            "without_rate": pct(tech_without),
            "difference_pp": pct(tech_with) - pct(tech_without),
            "evidence_status": "insufficient_matches",
            "rank": None,
            "causal": False,
        },
        "future": {"answerable": False},
        "source_scope": {"entries": len(next(e[5] for e in events if e[0] == "labs"))},
    }


def build(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    output.mkdir(parents=True)
    project = output / "transformations"
    shutil.copytree(
        ROOT / "transformations",
        project,
        ignore=shutil.ignore_patterns("target", "logs", "*.duckdb*"),
    )
    database = output / "benchmark.duckdb"
    events, matches, decks = raw_records()
    urls = {
        e[0]: (
            f"https://labs.limitlesstcg.com/{e[0]}"
            if e[3] == "limitless_labs"
            else f"https://play.limitlesstcg.com/tournament/{e[0]}"
        )
        for e in events
    }
    with duckdb.connect(str(database)) as con:
        con.execute("create schema pokemon_tcg_data; set schema=pokemon_tcg_data")
        con.execute("""
            create table tournaments(tournament_page varchar, data_date varchar,
                data_name varchar, source varchar, event_type varchar,
                data_format varchar, data_organizer varchar, data_winner varchar,
                data_players int, _dlt_load_id varchar);
            create table tournament_participants(tournament_link varchar, name varchar,
                deck varchar, _dlt_load_id varchar);
            create table participant_deck(_dlt_id varchar, tournament varchar,
                player varchar, decklist_link varchar, _dlt_load_id varchar);
            create table participant_deck__decklist(_dlt_parent_id varchar, name varchar,
                code varchar, quantity int, kind varchar);
            create table participant_matches(tournament varchar, p1 varchar, p2 varchar,
                round varchar, result varchar, _dlt_load_id varchar);
        """)
        for key, date, name, source, setting, entrants in events:
            con.execute(
                "insert into tournaments values (?,?,?,?,?,'STANDARD','Fixture','Alice',?,'1')",
                [urls[key], date, name, source, setting, len(entrants)],
            )
            con.executemany(
                "insert into tournament_participants values (?,?,null,'1')",
                [(urls[key], p) for p in entrants],
            )
        for (event, player), cards in decks.items():
            identity = f"{event}:{player}"
            con.execute(
                "insert into participant_deck values (?,?,?,'fixture-deck','1')",
                [identity, urls[event], player],
            )
            con.executemany(
                "insert into participant_deck__decklist values (?,?,?,?,?)",
                [(identity, *card) for card in cards],
            )
        con.executemany(
            "insert into participant_matches values (?,?,?,?,?,'1')",
            [(urls[e], p1, p2, r, result) for e, p1, p2, r, result in matches],
        )
    (project / "profiles.yml").write_text(
        yaml.safe_dump(
            {
                "pokemon_tcg_transform": {
                    "target": "evaluation",
                    "outputs": {
                        "evaluation": {
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
        args = [
            str(Path(sys.executable).with_name("dbt")),
            action,
            "--profiles-dir",
            ".",
        ]
        if action == "test":
            args += ["--select", "test_type:data"]
        result = subprocess.run(
            args,
            cwd=project,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
        )
        (output / f"dbt-{action}.log").write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(
                f"dbt {action} failed; see {output / f'dbt-{action}.log'}"
            )
    fingerprint = hashlib.sha256(database.read_bytes()).hexdigest()
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "fixture_version": 1,
                "sha256": fingerprint,
                "database": str(database),
                "synthetic": True,
            },
            indent=2,
        )
        + "\n"
    )
    # These answers are evaluator-only and are never sent to the candidate process.
    (output / "expected.json").write_text(json.dumps(oracle(), indent=2) + "\n")
    return database
