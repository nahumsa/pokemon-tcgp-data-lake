with source as (
    select * from {{ source('pokemon_tcg', 'participant_deck') }}
),

standings as (
    select
        tournament_link,
        name,
        _dlt_load_id
    from {{ source('pokemon_tcg', 'tournament_participants') }}
    qualify row_number() over (
        partition by tournament_link, name order by _dlt_load_id desc
    ) = 1
),

decks as (
    select * from source
    qualify row_number() over (
        partition by player, tournament order by _dlt_load_id desc
    ) = 1
),

joined as (
    select
        d.decklist_link,
        d._dlt_id as source_id,
        coalesce(s.name, d.player) as player_name,
        coalesce(s.tournament_link, d.tournament) as tournament_url
    from standings as s
    full outer join decks as d on s.name = d.player and s.tournament_link = d.tournament
),

renamed as (
    select
        *,
        {{ dbt_utils.generate_surrogate_key(['player_name', 'tournament_url']) }} as participant_id,
        {{ dbt_utils.generate_surrogate_key(['tournament_url']) }} as tournament_id
    from joined
)

select *
from renamed
