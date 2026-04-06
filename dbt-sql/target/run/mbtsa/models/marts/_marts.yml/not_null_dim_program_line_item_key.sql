
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select line_item_key
from "mbtsa"."main_marts"."dim_program"
where line_item_key is null



  
  
      
    ) dbt_internal_test