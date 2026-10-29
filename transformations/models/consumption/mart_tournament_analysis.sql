with tournaments as (
    select * from {{ ref('dim_tournaments') }}
),

matches as (
    select
        tournament_id,
        sum(perspective_record_count) as perspective_record_count,
        count(canonical_match_id) as unique_match_count,
        count(*) filter (where history_status = 'mirrored') as mirrored_match_count,
        count(*) filter (where history_status = 'one_sided') as one_sided_match_count,
        sum(perspective_record_count) filter (where history_status = 'bye') as bye_record_count,
        sum(perspective_record_count) filter (where history_status = 'unresolved')
            as unresolved_perspective_record_count,
        sum(duplicate_perspective_record_count) as duplicate_perspective_record_count,
        count(*) filter (where outcome_status = 'conflicting') as conflicting_outcome_match_count,
        count(*) filter (where outcome_status = 'incomplete') as incomplete_outcome_match_count
    from {{ ref('fct_tournament_matches') }}
    group by 1
),

sets as (
    select * from {{ ref('dim_pokemon_sets') }}
)

select
    t.*,
    s.set_name,
    -- Compatibility alias: retains its historical player-perspective unit.
    coalesce(m.perspective_record_count, 0) as total_matches,
    coalesce(m.perspective_record_count, 0) as perspective_record_count,
    coalesce(m.unique_match_count, 0) as unique_match_count,
    coalesce(m.mirrored_match_count, 0) as mirrored_match_count,
    coalesce(m.one_sided_match_count, 0) as one_sided_match_count,
    coalesce(m.bye_record_count, 0) as bye_record_count,
    coalesce(m.unresolved_perspective_record_count, 0) as unresolved_perspective_record_count,
    coalesce(m.duplicate_perspective_record_count, 0) as duplicate_perspective_record_count,
    coalesce(m.conflicting_outcome_match_count, 0) as conflicting_outcome_match_count,
    coalesce(m.incomplete_outcome_match_count, 0) as incomplete_outcome_match_count
from tournaments as t
left join matches as m
    on t.tournament_id = m.tournament_id
left join sets as s
    on t.tournament_date >= s.release_date
qualify row_number() over (partition by t.tournament_id order by s.release_date desc) = 1
