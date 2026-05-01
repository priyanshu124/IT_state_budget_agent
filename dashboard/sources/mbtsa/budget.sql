SELECT fiscal_year, category_name, agency_code, agency_name,
    unit_name, program_name, subprogram_name,
    object_name, subobject_name, fund_type,
    is_it, it_designation, it_tower, it_sub_tower, cost_pool,
    amount, it_amount
FROM main_marts.fct_it_spend
