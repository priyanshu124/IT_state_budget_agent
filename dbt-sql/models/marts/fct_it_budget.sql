/*
	fct_it_budget
	==================
	Fact table containing only IT-classified budget line items.

	This model selects rows where `is_it = true` from the
	`fct_it_spend` fact so all IT-related columns (towers, cost
	pools, designation, confidence, and IT measures) are preserved.

	Grain: one row per budget line item (IT-only)
*/

with source as (
	select * from {{ ref('fct_it_spend') }}
)

select
	*
from source
where coalesce(is_it, false) = true

