with included_cards as (
    -- One functional card per deck, combining alternate Pokemon printings.
    select
        set_name,
        source,
        event_type,
        archetype,
        participant_id,
        card_name,
        card_kind,
        sum(quantity) as quantity
    from {{ ref('int_classified_deck_cards') }}
    where archetype is not null
    group by 1, 2, 3, 4, 5, 6, 7
),

usage as (
    select
        set_name,
        source,
        event_type,
        archetype,
        card_name,
        card_kind,
        count(*) as decks_with_card,
        sum(quantity) as total_quantity_when_included
    from included_cards
    group by 1, 2, 3, 4, 5, 6
)

select
    u.*,
    p.total_archetype_decks,
    round(u.decks_with_card * 100.0 / p.total_archetype_decks, 2) as inclusion_rate,
    round(u.total_quantity_when_included * 1.0 / u.decks_with_card, 2) as mean_quantity
from usage as u
inner join {{ ref('mart_archetype_deck_populations') }} as p
    on
        u.set_name = p.set_name and u.source = p.source and u.event_type = p.event_type
        and u.archetype = p.archetype
