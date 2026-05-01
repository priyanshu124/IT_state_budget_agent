
    
    

select
    line_item_key as unique_field,
    count(*) as n_records

from "mbtsa"."main_marts"."dim_program"
where line_item_key is not null
group by line_item_key
having count(*) > 1


