with deck_cards as (
    select
        set_name,
        source,
        event_type,
        participant_id,
        card_name,
        min(card_kind) as card_kind,
        sum(quantity) as quantity
    from {{ ref('int_classified_deck_cards') }}
    group by 1, 2, 3, 4, 5
),

cohort_decks as (
    select
        set_name,
        source,
        event_type,
        count(distinct participant_id) as total_decks
    from deck_cards
    group by 1, 2, 3
),

global_staples as (
    -- Unique membership by functional card, not one row per printing.
    select
        d.set_name,
        d.source,
        d.event_type,
        d.card_name,
        p.total_decks,
        count(distinct d.participant_id) * 100.0 / p.total_decks as inclusion_rate
    from deck_cards as d
    inner join cohort_decks as p
        on d.set_name is not distinct from p.set_name and d.source = p.source and d.event_type = p.event_type
    group by 1, 2, 3, 4, 5
),

matches_with_meta as (
    select
        m.match_id,
        m.participant_id,
        m.result,
        a1.archetype as p1_archetype,
        a2.archetype as p2_archetype,
        t.set_name,
        t.source,
        t.event_type
    from {{ ref('fct_matches') }} as m
    inner join {{ ref('dim_deck_archetypes') }} as a1 on m.participant_id = a1.participant_id
    inner join {{ ref('dim_deck_archetypes') }} as a2 on m.opponent_id = a2.participant_id
    inner join {{ ref('int_tournament_context') }} as t on m.tournament_id = t.tournament_id
),

difficult_matchups as (
    select
        set_name,
        source,
        event_type,
        p1_archetype,
        p2_archetype,
        count(*) as total_matches,
        sum(case when result = 'WIN' then 1 else 0 end) * 1.0 / count(*) as win_rate
    from matches_with_meta
    group by 1, 2, 3, 4, 5
    having count(*) >= 10 and win_rate < 0.50
),

participant_cards as (
    select
        m.*,
        d.card_name,
        d.card_kind,
        d.quantity
    from matches_with_meta as m
    inner join difficult_matchups as dm
        on
            m.set_name is not distinct from dm.set_name and m.source = dm.source and m.event_type = dm.event_type
            and m.p1_archetype = dm.p1_archetype and m.p2_archetype = dm.p2_archetype
    inner join deck_cards as d on m.participant_id = d.participant_id
),

card_matchup_stats as (
    select
        set_name,
        source,
        event_type,
        p1_archetype,
        p2_archetype,
        card_name,
        min(card_kind) as card_kind,
        count(distinct case when result = 'WIN' then match_id end) as wins_with_card,
        count(distinct match_id) as total_matches_with_card,
        sum(case when result = 'WIN' then quantity else 0 end) as quantity_in_wins
    from participant_cards
    group by 1, 2, 3, 4, 5, 6
),

matchup_totals as (
    select
        set_name,
        source,
        event_type,
        p1_archetype,
        p2_archetype,
        count(distinct match_id) as total_matches,
        count(distinct case when result = 'WIN' then match_id end) as total_wins
    from participant_cards
    group by 1, 2, 3, 4, 5
),

results as (
    select
        c.set_name,
        c.source,
        c.event_type,
        c.p1_archetype as archetype,
        c.p2_archetype as opponent_archetype,
        c.card_name as suggested_card,
        c.card_kind,
        c.total_matches_with_card as sample_size,
        c.wins_with_card,
        c.quantity_in_wins,
        t.total_matches - c.total_matches_with_card as matches_without_card,
        t.total_wins - c.wins_with_card as wins_without_card,
        round(c.wins_with_card * 100.0 / c.total_matches_with_card, 2) as win_rate_with_card,
        round(
            (t.total_wins - c.wins_with_card) * 100.0
            / nullif(t.total_matches - c.total_matches_with_card, 0), 2
        ) as win_rate_without_card,
        round(c.quantity_in_wins * 1.0 / nullif(c.wins_with_card, 0), 1) as suggested_quantity
    from card_matchup_stats as c
    inner join matchup_totals as t
        on
            c.set_name is not distinct from t.set_name and c.source = t.source and c.event_type = t.event_type
            and c.p1_archetype = t.p1_archetype and c.p2_archetype = t.p2_archetype
    where c.total_matches_with_card >= 3
)

select
    r.*,
    r.win_rate_with_card - r.win_rate_without_card as relevance_score
from results as r
left join {{ ref('mart_archetype_card_staples') }} as a
    on
        r.set_name is not distinct from a.set_name and r.source = a.source and r.event_type = a.event_type
        and r.archetype = a.archetype and r.suggested_card = a.card_name and r.card_kind = a.card_kind
left join global_staples as g
    on
        r.set_name is not distinct from g.set_name and r.source = g.source and r.event_type = g.event_type
        and r.suggested_card = g.card_name
where
    (a.inclusion_rate is null or a.inclusion_rate < 50)
    and (g.inclusion_rate is null or g.inclusion_rate < 50)
    and r.win_rate_with_card - r.win_rate_without_card > 5
    and r.suggested_card not in (
        'Fire Energy', 'Water Energy', 'Grass Energy', 'Lightning Energy',
        'Psychic Energy', 'Fighting Energy', 'Darkness Energy', 'Metal Energy'
    )
qualify row_number() over (
    partition by r.set_name, r.source, r.event_type, r.archetype, r.opponent_archetype
    order by relevance_score desc, r.sample_size desc, r.suggested_card asc
) <= 5
