# Ingestion

- `main.py` imports Limitless Play; `labs.py` imports completed Masters TCG Labs
  events. Use their existing CLI entry points and `http_client.get` retry policy.
- Preserve source identifiers, original names, event metadata, and explicit missing
  data. A missing decklist must not remove a participant or invent a result.
- Both entry points use `runtime.pipeline_options()` for database and dlt state
  paths. Keep these independent of the caller's working directory.
- Validate Python logic with mocked requests and temporary paths using
  `make test-python`. Do not fetch live tournaments in unit tests.
- A snapshot is a reproducible input, not proof of a completed load. Inspect loader
  status; preserve failed state and report the error before attempting recovery.
- See root `AGENTS.md` for commands, task isolation, and handoff requirements.
