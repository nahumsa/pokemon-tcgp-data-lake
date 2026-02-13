with player_matches as (
    select
        p.player_name,
        m.result,
        da.archetype
    from {{ ref('dim_participants') }} as p
    inner join {{ ref('fct_matches') }} as m on p.participant_id = m.participant_id
    left join {{ ref('dim_deck_archetypes') }} as da on p.participant_id = da.participant_id
),

player_stats as (
    select
        player_name,
        count(*) as total_matches,
        sum(case when result = 'WIN' then 1 else 0 end) as wins,
        sum(case when result = 'LOSS' then 1 else 0 end) as losses,
        sum(case when result = 'TIE' then 1 else 0 end) as ties
    from player_matches
    group by 1
),

player_archetypes as (
    select
        player_name,
        archetype,
        count(*) as archetype_count
    from player_matches
    where archetype is not null
    group by 1, 2
),

fav_archetype as (
    select
        player_name,
        archetype as favorite_archetype
    from player_archetypes
    qualify row_number() over (partition by player_name order by archetype_count desc) = 1
)

select
    ps.player_name,
    ps.total_matches,
    ps.wins,
    ps.losses,
    ps.ties,
    fa.favorite_archetype,
    round(ps.wins * 100.0 / nullif(ps.total_matches, 0), 2) as win_rate
from player_stats as ps
left join fav_archetype as fa on ps.player_name = fa.player_name
order by 3 desc
