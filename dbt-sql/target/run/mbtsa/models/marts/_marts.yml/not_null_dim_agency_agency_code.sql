
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select agency_code
from "mbtsa"."main_marts"."dim_agency"
where agency_code is null



  
  
      
    ) dbt_internal_test