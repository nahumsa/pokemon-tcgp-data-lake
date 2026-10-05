with fixtures as (
    select f.* from (
        values
        ('https://labs.limitlesstcg.com/0075/standings', null, null, 'limitless_labs', 'in_person'),
        ('https://play.limitlesstcg.com/tournament/legacy', null, null, 'limitless_play', 'online'),
        (
            'https://play.limitlesstcg.com/tournament/offline',
            'limitless_play',
            'in_person',
            'limitless_play',
            'in_person'
        ),
        ('https://labs.limitlesstcg.com/future', 'limitless_labs', 'online', 'limitless_labs', 'online'),
        ('https://example.com/event', null, null, 'unknown', 'unknown'),
        ('https://labs.limitlesstcg.com/old', '', '', 'limitless_labs', 'in_person')
    ) as f (url, recorded_source, recorded_event_type, expected_source, expected_event_type)
),

classified as (
    select
        *,
        {{ tournament_source('url', 'recorded_source') }} as actual_source,
        {{ tournament_event_type('url', 'recorded_event_type') }} as actual_event_type
    from fixtures
)

select * from classified
where actual_source != expected_source or actual_event_type != expected_event_type
