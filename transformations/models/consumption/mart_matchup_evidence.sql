-- Event grain retains provenance; semantic rates/intervals pool counts at query time.
select
    tournament_id,
    tournament_name,
    tournament_url,
    tournament_date,
    game,
    format,
    set_name,
    source,
    event_type,
    p1_archetype,
    p1_sub_archetype,
    p2_archetype,
    p2_sub_archetype,
    matchup_type,
    sum(sample_size) as sample_size,
    sum(wins) as wins,
    sum(losses) as losses,
    sum(ties) as ties,
    sum(recorded_results) as recorded_results,
    sum(bye_results) as bye_results,
    sum(mirror_results) as mirror_results,
    sum(unknown_archetype_results) as unknown_archetype_results,
    sum(invalid_results) as invalid_results,
    sum(participants_without_history) as participants_without_history
from {{ ref('fct_matchup_results') }}
group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14
