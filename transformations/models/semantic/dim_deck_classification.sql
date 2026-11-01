with meta as (
    select * from {{ ref('meta_decks') }}
),

ruleset as (
    -- Hash rule content in stable ID order; changing precedence changes the version.
    select
        'v1:' || md5(coalesce(string_agg(
            cast(row(rule_id, rule_priority, card_name_1, card_name_2, archetype, sub_archetype) as varchar),
            '|' order by rule_id
        ), '')) as ruleset_version
    from meta
),

label_mapping as (
    select
        sub_archetype,
        min(archetype) as archetype,
        count(distinct archetype) as parent_count
    from meta
    group by sub_archetype
),

latest_labels as (
    select
        {{ dbt_utils.generate_surrogate_key(['name', 'tournament_link']) }} as participant_id,
        deck
    from {{ source('pokemon_tcg', 'tournament_participants') }}
    where tournament_link like 'https://labs.limitlesstcg.com/%'
    -- With equally fresh conflicting rows, a withdrawal wins; otherwise use label order.
    qualify row_number() over (
        partition by participant_id order by _dlt_load_id desc, deck asc nulls first
    ) = 1
),

labs_labels as (
    select
        s.participant_id,
        s.deck as sub_archetype,
        case when m.parent_count = 1 then m.archetype else s.deck end as archetype,
        case
            when m.parent_count = 1 then 'source_label_mapped'
            when m.parent_count > 1 then 'source_label_ambiguous'
            else 'source_label_unmapped'
        end as classification_status
    from latest_labels as s
    left join label_mapping as m on s.deck = m.sub_archetype
    where s.deck is not null
),

deck_cards as (
    select distinct
        participant_id,
        card_name
    from {{ ref('fct_deck_composition') }}
),

matches as (
    select
        d.participant_id,
        m.rule_id,
        m.rule_priority,
        m.archetype,
        m.sub_archetype,
        case when m.card_name_2 is null then 1 else 2 end as match_score
    from meta as m
    inner join deck_cards as d on m.card_name_1 = d.card_name
    left join deck_cards as d2 on d.participant_id = d2.participant_id and m.card_name_2 = d2.card_name
    where m.card_name_2 is null or d2.card_name is not null
),

ranked as (
    select
        *,
        dense_rank() over (
            partition by participant_id order by match_score desc, rule_priority desc
        ) as precedence_rank,
        row_number() over (
            partition by participant_id order by match_score desc, rule_priority desc, rule_id asc
        ) as selection_rank
    from matches
),

match_summary as (
    select
        participant_id,
        count(*) as matched_rule_count,
        string_agg(rule_id, ',' order by rule_id) as matched_rule_ids,
        count(distinct row(archetype, sub_archetype)) filter (where precedence_rank = 1) as top_candidate_count,
        string_agg(rule_id, ',' order by rule_id) filter (where precedence_rank = 1) as top_rule_ids
    from ranked
    group by participant_id
),

decks as (
    select distinct participant_id from deck_cards
)

select
    p.participant_id,
    l.sub_archetype as source_archetype_label,
    s.matched_rule_ids,
    s.top_rule_ids,
    v.ruleset_version,
    coalesce(l.archetype, r.archetype) as archetype,
    -- Source labels take precedence; retain card-rule diagnostics for comparison.
    coalesce(l.sub_archetype, r.sub_archetype) as sub_archetype,
    case
        when l.classification_status = 'source_label_mapped' then 'source_label_mapped'
        when l.participant_id is not null then 'source_label_unmapped'
        when r.rule_id is not null then 'card_rules'
        else 'unclassified'
    end as classification_method,
    case
        when l.participant_id is not null then l.classification_status
        when s.top_candidate_count > 1 then 'ambiguous'
        when r.rule_id is not null then 'matched'
        when d.participant_id is not null then 'unmatched'
        else 'missing_decklist'
    end as classification_status,
    case when l.participant_id is null then r.rule_id end as selected_rule_id,
    case when l.participant_id is null then r.match_score end as selected_match_score,
    case when l.participant_id is null then r.rule_priority end as selected_rule_priority,
    coalesce(s.matched_rule_count, 0) as matched_rule_count,
    coalesce(s.top_candidate_count, 0) as top_candidate_count
from {{ ref('dim_participants') }} as p
cross join ruleset as v
left join labs_labels as l on p.participant_id = l.participant_id
left join ranked as r on p.participant_id = r.participant_id and r.selection_rank = 1
left join match_summary as s on p.participant_id = s.participant_id
left join decks as d on p.participant_id = d.participant_id
