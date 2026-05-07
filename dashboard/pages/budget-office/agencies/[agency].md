---
title:
prerender: false
---

```sql g_unit
select distinct unit_name from mbtsa.subprogram_level
where '${params.agency}' not in ('', 'undefined')
  and agency_name = '${params.agency}' and unit_name is not null
order by unit_name
```

```sql g_program
select distinct program_name from mbtsa.subprogram_level
where '${params.agency}' not in ('', 'undefined')
  and agency_name = '${params.agency}' and program_name is not null
order by program_name
```

```sql g_fund
select distinct fund_type from mbtsa.subprogram_level
where '${params.agency}' not in ('', 'undefined')
  and agency_name = '${params.agency}' and fund_type is not null
order by fund_type
```

```sql filtered
select
    cast(fiscal_year as int) as fiscal_year,
    agency_code,
    agency_name,
    unit_name,
    program_name,
    subprogram_name,
    fund_type,
    total_budget_amount as amount
from mbtsa.subprogram_level
where '${params.agency}' not in ('', 'undefined')
  and agency_name = '${params.agency}'
        and ('${selectedUnit}' in ('%', '', 'undefined') or '${selectedUnit}' like '(select%' or lower(coalesce(unit_name, '')) like '${selectedUnit}')
        and ('${selectedProgram}' in ('%', '', 'undefined') or '${selectedProgram}' like '(select%' or lower(coalesce(program_name, '')) like '${selectedProgram}')
        and ('${selectedFund}' in ('%', '', 'undefined') or '${selectedFund}' like '(select%' or lower(coalesce(fund_type, '')) like '${selectedFund}')
```

```sql yearly_rollup
select
    cast(fiscal_year as int) as fiscal_year,
    sum(amount) as total_budget
from ${filtered}
group by fiscal_year
order by fiscal_year
```

```sql scope_meta
with ordered as (
    select
        fiscal_year,
        total_budget,
        row_number() over (order by fiscal_year desc) as year_rank
    from ${yearly_rollup}
),
bounds as (
    select
        min(fiscal_year) as start_year,
        max(fiscal_year) as max_year,
        sum(total_budget) as total_budget
    from ${yearly_rollup}
)
select
    b.start_year,
    b.max_year,
    b.total_budget,
    max(case when o.year_rank = 1 then o.total_budget end) as latest_budget,
    max(case when o.year_rank = 2 then o.total_budget end) as prior_budget,
    max(case when o.year_rank = 2 then o.fiscal_year end) as prior_year
from bounds b
left join ordered o on true
where b.max_year is not null
group by b.start_year, b.max_year, b.total_budget
```

```sql overview
with points as (
    select
        m.*,
        y_5.total_budget as budget_5y_ago,
        y_10.total_budget as budget_10y_ago
    from ${scope_meta} m
    left join ${yearly_rollup} y_5 on y_5.fiscal_year = m.max_year - 5
    left join ${yearly_rollup} y_10 on y_10.fiscal_year = m.max_year - 10
)
select
    total_budget,
    latest_budget,
    latest_budget - coalesce(prior_budget, 0) as dollar_change,
    round((latest_budget - coalesce(prior_budget, 0)) * 100.0 / nullif(prior_budget, 0), 1) as yoy_pct,
    round(
        case
            when budget_5y_ago > 0 and latest_budget > 0
                then (power(latest_budget / budget_5y_ago, 1.0 / 5.0) - 1.0) * 100.0
            else null
        end, 1
    ) as cagr_5y_pct,
    round(
        case
            when budget_10y_ago > 0 and latest_budget > 0
                then (power(latest_budget / budget_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
            else null
        end, 1
    ) as cagr_10y_pct,
    coalesce(cast(max_year as varchar), 'N/A') as max_year_label
from points
```

```sql yoy_detail
select
    fiscal_year,
    coalesce(
        round(
            (total_budget - lag(total_budget) over (order by fiscal_year)) * 100.0
            / nullif(lag(total_budget) over (order by fiscal_year), 0),
            1
        ),
        0
    ) as change_pct
from ${yearly_rollup}
order by fiscal_year
```

```sql fiscal_overview_cagr
with base as (
    select
        fiscal_year,
        total_budget,
        first_value(total_budget) over (order by fiscal_year) as base_budget,
        first_value(fiscal_year) over (order by fiscal_year) as base_year,
        last_value(fiscal_year) over (order by fiscal_year rows between unbounded preceding and unbounded following) as max_year,
        last_value(total_budget) over (order by fiscal_year rows between unbounded preceding and unbounded following) as final_budget,
        row_number() over (order by fiscal_year) - 1 as yr_idx,
        count(*) over () - 1 as total_years
    from ${yearly_rollup}
),
cagr_calc as (
    select
        fiscal_year,
        total_budget,
        base_budget,
        base_year,
        max_year,
        final_budget,
        yr_idx,
        total_years,
        round(
            case when total_years > 0 and base_budget > 0 and final_budget > 0
                then (power(final_budget / base_budget, 1.0 / total_years) - 1.0) * 100.0
                else null
            end, 2
        ) as cagr_pct
    from base
)
select
    fiscal_year,
    total_budget,
    round(base_budget * power(1.0 + cagr_pct / 100.0, yr_idx), 2) as cagr_trend,
    round(base_budget * case fiscal_year
        when 2017 then 1.000
        when 2018 then 1.021
        when 2019 then 1.041
        when 2020 then 1.056
        when 2021 then 1.116
        when 2022 then 1.196
        when 2023 then 1.245
        when 2024 then 1.271
        when 2025 then 1.292
        when 2026 then 1.313
        when 2027 then 1.334
        else 1.0
    end, 2) as inflation_baseline,
    cagr_pct
from cagr_calc
order by fiscal_year
```

