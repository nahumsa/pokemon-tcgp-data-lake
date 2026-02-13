with archetype_decks as (
    select
        participant_id,
        archetype
    from {{ ref('dim_deck_archetypes') }}
),

deck_compositions as (
    select
        participant_id,
        card_name,
        card_code,
        quantity
    from {{ ref('fct_deck_composition') }}
),

archetype_totals as (
    select
        archetype,
        count(distinct participant_id) as total_decks
    from archetype_decks
    group by 1
),

card_usage as (
    select
        ad.archetype,
        dc.card_name,
        dc.card_code,
        count(distinct ad.participant_id) as decks_with_card,
        avg(dc.quantity) as mean_quantity_when_included
    from archetype_decks as ad
    inner join deck_compositions as dc on ad.participant_id = dc.participant_id
    group by 1, 2, 3
)

select
    cu.archetype,
    cu.card_name,
    cu.card_code,
    cu.decks_with_card,
    archt.total_decks as total_archetype_decks,
    round(cu.decks_with_card * 100.0 / archt.total_decks, 2) as inclusion_rate,
    round(cu.mean_quantity_when_included, 2) as mean_quantity
from card_usage as cu
inner join archetype_totals as archt on cu.archetype = archt.archetype
order by 1 asc, 6 desc
