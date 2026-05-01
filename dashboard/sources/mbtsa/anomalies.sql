select
    anomaly_id,
    anomaly_level,
    entity,
    fiscal_year,
    spend,
    avg_spend,
    deviation_pct,
    abs_deviation_pct,
    deviation_direction,
    year_count,
    agency_names,
    fund_types,
    category_names
from main_marts.fct_budget_anomalies
