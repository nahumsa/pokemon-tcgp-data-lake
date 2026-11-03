-- Preserve every recorded perspective and one marker per entry without history.
with observations as (
    select
        t.tournament_id,
        t.tournament_name,
        t.tournament_url,
        t.tournament_date,
        t.set_name,
        t.source,
        t.event_type,
        p.participant_id,
        p.player_name,
        p.decklist_link,
        m.match_id,
        m.opponent_id,
        m.opponent_name,
        m.round,
        m.result,
        'PTCG' as game,
        upper(trim(t.format)) as format,
        coalesce(a.archetype, 'Unknown') as p1_archetype,
        coalesce(a.sub_archetype, 'Unknown') as p1_sub_archetype,
        coalesce(o.archetype, 'Unknown') as p2_archetype,
        coalesce(o.sub_archetype, 'Unknown') as p2_sub_archetype,
        case
            when m.match_id is null then 'missing_history'
            when upper(trim(m.opponent_name)) = 'BYE' then 'bye'
            when m.result is null or m.result not in ('WIN', 'LOSS', 'TIE') then 'invalid_result'
            when a.archetype is null or o.archetype is null then 'unknown_archetype'
            when a.archetype = o.archetype then 'mirror'
            else 'played'
        end as matchup_type
    from {{ ref('dim_participants') }} as p
    inner join {{ ref('int_tournament_context') }} as t on p.tournament_id = t.tournament_id
    left join {{ ref('fct_matches') }} as m
        on p.participant_id = m.participant_id and p.tournament_id = m.tournament_id
    left join {{ ref('dim_deck_archetypes') }} as a on p.participant_id = a.participant_id
    left join {{ ref('dim_deck_archetypes') }} as o on m.opponent_id = o.participant_id
)

select
    *,
    case when matchup_type = 'played' then 1 else 0 end as sample_size,
    case when matchup_type = 'played' and result = 'WIN' then 1 else 0 end as wins,
    case when matchup_type = 'played' and result = 'LOSS' then 1 else 0 end as losses,
    case when matchup_type = 'played' and result = 'TIE' then 1 else 0 end as ties,
    case when match_id is not null then 1 else 0 end as recorded_results,
    case when matchup_type = 'bye' then 1 else 0 end as bye_results,
    case when matchup_type = 'mirror' then 1 else 0 end as mirror_results,
    case when matchup_type = 'unknown_archetype' then 1 else 0 end as unknown_archetype_results,
    case when matchup_type = 'invalid_result' then 1 else 0 end as invalid_results,
    case when matchup_type = 'missing_history' then 1 else 0 end as participants_without_history
from observations
