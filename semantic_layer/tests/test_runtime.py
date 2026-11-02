"""Exercise read-only loading and readiness failures using tiny local fixtures."""

import importlib
import json

import duckdb
import pytest
import yaml

from semantic_layer.runtime import ReadinessError, open_models


@pytest.fixture
def registry(tmp_path):
    config = {
        "example": {
            "table": "stats",
            "database": "main_consumption",
            "dimensions": {"deck": {"expr": "_.deck"}},
            "measures": {
                "win_rate": {
                    "expr": '_["wins"].sum() * 100.0 / _["matches"].sum().nullif(0)'
                }
            },
        }
    }
    path = tmp_path / "models.yml"
    path.write_text(yaml.safe_dump(config))
    database = tmp_path / "data.duckdb"
    return path, database


def test_missing_database_reports_recovery_without_creating_a_file(registry):
    config, database = registry
    with pytest.raises(ReadinessError, match="make dbt-build"):
        with open_models(database, config):
            pytest.fail("An absent database must not load")
    assert not database.exists()


def test_missing_tables_are_named_and_connection_is_closed(registry):
    config, database = registry
    duckdb.connect(str(database)).close()
    with pytest.raises(ReadinessError, match=r"main_consumption.stats"):
        with open_models(database, config):
            pytest.fail("Missing relations must not pass readiness")
    # A writer can reopen it after a failed preflight (no leaked read-only handle).
    con = duckdb.connect(str(database))
    con.execute("create table marker (id integer)")
    con.close()


def test_registry_definitions_load_and_cannot_write_to_database(registry):
    config, database = registry
    con = duckdb.connect(str(database))
    con.execute("create schema main_consumption")
    con.execute(
        "create table main_consumption.stats as select 'Deck' as deck, 1 as wins, 2 as matches"
    )
    con.close()
    with open_models(database, config) as (path, models):
        assert path == database
        assert list(models) == ["example"]
        assert (
            models["example"].query(measures=["win_rate"]).execute().iloc[0]["win_rate"]
            == 50
        )
        backend = models["example"].table.get_backend()
        with pytest.raises(duckdb.InvalidInputException, match="read-only"):
            backend.raw_sql("create table accidental_write (id integer)")
    con = duckdb.connect(str(database))
    assert (
        con.execute(
            "select count(*) from information_schema.tables where table_name='accidental_write'"
        ).fetchone()[0]
        == 0
    )
    con.close()


def test_existing_table_with_missing_columns_fails_preflight(registry):
    config, database = registry
    con = duckdb.connect(str(database))
    con.execute(
        "create schema main_consumption; create table main_consumption.stats (deck varchar)"
    )
    con.close()
    with pytest.raises(ReadinessError, match="Semantic definitions could not load"):
        with open_models(database, config):
            pytest.fail("Missing expression inputs must fail readiness")


def test_server_import_does_not_connect_and_cli_failure_is_actionable(
    tmp_path, monkeypatch, capsys
):
    missing = tmp_path / "absent.duckdb"
    monkeypatch.setenv("POKEMON_TCG_DB_PATH", str(missing))
    server = importlib.import_module("semantic_layer.mcp_server")
    importlib.reload(server)
    assert not missing.exists()
    assert server.main(["--check"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "make dbt-build" in captured.err
    assert str(missing) in captured.err
    assert not missing.exists()


def test_preflight_success_reports_models_without_starting_server(
    registry, monkeypatch, capsys
):
    from contextlib import contextmanager
    from semantic_layer import mcp_server

    config, database = registry

    @contextmanager
    def ready():
        yield database, {"example": object()}

    monkeypatch.setattr(mcp_server, "open_models", ready)
    monkeypatch.setattr(
        mcp_server,
        "MCPSemanticModel",
        lambda **kwargs: pytest.fail("--check must not start MCP"),
    )
    assert mcp_server.main(["--check"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "database": str(database),
        "read_only": True,
        "models": ["example"],
    }
