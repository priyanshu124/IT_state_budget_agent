
    
    

select
    spend_id as unique_field,
    count(*) as n_records

from "mbtsa_work"."main_marts"."fct_it_spend"
where spend_id is not null
group by spend_id
having count(*) > 1


