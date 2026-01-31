import warnings

# Suppress the pkg_resources deprecation warning from dlt
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

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
from .constants import BASE_URL, HEADERS
from .extractors import (
    extract_matches,
    extract_participants,
    extract_tournaments,
    get_deck,
)


@dlt.resource(table_name="tournaments", write_disposition="append")
def tournaments(tournament_params: TournamentPayload):
    has_data = True
    while has_data:
        response = requests.get(
            BASE_URL + "/tournaments/completed", params=tournament_params, headers=HEADERS
        )

        tournaments_list = extract_tournaments(response)
        yield tournaments_list

        if len(tournaments_list) < tournament_params.show:
            has_data = False
            print("end scraping tournaments")
            break

        tournament_params.increment_page()


@dlt.transformer(data_from=tournaments, table_name="tournament_participants")
def participants(tournaments: dlt.sources.DltResource):
    @dlt.defer
    def _get_participants(_tournaments_url):
        return extract_participants(_tournaments_url)

    for t in tournaments:
        try:
            yield _get_participants(t.tournament_page)

        except Exception as exc:
            print(
                f"Tournament {t.tournament_page!r} generated an exception during participant extraction: {exc}"
            )


@dlt.transformer(
    data_from=participants, table_name="participant_deck", parallelized=True
)
def decks(participants: dlt.sources.DltResource):

    @dlt.defer
    def _get_decks(_participant):
        return get_deck(_participant)

    for p in participants:
        try:
            yield _get_decks(p)

        except Exception as exc:
            print(
                f"Participant {p.name!r} generated an exception during decklist extraction: {exc}"
            )


@dlt.transformer(
    data_from=participants, table_name="participant_matches", parallelized=True
)
def matches(participants: dlt.sources.DltResource):
    @dlt.defer
    def _get_matches(_participant):
        return extract_matches(_participant)

    for p in participants:
        try:
            yield _get_matches(p)

        except Exception as exc:
            print(
                f"Participant {p.name!r} generated an exception during matches extraction: {exc}"
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
    )

    tournaments_rsc = tournaments(payload)
    participants_rsc = tournaments_rsc | participants()

    load_info = pipeline.run(
        [participants_rsc | decks(), participants_rsc | matches()],
        write_disposition="append",
        loader_file_format="jsonl",
    )
    print(load_info)
