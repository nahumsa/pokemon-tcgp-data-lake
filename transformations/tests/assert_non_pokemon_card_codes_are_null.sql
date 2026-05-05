select
    card_name,
    card_kind,
    card_code
from {{ ref('stg_deck_cards') }}
where card_kind in ('trainer', 'energy')
    and card_code is not null
