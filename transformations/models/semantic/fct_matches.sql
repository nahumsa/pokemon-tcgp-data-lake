with staging as (
    select * from {{ ref('stg_matches') }}
)

select * from staging
