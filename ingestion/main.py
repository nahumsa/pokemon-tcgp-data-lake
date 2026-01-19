import re
import requests
import concurrent.futures
from typing import Optional
import dlt
from tqdm import tqdm
from selectolax.parser import HTMLParser

from payload import (
    FormatEnum,
    GameEnum,
    PlatformEnum,
    TimeEnum,
    TournamentPayload,
    TypeEnum,
)
from constants import BASE_URL, REGEX_CARD_PATTERN
from models import Deck, Participant, Tournament, Card


@dlt.resource(write_disposition="append")
def get_tournaments(tournament_params: TournamentPayload):
    has_data = True
    while has_data:
        response = requests.get(
            BASE_URL + "/tournaments/completed", params=tournament_params
        )

        tournaments_list = extract_tournaments(response)
        yield tournaments_list

        if len(tournaments_list) < tournament_params.show:
            has_data = False
            print("end scraping tournaments")
            break

        tournament_params.increment_page()


@dlt.resource(write_disposition="append")
def get_participants_dlt(tournaments: dlt.sources.DltResource):
    all_tournaments = list(tournaments)
    all_participants = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_tournament = {
            executor.submit(extract_participants, t.tournament_page): t
            for t in all_tournaments
        }
        progress = tqdm(
            concurrent.futures.as_completed(future_to_tournament),
            total=len(all_tournaments),
            desc="Extracting participants",
        )

        for future in progress:
            tournament = future_to_tournament[future]
            try:
                participants = future.result()
                all_participants.extend(participants)

            except Exception as exc:
                print(
                    f"{getattr(tournament, 'data_label', 'A tournament')!r} generated an exception during participant extraction: {exc}"
                )
    yield all_participants


@dlt.resource(write_disposition="append")
def get_decks_dlt(participants: dlt.sources.DltResource):
    all_participants = list(participants)
    all_decks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_participant = {
            executor.submit(get_deck, p): p for p in all_participants
        }
        progress = tqdm(
            concurrent.futures.as_completed(future_to_participant),
            total=len(all_participants),
            desc="Extracting decklists",
        )
        for future in progress:
            participant = future_to_participant[future]
            try:
                deck = future.result()
                all_decks.append(deck)

            except Exception as exc:
                print(
                    f"Participant {participant.name!r} generated an exception during decklist extraction: {exc}"
                )
    yield all_decks


def extract_tournaments(response: requests.Response) -> list[Tournament]:
    tournament_list = []

    tree = HTMLParser(response.text)

    table_tournament_tree = tree.css_first("body > div.main > div > table")
    for tournaments in table_tournament_tree.css("tr")[1:]:
        tournament_page: Optional[str] = None
        tournament_metadata = tournaments.attributes

        if page := tournaments.css_first("a").attributes.get("href"):
            tournament_page = BASE_URL + page

        tournament_list.append(
            Tournament(**dict(**tournament_metadata, tournament_page=tournament_page))
        )

    return tournament_list


def extract_participants(link: Optional[str]) -> list[Participant]:
    if not link:
        raise ValueError("tournament link not provided")

    response = requests.get(link)
    tree = HTMLParser(response.text)
    header_element = tree.css_first(
        "body > div.main > div > div.standings.completed > table > tbody > tr:nth-child(1)"
    )
    headers = [i.text() for i in header_element.css("th")]

    element_list = tree.css(
        "body > div.main > div > div.standings.completed > table > tbody > tr:nth-child(n)"
    )[1:]

    return [
        Participant(
            tournament_link=link, **dict(zip(headers, [i for i in element.css("td")]))
        )
        for element in element_list
    ]


def parse_card(text: str) -> Card:
    match = re.match(REGEX_CARD_PATTERN, text)

    if match:
        return Card(
            **{
                "quantity": int(match.group(1)),
                "name": match.group(2).strip(),
                "code": match.group(3) if match.group(3) else None,
            }
        )

    raise ValueError("invalid card string")


def extract_decklist(link: Optional[str]) -> list[Card]:
    if not link:
        raise ValueError("decklist link not provided")

    response = requests.get(link)
    tree = HTMLParser(response.text)
    card_container_list = tree.css(".cards")

    decklist = []
    for raw_card_node in card_container_list:
        decklist.extend([parse_card(node.text()) for node in raw_card_node.css("p")])

    return decklist


def get_deck(participant: Participant) -> Deck:
    """Fetches a decklist for a participant and constructs a Deck object."""
    decklist = extract_decklist(participant.decklist_link)
    return Deck(
        player=participant.name,
        tournament=participant.tournament_link,
        decklist=decklist,
        decklist_link=participant.decklist_link,
    )


if __name__ == "__main__":
    payload = TournamentPayload(
        game=GameEnum.TCG,
        format=FormatEnum.STANDARD,
        platform=PlatformEnum.ALL,
        type=TypeEnum.ONLINE,
        time=TimeEnum.PAST_SEVEN_DAYS,
    )

    pipeline = dlt.pipeline(
        pipeline_name="pokemon_tcgp_pipeline",
        destination="duckdb",
        dataset_name="pokemon_tcgp_data",
        full_refresh=False,
    )

    tournaments = get_tournaments(payload)
    participants = get_participants_dlt(tournaments)
    decks = get_decks_dlt(participants)

    load_info = pipeline.run(
        [tournaments, participants, decks],
        write_disposition="append",
        loader_file_format="jsonl",
    )
    print(load_info)
