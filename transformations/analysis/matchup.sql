select
    matches.match_id,
    matches.participant_id,
    matches.opponent_id,
    matches.result,
    player_archetypes.archetype as player_archetype,
    opponent_archetypes.archetype as opponent_archetype
from {{ ref('fct_matches') }} as matches
left join {{ ref('dim_deck_archetypes') }} as player_archetypes
    on matches.participant_id = player_archetypes.participant_id
left join {{ ref('dim_deck_archetypes') }} as opponent_archetypes
    on matches.opponent_id = opponent_archetypes.participant_id
where
    lower(opponent_archetypes.archetype) like '%zoroark'
    or lower(player_archetypes.archetype) like '%zoroark';

with zoroark_elgyem_participants as (
    select deck_composition.participant_id
    from {{ ref('fct_deck_composition') }} as deck_composition
    left join {{ ref('dim_deck_archetypes') }} as deck_archetypes
        on deck_composition.participant_id = deck_archetypes.participant_id
    where
        lower(deck_archetypes.archetype) like '%zoroark'
        and deck_composition.card_name = 'Elgyem'
)

select
    deck_composition.participant_id,
    deck_composition.card_name
from {{ ref('fct_deck_composition') }} as deck_composition
where
    deck_composition.participant_id in (
        select zoroark_elgyem_participants.participant_id
        from zoroark_elgyem_participants
    )
order by deck_composition.participant_id desc;
