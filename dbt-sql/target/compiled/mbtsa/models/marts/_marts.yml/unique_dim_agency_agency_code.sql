
    
    

select
    agency_code as unique_field,
    count(*) as n_records

from "mbtsa"."main_marts"."dim_agency"
where agency_code is not null
group by agency_code
having count(*) > 1