```sql filtered_latest
select f.*
from ${filtered} f
cross join ${scope_meta} m
where f.fiscal_year = m.max_year
```

```sql metrics_latest
select
    count(distinct unit_name) as units,
    count(distinct program_name) as programs,
    count(distinct subprogram_name) as subprograms,
    count(distinct fund_type) as fund_types
from ${filtered_latest}
```

```sql pareto_units
select
    unit_name as label,
    sum(amount) as spend,
    round(sum(amount) * 100.0 / nullif(sum(sum(amount)) over (), 0), 1) as pct_of_total,
    sum(sum(amount)) over (order by sum(amount) desc rows between unbounded preceding and current row) as cumulative,
    sum(sum(amount)) over () as grand_total
from ${filtered_latest}
where unit_name is not null
group by unit_name
order by spend desc
limit 10
```

```sql pareto_programs
select
    program_name as label,
    sum(amount) as spend,
    round(sum(amount) * 100.0 / nullif(sum(sum(amount)) over (), 0), 1) as pct_of_total,
    sum(sum(amount)) over (order by sum(amount) desc rows between unbounded preceding and current row) as cumulative,
    sum(sum(amount)) over () as grand_total
from ${filtered_latest}
where program_name is not null
group by program_name
order by spend desc
limit 10
```

```sql pareto_subprograms
select
    subprogram_name as label,
    sum(amount) as spend,
    round(sum(amount) * 100.0 / nullif(sum(sum(amount)) over (), 0), 1) as pct_of_total,
    sum(sum(amount)) over (order by sum(amount) desc rows between unbounded preceding and current row) as cumulative,
    sum(sum(amount)) over () as grand_total
from ${filtered_latest}
where subprogram_name is not null
group by subprogram_name
order by spend desc
limit 10
```

```sql fund_snapshot
with latest as (
    select fund_type, sum(amount) as latest_budget
    from ${filtered_latest}
    where fund_type is not null and trim(fund_type) <> ''
    group by fund_type
),
prior as (
    select f.fund_type, sum(f.amount) as prior_budget
    from ${filtered} f cross join ${scope_meta} m
    where f.fund_type is not null and trim(f.fund_type) <> ''
        and f.fiscal_year = m.prior_year
    group by f.fund_type
),
hist_5y as (
    select f.fund_type, sum(f.amount) as budget_5y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fund_type is not null and trim(f.fund_type) <> ''
        and f.fiscal_year = m.max_year - 5
    group by f.fund_type
),
hist_10y as (
    select f.fund_type, sum(f.amount) as budget_10y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fund_type is not null and trim(f.fund_type) <> ''
        and f.fiscal_year = m.max_year - 10
    group by f.fund_type
)
select
    l.fund_type,
    l.latest_budget,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round(l.latest_budget * 100.0 / nullif(sum(l.latest_budget) over (), 0), 1) as latest_year_pct,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_change_pct,
    round(case when h5.budget_5y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h5.budget_5y_ago, 1.0/5.0) - 1.0) * 100.0
        else null end, 1) as cagr_5y_pct,
    round(case when h10.budget_10y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h10.budget_10y_ago, 1.0/10.0) - 1.0) * 100.0
        else null end, 1) as cagr_10y_pct,
    coalesce(fp.fund_color, '#4C4743') as fund_color
from latest l
left join prior p using (fund_type)
left join hist_5y h5 using (fund_type)
left join hist_10y h10 using (fund_type)
left join ${fund_profile} fp on fp.fund_type = l.fund_type
order by l.latest_budget desc
```

```sql pivot_units
select
    unit_name,
    cast(fiscal_year as int) as fiscal_year,
    sum(amount) as spend
from ${filtered}
where unit_name is not null
group by unit_name, fiscal_year
order by unit_name, fiscal_year
```

```sql fund_trend
select
    cast(f.fiscal_year as int) as fiscal_year,
    f.fund_type,
    sum(f.amount) as spend,
    coalesce(fp.fund_rank, 99) as fund_rank,
    coalesce(fp.fund_color, '#4C4743') as fund_color
from ${filtered} f
left join ${fund_profile} fp on fp.fund_type = f.fund_type
where f.fund_type is not null
group by f.fiscal_year, f.fund_type, fp.fund_rank, fp.fund_color
order by f.fiscal_year, fund_rank
```

