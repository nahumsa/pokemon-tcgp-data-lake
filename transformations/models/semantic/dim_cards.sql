with staging as (
    select distinct
        card_name,
        card_code,
        card_kind
    from {{ ref('stg_deck_cards') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['card_name', 'card_code']) }} as card_id,
    *
from staging
