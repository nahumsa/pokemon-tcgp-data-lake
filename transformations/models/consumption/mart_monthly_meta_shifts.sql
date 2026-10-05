with archetype_monthly_counts as (
    select
        t.source,
        t.event_type,
        a.archetype,
        date_trunc('month', t.tournament_date) as tournament_month,
        count(distinct p.participant_id) as archetype_participants
    from {{ ref('dim_participants') }} as p
    inner join {{ ref('dim_tournaments') }} as t on p.tournament_id = t.tournament_id
    inner join {{ ref('dim_deck_archetypes') }} as a on p.participant_id = a.participant_id
    group by 1, 2, 3, 4
),

match_stats as (
    select
        t.source,
        t.event_type,
        a.archetype,
        date_trunc('month', t.tournament_date) as tournament_month,
        count(*) as total_matches,
        sum(case when m.result = 'WIN' then 1 else 0 end) as wins
    from {{ ref('fct_matches') }} as m
    inner join {{ ref('dim_tournaments') }} as t on m.tournament_id = t.tournament_id
    inner join {{ ref('dim_deck_archetypes') }} as a on m.participant_id = a.participant_id
    group by 1, 2, 3, 4
)

select
    a.*,
    p.total_participants,
    coalesce(m.total_matches, 0) as total_matches,
    coalesce(m.wins, 0) as wins,
    round(a.archetype_participants * 100.0 / p.total_participants, 2) as meta_share,
    round(coalesce(m.wins, 0) * 100.0 / nullif(m.total_matches, 0), 2) as win_rate
from archetype_monthly_counts as a
inner join {{ ref('mart_monthly_populations') }} as p
    on a.tournament_month = p.tournament_month and a.source = p.source and a.event_type = p.event_type
left join match_stats as m
    on
        a.tournament_month = m.tournament_month and a.source = m.source and a.event_type = m.event_type
        and a.archetype = m.archetype
