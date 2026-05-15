
  
    
    

    create  table
      "mbtsa_work"."main_marts"."dim_program__dbt_tmp"
  
    as (
      /*
    dim_program
    ===========
    Program/ dimension.
*/

with programs as (
    select
        organization_code,
        agency_code,
        agency_name,
        unit_code,
        unit_name,
        program_code,
        program_name,
        max(description) as description
    from "mbtsa_work"."main_staging"."stg_budget_line_items"
    group by
        organization_code,
        agency_code,
        agency_name,
        unit_code,
        unit_name,
        program_code,
        program_name
)

select * from programs
    );
  
  