with label_mapping as (
    -- Only unambiguous variants may map a provider label to a shared parent.
    select
        sub_archetype,
        min(archetype) as archetype
    from {{ ref('meta_decks') }}
    group by 1
    having count(distinct archetype) = 1
),

labs_archetypes as (
    select
        {{ dbt_utils.generate_surrogate_key(['s.name', 's.tournament_link']) }} as participant_id,
        coalesce(m.archetype, s.deck) as archetype,
        s.deck as sub_archetype,
        s.deck as source_archetype_label,
        case when m.archetype is null then 'source_label_unmapped' else 'source_label_mapped' end
            as classification_method
    from {{ source('pokemon_tcg', 'tournament_participants') }} as s
    left join label_mapping as m on s.deck = m.sub_archetype
    where s.tournament_link like 'https://labs.limitlesstcg.com/%' and s.deck is not null
    qualify row_number() over (
        partition by participant_id order by s._dlt_load_id desc
    ) = 1
),

deck_cards as (
    select distinct
        participant_id,
        card_name
    from {{ ref('fct_deck_composition') }}
),

meta as (
    select * from {{ ref('meta_decks') }}
),

matches as (
    select
        d.participant_id,
        m.archetype,
        m.sub_archetype,
        m.card_name_1,
        m.card_name_2,
        -- Score: 2 if both match, 1 if only c1 matches and c2 is null
        case
            when d2.card_name is not null then 2
            when m.card_name_2 is null then 1
            else 0
        end as match_score
    from meta as m
    inner join deck_cards as d on m.card_name_1 = d.card_name
    left join deck_cards as d2 on d.participant_id = d2.participant_id and m.card_name_2 = d2.card_name
    where
        -- Must match c2 if it exists
        (m.card_name_2 is null or d2.card_name is not null)
),

ranked as (
    select
        *,
        row_number() over (
            partition by participant_id order by match_score desc, archetype asc, sub_archetype asc
        ) as rn
    from matches
)

select
    participant_id,
    archetype,
    sub_archetype,
    source_archetype_label,
    classification_method
from labs_archetypes

union all

select
    r.participant_id,
    r.archetype,
    r.sub_archetype,
    null::varchar as source_archetype_label,
    'card_rules' as classification_method
from ranked as r
where
    r.rn = 1
    and not exists (
        select 1 from labs_archetypes as l
        where l.participant_id = r.participant_id
    )
