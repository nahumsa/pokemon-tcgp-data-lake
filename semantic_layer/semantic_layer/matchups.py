"""Sample-filtered matchup queries without filtering away small event cohorts."""

import json


COHORT_DIMENSIONS = [
    "game",
    "format",
    "set_name",
    "source",
    "event_type",
    "p1_archetype",
    "p2_archetype",
]
MEASURES = [
    "sample_size",
    "wins",
    "losses",
    "ties",
    "win_rate",
    "win_rate_lower_95",
    "win_rate_upper_95",
]


def query_matchup_evidence(
    model, dimensions=None, filters=None, min_sample_size=10, limit=100
):
    """Pool compatible cohorts first, then apply the sample gate and output limit.

    Additional dimensions can narrow the event/date/variant grain. The required
    dimensions prevent pooling different games, formats, periods or matchups.
    Use matchup_results with the same cohort filters for record-level provenance.
    """
    if type(min_sample_size) is not int or min_sample_size < 1:
        raise ValueError("min_sample_size must be a positive integer")
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("limit must be an integer between 1 and 1000")

    def validate_filter(predicate):
        if not isinstance(predicate, dict):
            raise ValueError("filters must use dimension-only JSON predicates")
        if "field" in predicate and predicate["field"] not in model.dimensions:
            raise ValueError(
                "filters must reference dimensions; use min_sample_size for sample counts"
            )
        for child in predicate.get("conditions", []):
            validate_filter(child)

    for predicate in filters or []:
        validate_filter(predicate)
    dimensions = list(dict.fromkeys(COHORT_DIMENSIONS + (dimensions or [])))
    frame = model.query(
        dimensions=dimensions, measures=MEASURES, filters=filters
    ).execute()
    frame = frame.loc[frame.sample_size >= min_sample_size]
    frame = frame.sort_values(
        ["sample_size", *dimensions], ascending=[False, *([True] * len(dimensions))]
    )
    return {
        "min_sample_size": min_sample_size,
        "qualifying_groups": len(frame),
        "rows": json.loads(
            frame.head(limit).to_json(orient="records", date_format="iso")
        ),
        "interval_method": "95% Wilson binomial, wins vs losses+draws; not cluster-adjusted or a forecast",
    }


def register_matchup_tools(server, models):
    @server.tool()
    def query_matchup_evidence_with_minimum_sample(
        dimensions: list[str] | None = None,
        filters: list[dict] | None = None,
        min_sample_size: int = 10,
        limit: int = 100,
    ) -> dict:
        """Observed non-mirror matchups with a minimum POOLED result count.

        Always separates game/format/period/provider/setting/archetypes. Add event,
        date or variant dimensions/filters to narrow cohorts. Returns pooled W/L/D,
        sample size and nominal Wilson bounds. Repeated pilots and incomplete
        histories violate binomial independence; these are not predictions.
        Use matchup_results with identical cohort filters for source records.
        """
        return query_matchup_evidence(
            models["matchup_evidence"], dimensions, filters, min_sample_size, limit
        )
