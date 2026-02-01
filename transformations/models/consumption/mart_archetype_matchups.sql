with matches as (
    select * from {{ ref('fct_matches') }}
),

participants as (
    select participant_id, player_name, tournament_url 
    from {{ ref('dim_participants') }}
),

archetypes as (
    select * from {{ ref('dim_deck_archetypes') }}
),

matches_with_ids as (
    select 
        m.match_id,
        m.participant_id as p1_id,
        m.result,
        m.opponent_id as p2_id
    from matches m
    left join participants p2 
  		on m.opponent_id = p2.participant_id
),

matches_with_archetypes as (
    select
        m.match_id,
        m.result,
        a1.archetype as p1_archetype,
        a1.sub_archetype as p1_sub_archetype,
        coalesce(a2.archetype, 'Unknown') as p2_archetype,
        coalesce(a2.sub_archetype, 'Unknown') as p2_sub_archetype
    from matches_with_ids m
    join archetypes a1 on m.p1_id = a1.participant_id
    left join archetypes a2 on m.p2_id = a2.participant_id
)

select
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
group by 1, 2, 3, 4
