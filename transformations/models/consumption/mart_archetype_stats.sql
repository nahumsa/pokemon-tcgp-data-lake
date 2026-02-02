with matches as (
    select * from {{ ref('fct_matches') }}
),

archetypes as (
    select * from {{ ref('dim_deck_archetypes') }}
),

matches_with_archetypes as (
    select
        m.result,
        a.archetype,
        a.sub_archetype
    from matches as m
    inner join archetypes as a on m.participant_id = a.participant_id
)

select
    archetype,
    sub_archetype,
    count(*) as total_matches,
    sum(case when result = 'WIN' then 1 else 0 end) as wins,
    sum(case when result = 'LOSS' then 1 else 0 end) as losses,
    sum(case when result = 'TIE' then 1 else 0 end) as ties,
    round(sum(case when result = 'WIN' then 1 else 0 end) * 100.0 / count(*), 2) as win_rate
from matches_with_archetypes
group by
    archetype,
    sub_archetype
