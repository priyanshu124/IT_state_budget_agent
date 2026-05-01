
  
    
    

    create  table
      "mbtsa"."main"."metricflow_time_spine__dbt_tmp"
  
    as (
      

select
    cast(d as date) as date_day
from generate_series(
    date '2010-01-01',
    date '2040-12-31',
    interval 1 day
) as t(d)
    );
  
  