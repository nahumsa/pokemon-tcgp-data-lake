select
    dc.*,
    t.set_name,
    t.source,
    t.event_type,
    a.archetype,
    a.sub_archetype
from {{ ref('fct_deck_composition') }} as dc
inner join {{ ref('dim_participants') }} as p on dc.participant_id = p.participant_id
inner join {{ ref('int_tournament_context') }} as t on p.tournament_id = t.tournament_id
left join {{ ref('dim_deck_archetypes') }} as a on dc.participant_id = a.participant_id