```sql fund_profile
with distinct_funds as (
    select distinct fund_type from ${filtered} where fund_type is not null
),
rules(pattern, fund_rank, fund_color, is_like) as (
    values
        ('federal funds', 1, '#C8122C', false),
        ('general funds', 2, '#FFC838', false),
        ('special funds', 3, '#2EAD6B', false),
        ('american rescue plan act%', 4, '#9B1C31', true),
        ('coronavirus aid, relief, and economic security act%', 5, '#B08A00', true),
        ('coronavirus response and relief sup act%', 6, '#6A1B2A', true),
        ('federal funds (covid)%', 7, '#1ABC9C', true),
        ('unrestricted', 8, '#F08C46', false),
        ('current%unrest%fund%', 8, '#F08C46', true),
        ('restricted', 9, '#5B8FF9', false),
        ('current%rest%fund%', 9, '#5B8FF9', true)
),
matches as (
    select
        d.fund_type,
        r.fund_rank,
        r.fund_color,
        row_number() over (partition by d.fund_type order by r.fund_rank) as rank_order
    from distinct_funds d
    join rules r on (
        (r.is_like and lower(d.fund_type) like r.pattern)
        or (not r.is_like and lower(d.fund_type) = r.pattern)
    )
)
select
    d.fund_type,
    coalesce(m.fund_rank, 99) as fund_rank,
    coalesce(m.fund_color, '#4C4743') as fund_color
from distinct_funds d
left join matches m on m.fund_type = d.fund_type and m.rank_order = 1
```

```sql unit_movers
with latest as (
    select coalesce(unit_name, '(No Unit)') as label, sum(amount) as latest_budget
    from ${filtered} cross join ${scope_meta} m
    where fiscal_year = m.max_year and unit_name is not null
    group by unit_name
),
prior as (
    select coalesce(unit_name, '(No Unit)') as label, sum(amount) as prior_budget
    from ${filtered} cross join ${scope_meta} m
    where fiscal_year = m.prior_year and unit_name is not null
    group by unit_name
)
select
    l.label,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as pct_change
from latest l left join prior p using (label)
where abs(l.latest_budget - coalesce(p.prior_budget, 0)) > 0
order by abs(l.latest_budget - coalesce(p.prior_budget, 0)) desc
```

```sql program_movers
with latest as (
    select coalesce(program_name, '(No Program)') as label, sum(amount) as latest_budget
    from ${filtered} cross join ${scope_meta} m
    where fiscal_year = m.max_year and program_name is not null
    group by program_name
),
prior as (
    select coalesce(program_name, '(No Program)') as label, sum(amount) as prior_budget
    from ${filtered} cross join ${scope_meta} m
    where fiscal_year = m.prior_year and program_name is not null
    group by program_name
)
select
    l.label,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as pct_change
from latest l left join prior p using (label)
where abs(l.latest_budget - coalesce(p.prior_budget, 0)) > 0
order by abs(l.latest_budget - coalesce(p.prior_budget, 0)) desc
```

```sql subprogram_movers
with latest as (
    select coalesce(subprogram_name, '(No Subprogram)') as label, sum(amount) as latest_budget
    from ${filtered} cross join ${scope_meta} m
    where fiscal_year = m.max_year and subprogram_name is not null
    group by subprogram_name
),
prior as (
    select coalesce(subprogram_name, '(No Subprogram)') as label, sum(amount) as prior_budget
    from ${filtered} cross join ${scope_meta} m
    where fiscal_year = m.prior_year and subprogram_name is not null
    group by subprogram_name
)
select
    l.label,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as pct_change
from latest l left join prior p using (label)
where abs(l.latest_budget - coalesce(p.prior_budget, 0)) > 0
order by abs(l.latest_budget - coalesce(p.prior_budget, 0)) desc
```

```sql unit_latest
with latest as (
    select unit_name, sum(amount) as latest_budget
    from ${filtered_latest}
    where unit_name is not null
    group by unit_name
),
prior as (
    select unit_name, sum(amount) as prior_budget
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.prior_year and f.unit_name is not null
    group by unit_name
),
hist_5y as (
    select unit_name, sum(amount) as budget_5y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.max_year - 5 and f.unit_name is not null
    group by unit_name
),
hist_10y as (
    select unit_name, sum(amount) as budget_10y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.max_year - 10 and f.unit_name is not null
    group by unit_name
)
select
    l.unit_name,
    l.latest_budget,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round(l.latest_budget * 100.0 / nullif(sum(l.latest_budget) over (), 0), 1) as latest_year_pct,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_change_pct,
    round(case when h5.budget_5y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h5.budget_5y_ago, 1.0/5.0) - 1.0) * 100.0
        else null end, 1) as cagr_5y_pct,
    round(case when h10.budget_10y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h10.budget_10y_ago, 1.0/10.0) - 1.0) * 100.0
        else null end, 1) as cagr_10y_pct
from latest l
left join prior p using (unit_name)
left join hist_5y h5 using (unit_name)
left join hist_10y h10 using (unit_name)
order by l.latest_budget desc
```

```sql program_latest
with latest as (
    select unit_name, program_name, sum(amount) as latest_budget
    from ${filtered_latest}
    where unit_name is not null and program_name is not null
    group by unit_name, program_name
),
prior as (
    select unit_name, program_name, sum(amount) as prior_budget
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.prior_year and f.unit_name is not null and f.program_name is not null
    group by unit_name, program_name
),
hist_5y as (
    select unit_name, program_name, sum(amount) as budget_5y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.max_year - 5 and f.unit_name is not null and f.program_name is not null
    group by unit_name, program_name
),
hist_10y as (
    select unit_name, program_name, sum(amount) as budget_10y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.max_year - 10 and f.unit_name is not null and f.program_name is not null
    group by unit_name, program_name
),
total as (select sum(latest_budget) as grand_total from latest)
select
    l.unit_name,
    l.program_name,
    l.latest_budget,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round(l.latest_budget * 100.0 / nullif(t.grand_total, 0), 1) as latest_year_pct,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_change_pct,
    round(case when h5.budget_5y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h5.budget_5y_ago, 1.0/5.0) - 1.0) * 100.0
        else null end, 1) as cagr_5y_pct,
    round(case when h10.budget_10y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h10.budget_10y_ago, 1.0/10.0) - 1.0) * 100.0
        else null end, 1) as cagr_10y_pct
from latest l
left join prior p using (unit_name, program_name)
left join hist_5y h5 using (unit_name, program_name)
left join hist_10y h10 using (unit_name, program_name)
cross join total t
order by l.unit_name, l.latest_budget desc
```

