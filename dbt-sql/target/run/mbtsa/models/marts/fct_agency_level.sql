
  
    
    

    create  table
      "mbtsa_work"."main_marts"."fct_agency_level__dbt_tmp"
  
    as (
      /*
	fct_agency_level
	================
	Agency-level budget aggregation for dashboard reporting.

	Grain: one row per fiscal_year x fund_type x agency_code x agency_name.
	Measure: total budget amount at that grain.
*/

with base as (
	select
		fiscal_year,
		fund_type,
		agency_code,
		agency_name,
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
		sum(amount) as total_budget_amount
	from base
	group by 1, 2, 3, 4
)

select *
from final
order by fiscal_year desc, agency_code
    );
  
  