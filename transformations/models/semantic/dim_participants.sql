with staging as (
    select * from {{ ref('stg_participants') }}
)

select * from staging
