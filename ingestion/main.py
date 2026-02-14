import argparse
import warnings
from datetime import datetime
from typing import Optional

import dlt
import requests

from .constants import BASE_URL, HEADERS
from .extractors import (
    extract_matches,
    extract_participants,
    extract_tournaments,
    get_deck,
)
from .payload import (
    FormatEnum,
    GameEnum,
    PlatformEnum,
    TimeEnum,
    TournamentPayload,
    TypeEnum,
)

# Suppress the pkg_resources deprecation warning from dlt
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")


@dlt.resource(
    table_name="tournaments", write_disposition="merge", primary_key="tournament_page"
)
def tournaments(
    tournament_params: TournamentPayload,
    target_month: Optional[str] = None,
    backfill: bool = False,
):
    """
    scrapes tournaments.
    If backfill is True, scrapes everything (respecting tournament_params limits if any).
    If backfill is False, scrapes only for the target_month (YYYY-MM).
    If target_month is not provided, defaults to current month.
    """
    target_dt = None
    if not backfill:
        if target_month:
            try:
                target_dt = datetime.strptime(target_month, "%Y-%m")
            except ValueError:
                print(f"Invalid target_month format: {target_month}. Expected YYYY-MM.")
                return
        else:
            now = datetime.now()
            target_dt = datetime(now.year, now.month, 1)
        print(f"Running in incremental mode for month: {target_dt.strftime('%Y-%m')}")
    else:
        print("Running in backfill mode.")

    has_data = True
    while has_data:
        params = tournament_params.model_dump()

        print(f"Scraping page {tournament_params.page}...")

        response = requests.get(
            BASE_URL + "/tournaments/completed", params=params, headers=HEADERS
        )

        tournaments_list = extract_tournaments(response)

        if not tournaments_list:
            print("No tournaments found on this page.")
            break

        batch_to_yield = []
        stop_extraction = False

        for t in tournaments_list:
            if backfill:
                batch_to_yield.append(t)
            else:
                if not t.date:
                    continue
                try:
                    # Date is in ISO format (e.g., 2026-02-01T02:00:00.000Z) or YYYY-MM-DD
                    date_str = t.date.split("T")[0]
                    t_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    print(f"Failed to parse date: {t.date}")
                    continue

                # We only want tournaments from the target month
                if t_date.year == target_dt.year and t_date.month == target_dt.month:
                    batch_to_yield.append(t)

                elif t_date < target_dt:
                    stop_extraction = True
                else:
                    continue

        if batch_to_yield:
            print(
                f"Yielding batch of {len(batch_to_yield)} tournaments from page {tournament_params.page}"
            )
            yield batch_to_yield

        if stop_extraction and not backfill:
            print("Reached past data relative to target month. Stopping.")
            has_data = False
            break

        if len(tournaments_list) < tournament_params.show:
            has_data = False
            print("End scraping tournaments (last page reached).")
            break

        tournament_params.increment_page()


@dlt.transformer(
    data_from=tournaments,
    table_name="tournament_participants",
    write_disposition="merge",
    primary_key=["tournament_link", "name"],
)
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
    data_from=participants,
    table_name="participant_deck",
    parallelized=True,
    write_disposition="merge",
    primary_key=["tournament", "player"],
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
    data_from=participants,
    table_name="participant_matches",
    parallelized=True,
    write_disposition="merge",
    primary_key=["tournament", "Round", "P1"],
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
    parser = argparse.ArgumentParser(description="Ingest Pokemon TCGP data.")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run in backfill mode (scrape all available history).",
    )
    parser.add_argument(
        "--month",
        type=str,
        help="Target month for incremental scrape in YYYY-MM-01 format. Defaults to current month.",
        default=None,
    )

    args = parser.parse_args()

    time_param = TimeEnum.ALL

    payload = TournamentPayload(
        game=GameEnum.TCG,
        format=FormatEnum.STANDARD,
        platform=PlatformEnum.ALL,
        type=TypeEnum.ONLINE,
        time=time_param,
    )

    pipeline = dlt.pipeline(
        pipeline_name="pokemon_tcgp_pipeline",
        destination="duckdb",
        dataset_name="pokemon_tcgp_data",
    )

    tournaments_rsc = tournaments(
        payload, target_month=args.month, backfill=args.backfill
    )
    participants_rsc = tournaments_rsc | participants()

    load_info = pipeline.run(
        [tournaments_rsc, participants_rsc | decks(), participants_rsc | matches()],
        # write_disposition and keys are defined in decorators now
        loader_file_format="jsonl",
    )
    print(load_info)
