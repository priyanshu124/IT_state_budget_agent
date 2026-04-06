/*
    metricflow_time_spine
    =====================
    Minimal time spine required by MetricFlow.
    One row per day across the fiscal year range.
    MetricFlow won't parse without this, even if
    no metrics use a time dimension.
*/

{{ config(materialized='table') }}

with days as (
    select
        unnest(
            generate_series(
                date '2017-01-01',
                date '2028-12-31',
                interval '1 day'
            )
        ) as date_day
)

select
    date_day::date as date_day
from days
