BASE_URL = "https://play.limitlesstcg.com"

REGEX_CARD_PATTERN = r"(\d+)\s+([\w\s'’áéíóúÁÉÍÓÚüÜ-]+)(?:\s*\(([\w-]+)\))?"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

DETAIL_FETCH_WORKERS = 8

REQUEST_TIMEOUT_SECONDS = 30
REQUEST_RETRY_ATTEMPTS = 5
REQUEST_RETRY_BACKOFF_FACTOR = 1
REQUEST_RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
REQUEST_RETRY_ALLOWED_METHODS = frozenset(["GET"])

PIPELINE_NAME = "pokemon_tcgp_pipeline"
PIPELINE_DESTINATION = "duckdb"
PIPELINE_DATASET_NAME = "pokemon_tcgp_data"

TOURNAMENTS_TABLE = "tournaments"
TOURNAMENT_PARTICIPANTS_TABLE = "tournament_participants"
PARTICIPANT_DECK_TABLE = "participant_deck"
PARTICIPANT_MATCHES_TABLE = "participant_matches"

TOURNAMENTS_PRIMARY_KEY = "tournament_page"
TOURNAMENT_PARTICIPANTS_PRIMARY_KEY = ["tournament_link", "name"]
PARTICIPANT_DECK_PRIMARY_KEY = ["tournament", "player"]
PARTICIPANT_MATCHES_PRIMARY_KEY = ["tournament", "Round", "P1"]
