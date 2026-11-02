"""Validate production definitions together against a disposable synthetic warehouse."""

import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys

import duckdb
import ibis
import pytest
import yaml
from boring_semantic_layer import from_config

ROOT = Path(__file__).resolve().parents[1]


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject YAML keys that safe_load would silently overwrite."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(
                f"Duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}"
            )
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


@pytest.mark.parametrize(
    "path",
    sorted(
        p.relative_to(ROOT)
        for folder in ("transformations", "semantic_layer")
        for p in (ROOT / folder).rglob("*.yml")
        if not {"dbt_packages", "target", "logs"}.intersection(p.parts)
    ),
)
def test_yaml_has_no_overwritten_definitions(path):
    yaml.load((ROOT / path).read_text(), Loader=UniqueKeyLoader)


def test_duplicate_key_guard():
    with pytest.raises(ValueError, match="Duplicate YAML key"):
        yaml.load("model:\n  table: first\n  table: second\n", Loader=UniqueKeyLoader)


CONFIG = yaml.load(
    (ROOT / "semantic_layer/semantic_layer/boring.yml").read_text(),
    Loader=UniqueKeyLoader,
)


def test_server_registers_exact_semantic_tables():
    # Read the AST; importing the server opens the user's pipeline database.
    tree = ast.parse((ROOT / "semantic_layer/semantic_layer/mcp_server.py").read_text())
    tables = next(
        n.value
        for n in tree.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "tables"
    )
    registered = {}
    for key, call in zip(tables.keys, tables.values):
        assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        assert call.func.attr == "table"
        schema = next(k.value.value for k in call.keywords if k.arg == "database")
        registered[key.value] = (schema, call.args[0].value)
    expected = {c["table"]: (c["database"], c["table"]) for c in CONFIG.values()}
    assert registered == expected


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory):
    """Build every real dbt model without touching saved databases or the network."""
    work = tmp_path_factory.mktemp("definitions")
    project = work / "transformations"
    shutil.copytree(
        ROOT / "transformations",
        project,
        ignore=shutil.ignore_patterns("target", "logs", "*.duckdb*"),
    )
    database = work / "validation.duckdb"
    with duckdb.connect(str(database)) as con:
        con.execute("create schema pokemon_tcg_data; set schema=pokemon_tcg_data")
        con.execute("""
            create table tournaments as select *, '1' as _dlt_load_id,
                'Standard' as data_format, 'Organizer' as data_organizer,
                'Alice' as data_winner, 3 as data_players
            from (values
                ('https://play.limitlesstcg.com/tournament/test', 'Play', '2026-01-15'),
                ('https://labs.limitlesstcg.com/test', 'Labs', '2026-02-15')
            ) t(tournament_page, data_name, data_date);
            create table tournament_participants as
                select tournament_page as tournament_link, name, cast(null as varchar) as deck,
                    '1' as _dlt_load_id
                from tournaments cross join (values ('Alice'), ('Bob'), ('No list')) p(name);
            create table participant_deck as
                select tournament_page || player as _dlt_id, tournament_page as tournament,
                    player, 'deck' as decklist_link, '1' as _dlt_load_id
                from tournaments cross join (values ('Alice'), ('Bob')) p(player);
            create table participant_deck__decklist as
                select _dlt_id as _dlt_parent_id, 'Dragapult ex' as name,
                    'TWM-130' as code, 4 as quantity, 'pokemon' as kind
                from participant_deck;
            create table participant_matches as
                select tournament_page as tournament, p1, p2, round, result,
                    '1' as _dlt_load_id
                from tournaments cross join (values
                    ('Alice', 'Bob', '1', 'WIN'), ('Bob', 'Alice', '1', 'LOSS'),
                    ('No list', 'BYE', '1', 'BYE')
                ) m(p1, p2, round, result);
        """)
    (project / "profiles.yml").write_text(
        yaml.safe_dump(
            {
                "pokemon_tcg_transform": {
                    "target": "validation",
                    "outputs": {
                        "validation": {
                            "type": "duckdb",
                            "path": str(database),
                            "threads": 1,
                        }
                    },
                }
            }
        )
    )
    env = {**os.environ, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    dbt = str(Path(sys.executable).with_name("dbt"))
    for command in ("seed", "run", "test"):
        args = [dbt, command, "--profiles-dir", str(project)]
        if command == "test":
            args += ["--select", "test_type:data"]
        result = subprocess.run(
            args,
            cwd=project,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
        )
        assert result.returncode == 0, result.stdout
    return database


@pytest.mark.parametrize("name", sorted(CONFIG))
def test_every_semantic_field_executes_on_dbt_output(warehouse, name):
    config = CONFIG[name]
    con = ibis.duckdb.connect(str(warehouse))
    try:
        table = con.table(config["table"], database=config["database"])
        model = from_config({name: config}, tables={config["table"]: table})[name]
        # Query separately: grouped fields and table-level reductions have different grains.
        for dimension in config.get("dimensions", {}):
            model.query(dimensions=[dimension]).execute()
        for measure in config.get("measures", {}):
            model.query(measures=[measure]).execute()
    finally:
        con.disconnect()


def test_documented_columns_exist_in_built_models(warehouse):
    errors = []
    with duckdb.connect(str(warehouse), read_only=True) as con:
        for path in (ROOT / "transformations/models").rglob("*.yml"):
            for model in yaml.safe_load(path.read_text()).get("models", []):
                columns = {
                    r[0]
                    for r in con.execute(
                        "select column_name from information_schema.columns where table_name = ?",
                        [model["name"]],
                    ).fetchall()
                }
                for column in model.get("columns", []):
                    if column["name"] not in columns:
                        errors.append(f"{model['name']}.{column['name']}")
    assert not errors, "Documented columns absent from dbt output: " + ", ".join(errors)
