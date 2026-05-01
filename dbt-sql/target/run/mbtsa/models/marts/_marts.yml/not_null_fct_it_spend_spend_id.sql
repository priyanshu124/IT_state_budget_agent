
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select spend_id
from "mbtsa"."main_marts"."fct_it_spend"
where spend_id is null



  
  
      
    ) dbt_internal_test