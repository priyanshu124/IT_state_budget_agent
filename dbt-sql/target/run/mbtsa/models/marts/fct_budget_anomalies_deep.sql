
  
    
    

    create  table
      "mbtsa_work"."main_marts"."fct_budget_anomalies_deep__dbt_tmp"
  
    as (
      /*
    fct_budget_anomalies_deep
    ========================
    Deep hierarchy anomaly metrics for root-cause drill-down.

    One row per full hierarchy + fund_type + fiscal_year.
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
    from "mbtsa_work"."main_marts"."fct_it_spend"
    where amount is not null
),

by_key as (
    select
        agency_name,
        unit_name,
        program_name,
        subprogram_name,
        object_name,
        subobject_name,
        fund_type,
        fiscal_year,
        sum(amount) as spend,
        list(distinct category_name) as category_names
    from base
    where agency_name is not null
      and unit_name is not null
      and program_name is not null
      and subprogram_name is not null
      and object_name is not null
      and subobject_name is not null
      and fund_type is not null
    group by 1, 2, 3, 4, 5, 6, 7, 8
),

scored as (
    select
        agency_name,
        unit_name,
        program_name,
        subprogram_name,
        object_name,
        subobject_name,
        fund_type,
        fiscal_year,
        spend,
        avg(spend) over (
            partition by
                agency_name,
                unit_name,
                program_name,
                subprogram_name,
                object_name,
                subobject_name,
                fund_type
        ) as avg_spend,
        count(*) over (
            partition by
                agency_name,
                unit_name,
                program_name,
                subprogram_name,
                object_name,
                subobject_name,
                fund_type
        ) as year_count,
        category_names
    from by_key
),

final as (
    select
        md5(cast(coalesce(cast(agency_name as 
    string
), '') || '-' || coalesce(cast(unit_name as 
    string
), '') || '-' || coalesce(cast(program_name as 
    string
), '') || '-' || coalesce(cast(subprogram_name as 
    string
), '') || '-' || coalesce(cast(object_name as 
    string
), '') || '-' || coalesce(cast(subobject_name as 
    string
), '') || '-' || coalesce(cast(fund_type as 
    string
), '') || '-' || coalesce(cast(fiscal_year as 
    string
), '') as 
    string
)) as deep_anomaly_id,
        agency_name,
        unit_name,
        program_name,
        subprogram_name,
        object_name,
        subobject_name,
        fund_type,
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
        category_names
    from scored
)

select * from final
    );
  
  