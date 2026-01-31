import re
import requests
from typing import Optional
from selectolax.parser import HTMLParser

from .constants import BASE_URL, REGEX_CARD_PATTERN, HEADERS
from .models import Deck, Participant, Tournament, Card, Match


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

    response = requests.get(link, headers=HEADERS)
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

    response = requests.get(link, headers=HEADERS)
    tree = HTMLParser(response.text)
    card_container_list = tree.css(".cards")

    decklist = []
    for raw_card_node in card_container_list:
        decklist.extend([parse_card(node.text()) for node in raw_card_node.css("p")])

    return decklist


def get_deck(participant: Participant) -> Optional[Deck]:
    """Fetches a decklist for a participant and constructs a Deck object."""
    if not participant.decklist_link:
        return None

    decklist = extract_decklist(participant.decklist_link)
    return Deck(
        player=participant.name,
        tournament=participant.tournament_link,
        decklist=decklist,
        decklist_link=participant.decklist_link,
    )


def extract_matches(participant: Participant) -> list[Match]:
    if not participant.matches:
        return []

    response = requests.get(participant.matches, headers=HEADERS)
    tree = HTMLParser(response.text)

    # Use the 'history' class to find the table as seen in the HTML snippet
    table = tree.css_first("div.history table")
    if not table:
        return []

    rows = table.css("tr")
    # Skip header row
    data_rows = rows[1:]

    matches = []
    for row in data_rows:
        cols = row.css("td")
        if len(cols) < 5:
            continue

        # Column mapping based on HTML:
        # 0: Round
        # 1: Result (WIN/LOSS/TIE)
        # 2: Opponent (P2)
        # 3: Opponent Deck (ignored)
        # 4: Opponent Score (ignored)

        matches.append(
            Match(
                tournament=participant.tournament_link,
                Round=cols[0],
                Result=cols[1],
                P2=cols[2],
                P1=participant.name,
            )
        )

    return matches
