with tournaments as (
    select * from {{ ref('dim_tournaments') }}
),

matches as (
    select
        tournament_id,
        count(*) as total_matches
    from {{ ref('fct_matches') }}
    group by 1
)

select
    t.*,
    coalesce(m.total_matches, 0) as total_matches
from tournaments as t
left join matches as m on t.tournament_id = m.tournament_id
