
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select fiscal_year
from "mbtsa"."main_marts"."fct_it_spend"
where fiscal_year is null



  
  
      
    ) dbt_internal_test