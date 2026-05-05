select
    card_name,
    card_kind,
    card_code
from {{ ref('stg_deck_cards') }}
where card_kind = 'pokemon'
    and card_code is null
