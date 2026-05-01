/*
    dim_agency
    ==========
    Agency dimension — one row per agency.
*/

with agencies as (
    select distinct
        agency_code,
        agency_name,
        category_code,
        category_name
    from {{ ref('stg_budget_line_items') }}
)

select
    agency_code,
    agency_name,
    category_code,
    category_name
from agencies
