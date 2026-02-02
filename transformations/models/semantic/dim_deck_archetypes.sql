with deck_cards as (
    select
        participant_id,
        card_name
    from {{ ref('fct_deck_composition') }}
),

meta as (
    select * from {{ ref('meta_decks') }}
),

matches as (
    select
        d.participant_id,
        m.archetype,
        m.sub_archetype,
        m.card_name_1,
        m.card_name_2,
        -- Score: 2 if both match, 1 if only c1 matches and c2 is null
        case
            when d2.card_name is not null then 2
            when m.card_name_2 is null then 1
            else 0
        end as match_score
    from meta as m
    inner join deck_cards as d on m.card_name_1 = d.card_name
    left join deck_cards as d2 on d.participant_id = d2.participant_id and m.card_name_2 = d2.card_name
    where
        -- Must match c2 if it exists
        (m.card_name_2 is null or d2.card_name is not null)
),

ranked as (
    select
        *,
        row_number() over (partition by participant_id order by match_score desc) as rn
    from matches
)

select
    participant_id,
    archetype,
    sub_archetype
from ranked
where rn = 1
