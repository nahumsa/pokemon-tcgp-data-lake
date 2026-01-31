with cards as (
    select * from {{ source('pokemon_tcg', 'participant_deck__decklist') }}
),

parents as (
    select
        _dlt_id,
        _dlt_load_id,
        {{ dbt_utils.generate_surrogate_key(['player', 'tournament']) }} as participant_id
    from {{ source('pokemon_tcg', 'participant_deck') }}
),

deduplicated_parents as (
    select
        _dlt_id
    from parents
    qualify row_number() over (partition by participant_id order by _dlt_load_id desc) = 1
),

joined as (
    select
        c._dlt_parent_id as source_participant_id,
        c.name as card_name,
        c.code as card_code,
        c.quantity,
        c.kind as card_kind
    from cards c
    inner join deduplicated_parents p on c._dlt_parent_id = p._dlt_id
)

select
    {{ dbt_utils.generate_surrogate_key(['source_participant_id', 'card_name', 'card_code']) }} as card_entry_id,
    source_participant_id,
    card_name,
    card_code,
    card_kind,
    sum(quantity) as quantity
from joined
group by 1, 2, 3, 4, 5