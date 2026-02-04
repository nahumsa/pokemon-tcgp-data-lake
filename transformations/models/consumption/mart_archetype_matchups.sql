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

matches_with_ids as (
    select
        m.match_id,
        m.participant_id as p1_id,
        m.result,
        m.opponent_id as p2_id,
        m.tournament_id
    from matches as m
),

matches_with_archetypes as (
    select
        m.match_id,
        m.result,
        a1.archetype as p1_archetype,
        a1.sub_archetype as p1_sub_archetype,
        coalesce(a2.archetype, 'Unknown') as p2_archetype,
        coalesce(a2.sub_archetype, 'Unknown') as p2_sub_archetype,
        ts.set_name
    from matches_with_ids as m
    inner join archetypes as a1 on m.p1_id = a1.participant_id
    left join archetypes as a2 on m.p2_id = a2.participant_id
    left join tournaments_with_sets as ts on m.tournament_id = ts.tournament_id
)

select
    set_name,
    p1_archetype,
    p1_sub_archetype,
    p2_archetype,
    p2_sub_archetype,
    count(*) as total_matches,
    sum(case when result = 'WIN' then 1 else 0 end) as wins,
    sum(case when result = 'LOSS' then 1 else 0 end) as losses,
    sum(case when result = 'TIE' then 1 else 0 end) as ties,
    round(sum(case when result = 'WIN' then 1 else 0 end) * 100.0 / count(*), 2) as win_rate
from matches_with_archetypes
group by
    set_name,
    p1_archetype,
    p1_sub_archetype,
    p2_archetype,
    p2_sub_archetype
