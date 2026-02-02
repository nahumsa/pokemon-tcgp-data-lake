with matches as (
    select
        participant_id,
        count(*) as total_matches,
        sum(case when result = 'WIN' then 1 else 0 end) as wins,
        sum(case when result = 'LOSS' then 1 else 0 end) as losses,
        sum(case when result = 'TIE' then 1 else 0 end) as ties
    from {{ ref('fct_matches') }}
    group by participant_id
),

participants as (
    select * from {{ ref('dim_participants') }}
)

select
    p.player_name,
    p.tournament_url,
    m.total_matches,
    m.wins,
    m.losses,
    m.ties,
    case when m.total_matches > 0 then m.wins::double / m.total_matches else 0 end as win_rate
from participants as p
left join matches as m on p.participant_id = m.participant_id
order by win_rate desc
