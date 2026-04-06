/*
    dim_program
    ===========
    Program/subprogram dimension with IT designation.
*/

with programs as (
    select distinct
        program_key,
        line_item_key,
        agency_code,
        agency_name,
        program_code,
        program_name,
        subprogram_code,
        subprogram_name,
        is_it,
        it_designation
    from "mbtsa_work"."main_staging"."stg_budget_line_items"
)

select * from programs