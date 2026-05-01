

with days as (
    select
        cast(d as date) as date_day
    from generate_series(
        date '1990-01-01',
        date '2030-01-01',
        interval 1 day
    ) as t(d)
),

final as (
    select
        date_day,
        cast(date_trunc('week', date_day) as date) as date_week,
        cast(date_trunc('month', date_day) as date) as date_month,
        cast(date_trunc('quarter', date_day) as date) as date_quarter,
        cast(date_trunc('year', date_day) as date) as date_year
    from days
)

select * from final