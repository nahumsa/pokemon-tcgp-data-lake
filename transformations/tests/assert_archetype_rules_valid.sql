with rules as (
    select
        *,
        least(card_name_1, coalesce(card_name_2, card_name_1)) as first_card,
        greatest(card_name_1, coalesce(card_name_2, card_name_1)) as last_card
    from {{ ref('meta_decks') }}
),

invalid_metadata as (
    select 'invalid_metadata' as problem
    from rules
    where
        nullif(trim(rule_id), '') is null
        or rule_priority is null
        or rule_priority != trunc(rule_priority)
        or nullif(trim(card_name_1), '') is null
        or nullif(trim(archetype), '') is null
        or nullif(trim(sub_archetype), '') is null
        or card_name_2 = ''
        or card_name_1 = card_name_2
),

duplicate_ids as (
    select 'duplicate_rule_id' as problem
    from rules
    group by rule_id
    having count(*) > 1
),

duplicate_rules as (
    select 'duplicate_rule' as problem
    from rules
    group by first_card, last_card, archetype, sub_archetype
    having count(*) > 1
),

conflicting_rules as (
    select 'conflicting_rule' as problem
    from rules
    group by first_card, last_card, rule_priority
    having count(distinct row(archetype, sub_archetype)) > 1
)

select * from invalid_metadata
union all
select * from duplicate_ids
union all
select * from duplicate_rules
union all
select * from conflicting_rules
