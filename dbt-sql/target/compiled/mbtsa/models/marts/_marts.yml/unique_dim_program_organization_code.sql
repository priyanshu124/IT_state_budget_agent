
    
    

select
    organization_code as unique_field,
    count(*) as n_records

from "mbtsa_work"."main_marts"."dim_program"
where organization_code is not null
group by organization_code
having count(*) > 1


