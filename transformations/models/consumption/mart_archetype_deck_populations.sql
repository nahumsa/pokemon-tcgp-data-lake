select
    set_name,
    source,
    event_type,
    archetype,
    count(distinct participant_id) as total_archetype_decks
from {{ ref('int_classified_deck_cards') }}
where archetype is not null
group by 1, 2, 3, 4
