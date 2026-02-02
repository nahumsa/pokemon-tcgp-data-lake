with cards as (
    select * from {{ ref('stg_deck_cards') }}
),

participants as (
    select
        participant_id,
        source_id
    from {{ ref('stg_participants') }}
)

select
    p.participant_id,
    c.card_entry_id,
    c.card_name,
    c.card_code,
    c.quantity,
    c.card_kind
from cards as c
left join participants as p on c.source_participant_id = p.source_id
