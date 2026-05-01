
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select cost_pool
from "mbtsa"."main_marts"."fct_it_spend"
where cost_pool is null



  
  
      
    ) dbt_internal_test