select
    card_name,
    card_kind,
    count(distinct card_id) as card_id_count
from {{ ref('dim_cards') }}
where card_kind in ('trainer', 'energy')
group by 1, 2
having count(distinct card_id) > 1
