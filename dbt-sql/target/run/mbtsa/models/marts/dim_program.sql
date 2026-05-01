
  
    
    

    create  table
      "mbtsa_work"."main_marts"."dim_program__dbt_tmp"
  
    as (
      /*
    dim_program
    ===========
    Program/ dimension.
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
    from "mbtsa_work"."main_staging"."stg_budget_line_items"
)

select * from programs
    );
  
  