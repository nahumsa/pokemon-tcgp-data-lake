#!/usr/bin/env python3
import ibis
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from boring_semantic_layer import from_yaml

# Setup same environment as server
base_dir: Path = Path(__file__).parent
yaml_path: Path = base_dir / "boring.yml"
con: Any = ibis.duckdb.connect(str(base_dir.parent / "pokemon_tcgp_pipeline.duckdb"))
tables: Dict[str, Any] = {
    "mart_archetype_stats": con.table(
        "mart_archetype_stats", database="main_consumption"
    ),
    "dim_cards": con.table("dim_cards", database="main_semantic"),
    "fct_matches": con.table("fct_matches", database="main_semantic"),
    "mart_archetype_card_staples": con.table(
        "mart_archetype_card_staples", database="main_consumption"
    ),
    "mart_archetype_matchups": con.table(
        "mart_archetype_matchups", database="main_consumption"
    ),
}

models: Dict[str, Any] = from_yaml(str(yaml_path), tables=tables)


def run_test(
    name: str,
    model_name: str,
    dimensions: Optional[List[str]] = None,
    measures: Optional[List[str]] = None,
    filters: Optional[Union[Callable, List[Callable]]] = None,
    order_by: Optional[List[Tuple[str, str]]] = None,
    limit: Optional[int] = None,
) -> None:
    print(f"\n--- Testing: {name} ---")
    model = models[model_name]
    try:
        current_filters: List[Callable] = []
        if filters:
            if isinstance(filters, list):
                current_filters = filters
            else:
                current_filters = [filters]
        res = model.query(
            dimensions=dimensions or [],
            measures=measures or [],
            filters=current_filters,
            order_by=order_by,
            limit=limit,
        )
        data = res.execute()
        print(data)
    except Exception as e:
        print(f"FAILED: {e}")


# 1. Win rate of Charizard decks
run_test(
    "Win rate of Charizard decks",
    "archetype_stats",
    dimensions=["archetype"],
    measures=["avg_win_rate"],
    filters=lambda t: t.archetype == "Charizard",
)

# 2. Staples for Dragapult archetype
run_test(
    "Staples for Dragapult archetype (top 10)",
    "card_staples",
    dimensions=["card_name"],
    measures=["avg_inclusion_rate"],
    filters=lambda t: t.archetype == "Dragapult",
    order_by=[("avg_inclusion_rate", "desc")],
    limit=10,
)

# 3. Performance against Gholdengo
run_test(
    "Performance against Gholdengo",
    "archetype_matchups",
    dimensions=["p1_archetype"],
    measures=["win_rate"],
    filters=lambda t: t.p2_archetype == "Gholdengo",
    order_by=[("win_rate", "desc")],
    limit=5,
)
