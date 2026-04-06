
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select fiscal_year
from "mbtsa"."main"."budget_line_items"
where fiscal_year is null



  
  
      
    ) dbt_internal_test