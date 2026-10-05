"""Import completed Limitless Labs Masters events into the existing dlt tables."""

import argparse
import gzip
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import dlt

from .constants import (
    PARTICIPANT_DECK_PRIMARY_KEY,
    PARTICIPANT_DECK_TABLE,
    PARTICIPANT_MATCHES_PRIMARY_KEY,
    PARTICIPANT_MATCHES_TABLE,
    PIPELINE_DATASET_NAME,
    PIPELINE_DESTINATION,
    PIPELINE_NAME,
    TOURNAMENT_PARTICIPANTS_PRIMARY_KEY,
    TOURNAMENT_PARTICIPANTS_TABLE,
    TOURNAMENTS_PRIMARY_KEY,
    TOURNAMENTS_TABLE,
)
from .http_client import get

API_URL = "https://mew.limitlesstcg.com/labs/data/tcg"
LABS_URL = "https://labs.limitlesstcg.com"
TABLE_KEYS = {
    TOURNAMENTS_TABLE: TOURNAMENTS_PRIMARY_KEY,
    TOURNAMENT_PARTICIPANTS_TABLE: TOURNAMENT_PARTICIPANTS_PRIMARY_KEY,
    PARTICIPANT_DECK_TABLE: PARTICIPANT_DECK_PRIMARY_KEY,
    PARTICIPANT_MATCHES_TABLE: PARTICIPANT_MATCHES_PRIMARY_KEY,
}


def api(resource, **params):
    """Use Labs' public data endpoints with the shared retry/timeout policy."""
    payload = get(f"{API_URL}/{resource}", params=params).json()
    if payload.get("ok") is not True:
        raise ValueError(f"Labs {resource} failed: {payload.get('message')}")
    return payload["message"]


def latest_completed(events, limit):
    return sorted(
        (event for event in events if event.get("completed") == 1),
        key=lambda event: (event["utc_start"], event["id"]),
        reverse=True,
    )[:limit]


def participant_row(player, url):
    return {
        "tournament_link": url,
        "name": player["name"],
        "place": str(player["placement"]),
        "record": f"{player['wins']}-{player['losses']}-{player['ties']}",
        "points": str(player["points"]),
        "deck": player.get("deck_name"),
        "source": "limitless_labs",
        "source_player_id": player["tp_id"],
        "source_player_name": player.get("source_name", player["name"]),
    }


def match_rows(pairings, round_number, url, names_by_id=None):
    """Keep one result per player/round, as expected by the existing marts."""
    rows = []
    for pairing in pairings:
        if not pairing.get("completed"):
            raise ValueError(f"Unfinished pairing in completed event {url}")
        winner = pairing["winner"]
        ids = (pairing["player1"], pairing["player2"])
        if winner not in (*ids, 0, -1):
            raise ValueError(f"Unknown winner {winner!r} in {url}")
        for side, opponent in ((1, 2), (2, 1)):
            name = pairing.get(f"p{side}_name")
            if not name:
                continue
            if names_by_id is not None:
                name = names_by_id[pairing[f"player{side}"]]
            # A missing opponent is a bye. Keep it explicit, never a real player.
            other = pairing.get(f"p{opponent}_name") or "BYE"
            if other != "BYE" and names_by_id is not None:
                other = names_by_id[pairing[f"player{opponent}"]]
            result = "WIN" if winner == pairing[f"player{side}"] else "LOSS"
            if winner == 0:
                result = "TIE"
            rows.append(
                {
                    "tournament": url,
                    "Round": str(round_number),
                    "P1": name,
                    "P2": other,
                    "Result": result,
                }
            )
    return rows


def deck_row(player, cards, tournament_id, url):
    decklist = [
        {
            "name": card["name"],
            "code": f"{card['set']}-{card['number']}",
            "quantity": card["count"],
            "kind": kind,
        }
        for kind in ("pokemon", "trainer", "energy")
        for card in cards.get(kind, [])
    ]
    if sum(card["quantity"] for card in decklist) != 60:
        raise ValueError(f"Invalid deck size for {player['name']} in {url}")
    return {
        "player": player["name"],
        "tournament": url,
        "decklist": decklist,
        "decklist_link": f"{LABS_URL}/{tournament_id}/player/{player['tp_id']:04d}/decklist",
    }


