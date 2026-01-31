with staging as (
    select * from {{ ref('stg_tournaments') }}
)

select * from staging
