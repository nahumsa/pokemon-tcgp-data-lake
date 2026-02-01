with source as (
    select * from {{ source('pokemon_tcg', 'participant_matches') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key(['tournament', 'p1', 'round']) }} as match_id,
        {{ dbt_utils.generate_surrogate_key(['tournament']) }} as tournament_id,
        {{ dbt_utils.generate_surrogate_key(['p1', 'tournament']) }} as participant_id,
        {{ dbt_utils.generate_surrogate_key(['p2', 'tournament']) }} as opponent_id,
        tournament as tournament_url,
        round,
        p1 as player_name,
        p2 as opponent_name,
        result,
        _dlt_load_id
    from source
)

select * exclude (_dlt_load_id)
from renamed
qualify row_number() over (partition by match_id order by _dlt_load_id desc) = 1
