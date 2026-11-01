with latest as (
    select
        {{ dbt_utils.generate_surrogate_key(['name', 'tournament_link']) }} as participant_id,
        deck
    from {{ source('pokemon_tcg', 'tournament_participants') }}
    where tournament_link like 'https://labs.limitlesstcg.com/%'
    qualify row_number() over (
        partition by participant_id order by _dlt_load_id desc, deck asc nulls first
    ) = 1
)

select s.participant_id
from latest as s
left join {{ ref('dim_deck_archetypes') }} as a on s.participant_id = a.participant_id
where
    s.deck is not null
    and (a.source_archetype_label is distinct from s.deck or a.sub_archetype is distinct from s.deck)
