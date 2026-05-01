
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    spend_id as unique_field,
    count(*) as n_records

from "mbtsa"."main_marts"."fct_it_spend"
where spend_id is not null
group by spend_id
having count(*) > 1



  
  
      
    ) dbt_internal_test