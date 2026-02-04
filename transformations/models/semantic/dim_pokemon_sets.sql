with source as (
    select * from {{ ref('pokemon_sets') }}
),

renamed as (
    select
        "Set Name" as set_name,
        "Abbreviation" as set_abbreviation,
        "Release Date" as release_date,
        ("Release Date" - interval '1 day') as online_start_date
    from source
)

select * from renamed
