-- Preserve the classified-only population and columns used by existing analytics.
select
    participant_id,
    archetype,
    sub_archetype,
    source_archetype_label,
    classification_method
from {{ ref('dim_deck_classification') }}
where archetype is not null
