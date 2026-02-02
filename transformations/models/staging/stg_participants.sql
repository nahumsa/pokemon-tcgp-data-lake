with source as (
    select * from {{ source('pokemon_tcg', 'participant_deck') }}
),

renamed as (
    select
        {{ dbt_utils.generate_surrogate_key(['player', 'tournament']) }} as participant_id,
        {{ dbt_utils.generate_surrogate_key(['tournament']) }} as tournament_id,
        player as player_name,
        tournament as tournament_url,
        decklist_link,
        _dlt_id as source_id,
        _dlt_load_id
    from source
)

select * exclude (_dlt_load_id)
from renamed
qualify row_number() over (partition by participant_id order by _dlt_load_id desc) = 1
