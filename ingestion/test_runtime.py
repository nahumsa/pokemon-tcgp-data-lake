"""Runtime selection must not fall back to another task's database or home state."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from ingestion import runtime


def test_ingestion_uses_explicit_database_and_state_from_any_directory(
    tmp_path, monkeypatch
):
    database = tmp_path / "task" / "data.duckdb"
    state = tmp_path / "task" / "state"
    monkeypatch.setenv("POKEMON_TCG_DB_PATH", str(database))
    monkeypatch.setenv("POKEMON_TCG_DLT_STATE_DIR", str(state))
    monkeypatch.chdir(tmp_path)
    destination = Mock(return_value=object())
    monkeypatch.setattr(runtime.dlt.destinations, "duckdb", destination)
    options = runtime.pipeline_options()
    destination.assert_called_once_with(str(database))
    assert Path(options["pipelines_dir"]) == state
    assert state.is_dir()
    assert database.parent.is_dir()
    assert not database.exists()


@pytest.mark.parametrize(
    "variable", ["POKEMON_TCG_DB_PATH", "POKEMON_TCG_DLT_STATE_DIR"]
)
def test_relative_runtime_overrides_are_rejected(tmp_path, monkeypatch, variable):
    monkeypatch.setenv("POKEMON_TCG_DB_PATH", str(tmp_path / "data.duckdb"))
    monkeypatch.setenv("POKEMON_TCG_DLT_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv(variable, "relative/path")
    with pytest.raises(ValueError, match=f"{variable} must be an absolute path"):
        runtime.pipeline_options()
