select
    deep_anomaly_id,
    agency_name,
    unit_name,
    program_name,
    subprogram_name,
    object_name,
    subobject_name,
    fund_type,
    fiscal_year,
    spend,
    avg_spend,
    deviation_pct,
    abs_deviation_pct,
    deviation_direction,
    year_count,
    category_names
from main_marts.fct_budget_anomalies_deep
