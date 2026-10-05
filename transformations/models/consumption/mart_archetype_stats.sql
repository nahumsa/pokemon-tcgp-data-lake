select
    t.set_name,
    t.source,
    t.event_type,
    a.archetype,
    a.sub_archetype,
    count(*) as total_matches,
    sum(case when m.result = 'WIN' then 1 else 0 end) as wins,
    sum(case when m.result = 'LOSS' then 1 else 0 end) as losses,
    sum(case when m.result = 'TIE' then 1 else 0 end) as ties,
    round(sum(case when m.result = 'WIN' then 1 else 0 end) * 100.0 / count(*), 2) as win_rate
from {{ ref('fct_matches') }} as m
inner join {{ ref('dim_deck_archetypes') }} as a on m.participant_id = a.participant_id
inner join {{ ref('int_tournament_context') }} as t on m.tournament_id = t.tournament_id
group by 1, 2, 3, 4, 5
