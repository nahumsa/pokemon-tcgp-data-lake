select
    t.source,
    t.event_type,
    date_trunc('month', t.tournament_date) as tournament_month,
    count(distinct p.participant_id) as total_participants
from {{ ref('dim_participants') }} as p
inner join {{ ref('dim_tournaments') }} as t on p.tournament_id = t.tournament_id
group by 1, 2, 3
