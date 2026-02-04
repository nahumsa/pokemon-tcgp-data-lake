with tournaments as (
    select * from {{ ref('dim_tournaments') }}
),

matches as (
    select
        tournament_id,
        count(*) as total_matches
    from {{ ref('fct_matches') }}
    group by 1
),

sets as (
    select * from {{ ref('dim_pokemon_sets') }}
)

select
    t.*,
    s.set_name,
    coalesce(m.total_matches, 0) as total_matches
from tournaments as t
left join matches as m
    on t.tournament_id = m.tournament_id
left join sets as s
    on t.tournament_date >= s.release_date
qualify row_number() over (partition by t.tournament_id order by s.release_date desc) = 1
