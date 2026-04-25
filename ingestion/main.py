import argparse
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import dlt

from .constants import (
    BASE_URL,
    DETAIL_FETCH_WORKERS,
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
from .extractors import (
    extract_matches,
    extract_participants,
    extract_tournaments,
    get_deck,
)
from .http_client import get
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

def iter_tournaments(
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
        print(
            f"Running in incremental mode for month: {target_dt.strftime('%Y-%m')}",
            flush=True,
        )
    else:
        print("Running in backfill mode.", flush=True)

    has_data = True
    page = tournament_params.page
    while has_data:
        params = tournament_params.model_dump()
        params["page"] = page

        print(f"Scraping page {page}...", flush=True)

        response = get(BASE_URL + "/tournaments/completed", params=params)

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
                if target_dt is None:
                    raise ValueError("invalid value for target date")

                elif t_date.year == target_dt.year and t_date.month == target_dt.month:
                    batch_to_yield.append(t)

                elif t_date < target_dt:
                    stop_extraction = True
                else:
                    continue

        if batch_to_yield:
            print(
                f"Yielding batch of {len(batch_to_yield)} tournaments from page {page}",
                flush=True,
            )
            yield batch_to_yield

        if stop_extraction and not backfill:
            print("Reached past data relative to target month. Stopping.", flush=True)
            has_data = False
            break

        if len(tournaments_list) < tournament_params.show:
            has_data = False
            print("End scraping tournaments (last page reached).", flush=True)
            break

        page += 1


@dlt.resource(
    table_name=TOURNAMENTS_TABLE,
    write_disposition="merge",
    primary_key=TOURNAMENTS_PRIMARY_KEY,
)
def tournaments(
    tournament_params: TournamentPayload,
    target_month: Optional[str] = None,
    backfill: bool = False,
):
    yield from iter_tournaments(tournament_params, target_month, backfill)


@dlt.transformer(
    data_from=tournaments,
    table_name=TOURNAMENT_PARTICIPANTS_TABLE,
    write_disposition="merge",
    primary_key=TOURNAMENT_PARTICIPANTS_PRIMARY_KEY,
)
def participants(tournaments: dlt.sources.DltResource):
    for t in tournaments:
        try:
            yield extract_participants(t.tournament_page)

        except Exception as exc:
            print(
                f"Tournament {t.tournament_page!r} generated an exception during participant extraction: {exc}"
            )


@dlt.transformer(
    data_from=participants,
    table_name=PARTICIPANT_DECK_TABLE,
    write_disposition="merge",
    primary_key=PARTICIPANT_DECK_PRIMARY_KEY,
)
def decks(participants: dlt.sources.DltResource):
    for p in participants:
        try:
            deck = get_deck(p)
            if deck:
                yield deck.model_dump()

        except Exception as exc:
            print(
                f"Participant {p.name!r} generated an exception during decklist extraction: {exc}"
            )


@dlt.transformer(
    data_from=participants,
    table_name=PARTICIPANT_MATCHES_TABLE,
    write_disposition="merge",
    primary_key=PARTICIPANT_MATCHES_PRIMARY_KEY,
)
def matches(participants: dlt.sources.DltResource):
    for p in participants:
        try:
            yield [match.model_dump(by_alias=True) for match in extract_matches(p)]

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

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=PIPELINE_DESTINATION,
        dataset_name=PIPELINE_DATASET_NAME,
    )

    payload = TournamentPayload(
        game=GameEnum.TCG,
        format=FormatEnum.STANDARD,
        platform=PlatformEnum.ALL,
        type=TypeEnum.ONLINE,
        time=time_param,
    )
    tournament_rows = [
        tournament
        for batch in iter_tournaments(
            payload, target_month=args.month, backfill=args.backfill
        )
        for tournament in batch
    ]
    print(f"Loaded {len(tournament_rows)} tournaments from scraper.", flush=True)

    participant_rows = []
    for tournament in tournament_rows:
        try:
            participant_rows.extend(extract_participants(tournament.tournament_page))
        except Exception as exc:
            print(
                f"Tournament {tournament.tournament_page!r} generated an exception during participant extraction: {exc}"
            )
    print(f"Loaded {len(participant_rows)} participants from scraper.", flush=True)

    def fetch_participant_details(participant):
        deck_row = None
        participant_matches = []
        errors = []

        try:
            deck = get_deck(participant)
            if deck:
                deck_row = deck.model_dump()
        except Exception as exc:
            errors.append(
                f"Participant {participant.name!r} generated an exception during decklist extraction: {exc}"
            )

        try:
            participant_matches = [
                match.model_dump(by_alias=True)
                for match in extract_matches(participant)
            ]
        except Exception as exc:
            errors.append(
                f"Participant {participant.name!r} generated an exception during matches extraction: {exc}"
            )

        return deck_row, participant_matches, errors

    deck_rows = []
    match_rows = []
    with ThreadPoolExecutor(max_workers=DETAIL_FETCH_WORKERS) as executor:
        futures = [
            executor.submit(fetch_participant_details, participant)
            for participant in participant_rows
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            deck_row, participant_matches, errors = future.result()
            if deck_row:
                deck_rows.append(deck_row)
            match_rows.extend(participant_matches)
            for error in errors:
                print(error, flush=True)
            if completed % 500 == 0 or completed == len(futures):
                print(
                    f"Fetched details for {completed}/{len(futures)} participants.",
                    flush=True,
                )
    print(
        f"Loaded {len(deck_rows)} decks and {len(match_rows)} matches from scraper.",
        flush=True,
    )

    if tournament_rows:
        load_info = pipeline.run(
            [tournament.model_dump() for tournament in tournament_rows],
            table_name=TOURNAMENTS_TABLE,
            write_disposition="merge",
            primary_key=TOURNAMENTS_PRIMARY_KEY,
            loader_file_format="jsonl",
        )
        print(load_info)

    if participant_rows:
        load_info = pipeline.run(
            [participant.model_dump() for participant in participant_rows],
            table_name=TOURNAMENT_PARTICIPANTS_TABLE,
            write_disposition="merge",
            primary_key=TOURNAMENT_PARTICIPANTS_PRIMARY_KEY,
            loader_file_format="jsonl",
        )
        print(load_info)

    if deck_rows:
        load_info = pipeline.run(
            deck_rows,
            table_name=PARTICIPANT_DECK_TABLE,
            write_disposition="merge",
            primary_key=PARTICIPANT_DECK_PRIMARY_KEY,
            loader_file_format="jsonl",
        )
        print(load_info)

    if match_rows:
        load_info = pipeline.run(
            match_rows,
            table_name=PARTICIPANT_MATCHES_TABLE,
            write_disposition="merge",
            primary_key=PARTICIPANT_MATCHES_PRIMARY_KEY,
            loader_file_format="jsonl",
        )
        print(load_info)