```sql subprogram_latest
with latest as (
    select unit_name, program_name, subprogram_name, sum(amount) as latest_budget
    from ${filtered_latest}
    where unit_name is not null and program_name is not null and subprogram_name is not null
    group by unit_name, program_name, subprogram_name
),
prior as (
    select unit_name, program_name, subprogram_name, sum(amount) as prior_budget
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.prior_year and f.unit_name is not null and f.program_name is not null and f.subprogram_name is not null
    group by unit_name, program_name, subprogram_name
),
hist_5y as (
    select unit_name, program_name, subprogram_name, sum(amount) as budget_5y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.max_year - 5 and f.unit_name is not null and f.program_name is not null and f.subprogram_name is not null
    group by unit_name, program_name, subprogram_name
),
hist_10y as (
    select unit_name, program_name, subprogram_name, sum(amount) as budget_10y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.max_year - 10 and f.unit_name is not null and f.program_name is not null and f.subprogram_name is not null
    group by unit_name, program_name, subprogram_name
),
total as (select sum(latest_budget) as grand_total from latest)
select
    l.unit_name,
    l.program_name,
    l.subprogram_name,
    l.latest_budget,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round(l.latest_budget * 100.0 / nullif(t.grand_total, 0), 1) as latest_year_pct,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_change_pct,
    round(case when h5.budget_5y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h5.budget_5y_ago, 1.0/5.0) - 1.0) * 100.0
        else null end, 1) as cagr_5y_pct,
    round(case when h10.budget_10y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h10.budget_10y_ago, 1.0/10.0) - 1.0) * 100.0
        else null end, 1) as cagr_10y_pct
from latest l
left join prior p using (unit_name, program_name, subprogram_name)
left join hist_5y h5 using (unit_name, program_name, subprogram_name)
left join hist_10y h10 using (unit_name, program_name, subprogram_name)
cross join total t
order by l.unit_name, l.program_name, l.latest_budget desc
```

```sql pivot_programs
select
    unit_name,
    program_name,
    cast(fiscal_year as int) as fiscal_year,
    sum(amount) as spend
from ${filtered}
where unit_name is not null
    and program_name is not null
group by unit_name, program_name, fiscal_year
order by unit_name, program_name, fiscal_year
```

```sql pivot_subprograms
select
    unit_name,
    program_name,
    subprogram_name,
    cast(fiscal_year as int) as fiscal_year,
    sum(amount) as spend
from ${filtered}
where unit_name is not null
    and program_name is not null
    and subprogram_name is not null
group by unit_name, program_name, subprogram_name, fiscal_year
order by unit_name, program_name, subprogram_name, fiscal_year
```

