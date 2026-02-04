with deck_composition as (
    select * from {{ ref('fct_deck_composition') }}
),

participants as (
    select * from {{ ref('dim_participants') }}
),

tournaments as (
    select * from {{ ref('dim_tournaments') }}
),

sets as (
    select * from {{ ref('dim_pokemon_sets') }}
),

tournaments_with_sets as (
    select
        t.tournament_id,
        s.set_name
    from tournaments as t
    left join sets as s
        on t.tournament_date >= s.release_date
    qualify row_number() over (partition by t.tournament_id order by s.release_date desc) = 1
),

cards_with_sets as (
    select
        dc.card_name,
        dc.card_code,
        dc.quantity,
        dc.participant_id,
        ts.set_name
    from deck_composition as dc
    inner join participants as p on dc.participant_id = p.participant_id
    left join tournaments_with_sets as ts on p.tournament_id = ts.tournament_id
)

select
    set_name,
    card_name,
    card_code,
    sum(quantity) as total_used,
    count(distinct participant_id) as decks_containing
from cards_with_sets
group by
    set_name,
    card_name,
    card_code
order by total_used desc
