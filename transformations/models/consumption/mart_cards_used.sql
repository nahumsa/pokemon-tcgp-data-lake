select
    set_name,
    source,
    event_type,
    card_name,
    card_code,
    card_kind,
    sum(quantity) as total_used,
    count(distinct participant_id) as decks_containing
from {{ ref('int_classified_deck_cards') }}
group by 1, 2, 3, 4, 5, 6
