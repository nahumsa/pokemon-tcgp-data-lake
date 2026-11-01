{% set min_matches = var('association_min_matches', 10) %}
{% set min_decks = var('association_min_decks', 3) %}
{% if min_matches is not integer or min_decks is not integer or min_matches < 1 or min_decks < 1 %}
    {{ exceptions.raise_compiler_error('Association sample thresholds must be positive integers') }}
{% endif %}

with deck_cards as (
    select
        participant_id,
        card_name,
        min(card_kind) as card_kind,
        sum(quantity) as quantity
    from {{ ref('fct_deck_composition') }}
    where quantity > 0
    group by 1, 2
),

matches as (
    -- Both supported importers currently load Pokemon TCG, not Pocket.
    -- Keep known formats and periods separate; do not invent unknown cohorts.
    select distinct
        m.match_id,
        m.participant_id,
        m.result,
        a1.archetype,
        a2.archetype as opponent_archetype,
        'PTCG' as game,
        t.set_name,
        t.source,
        t.event_type,
        upper(trim(t.format)) as format,
        exists(
            select 1 from deck_cards as d
            where d.participant_id = m.participant_id
        ) as has_decklist
    from {{ ref('fct_matches') }} as m
    inner join {{ ref('dim_deck_archetypes') }} as a1 on m.participant_id = a1.participant_id
    inner join {{ ref('dim_deck_archetypes') }} as a2 on m.opponent_id = a2.participant_id
    inner join {{ ref('int_tournament_context') }} as t on m.tournament_id = t.tournament_id
    where
        m.result in ('WIN', 'LOSS', 'TIE')
        and t.set_name is not null and nullif(trim(t.format), '') is not null
),

cohort_totals as (
    select
        game,
        format,
        set_name,
        source,
        event_type,
        archetype,
        opponent_archetype,
        count(*) as recorded_match_count,
        count(*) filter (where has_decklist) as matches_with_decklists,
        count(distinct participant_id) filter (where has_decklist) as decks_with_results,
        count(*) filter (where has_decklist and result = 'WIN') as total_wins,
        count(*) filter (where has_decklist and result = 'LOSS') as total_losses,
        count(*) filter (where has_decklist and result = 'TIE') as total_ties
    from matches
    group by 1, 2, 3, 4, 5, 6, 7
),

card_stats as (
    select
        m.game,
        m.format,
        m.set_name,
        m.source,
        m.event_type,
        m.archetype,
        m.opponent_archetype,
        d.card_name as suggested_card,
        min(d.card_kind) as card_kind,
        count(*) as sample_size,
        count(distinct m.participant_id) as decks_with_card,
        count(*) filter (where m.result = 'WIN') as wins_with_card,
        count(*) filter (where m.result = 'LOSS') as losses_with_card,
        count(*) filter (where m.result = 'TIE') as ties_with_card,
        sum(case when m.result = 'WIN' then d.quantity else 0 end) as quantity_in_wins
    from matches as m
    inner join deck_cards as d on m.participant_id = d.participant_id
    group by 1, 2, 3, 4, 5, 6, 7, 8
),

comparison_counts as (
    select
        c.*,
        t.recorded_match_count,
        t.matches_with_decklists,
        t.decks_with_results - c.decks_with_card as decks_without_card,
        t.matches_with_decklists - c.sample_size as matches_without_card,
        t.total_wins - c.wins_with_card as wins_without_card,
        t.total_losses - c.losses_with_card as losses_without_card,
        t.total_ties - c.ties_with_card as ties_without_card,
        {{ min_matches }} as min_matches_per_group,
        {{ min_decks }} as min_decks_per_group
    from card_stats as c
    inner join cohort_totals as t
        on
            c.game = t.game and c.format = t.format and c.set_name = t.set_name
            and c.source = t.source and c.event_type = t.event_type
            and c.archetype = t.archetype and c.opponent_archetype = t.opponent_archetype

),

rates as (
    select
        *,
        100.0 * wins_with_card / nullif(sample_size, 0) as win_rate_with_card,
        100.0 * wins_without_card / nullif(matches_without_card, 0) as win_rate_without_card,
        100.0 * matches_with_decklists / nullif(recorded_match_count, 0) as decklist_match_coverage,
        quantity_in_wins * 1.0 / nullif(wins_with_card, 0) as suggested_quantity,
        case
            when matches_without_card = 0 then 'missing_comparison_group'
            when sample_size < min_matches_per_group or matches_without_card < min_matches_per_group
                then 'insufficient_matches'
            when decks_with_card < min_decks_per_group or decks_without_card < min_decks_per_group
                then 'insufficient_decks'
            else 'meets_sample_thresholds'
        end as evidence_status
    from comparison_counts
),

associations as (
    select
        *,
        win_rate_with_card - win_rate_without_card as relevance_score
    from rates
)

select
    *,
    case
        when evidence_status = 'meets_sample_thresholds' then row_number() over (
            partition by game, format, set_name, source, event_type, archetype, opponent_archetype, evidence_status
            order by relevance_score desc, sample_size desc, suggested_card asc
        )
    end as association_rank
from associations
