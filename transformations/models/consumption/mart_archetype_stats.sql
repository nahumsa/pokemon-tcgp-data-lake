with matches as (
    select * from {{ ref('fct_matches') }}
),

archetypes as (
    select * from {{ ref('dim_deck_archetypes') }}
),

tournaments as (
    select * from {{ ref('dim_tournaments') }}
),

sets as (
    select * from {{ ref('dim_pokemon_sets') }}
),

tournaments_with_sets as (
    select
        t.tournament_id,
        s.set_name
    from tournaments as t
    left join sets as s
        on t.tournament_date >= s.release_date
    qualify row_number() over (partition by t.tournament_id order by s.release_date desc) = 1
),

matches_with_archetypes as (
    select
        m.result,
        a.archetype,
        a.sub_archetype,
        ts.set_name
    from matches as m
    inner join archetypes as a on m.participant_id = a.participant_id
    left join tournaments_with_sets as ts on m.tournament_id = ts.tournament_id
)

select
    set_name,
    archetype,
    sub_archetype,
    count(*) as total_matches,
    sum(case when result = 'WIN' then 1 else 0 end) as wins,
    sum(case when result = 'LOSS' then 1 else 0 end) as losses,
    sum(case when result = 'TIE' then 1 else 0 end) as ties,
    round(sum(case when result = 'WIN' then 1 else 0 end) * 100.0 / count(*), 2) as win_rate
from matches_with_archetypes
group by
    set_name,
    archetype,
    sub_archetype
