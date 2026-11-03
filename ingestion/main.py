import argparse
import warnings
from concurrent.futures import ThreadPoolExecutor
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
from .coverage import AUDIT_TABLE, build_audit
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
        for tournament in tournaments_list:
            tournament.event_type = tournament_params.type.value
            tournament.completed = True

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


def collect_rows(tournament_rows, workers=DETAIL_FETCH_WORKERS):
    from .labs import TABLE_KEYS

    rows = {table: [] for table in TABLE_KEYS}
    rows[AUDIT_TABLE] = []
    for tournament in tournament_rows:
        event = tournament.model_dump()
        rows[TOURNAMENTS_TABLE].append(event)
        errors = []
        try:
            entrants = extract_participants(tournament.tournament_page)
        except Exception as exc:
            print(
                f"Participant extraction failed for {tournament.tournament_page}: {exc}",
                flush=True,
            )
            rows[AUDIT_TABLE].append(build_audit(event, errors=["participants"]))
            continue
        participants = [p.model_dump() for p in entrants]
        decks, matches = [], []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for deck, history, failures in executor.map(
                fetch_participant_details, entrants
            ):
                if deck:
                    decks.append(deck)
                matches.extend(history)
                errors.extend(failures)
        rows[TOURNAMENT_PARTICIPANTS_TABLE].extend(participants)
        rows[PARTICIPANT_DECK_TABLE].extend(decks)
        rows[PARTICIPANT_MATCHES_TABLE].extend(matches)
        rows[AUDIT_TABLE].append(
            build_audit(
                event,
                participants=participants,
                decks=decks,
                matches=matches,
                errors=errors,
            )
        )
    return rows


def fetch_participant_details(participant):
    deck_row, history, errors = None, [], []
    try:
        deck = get_deck(participant)
        if deck:
            deck_row = deck.model_dump()
    except Exception as exc:
        print(f"Deck extraction failed for {participant.name}: {exc}", flush=True)
        errors.append("decks")
    try:
        history = [
            match.model_dump(by_alias=True) for match in extract_matches(participant)
        ]
    except Exception as exc:
        print(f"History extraction failed for {participant.name}: {exc}", flush=True)
        errors.append("matches")
    return deck_row, history, errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Pokemon TCG data.")
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

    from .labs import load_rows

    payload = TournamentPayload(
        game=GameEnum.TCG,
        format=FormatEnum.STANDARD,
        platform=PlatformEnum.ALL,
        type=TypeEnum.ONLINE,
        time=TimeEnum.ALL,
    )
    tournament_rows = [
        tournament
        for batch in iter_tournaments(
            payload, target_month=args.month, backfill=args.backfill
        )
        for tournament in batch
    ]
    rows = collect_rows(tournament_rows)
    load_rows(rows)
    if any(audit["extraction_status"] != "success" for audit in rows[AUDIT_TABLE]):
        raise SystemExit("Some events failed extraction; inspect ingestion_event_runs")
