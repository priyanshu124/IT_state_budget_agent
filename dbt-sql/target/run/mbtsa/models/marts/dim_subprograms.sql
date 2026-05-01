
  
    
    

    create  table
      "mbtsa_work"."main_marts"."dim_subprograms__dbt_tmp"
  
    as (
      /*
    dim_program
    ===========
    Program/subprogram dimension with IT designation.
*/

with programs as (
    select distinct
        organization_code,
        agency_code,
        agency_name,
        unit_code,
        unit_name,
        program_code,
        program_name,
        subprogram_code,
        subprogram_name,
        is_it,
        it_designation,
        it_tower,
        it_sub_tower
    from "mbtsa_work"."main_staging"."stg_budget_line_items"
)

select * from programs
    );
  
  