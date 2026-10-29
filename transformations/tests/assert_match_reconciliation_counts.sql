-- Every perspective record belongs to exactly one coverage bucket. Unique
-- played match counts include both mirrored and one-sided histories.
with perspectives as (
    select
        tournament_id,
        count(*) as perspective_record_count
    from {{ ref('fct_matches') }}
    group by 1
),

identified as (
    select
        tournament_id,
        sum(perspective_record_count) as perspective_record_count
    from {{ ref('fct_tournament_matches') }}
    where canonical_match_id is not null
    group by 1
)

select t.tournament_id
from {{ ref('mart_tournament_analysis') }} as t
left join perspectives as p on t.tournament_id = p.tournament_id
left join identified as i on t.tournament_id = i.tournament_id
where
    t.perspective_record_count != coalesce(p.perspective_record_count, 0)
    or t.unique_match_count != t.mirrored_match_count + t.one_sided_match_count
    or t.perspective_record_count != t.bye_record_count + t.unresolved_perspective_record_count
    + coalesce(i.perspective_record_count, 0)
