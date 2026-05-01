
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select budget
from "mbtsa"."main"."budget_line_items"
where budget is null



  
  
      
    ) dbt_internal_test