with matches as (
    select * from {{ ref('fct_matches') }}
),

archetypes as (
    select * from {{ ref('dim_deck_archetypes') }}
),

tournaments as (
    select * from {{ ref('dim_tournaments') }}
),

sets as (
    select * from {{ ref('dim_pokemon_sets') }}
),

deck_composition as (
    select * from {{ ref('fct_deck_composition') }}
),

archetype_staples as (
    select
        archetype,
        card_name,
        max(inclusion_rate) as inclusion_rate
    from {{ ref('mart_archetype_card_staples') }}
    group by 1, 2
),

global_staples as (
    select
        card_name,
        (decks_containing * 100.0 / (select count(distinct participant_id) from archetypes)) as global_inclusion_rate
    from {{ ref('mart_cards_used') }}
),

unique_cards as (
    select
        card_name,
        min(card_kind) as card_kind
    from {{ ref('dim_cards') }}
    group by 1
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

matches_with_meta as (
    select
        m.match_id,
        m.participant_id,
        m.opponent_id,
        m.result,
        a1.archetype as p1_archetype,
        a2.archetype as p2_archetype,
        ts.set_name
    from matches as m
    inner join archetypes as a1 on m.participant_id = a1.participant_id
    inner join archetypes as a2 on m.opponent_id = a2.participant_id
    left join tournaments_with_sets as ts on m.tournament_id = ts.tournament_id
),

difficult_matchups as (
    select
        set_name,
        p1_archetype,
        p2_archetype,
        count(*) as total_matches,
        sum(case when result = 'WIN' then 1 else 0 end) * 1.0 / count(*) as win_rate
    from matches_with_meta
    group by 1, 2, 3
    having count(*) >= 10 and win_rate < 0.50
),

participant_cards as (
    select
        ma.match_id,
        ma.participant_id,
        ma.p1_archetype,
        ma.p2_archetype,
        ma.set_name,
        ma.result,
        dc.card_name,
        sum(dc.quantity) as total_quantity
    from matches_with_meta as ma
    inner join difficult_matchups as dm
        on
            ma.p1_archetype = dm.p1_archetype
            and ma.p2_archetype = dm.p2_archetype
            and ma.set_name = dm.set_name
    inner join deck_composition as dc
        on ma.participant_id = dc.participant_id
    group by 1, 2, 3, 4, 5, 6, 7
),

card_matchup_stats as (
    select
        set_name,
        p1_archetype,
        p2_archetype,
        card_name,
        count(distinct case when result = 'WIN' then match_id end) as wins_with_card,
        count(distinct match_id) as total_matches_with_card,
        avg(case when result = 'WIN' then total_quantity end) as avg_qty_in_wins
    from participant_cards
    group by 1, 2, 3, 4
),

matchup_totals as (
    select
        set_name,
        p1_archetype,
        p2_archetype,
        count(distinct match_id) as total_matchup_matches,
        count(distinct case when result = 'WIN' then match_id end) as total_matchup_wins
    from participant_cards
    group by 1, 2, 3
),

results as (
    select
        cms.set_name,
        cms.p1_archetype as archetype,
        cms.p2_archetype as opponent_archetype,
        cms.card_name as suggested_card,
        cms.total_matches_with_card as sample_size,
        round(cms.wins_with_card * 100.0 / cms.total_matches_with_card, 2) as win_rate_with_card,
        round(
            (mt.total_matchup_wins - cms.wins_with_card) * 100.0
            / nullif(mt.total_matchup_matches - cms.total_matches_with_card, 0),
            2
        ) as win_rate_without_card,
        round(cms.avg_qty_in_wins, 1) as suggested_quantity
    from card_matchup_stats as cms
    inner join matchup_totals as mt
        on
            cms.p1_archetype = mt.p1_archetype
            and cms.p2_archetype = mt.p2_archetype
            and cms.set_name = mt.set_name
    where cms.total_matches_with_card >= 3
)

select
    r.set_name,
    r.archetype,
    r.opponent_archetype,
    r.suggested_card,
    c.card_kind,
    r.sample_size,
    r.win_rate_with_card,
    r.win_rate_without_card,
    r.suggested_quantity,
    (r.win_rate_with_card - r.win_rate_without_card) as relevance_score
from results as r
inner join unique_cards as c on r.suggested_card = c.card_name
left join archetype_staples as as_
    on
        r.archetype = as_.archetype
        and r.suggested_card = as_.card_name
left join global_staples as gs
    on r.suggested_card = gs.card_name
where
    (as_.inclusion_rate is null or as_.inclusion_rate < 50)
    and (gs.global_inclusion_rate is null or gs.global_inclusion_rate < 50)
    and (r.win_rate_with_card - r.win_rate_without_card) > 5
    and r.suggested_card not in (
        'Fire Energy',
        'Water Energy',
        'Grass Energy',
        'Lightning Energy',
        'Psychic Energy',
        'Fighting Energy',
        'Darkness Energy',
        'Metal Energy'
    )
qualify row_number() over (partition by r.set_name, r.archetype, r.opponent_archetype order by 10 desc) <= 5
order by 1, 2, 3, 10 desc
