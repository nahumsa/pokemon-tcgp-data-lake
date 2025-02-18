from typing import Optional
import requests
from selectolax.parser import HTMLParser

BASE_URL = "https://play.limitlesstcg.com"


def extract_tournaments(response: requests.Response) -> list[dict]:
    tournament_list = []

    tree = HTMLParser(response.text)

    table_tournament_tree = tree.css_first("body > div.main > div > table")
    for tournaments in table_tournament_tree.css("tr")[1:]:
        tournament_page: Optional[str] = None
        tournament_metadata = tournaments.attributes

        if page := tournaments.css_first("a").attributes.get("href"):
            tournament_page = BASE_URL + page

        tournament_list.append(
            dict(**tournament_metadata, tournament_page=tournament_page)
        )
    return tournament_list


has_data = True
all_tournaments = []
page = 1
params = {
    "game": "POCKET",
    "format": "STANDARD",
    "platform": "all",
    "type": "online",
    "time": "4weeks",
    "show": 100,
}

while has_data:
    params["page"] = page

    response = requests.get(
        BASE_URL + "/tournaments/completed", params=params
    )

    tournaments_list = extract_tournaments(response)
    all_tournaments.extend(tournaments_list)

    if len(tournaments_list) < params["show"]:
        has_no_data = False
        break

    page += 1

print(len(all_tournaments))
link = all_tournaments[1]["tournament_page"]




response = requests.get(link)
tree = HTMLParser(response.text)
header_element = tree.css_first("body > div.main > div > div.standings.completed > table > tbody > tr:nth-child(1)")
headers = [i.text() for i in header_element.css("th")]
expected_headers = ["Place", "Name", "", "Points", "Record", "Opp. Win %", "Opp. Opp. %", "Deck", "List"]
assert expected_headers == headers, "headers are not what is expected"

element_list = tree.css("body > div.main > div > div.standings.completed > table > tbody > tr:nth-child(n)")[1:]

for element in element_list:
    participant = dict(zip(headers,[i for i in element.css("td")]))
