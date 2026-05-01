
  
    
    

    create  table
      "mbtsa_work"."main_marts"."fct_subprogram_level__dbt_tmp"
  
    as (
      /*
    fct_subprogram_level
    ====================
    Subprogram-level budget aggregation for dashboard reporting.

    Grain: one row per fiscal_year x fund_type x agency_code x agency_name x unit_code x unit_name x program_code x program_name x subprogram_code x subprogram_name.
    Measure: total budget amount at that grain.
*/

with base as (
	select
		fiscal_year,
		fund_type,
		agency_code,
		agency_name,
		unit_code,
		unit_name,
		program_code,
		program_name,
		subprogram_code,
		subprogram_name,
        organization_code,
        organization_sub_code,
		amount
	from "mbtsa_work"."main_marts"."fct_it_spend"
	where amount is not null
),

final as (
	select
		fiscal_year,
		fund_type,
		agency_code,
		agency_name,
		unit_code,
		unit_name,
		program_code,
		program_name,
		subprogram_code,
		subprogram_name,
		organization_code,
		organization_sub_code,
        organization_code,
        organization_sub_code,
		sum(amount) as total_budget_amount
	from base
	group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
)

select *
from final
order by fiscal_year desc,organization_code, organization_sub_code
    );
  
  