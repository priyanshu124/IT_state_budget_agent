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
		amount,
		it_amount
	from {{ ref('fct_it_spend') }}
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
		sum(amount) as total_budget_amount,
		sum(coalesce(it_amount, 0)) as total_it_amount,
		count(*) as line_count
	from base
	group by 1,2,3,4,5,6,7,8,9,10,11,12
)

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
	total_budget_amount,
	total_it_amount,
	line_count,
	coalesce(total_it_amount / nullif(total_budget_amount, 0), 0) as it_amount_pct
from final
order by fiscal_year desc, organization_code, organization_sub_code