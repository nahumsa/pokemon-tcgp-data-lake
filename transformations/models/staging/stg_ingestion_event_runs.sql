{% set audit_source = source('pokemon_tcg', 'ingestion_event_runs') %}
{% set audit_relation = none %}
{% if execute %}
    {% set audit_relation = adapter.get_relation(database=audit_source.database, schema=audit_source.schema, identifier=audit_source.identifier) %}
{% endif %}

{% if audit_relation %}
select * exclude (_dlt_id, _dlt_load_id)
from {{ audit_source }}
qualify row_number() over (
    partition by tournament_url, attempt_id order by _dlt_load_id desc
) = 1
{% else %}
-- Older databases/snapshots remain queryable but cannot claim observed freshness.
select
    null::varchar as tournament_url,
    null::varchar as attempt_id,
    null::boolean as source_completed,
    null::bigint as expected_participant_count,
    null::bigint as participant_count,
    null::bigint as decklist_count,
    null::bigint as history_participant_count,
    null::bigint as participant_error_count,
    null::bigint as decklist_error_count,
    null::bigint as history_error_count,
    null::bigint as extraction_error_count,
    null::varchar as source_updated_at,
    null::varchar as extraction_status,
    null::varchar as load_status,
    null::timestamptz as extracted_at,
    null::timestamptz as loaded_at
where false
{% endif %}
