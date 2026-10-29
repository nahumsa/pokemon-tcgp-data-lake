{% set relation = source('pokemon_tcg', 'tournaments') %}
{% if execute %}
    {% set raw_columns = adapter.get_columns_in_relation(relation) | map(attribute='name') | list %}
{% else %}
    {% set raw_columns = [] %}
{% endif %}

with source as (
    select * from {{ source('pokemon_tcg', 'tournaments') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key(['tournament_page']) }} as tournament_id,
        tournament_page as tournament_url,
        data_date::date as tournament_date,
        data_name as tournament_name,
        data_organizer as organizer,
        data_format as format,
        data_players::int as player_count,
        data_winner as winner_name,
        _dlt_load_id,
        {{ tournament_source('tournament_page', 'source' if 'source' in raw_columns else 'null') }} as source,
        {{ tournament_event_type('tournament_page', 'event_type' if 'event_type' in raw_columns else 'null') }}
            as event_type
    from source
)

select * exclude (_dlt_load_id)
from renamed
qualify row_number() over (partition by tournament_id order by _dlt_load_id desc) = 1
