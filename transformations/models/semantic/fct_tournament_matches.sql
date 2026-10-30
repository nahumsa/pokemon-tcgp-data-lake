-- Reconcile player-perspective facts without changing their identities/outcomes.
with normalized_rounds as (
    select
        m.*,
        regexp_replace(lower(trim(cast(m.round as varchar))), '\s+', ' ', 'g') as round_label,
        upper(trim(m.opponent_name)) = 'BYE' as is_bye,
        upper(trim(m.result)) as normalized_result,
        p.participant_id is not null as player_known,
        o.participant_id is not null as opponent_known
    from {{ ref('fct_matches') }} as m
    left join {{ ref('dim_participants') }} as p
        on m.participant_id = p.participant_id and m.tournament_id = p.tournament_id
    left join {{ ref('dim_participants') }} as o
        on m.opponent_id = o.participant_id and m.tournament_id = o.tournament_id
),

round_keys as (
    select
        *,
        regexp_replace(round_label, '^round ([+-]?[0-9]+)$', '\1') as round_number_label
    from normalized_rounds
),

validated as (
    select
        *,
        case
            when round_label is null or round_label in ('', '?', '-', 'unknown', 'n/a', 'tbd', 'none') then null
            when regexp_full_match(round_number_label, '[+-]?[0-9]+')
                then
                    case
                        when try_cast(round_number_label as bigint) > 0
                            then cast(try_cast(round_number_label as bigint) as varchar)
                    end
            else round_label
        end as round_key
    from round_keys
),

candidates as (
    select
        *,
        case
            when coalesce(is_bye, false) then 'bye'
            when round_key is null then 'missing_round'
            when not player_known then 'unknown_player'
            when not opponent_known then 'unknown_opponent'
            when participant_id = opponent_id then 'self_pairing'
            else 'resolved'
        end as initial_resolution
    from validated
),

pairing_edges as (
    -- Include both ends even for a one-sided history. A player cannot be paired
    -- with two different opponents in the same event/round.
    select
        tournament_id,
        round_key,
        participant_id,
        opponent_id
    from candidates
    where initial_resolution = 'resolved'
    union
    select
        tournament_id,
        round_key,
        opponent_id as participant_id,
        participant_id as opponent_id
    from candidates
    where initial_resolution = 'resolved'
),

opponent_counts as (
    select
        tournament_id,
        round_key,
        participant_id,
        count(distinct opponent_id) as opponent_count
    from pairing_edges
    group by 1, 2, 3
),

keyed as (
    select
        c.*,
        case
            when c.initial_resolution = 'resolved' and (p.opponent_count > 1 or o.opponent_count > 1)
                then 'conflicting_pairing'
            else c.initial_resolution
        end as resolution_reason,
        case
            when c.initial_resolution = 'resolved'
                then least(c.participant_id, c.opponent_id)
        end as player_low_id,
        case
            when c.initial_resolution = 'resolved'
                then greatest(c.participant_id, c.opponent_id)
        end as player_high_id,
        case
            when c.initial_resolution = 'resolved'
                then 'match:' || md5(to_json(list_value(
                    c.tournament_id, c.round_key,
                    least(c.participant_id, c.opponent_id), greatest(c.participant_id, c.opponent_id)
                )))
            else 'record:' || c.match_id
        end as match_group_id
    from candidates as c
    left join opponent_counts as p
        on c.tournament_id = p.tournament_id and c.round_key = p.round_key and c.participant_id = p.participant_id
    left join opponent_counts as o
        on c.tournament_id = o.tournament_id and c.round_key = o.round_key and c.opponent_id = o.participant_id
),

summaries as (
    select
        match_group_id,
        tournament_id,
        round_key,
        player_low_id,
        player_high_id,
        resolution_reason,
        list(distinct match_id order by match_id) as perspective_record_ids,
        count(*) as perspective_record_count,
        count(distinct participant_id) as participant_count,
        count(*) - count(distinct participant_id) as duplicate_perspective_record_count,
        count(*) filter (where normalized_result is null or normalized_result not in ('WIN', 'LOSS', 'TIE'))
            as missing_outcome_count,
        count(distinct normalized_result) filter (where participant_id = player_low_id) as low_outcome_count,
        count(distinct normalized_result) filter (where participant_id = player_high_id) as high_outcome_count,
        min(normalized_result) filter (where participant_id = player_low_id) as low_result,
        min(normalized_result) filter (where participant_id = player_high_id) as high_result
    from keyed
    group by 1, 2, 3, 4, 5, 6
)

select
    match_group_id,
    tournament_id,
    round_key,
    player_low_id,
    player_high_id,
    resolution_reason,
    perspective_record_ids,
    perspective_record_count,
    duplicate_perspective_record_count,
    case when resolution_reason = 'resolved' then match_group_id end as canonical_match_id,
    case
        when resolution_reason = 'bye' then 'bye'
        when resolution_reason != 'resolved' then 'unresolved'
        when participant_count = 2 then 'mirrored'
        else 'one_sided'
    end as history_status,
    case when low_outcome_count = 1 then low_result end as low_player_result,
    case when high_outcome_count = 1 then high_result end as high_player_result,
    case
        when resolution_reason = 'bye' then 'not_applicable'
        when resolution_reason != 'resolved' then 'unresolved'
        when low_outcome_count > 1 or high_outcome_count > 1 then 'conflicting'
        when missing_outcome_count > 0 then 'incomplete'
        when participant_count = 1 then 'one_sided'
        when low_result = 'LOSS' and high_result = 'LOSS' then 'double_loss'
        when
            (low_result = 'WIN' and high_result = 'LOSS')
            or (low_result = 'LOSS' and high_result = 'WIN')
            or (low_result = 'TIE' and high_result = 'TIE') then 'consistent'
        else 'conflicting'
    end as outcome_status
from summaries
