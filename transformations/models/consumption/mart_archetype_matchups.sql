select
    t.set_name,
    t.source,
    t.event_type,
    a1.archetype as p1_archetype,
    a1.sub_archetype as p1_sub_archetype,
    coalesce(a2.archetype, 'Unknown') as p2_archetype,
    coalesce(a2.sub_archetype, 'Unknown') as p2_sub_archetype,
    count(*) as total_matches,
    sum(case when m.result = 'WIN' then 1 else 0 end) as wins,
    sum(case when m.result = 'LOSS' then 1 else 0 end) as losses,
    sum(case when m.result = 'TIE' then 1 else 0 end) as ties,
    round(sum(case when m.result in ('WIN', 'TIE') then 1 else 0 end) * 100.0 / count(*), 2) as win_ties_rate,
    round(sum(case when m.result = 'WIN' then 1 else 0 end) * 100.0 / count(*), 2) as win_no_ties_rate
from {{ ref('fct_matches') }} as m
inner join {{ ref('dim_deck_archetypes') }} as a1 on m.participant_id = a1.participant_id
left join {{ ref('dim_deck_archetypes') }} as a2 on m.opponent_id = a2.participant_id
inner join {{ ref('int_tournament_context') }} as t on m.tournament_id = t.tournament_id
group by 1, 2, 3, 4, 5, 6, 7
