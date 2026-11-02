# Transformations

- Staging views deduplicate raw source identities using load metadata. Semantic
  models own business logic; consumption models aggregate at documented grains.
  Keep semantic and consumption models materialized as tables.
- Schemas are `main_staging`, `main_semantic`, and `main_consumption`;
  `pokemon_tcg_data` contains raw imported tables. Do not use `consumption` alone.
- Preserve existing identity contracts. Use `dbt_utils.generate_surrogate_key` for
  ordinary keys; canonical pairing keys have their own documented contract.
- Add SQL model logic tests under `models/` as native `unit_tests` YAML. Mock every
  parent `ref`/`source`, compare expected rows, and keep models independent.
  SQL fixtures with explicit types allow `make test-sql` to run in memory.
- Run `make test-sql` and lint changed SQL from the repository root. CI's
  `make check` also parses dbt and runs Python checks. Dataset-dependent checks
  (`make dbt-test`) require a built database and do not replace logic tests.
- Follow the metric/match contracts linked in root `AGENTS.md`; update applicable
  contracts and semantic descriptions when changing grains, formulas, or units.