def extract_events(limit=3, workers=4):
    rows = {table: [] for table in TABLE_KEYS}
    for event in latest_completed(api("tournaments"), limit):
        event_id = f"{event['id']:04d}"
        url = f"{LABS_URL}/{event_id}/standings"
        metadata = api("tournament", id=event_id, division="MA")
        if not metadata.get("completed"):
            raise ValueError(f"Masters division still in progress: {url}")
        players = api("standings", tournamentId=event_id, division="MA")
        if len(players) != metadata["players"]:
            raise ValueError(f"Incomplete standings for {url}")
        counts = Counter(p["name"] for p in players)
        names_by_id = {
            p["tp_id"]: p["name"]
            if counts[p["name"]] == 1
            else f"{p['name']} [Labs {p['tp_id']}]"
            for p in players
        }
        players = [
            dict(p, source_name=p["name"], name=names_by_id[p["tp_id"]])
            for p in players
        ]
        winner = next(p["name"] for p in players if p["placement"] == 1)
        rows[TOURNAMENTS_TABLE].append(
            {
                "tournament_page": url,
                "data_date": datetime.strptime(
                    re.match(r"([A-Za-z]+ \d+)", event["date"])[1]
                    + ", "
                    + event["date"][-4:],
                    "%B %d, %Y",
                )
                .date()
                .isoformat(),
                "data_name": metadata.get("name")
                or f"{event['type'].title()} Championship {event['city']}",
                "data_organizer": "Play! Pokémon",
                "data_format": "STANDARD",
                "data_players": str(metadata["players"]),
                "data_winner": winner,
                "source": "limitless_labs",
                "event_type": "in_person",
                "division": "MA",
                "completed": True,
                "source_updated_at": metadata["updated_at"],
            }
        )
        rows[TOURNAMENT_PARTICIPANTS_TABLE].extend(
            participant_row(p, url) for p in players
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            pairings = executor.map(
                lambda number: api(
                    "pairings", tournamentId=event_id, division="MA", round=number
                ),
                range(1, metadata["round"] + 1),
            )
            for number, pairs in enumerate(pairings, start=1):
                rows[PARTICIPANT_MATCHES_TABLE].extend(
                    match_rows(pairs, number, url, names_by_id)
                )

            def fetch_deck(player):
                cards = api(
                    "decklist", tournamentId=event_id, playerId=f"{player['tp_id']:04d}"
                )
                return deck_row(player, cards, event_id, url)

            available = [p for p in players if p.get("decklist")]
            for count, deck in enumerate(executor.map(fetch_deck, available), start=1):
                rows[PARTICIPANT_DECK_TABLE].append(deck)
                if count % 250 == 0:
                    print(f"{event_id}: {count}/{len(available)} decks", flush=True)
        print(f"{event_id}: {len(players)} players, {len(available)} decks", flush=True)
    return rows


def load_rows(rows):
    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=PIPELINE_DESTINATION,
        dataset_name=PIPELINE_DATASET_NAME,
    )
    for table, key in TABLE_KEYS.items():
        if rows[table]:
            print(
                pipeline.run(
                    rows[table],
                    table_name=table,
                    write_disposition="merge",
                    primary_key=key,
                    loader_file_format="jsonl",
                )
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Save fetched rows as gzip JSON for reproducible reloads.",
    )
    parser.add_argument(
        "--from-snapshot",
        type=Path,
        help="Load a saved snapshot without network requests.",
    )
    args = parser.parse_args()
    if args.latest < 1 or args.workers < 1:
        parser.error("--latest and --workers must be positive")
    if args.from_snapshot:
        with gzip.open(args.from_snapshot, "rt", encoding="utf-8") as handle:
            rows = json.load(handle)
    else:
        rows = extract_events(args.latest, args.workers)
    if args.snapshot:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(args.snapshot, "wt", encoding="utf-8") as handle:
            json.dump(rows, handle, ensure_ascii=False)
    load_rows(rows)


if __name__ == "__main__":
    main()
