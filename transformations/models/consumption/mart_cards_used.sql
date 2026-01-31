select
    card_name,
    card_code,
    sum(quantity) as total_used,
    count(distinct participant_id) as decks_containing
from {{ ref('fct_deck_composition') }}
group by 1, 2
order by total_used desc
