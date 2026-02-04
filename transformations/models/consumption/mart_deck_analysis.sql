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
)

select
    ts.set_name,
    p.player_name,
    p.tournament_url,
    m.total_matches,
    m.wins,
    m.losses,
    m.ties,
    case when m.total_matches > 0 then m.wins::double / m.total_matches else 0 end as win_rate
from participants as p
left join matches as m on p.participant_id = m.participant_id
left join tournaments_with_sets as ts on p.tournament_id = ts.tournament_id
order by win_rate desc
