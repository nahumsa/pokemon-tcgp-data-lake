from typing import Optional
import requests
from selectolax.parser import HTMLParser

from payload import FormatEnum, GameEnum, PlatformEnum, TimeEnum, TournamentPayload, TypeEnum
from constants import BASE_URL
from models import Participant, Tournament


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

def get_tournaments(tournament_params: TournamentPayload) -> list[Tournament]:
    has_data = True
    all_tournaments = []
    while has_data:
        response = requests.get(
            BASE_URL + "/tournaments/completed", params=tournament_params
        )

        tournaments_list = extract_tournaments(response)
        all_tournaments.extend(tournaments_list)

        if len(tournaments_list) < tournament_params.show:
            has_data = False
            break

        tournament_params.increment_page()

    return all_tournaments

def extract_participants(link: Optional[str]) -> list[Participant]:
    if not link:
        raise ValueError("tournament link not provided")

    print(link)
    response = requests.get(link)
    tree = HTMLParser(response.text)
    header_element = tree.css_first("body > div.main > div > div.standings.completed > table > tbody > tr:nth-child(1)")
    headers = [i.text() for i in header_element.css("th")]

    element_list = tree.css("body > div.main > div > div.standings.completed > table > tbody > tr:nth-child(n)")[1:]

    participant_list = []
    for element in element_list:
        participant_list.append(Participant(tournament_link=link, **dict(zip(headers,[i for i in element.css("td")]))))

    return participant_list

if __name__ == "__main__":
    payload = TournamentPayload(
        game=GameEnum.POCKET,
        format=FormatEnum.STANDARD,
        platform=PlatformEnum.ALL,
        type=TypeEnum.ONLINE,
        time=TimeEnum.PAST_FOUR_WEEKS,
    )

    all_tournaments = get_tournaments(payload)
    for tournament in all_tournaments:
        participants = extract_participants(tournament.tournament_page)
