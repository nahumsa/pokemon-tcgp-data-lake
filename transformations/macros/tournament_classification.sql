{% macro tournament_source(url, recorded_source='null') %}
    coalesce(nullif({{ recorded_source }}, ''), case
        when {{ url }} like 'https://labs.limitlesstcg.com/%' then 'limitless_labs'
        when {{ url }} like 'https://play.limitlesstcg.com/%' then 'limitless_play'
        else 'unknown'
    end)
{% endmacro %}

{% macro tournament_event_type(url, recorded_event_type='null') %}
    coalesce(nullif({{ recorded_event_type }}, ''), case
        when {{ url }} like 'https://labs.limitlesstcg.com/%' then 'in_person'
        -- Legacy Play rows were collected by the online-only importer.
        when {{ url }} like 'https://play.limitlesstcg.com/%' then 'online'
        else 'unknown'
    end)
{% endmacro %}
