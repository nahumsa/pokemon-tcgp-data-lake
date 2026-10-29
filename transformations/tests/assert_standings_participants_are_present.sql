select
    s.tournament_link,
    s.name
from {{ source('pokemon_tcg', 'tournament_participants') }} as s
left join {{ ref('stg_participants') }} as p
    on s.tournament_link = p.tournament_url and s.name = p.player_name
where p.participant_id is null
