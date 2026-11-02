"""Independent reference SQL over original API records, never dbt marts or MCP output."""

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from .fixture import ROOT


def make_reference(work):
    work = Path(work)
    manifest = json.loads((work / "manifest.json").read_text())
    packets = [json.loads(p.read_text()) for p in (work / "api").glob("*.json")]
    selected = {
        p["params"]["tournamentId"] for p in packets if p["resource"] == "standings"
    }
    catalogue = next(p["response"] for p in packets if p["resource"] == "tournaments")
    catalog = {f"{e['id']:04d}": e for e in catalogue if f"{e['id']:04d}" in selected}
    latest = max(catalog, key=lambda e: catalog[e]["utc_start"])
    labels = defaultdict(set)
    for rule in csv.DictReader((ROOT / "transformations/seeds/meta_decks.csv").open()):
        labels[rule["sub_archetype"]].add(rule["archetype"])
    entries = []
    for packet in packets:
        if packet["resource"] != "standings":
            continue
        event = packet["params"]["tournamentId"]
        counts = Counter(p["name"] for p in packet["response"])
        for player in packet["response"]:
            label = player.get("deck_name")
            parent = (
                next(iter(labels[label]))
                if label is not None and len(labels[label]) == 1
                else label
            )
            entries.append(
                {
                    "event": event,
                    "player_id": player["tp_id"],
                    "name": player["name"]
                    if counts[player["name"]] == 1
                    else f"{player['name']} [Labs {player['tp_id']}]",
                    "archetype": parent,
                    "published": bool(player.get("decklist")),
                    "placement": player["placement"],
                }
            )
    events = [
        {"event": key, "source": "limitless_labs", "event_type": "in_person"}
        for key in selected
    ]
    lookup = {(e["event"], e["player_id"]): e for e in entries}
    cards, results, pairings = [], [], []
    for packet in packets:
        params, data = packet["params"], packet["response"]
        if packet["resource"] == "decklist":
            event, player = params["tournamentId"], int(params["playerId"])
            for kind in ("pokemon", "trainer", "energy"):
                for card in data.get(kind, []):
                    cards.append(
                        {
                            "event": event,
                            "player_id": player,
                            "name": card["name"],
                            "quantity": card["count"],
                            "kind": kind,
                        }
                    )
        elif packet["resource"] == "pairings":
            event, round_number = params["tournamentId"], int(params["round"])
            for pairing in data:
                ids = [pairing["player1"] or 0, pairing["player2"] or 0]
                known = [
                    bool(pairing.get(f"p{i}_name")) and (event, ids[i - 1]) in lookup
                    for i in (1, 2)
                ]
                pairings.append(
                    {
                        "event": event,
                        "round": round_number,
                        "low": min(ids),
                        "high": max(ids),
                        "played": all(known),
                        "bye": sum(known) == 1,
                    }
                )
                for side in (1, 2):
                    if not pairing.get(f"p{side}_name"):
                        continue
                    own, other = pairing[f"player{side}"], pairing[f"player{3 - side}"]
                    winner = pairing["winner"]
                    outcome = (
                        "TIE" if winner == 0 else ("WIN" if winner == own else "LOSS")
                    )
                    results.append(
                        {
                            "event": event,
                            "round": round_number,
                            "player_id": own,
                            "opponent_id": other,
                            "outcome": outcome,
                            "bye": not bool(pairing.get(f"p{3 - side}_name")),
                        }
                    )
    con = duckdb.connect()
    for name, rows in [
        ("events", events),
        ("entries", entries),
        ("cards", cards),
        ("results", results),
        ("pairings", pairings),
    ]:
        con.register(name + "_input", pd.DataFrame(rows))
        con.execute(f"create table {name} as select * from {name}_input")
    duplicate_count = con.execute(
        "select count(*) from (select event,round,player_id from results group by all having count(*)>1)"
    ).fetchone()[0]
    if duplicate_count:
        raise ValueError(
            "Raw API contains duplicate player/round records; define reference reconciliation explicitly"
        )
    winner = next(e for e in entries if e["event"] == latest and e["placement"] == 1)

    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    base_assoc = """
      with membership as (select distinct event,player_id from cards where name='Dusknoir'),
      eligible as (
        select r.*, (m.player_id is not null) as with_card
        from results r
        join entries own on (r.event=own.event and r.player_id=own.player_id)
        join entries opp on (r.event=opp.event and r.opponent_id=opp.player_id)
        left join membership m on (r.event=m.event and r.player_id=m.player_id)
        where own.archetype='Dragapult' and opp.archetype='Dragapult' and own.published
      ), grouped as (
        select count(*) filter(where with_card) as with_results,
          count(*) filter(where not with_card) as without_results,
          count(*) filter(where with_card and outcome='WIN') as with_wins,
          count(*) filter(where not with_card and outcome='WIN') as without_wins,
          count(distinct (event,player_id)) filter(where with_card) as with_decks,
          count(distinct (event,player_id)) filter(where not with_card) as without_decks
        from eligible
      )
    """
    specifications = [
        (
            "real_entries",
            "How many imported tournament entries are in this real-data snapshot? Distinguish entries from lifetime people.",
            ["entries"],
            ["entries_not_people"],
            "select count(*) as entries from entries",
        ),
        (
            "real_records",
            "How many player-result records exist across the snapshot? These are not unique physical matches.",
            ["player_records"],
            ["perspectives_not_pairings"],
            "select count(*) as player_records from results",
        ),
        (
            "real_latest_matches",
            f"For Regional Championship {catalog[latest]['city']}, report observed unique played pairings and player-result records.",
            ["played_pairings", "player_records"],
            ["observed_not_complete", "perspectives_not_pairings"],
            f"select (select count(distinct (round,low,high)) from pairings where event={quote(latest)} and played) as played_pairings, (select count(*) from results where event={quote(latest)}) as player_records",
        ),
        (
            "real_byes",
            "How many bye records are represented across the snapshot? Do not count them as played pairings.",
            ["byes"],
            ["byes_not_played"],
            "select count(*) as byes from results where bye",
        ),
        (
            "real_classification",
            "How many imported entries have no published decklist or source archetype label? Are they still included in the overall population?",
            ["missing_entries"],
            ["classification_coverage", "entries_still_in_population"],
            "select count(*) as missing_entries from entries where archetype is null and not published",
        ),
        (
            "real_dragapult_share",
            "Across these imported events, what share of all entries are classified as Dragapult? Include every entrant in the population and disclose classification coverage.",
            ["archetype_entries", "all_entries", "meta_share"],
            ["unclassified_in_denominator", "classification_coverage"],
            "select count(*) filter(where archetype='Dragapult') as archetype_entries,count(*) as all_entries,100.0*count(*) filter(where archetype='Dragapult')/count(*) as meta_share from entries",
        ),
        (
            "real_dragapult_rate",
            "What is the pooled recorded-result win rate of classified Dragapult entries? Report wins, results, and percentage; preserve ties in the denominator.",
            ["wins", "results", "win_rate"],
            ["ratio_of_counts", "ties_in_denominator", "classification_coverage"],
            "select count(*) filter(where outcome='WIN') as wins,count(*) as results,100.0*count(*) filter(where outcome='WIN')/nullif(count(*),0) as win_rate from results r join entries e on r.event=e.event and r.player_id=e.player_id where e.archetype='Dragapult'",
        ),
        (
            "real_card",
            "How many published classified decks contain Dreepy, and how many copies are recorded? Combine printings for deck counts.",
            ["decks", "copies"],
            ["functional_card_deduplication", "published_classified_only"],
            "select count(distinct(c.event,c.player_id)) as decks,sum(c.quantity) as copies from cards c join entries e on c.event=e.event and c.player_id=e.player_id where c.name='Dreepy' and e.archetype is not null",
        ),
        (
            "real_player",
            f"For {winner['name']} at Regional Championship {catalog[latest]['city']}, report recorded wins, ties, result count, and win-only percentage.",
            ["wins", "ties", "results", "win_rate"],
            ["ties_in_denominator"],
            f"select count(*) filter(where outcome='WIN') as wins,count(*) filter(where outcome='TIE') as ties,count(*) as results,100.0*count(*) filter(where outcome='WIN')/nullif(count(*),0) as win_rate from results where event={quote(latest)} and player_id={winner['player_id']}",
        ),
        (
            "real_association",
            "For Dusknoir in Dragapult mirror comparisons in this snapshot, report with-card/without-card counts and win rates, percentage-point difference, evidence status, and whether the comparison proves a causal effect.",
            [
                "with_results",
                "without_results",
                "with_rate",
                "without_rate",
                "difference_pp",
                "evidence_status",
                "causal",
            ],
            ["observational_not_causal", "sample_thresholds_not_significance"],
            base_assoc
            + """select with_results,without_results,100.0*with_wins/nullif(with_results,0) as with_rate,
        100.0*without_wins/nullif(without_results,0) as without_rate,
        100.0*with_wins/nullif(with_results,0)-100.0*without_wins/nullif(without_results,0) as difference_pp,
        case when without_results=0 then 'missing_comparison_group'
          when least(with_results,without_results)<10 then 'insufficient_matches'
          when least(with_decks,without_decks)<3 then 'insufficient_decks' else 'meets_sample_thresholds' end as evidence_status,
        false as causal from grouped""",
        ),
        (
            "real_online",
            "How many imported entries in this snapshot belong to online events? Do not mistake absence of online records for poor online performance.",
            ["entries"],
            ["snapshot_scope_only"],
            "select count(*) as entries from entries e join events t on e.event=t.event where t.event_type='online'",
        ),
        (
            "real_forecast",
            "Can this snapshot determine the winning archetype of the next tournament?",
            ["answerable"],
            ["future_outcome_not_observed"],
            "select false as answerable",
        ),
    ]
    questions, expected, references = [], {}, {}
    for identity, question, facts, caveats, sql in specifications:
        cursor = con.execute(sql)
        row = dict(zip([x[0] for x in cursor.description], cursor.fetchone()))
        expected[identity] = row
        references[identity] = {"sql": sql, "expected": row}
        questions.append(
            {
                "id": identity,
                "question": question,
                "facts": facts,
                "required_caveats": caveats,
            }
        )
    # Keep the actual independent SQL and its inputs locally, separately from the MCP warehouse.
    con.execute(
        f"export database {quote(str((work / 'reference-tables').resolve()))} (format parquet)"
    )
    con.close()
    for name, obj in [
        ("questions.json", questions),
        ("expected.json", expected),
        ("references.json", references),
    ]:
        (work / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    manifest["reference_sha256"] = hashlib.sha256(
        (work / "references.json").read_bytes()
    ).hexdigest()
    manifest["reference_method"] = (
        "Independent SQL over original cached API standings, pairings and decklists; no production marts"
    )
    (work / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {
                "questions": len(questions),
                "duplicate_player_rounds": duplicate_count,
                "latest_event": latest,
                "winner_question": winner["name"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    make_reference(parser.parse_args().work)
