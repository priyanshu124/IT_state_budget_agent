/*
    fct_budget_anomalies
    ===================
    Precomputed anomaly metrics across selectable hierarchy levels.

    One row per (anomaly_level, entity, fiscal_year) with deviation
    calculated against the full historical average for that entity.
    Optional dashboard filters (agency/fund/category) should slice these
    rows, not recalculate anomaly baselines.
*/

with base as (
    select
        fiscal_year,
        agency_name,
        unit_name,
        program_name,
        subprogram_name,
        object_name,
        subobject_name,
        fund_type,
        category_name,
        amount
    from {{ ref('fct_it_spend') }}
    where amount is not null
),

by_level as (
    select
        'agency_name' as anomaly_level,
        agency_name as entity,
        fiscal_year,
        sum(amount) as spend,
        list(distinct agency_name) as agency_names,
        list(distinct fund_type) as fund_types,
        list(distinct category_name) as category_names
    from base
    where agency_name is not null
    group by 1, 2, 3

    union all

    select
        'unit_name' as anomaly_level,
        unit_name as entity,
        fiscal_year,
        sum(amount) as spend,
        list(distinct agency_name) as agency_names,
        list(distinct fund_type) as fund_types,
        list(distinct category_name) as category_names
    from base
    where unit_name is not null
    group by 1, 2, 3

    union all

    select
        'program_name' as anomaly_level,
        program_name as entity,
        fiscal_year,
        sum(amount) as spend,
        list(distinct agency_name) as agency_names,
        list(distinct fund_type) as fund_types,
        list(distinct category_name) as category_names
    from base
    where program_name is not null
    group by 1, 2, 3

    union all

    select
        'subprogram_name' as anomaly_level,
        subprogram_name as entity,
        fiscal_year,
        sum(amount) as spend,
        list(distinct agency_name) as agency_names,
        list(distinct fund_type) as fund_types,
        list(distinct category_name) as category_names
    from base
    where subprogram_name is not null
    group by 1, 2, 3

    union all

    select
        'object_name' as anomaly_level,
        object_name as entity,
        fiscal_year,
        sum(amount) as spend,
        list(distinct agency_name) as agency_names,
        list(distinct fund_type) as fund_types,
        list(distinct category_name) as category_names
    from base
    where object_name is not null
    group by 1, 2, 3

    union all

    select
        'subobject_name' as anomaly_level,
        subobject_name as entity,
        fiscal_year,
        sum(amount) as spend,
        list(distinct agency_name) as agency_names,
        list(distinct fund_type) as fund_types,
        list(distinct category_name) as category_names
    from base
    where subobject_name is not null
    group by 1, 2, 3
),

scored as (
    select
        anomaly_level,
        entity,
        fiscal_year,
        spend,
        avg(spend) over (partition by anomaly_level, entity) as avg_spend,
        count(*) over (partition by anomaly_level, entity) as year_count,
        agency_names,
        fund_types,
        category_names
    from by_level
),

final as (
    select
        {{ dbt_utils.surrogate_key(['anomaly_level', 'entity', 'fiscal_year']) }} as anomaly_id,
        anomaly_level,
        entity,
        fiscal_year,
        spend,
        avg_spend,
        round((spend - avg_spend) * 100.0 / nullif(avg_spend, 0), 1) as deviation_pct,
        abs(round((spend - avg_spend) * 100.0 / nullif(avg_spend, 0), 1)) as abs_deviation_pct,
        case
            when spend > avg_spend then 'positive'
            when spend < avg_spend then 'negative'
            else 'neutral'
        end as deviation_direction,
        year_count,
        agency_names,
        fund_types,
        category_names
    from scored
)

select * from final
