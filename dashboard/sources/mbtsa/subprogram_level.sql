SELECT fiscal_year, fund_type, agency_code, agency_name, unit_code, unit_name, program_code, program_name, subprogram_code, subprogram_name, 
        is_it,
        it_designation,
        it_tower,
        it_sub_tower, 
        total_budget_amount
FROM main_marts.fct_subprogram_level
