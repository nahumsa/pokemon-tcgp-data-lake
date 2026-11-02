with audits as (
    select * from {{ ref('stg_ingestion_event_runs') }}
),

latest as (
    select * from audits
    qualify row_number() over (
        partition by tournament_url order by loaded_at desc, attempt_id desc
    ) = 1
),

successful as (
    select
        tournament_url,
        max(loaded_at::timestamptz) as last_successful_ingestion_at
    from audits
    where extraction_status = 'success' and load_status = 'success'
    group by tournament_url
),

participants as (
    select
        p.tournament_id,
        count(*) as observed_participant_count,
        count(*) filter (
            where c.classification_status in ('matched', 'source_label_mapped', 'source_label_unmapped')
        ) as classified_participant_count,
        count(*) filter (
            where c.classification_status in ('ambiguous', 'source_label_ambiguous')
        ) as ambiguous_participant_count
    from {{ ref('dim_participants') }} as p
    left join {{ ref('dim_deck_classification') }} as c on p.participant_id = c.participant_id
    group by p.tournament_id
),

events as (
    select
        tournament_id, tournament_url, tournament_name, tournament_date,
        source, event_type, format, player_count
    from {{ ref('dim_tournaments') }}
    union all
    -- Even a first failed attempt has provenance and an explicit unready row.
    select
        md5(a.tournament_url), a.tournament_url, null, null, 'unknown', 'unknown', null, null
    from latest as a
    where not exists (
        select 1 from {{ ref('dim_tournaments') }} as t where t.tournament_url = a.tournament_url
    )
),

counts as (
    select
        t.* exclude (player_count),
        coalesce(a.expected_participant_count, t.player_count) as expected_participant_count,
        coalesce(p.observed_participant_count, 0) as observed_participant_count,
        coalesce(p.classified_participant_count, 0) as classified_participant_count,
        coalesce(p.ambiguous_participant_count, 0) as ambiguous_participant_count,
        a.participant_count as latest_participant_count,
        a.decklist_count as latest_decklist_count,
        a.history_participant_count as latest_history_participant_count,
        a.source_completed,
        a.extraction_status as latest_extraction_status,
        a.load_status as latest_load_status,
        a.participant_error_count,
        a.decklist_error_count,
        a.history_error_count,
        a.extraction_error_count,
        a.source_updated_at,
        a.extracted_at::timestamptz as extracted_at,
        a.loaded_at::timestamptz as latest_load_at,
        s.last_successful_ingestion_at,
        '{{ run_started_at }}'::timestamptz as transformed_at
    from events as t
    left join participants as p on t.tournament_id = p.tournament_id
    left join latest as a on t.tournament_url = a.tournament_url
    left join successful as s on t.tournament_url = s.tournament_url
)

select
    *,
    observed_participant_count * 100.0 / nullif(expected_participant_count, 0) as participant_coverage_pct,
    latest_decklist_count * 100.0 / nullif(latest_participant_count, 0) as decklist_coverage_pct,
    latest_history_participant_count * 100.0 / nullif(latest_participant_count, 0) as history_coverage_pct,
    classified_participant_count * 100.0 / nullif(observed_participant_count, 0) as classification_coverage_pct
from counts
