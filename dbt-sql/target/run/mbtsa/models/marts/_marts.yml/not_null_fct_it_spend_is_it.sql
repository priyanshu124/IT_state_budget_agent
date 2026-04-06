
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select is_it
from "mbtsa"."main_marts"."fct_it_spend"
where is_it is null



  
  
      
    ) dbt_internal_test