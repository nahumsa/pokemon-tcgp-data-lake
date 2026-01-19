import requests
import concurrent.futures
import dlt
from tqdm import tqdm

from .payload import (
    FormatEnum,
    GameEnum,
    PlatformEnum,
    TimeEnum,
    TournamentPayload,
    TypeEnum,
)
from .constants import BASE_URL
from .extractor import (
    extract_participants,
    extract_tournaments,
    get_deck,
)


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
    )

    tournaments = get_tournaments(payload)
    participants = get_participants_dlt(tournaments)
    decks = get_decks_dlt(participants)

    load_info = pipeline.run(
        [decks],
        write_disposition="append",
        loader_file_format="jsonl",
    )
    print(load_info)
