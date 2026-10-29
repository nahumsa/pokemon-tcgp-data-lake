select
    t.*,
    s.set_name
from {{ ref('dim_tournaments') }} as t
left join {{ ref('dim_pokemon_sets') }} as s on t.tournament_date >= s.release_date
qualify row_number() over (partition by t.tournament_id order by s.release_date desc) = 1