<script>
    import { getInputContext } from '@evidence-dev/sdk/utils/svelte';
    const inputStore = getInputContext();

    const selectedValue = (entry, lower = true) => {
        const val = readInputValue(entry, '%').replace(/'/g, "''");
        return lower ? val.toLowerCase() : val;
    };

    const readInputValue = (entry, fallback = '%') => {
        const candidates = [
            entry?.rawValues?.[0]?.value, entry?.rawValue?.value,
            entry?.value?.value, entry?.value, entry?.rawValue,
            entry?.rawValues?.[0]?.label, entry?.label, entry?.rawValues?.[0]
        ];
        for (const candidate of candidates) {
            if (candidate == null) continue;
            if (typeof candidate === 'object') {
                if (candidate.value != null) return String(candidate.value).toLowerCase();
                if (candidate.label != null) return String(candidate.label).toLowerCase();
            }
            const normalized = String(candidate).toLowerCase();
            if (normalized && normalized !== '[object object]') return normalized;
        }
        return fallback;
    };

    const usdCompact = (value) => {
        const num = Number(value) || 0;
        const abs = Math.abs(num);
        if (abs >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
        if (abs >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
        if (abs >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
        return `$${num.toFixed(2)}`;
    };

    const formatAmount = (v) => {
        const n = Number(v) || 0;
        if (n === 0) return '-';
        if (Math.abs(n) >= 1e9) return '$' + (n/1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return '$' + (n/1e6).toFixed(2) + 'M';
        return '$' + (n/1e3).toFixed(2) + 'K';
    };

    const chartTitleStyle = { fontSize: 14, fontWeight: 600, color: '#231F20' };
    const getChartGrid = () => ({
        top: '15%', right: '4%', bottom: '11%', left: '8%', containLabel: true
    });

    const calculateTrendResults = (data) => {
        if (!data || data.length < 2) return { chartData: [], trendPoints: [] };
        const values = data.map((d) => Number(d.total_budget) || 0);
        const x = Array.from({ length: data.length }, (_, i) => i + 1);
        const validPoints = x.map((xi, i) => ({ x: xi, y: values[i] })).filter((p) => p.y > 0);
        if (validPoints.length < 2) return { chartData: values, trendPoints: values };
        const lnX = validPoints.map((p) => Math.log(p.x));
        const lnY = validPoints.map((p) => Math.log(p.y));
        const count = validPoints.length;
        const sumLnX = lnX.reduce((t, v) => t + v, 0);
        const sumLnY = lnY.reduce((t, v) => t + v, 0);
        const sumLnXLnY = lnX.reduce((t, v, i) => t + v * lnY[i], 0);
        const sumLnX2 = lnX.reduce((t, v) => t + v * v, 0);
        const denominator = count * sumLnX2 - sumLnX * sumLnX;
        if (Math.abs(denominator) < 1e-10) return { chartData: values, trendPoints: values };
        const b = (count * sumLnXLnY - sumLnX * sumLnY) / denominator;
        const a = Math.exp((sumLnY - b * sumLnX) / count);
        return { chartData: values, trendPoints: x.map((xi) => a * Math.pow(xi, b)) };
    };
    $: selectedUnit = selectedValue($inputStore?.f_unit);
    $: selectedProgram = selectedValue($inputStore?.f_program);
    $: selectedFund = selectedValue($inputStore?.f_fund);
    $: cagrPct = fiscal_overview_cagr?.[0]?.cagr_pct != null ? Number(fiscal_overview_cagr[0].cagr_pct).toFixed(1) : null;

    $: fundTableColumns = [
        { id: 'fund_type', title: 'Fund Type', align: 'left' },
        { id: 'latest_budget', title: `Latest Year (${overview?.[0]?.max_year_label ?? 'N/A'})`, fmt: 'money', sortable: true },
        { id: 'latest_year_pct', title: '% of Total', fmt: 'pct', sortable: true },
        { id: 'dollar_change', title: 'YoY Change ($)', fmt: 'money', conditional: true, sortable: true },
        { id: 'yoy_change_pct', title: 'YoY Change (%)', fmt: 'pct', conditional: true, sortable: true }
    ];

    $: unitTableColumns = [
        { id: 'unit_name', title: 'Unit', align: 'left' },
        { id: 'latest_budget', title: `Latest Year (${overview?.[0]?.max_year_label ?? 'N/A'})`, fmt: 'money', sortable: true },
        { id: 'latest_year_pct', title: '% of Total', fmt: 'pct', sortable: true },
        { id: 'dollar_change', title: 'YoY Change ($)', fmt: 'money', conditional: true, sortable: true },
        { id: 'yoy_change_pct', title: 'YoY Change (%)', fmt: 'pct', conditional: true, sortable: true }
    ];

    let localView = 'trend';
    let drillYearView = '3y';
    let expandedUnits = {};
    let expandedPrograms = {};
    let drillSortCol = null;
    let drillSortDir = -1;
    let drillSearchTerm = '';

    

    const setDrillSort = (col) => {
        if (drillSortCol === col) {
            drillSortDir = drillSortDir * -1;
        } else {
            drillSortCol = col;
            drillSortDir = -1;
        }
    };

    $: viewMode = localView;
    $: trendResults = calculateTrendResults(yearly_rollup);

    let paretoLevel = 'unit';


    $: moversData = paretoLevel === 'program'
        ? (program_movers ?? [])
        : paretoLevel === 'subprogram'
            ? (subprogram_movers ?? [])
            : (unit_movers ?? []);

    $: moversLabel = paretoLevel === 'program'
        ? 'Biggest program budget changes vs prior year'
        : paretoLevel === 'subprogram'
            ? 'Biggest subprogram budget changes vs prior year'
            : 'Biggest unit budget changes vs prior year';

    $: moversAlert = paretoLevel === 'program'
        ? 'Programs sorted by absolute dollar change from prior year.'
        : paretoLevel === 'subprogram'
            ? 'Subprograms sorted by absolute dollar change from prior year.'
            : 'Units sorted by absolute dollar change from prior year.';

    $: paretoData = paretoLevel === 'program'
        ? (pareto_programs ?? [])
        : paretoLevel === 'subprogram'
            ? (pareto_subprograms ?? [])
            : (pareto_units ?? []);

    $: paretoTitle = paretoLevel === 'program'
        ? 'Top 10 programs by budget — Latest Year'
        : paretoLevel === 'subprogram'
            ? 'Top 10 subprograms by budget — Latest Year'
            : 'Top 10 units by budget — Latest Year';

    $: fundTrendYears = [...new Set((fund_trend ?? []).map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: fundSeriesNames = [...new Set((fund_trend ?? []).map(d => d.fund_type))].sort((a, b) => {
        const ra = fund_trend.find(d => d.fund_type === a)?.fund_rank ?? 99;
        const rb = fund_trend.find(d => d.fund_type === b)?.fund_rank ?? 99;
        return ra - rb;
    });
    $: fundSeriesTotals = fundSeriesNames.reduce((acc, name) => {
        acc[name] = (fund_trend ?? [])
            .filter(d => d.fund_type === name)
            .reduce((sum, d) => sum + (Number(d.spend) || 0), 0);
        return acc;
    }, {});

    $: drillYears = [...new Set((pivot_units ?? []).map(d => d.fiscal_year))].sort((a, b) => a - b);
    $: drillViewYears = (() => {
        if (drillYearView === '3y') return drillYears.slice(-3);
        if (drillYearView === '5y') return drillYears.slice(-5);
        return drillYears;
    })();

    $: top_units_trend = Object.values(
        (pivot_units ?? []).reduce((acc, row) => {
            if (!acc[row.unit_name]) acc[row.unit_name] = { agency_name: row.unit_name, total_budget: 0 };
            acc[row.unit_name].total_budget += (Number(row.spend) || 0);
            return acc;
        }, {})
    ).sort((a, b) => b.total_budget - a.total_budget).slice(0, 10);

    $: unit_trend_lines = (pivot_units ?? []).map(d => ({
        fiscal_year: d.fiscal_year,
        agency_name: d.unit_name,
        spend: d.spend
    }));

    $: unitLineTrendYears = [...new Set((pivot_units ?? []).map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));


    // Unit rows (level 1)
    $: unitPivotRows = Object.values(
        (pivot_units ?? []).reduce(function(acc, row) {
            if (!acc[row.unit_name]) acc[row.unit_name] = { name: row.unit_name };
            acc[row.unit_name]['FY' + row.fiscal_year] = (acc[row.unit_name]['FY' + row.fiscal_year] || 0) + row.spend;
            return acc;
        }, {})
    ).sort((a, b) => (b['FY' + drillYears[drillYears.length - 1]] || 0) - (a['FY' + drillYears[drillYears.length - 1]] || 0));

    // Program rows per unit (level 2)
    $: programPivotRows = (pivot_programs ?? []).reduce(function(acc, row) {
        const uKey = row.unit_name;
        const pKey = row.program_name;
        if (!acc[uKey]) acc[uKey] = {};
        if (!acc[uKey][pKey]) acc[uKey][pKey] = { name: pKey };
        acc[uKey][pKey]['FY' + row.fiscal_year] = (acc[uKey][pKey]['FY' + row.fiscal_year] || 0) + row.spend;
        return acc;
    }, {});

    // Subprogram rows per unit+program (level 3)
    $: subprogramPivotRows = (pivot_subprograms ?? []).reduce(function(acc, row) {
        const uKey = row.unit_name;
        const pKey = row.program_name;
        const sKey = row.subprogram_name;
        if (!acc[uKey]) acc[uKey] = {};
        if (!acc[uKey][pKey]) acc[uKey][pKey] = {};
        if (!acc[uKey][pKey][sKey]) acc[uKey][pKey][sKey] = { name: sKey };
        acc[uKey][pKey][sKey]['FY' + row.fiscal_year] = (acc[uKey][pKey][sKey]['FY' + row.fiscal_year] || 0) + row.spend;
        return acc;
    }, {});

    $: grandTotal = drillViewYears.reduce(function(acc, yr) {
        acc['FY' + yr] = unitPivotRows.reduce((s, r) => s + (r['FY' + yr] || 0), 0);
        return acc;
    }, {});

    $: sortedUnitRows = drillSortCol
        ? unitPivotRows.slice().sort(function(a, b) {
            if (drillSortCol === 'name') return drillSortDir * String(a.name).localeCompare(String(b.name));
            return drillSortDir * ((b[drillSortCol] || 0) - (a[drillSortCol] || 0));
        })
        : unitPivotRows;

    $: cagrPct = fiscal_overview_cagr?.[0]?.cagr_pct != null ? Number(fiscal_overview_cagr[0].cagr_pct).toFixed(1) : null;

    $: trendResults = calculateTrendResults(yearly_rollup);

    

    const sortRows = (rows, col, dir) => {
        if (!col) return rows;
        return rows.slice().sort(function(a, b) {
            if (col === 'name') return dir * String(a.name).localeCompare(String(b.name));
            return dir * ((b[col] || 0) - (a[col] || 0));
        });
    };

    const getSortedPrograms = (unitName) => {
        return sortRows(Object.values(programPivotRows[unitName] ?? {}), drillSortCol, drillSortDir);
    };

    const getSortedSubprograms = (unitName, progName) => {
        return sortRows(Object.values(subprogramPivotRows[unitName]?.[progName] ?? {}), drillSortCol, drillSortDir);
    };

    $: drillSearchLower = drillSearchTerm.toLowerCase();

    $: if (drillSearchTerm) {
        expandedUnits = sortedUnitRows.reduce(function(acc, unit) {
            acc[unit.name] = true;
            return acc;
        }, {});
        expandedPrograms = Object.keys(programPivotRows).reduce(function(acc, unitName) {
            Object.keys(programPivotRows[unitName]).forEach(function(progName) {
                acc[unitName + '||' + progName] = true;
            });
            return acc;
        }, {});
    } else {
        expandedUnits = {};
        expandedPrograms = {};
    }

    $: filteredUnitRows = drillSearchTerm
        ? sortedUnitRows.filter(function(unit) {
            // Keep unit if unit name matches
            if (unit.name.toLowerCase().includes(drillSearchLower)) return true;
            // Keep unit if any program matches
            const progs = Object.values(programPivotRows[unit.name] ?? {});
            return progs.some(function(prog) {
                if (prog.name.toLowerCase().includes(drillSearchLower)) return true;
                // Keep if any subprogram matches
                const subs = Object.values(subprogramPivotRows[unit.name]?.[prog.name] ?? {});
                return subs.some(function(sub) {
                    return sub.name.toLowerCase().includes(drillSearchLower);
                });
            });
        })
        : sortedUnitRows;

    const getFilteredPrograms = (unitName) => {
        const progs = getSortedPrograms(unitName);
        if (!drillSearchTerm) return progs;
        return progs.filter(function(prog) {
            if (prog.name.toLowerCase().includes(drillSearchLower)) return true;
            const subs = Object.values(subprogramPivotRows[unitName]?.[prog.name] ?? {});
            return subs.some(function(sub) {
                return sub.name.toLowerCase().includes(drillSearchLower);
            });
        });
    };

    const getFilteredSubprograms = (unitName, progName) => {
        const subs = getSortedSubprograms(unitName, progName);
        if (!drillSearchTerm) return subs;
        return subs.filter(function(sub) {
            return sub.name.toLowerCase().includes(drillSearchLower);
        });
    };

    const toggleUnit = (name) => {
        expandedUnits = { ...expandedUnits, [name]: !expandedUnits[name] };
    };

    const toggleProgram = (unit, prog) => {
        const key = unit + '||' + prog;
        expandedPrograms = { ...expandedPrograms, [key]: !expandedPrograms[key] };
    };
</script>



<div style="background: linear-gradient(135deg, #ede5f8 0%, #d4bef0 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #802cd7; margin-bottom: 0; display:flex; align-items:flex-end; justify-content:space-between; gap:24px; flex-wrap:wrap;">
    <div>
        <h1 style="color: #211030; font-size: 1.7rem; font-weight: 700; margin: 0;">🏛️ {params.agency}</h1>
        <p style="color: #6321a5; font-size: 0.95rem; margin: 4px 0 0 0;">Agency Budget Detail </p>
    </div>
    <div style="display:flex; border: 1px solid #c9a8f0; border-radius:6px; width:fit-content; overflow:hidden; background:rgba(255,255,255,0.5);">
        {#each [['latest','Latest Year'],['trend','Trend Over Years']] as [val, label]}
            <button
                on:click={() => localView = val}
                style={'padding:7px 18px; font-size:0.875rem; cursor:pointer; border:none; border-right: 1px solid #c9a8f0; background: ' + (localView === val ? '#802cd7' : 'rgba(255,255,255,0.6)') + '; color: ' + (localView === val ? '#ffffff' : '#211030') + '; font-weight: ' + (localView === val ? 700 : 500)}
            >{label}</button>
        {/each}
    </div>
</div>

<a href="/budget-office" style="display:inline-block; margin: 12px 0; color: var(--nxt-blue-violet); font-size: 0.9rem; text-decoration: none;">← Back to Budget Office</a>

<div id="page-filters">
    <Details title="🔍 Filters" open=false>
        <Grid cols=3>
            <Dropdown name=f_unit data={g_unit} value=unit_name title="Unit" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Units"/>
            </Dropdown>
            <Dropdown name=f_program data={g_program} value=program_name title="Program" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Programs"/>
            </Dropdown>
            <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Fund Types"/>
            </Dropdown>
        </Grid>
    </Details>
</div>

<FilterSidebar title="🔍 Filters" targetId="page-filters"/>

{#if viewMode == 'latest'}

<p style="font-size:1.1rem; font-weight:700; color:#231F20; margin: 16px 0 16px 0;">Latest Year FY{overview?.[0]?.max_year_label ?? ''}</p>

<div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin:16px 0;">
    <div style="background:var(--nxt-surface); border:1px solid var(--nxt-border); border-left:4px solid #C8122C; border-radius:8px; padding:16px 28px; min-width:200px; text-align:center;">
        <div style="font-size:11px; font-weight:500; color:#6B7280; text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px;">Latest Year Budget</div>
        <div style="font-size:1.8rem; font-weight:700; color:#231F20;">{(() => { const n = Number(overview?.[0]?.latest_budget)||0; const abs=Math.abs(n); if(abs>=1e9) return '$'+(abs/1e9).toFixed(2)+'B'; if(abs>=1e6) return '$'+(abs/1e6).toFixed(1)+'M'; return '$'+Math.round(abs).toLocaleString(); })()}</div>
    </div>
    <div style={'background:var(--nxt-surface); border:1px solid var(--nxt-border); border-left:4px solid ' + ((overview?.[0]?.yoy_pct ?? 0) >= 0 ? '#2EAD6B' : '#C8122C') + '; border-radius:8px; padding:16px 28px; min-width:200px; text-align:center;'}>
        <div style="font-size:11px; font-weight:500; color:#6B7280; text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px;">YoY Change</div>
        <div style={'font-size:1.8rem; font-weight:700; color:' + ((overview?.[0]?.yoy_pct ?? 0) >= 0 ? '#1A7340' : '#C8122C')}>
            {(() => { const n = Number(overview?.[0]?.dollar_change)||0; const abs=Math.abs(n); const sign=n>=0?'+':'-'; if(abs>=1e9) return sign+'$'+(abs/1e9).toFixed(2)+'B'; if(abs>=1e6) return sign+'$'+(abs/1e6).toFixed(1)+'M'; return sign+'$'+Math.round(abs).toLocaleString(); })()}
        </div>
        <div style={'font-size:0.95rem; font-weight:500; margin-top:2px; color:' + ((overview?.[0]?.yoy_pct ?? 0) >= 0 ? '#1A7340' : '#C8122C')}>
            {overview?.[0]?.yoy_pct != null ? ((overview[0].yoy_pct >= 0 ? '+' : '') + overview[0].yoy_pct + '%') : '—'}
        </div>
    </div>
</div>

---



{/if}

{#if viewMode == 'latest'}


## Budget drilldown

<div style="margin: 8px 0 14px 0; color: #6B7280; font-size: 0.9rem;">
    Click a unit to drill into programs, then click a program to drill into subprograms.
</div>

{#if pivot_units?.length > 0}
    <ParetoBarChart
        title=""
        drillable={true}
        drillUnitData={pivot_units}
        drillProgramData={pivot_programs}
        drillSubprogramData={pivot_subprograms}
        barField="spend"
        labelField="label"
        pctField="pct_of_total"
        cumulativeField="cumulative"
        totalField="grand_total"
        height="420px"
    />
{:else}
    <Alert status=warning>No data available for this selection.</Alert>
{/if}

---

## Fund Type Share — Latest Year

{#if fund_snapshot?.length > 0}
    <DonutFundSnapshot
        data={fund_snapshot}
        fund_profile={fund_profile}
        title=""
        height="380px"
        nameField="fund_type"
        valueField="latest_budget"
        pctField="latest_year_pct"
    />
    <ConditionalTable
        data={fund_snapshot}
        columns={fundTableColumns}
        search={false}
        defaultSort="latest_budget"
        defaultDir={-1}
    />
{:else}
    <Alert status=warning>No fund type data available for this selection.</Alert>
{/if}

---

## Budget Changes — Year over Year

<div style="display:flex; gap:8px; margin: 8px 0 14px 0;">
    {#each [['unit','Units'],['program','Programs'],['subprogram','Subprograms']] as [val, label]}
        <button
            on:click={() => paretoLevel = val}
            style={'border-radius:14px; padding:6px 14px; font-size:0.9rem; cursor:pointer; border: ' + (paretoLevel === val ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)') + '; background: ' + (paretoLevel === val ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white') + '; color: ' + (paretoLevel === val ? '#C8122C' : '#231F20') + '; font-weight: ' + (paretoLevel === val ? 700 : 500)}
        >{label}</button>
    {/each}
</div>

<Alert status=info>{moversAlert}</Alert>

<BudgetChangesChart
    data={moversData}
    labelField="label"
    title={moversLabel}
    height="480px"
    limit={10}
/>

---

## Latest Year — Unit · Program · Subprogram

{#if unit_latest?.length > 0}
    <PivotLatest
        unitData={unit_latest}
        programData={program_latest}
        subprogramData={subprogram_latest}
        latestYearLabel={overview?.[0]?.max_year_label ?? ''}
    />
{:else}
    <Alert status=warning>No latest year data available for this selection.</Alert>
{/if}

---


{/if}

{#if viewMode == 'trend'}

## Fiscal Overview

<TrendOverview
    yearly={yearly_rollup}
    yoyDetail={yoy_detail}
    fiscalOverviewCagr={fiscal_overview_cagr}
    {cagrPct}
    chartHeight="320px"
/>

---

## Fund Composition Over Time

{#if fund_trend?.length > 0}
    <FundCompositionTrend
        fundTrend={fund_trend}
        {fundTrendYears}
        {fundSeriesNames}
        {fundSeriesTotals}
    />
{:else}
    <Alert status=warning>No fund trend data available for this agency.</Alert>
{/if}

---

## Top Units by Budget Over Time
<AgencyTrendChart
    agencies={top_units_trend}
    trendLines={unit_trend_lines}
    years={unitLineTrendYears}
    title="Top Units by Budget — Trend Over Time"
    entityLabel="unit"
    topN={5}
    height="480px"
/>

## Unit · Program · Subprogram Drill-Down

<div style="display:flex; gap:8px; margin: 8px 0 14px 0;">
    {#each [['3y','Last 3 Years'],['5y','Last 5 Years'],['all','All Years']] as [val, label]}
        <button
            on:click={() => drillYearView = val}
            style={'border-radius:14px; padding:6px 14px; font-size:0.9rem; cursor:pointer; border: ' + (drillYearView === val ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)') + '; background: ' + (drillYearView === val ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white') + '; color: ' + (drillYearView === val ? '#C8122C' : '#231F20') + '; font-weight: ' + (drillYearView === val ? 700 : 500)}
        >{label}</button>
    {/each}
</div>

<input
    bind:value={drillSearchTerm}
    placeholder="Search units, programs, subprograms..."
    style="border: 1px solid #D9DDE3; border-radius: 8px; padding: 8px 12px; font-size: 0.9rem; width: 320px; margin-bottom: 12px;"
/>

{#if unitPivotRows?.length > 0}
    <TrendPivotTable
        {filteredUnitRows}
        {drillViewYears}
        drillYears={drillYears}
        {grandTotal}
        {getFilteredPrograms}
        {getFilteredSubprograms}
    />
{:else}
    <Alert status=warning>No unit data available for this agency.</Alert>
{/if}

{/if}