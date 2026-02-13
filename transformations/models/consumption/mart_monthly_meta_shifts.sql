with participants as (
    select
        p.participant_id,
        p.tournament_id,
        da.archetype,
        t.tournament_date,
        date_trunc('month', t.tournament_date) as tournament_month
    from {{ ref('dim_participants') }} as p
    inner join {{ ref('dim_tournaments') }} as t on p.tournament_id = t.tournament_id
    left join {{ ref('dim_deck_archetypes') }} as da on p.participant_id = da.participant_id
),

monthly_totals as (
    select
        tournament_month,
        count(distinct participant_id) as total_participants
    from participants
    group by 1
),

archetype_monthly_counts as (
    select
        tournament_month,
        archetype,
        count(distinct participant_id) as archetype_participants
    from participants
    group by 1, 2
),

match_stats as (
    select
        da.archetype,
        date_trunc('month', t.tournament_date) as tournament_month,
        count(*) as total_matches,
        sum(case when m.result = 'WIN' then 1 else 0 end) as wins
    from {{ ref('fct_matches') }} as m
    inner join {{ ref('dim_tournaments') }} as t on m.tournament_id = t.tournament_id
    inner join {{ ref('dim_deck_archetypes') }} as da on m.participant_id = da.participant_id
    group by 1, 2
)

select
    amc.tournament_month,
    amc.archetype,
    amc.archetype_participants,
    mt.total_participants,
    coalesce(ms.total_matches, 0) as total_matches,
    coalesce(ms.wins, 0) as wins,
    round(amc.archetype_participants * 100.0 / mt.total_participants, 2) as meta_share,
    round(coalesce(ms.wins, 0) * 100.0 / nullif(ms.total_matches, 0), 2) as win_rate
from archetype_monthly_counts as amc
inner join monthly_totals as mt on amc.tournament_month = mt.tournament_month
left join match_stats as ms
    on
        amc.tournament_month = ms.tournament_month
        and amc.archetype = ms.archetype
where amc.archetype is not null
order by 1 desc, 7 desc
