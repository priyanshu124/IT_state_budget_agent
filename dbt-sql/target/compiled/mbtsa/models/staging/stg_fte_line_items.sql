/*
    stg_fte_line_items
    ===================
    Clean, typed FTE headcount data from the raw FTE pipeline.

    Grain: one row per fiscal_year × agency_code × unit_code × program_code × organization_code.
*/

with source as (
    select *
    from "mbtsa_work"."main"."fte_line_items"
),

staged as (
    select
        fiscal_year::int as fiscal_year,
        trim(regexp_replace(cast(agency_code as varchar), '\s+', ' ')) as agency_code,
        trim(regexp_replace(cast(agency_name as varchar), '\s+', ' ')) as agency_name,
        trim(regexp_replace(cast(unit_code as varchar), '\s+', ' ')) as unit_code,
        trim(regexp_replace(cast(unit_name as varchar), '\s+', ' ')) as unit_name,
        trim(regexp_replace(cast(program_code as varchar), '\s+', ' ')) as program_code,
        trim(regexp_replace(cast(program_name as varchar), '\s+', ' ')) as program_name,
        trim(regexp_replace(cast(organization_code as varchar), '\s+', ' ')) as organization_code,
        coalesce(fte_count::double, 0.0) as fte_count
    from source
)

select *
from staged