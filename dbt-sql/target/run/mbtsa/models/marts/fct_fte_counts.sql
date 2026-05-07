
  
    
    

    create  table
      "mbtsa_work"."main_marts"."fct_fte_counts__dbt_tmp"
  
    as (
      /*
    fct_fte_counts
    ==============
    FTE headcount aggregation for dashboard reporting.

    Grain: one row per fiscal_year x agency_code x agency_name x unit_code x unit_name x program_code x program_name x organization_code.
    Measure: total FTE count at that grain.
*/

with base as (
	select
		fiscal_year,
		agency_code,
		agency_name,
		unit_code,
		unit_name,
		program_code,
		program_name,
		organization_code,
		fte_count
	from "mbtsa_work"."main_staging"."stg_fte_line_items"
	where fte_count is not null
),

final as (
	select
		fiscal_year,
		agency_code,
		agency_name,
		unit_code,
		unit_name,
		program_code,
		program_name,
		organization_code,
		sum(fte_count) as total_fte_count
	from base
	group by 1, 2, 3, 4, 5, 6, 7, 8
)

select *
from final
order by fiscal_year desc, agency_code, unit_code, program_code
    );
  
  