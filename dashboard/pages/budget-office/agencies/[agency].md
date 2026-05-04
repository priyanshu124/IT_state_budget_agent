---
title: Agency Detail
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
    round((latest_budget - prior_budget) * 100.0 / nullif(prior_budget, 0), 1) as yoy_pct,
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
    from ${filtered_latest}
    group by unit_name
),
prior as (
    select coalesce(unit_name, '(No Unit)') as label, sum(amount) as prior_budget
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.prior_year
    group by unit_name
)
select
    l.label,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as pct_change
from latest l
left join prior p using (label)
```

```sql program_movers
with latest as (
    select coalesce(program_name, '(No Program)') as label, sum(amount) as latest_budget
    from ${filtered_latest}
    where program_name is not null
    group by program_name
),
prior as (
    select coalesce(program_name, '(No Program)') as label, sum(amount) as prior_budget
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.prior_year
        and f.program_name is not null
    group by program_name
)
select
    l.label,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as pct_change
from latest l
left join prior p using (label)
```

```sql subprogram_movers
with latest as (
    select coalesce(subprogram_name, '(No Subprogram)') as label, sum(amount) as latest_budget
    from ${filtered_latest}
    where subprogram_name is not null
    group by subprogram_name
),
prior as (
    select coalesce(subprogram_name, '(No Subprogram)') as label, sum(amount) as prior_budget
    from ${filtered} f cross join ${scope_meta} m
    where f.fiscal_year = m.prior_year
        and f.subprogram_name is not null
    group by subprogram_name
)
select
    l.label,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as pct_change
from latest l
left join prior p using (label)
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

    $: fundTableColumns = [
        { id: 'fund_type', title: 'Fund Type', align: 'left' },
        { id: 'latest_budget', title: `Latest Year (${overview?.[0]?.max_year_label ?? 'N/A'})`, fmt: 'money', sortable: true },
        { id: 'latest_year_pct', title: '% of Total', fmt: 'pct', sortable: true },
        { id: 'yoy_change_pct', title: 'YoY Change', fmt: 'pct', conditional: true, sortable: true },
        { id: 'cagr_5y_pct', title: '5-Year CAGR', fmt: 'pct', conditional: true, sortable: true },
        { id: 'cagr_10y_pct', title: '10-Year CAGR', fmt: 'pct', conditional: true, sortable: true }
    ];

    let localView = 'latest';
    let drillYearView = '5y';
    let expandedUnits = {};
    let expandedPrograms = {};
    let drillSortCol = null;
    let drillSortDir = -1;
    let selectedFundSeries = null;
    let drillSearchTerm = '';

    

    const toggleFundSeries = (name) => {
        selectedFundSeries = selectedFundSeries === name ? null : name;
    };

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

    $: drillYears = [...new Set((pivot_units ?? []).map(d => d.fiscal_year))].sort((a, b) => a - b);
    $: drillViewYears = (() => {
        if (drillYearView === '3y') return drillYears.slice(-3);
        if (drillYearView === '5y') return drillYears.slice(-5);
        return drillYears;
    })();


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



<div style="background: linear-gradient(135deg, #802cd7 0%, #211030 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #b376f6; margin-bottom: 0;">
    <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">🏛️ {params.agency}</h1>
    <p style="color: #b376f6; font-size: 0.95rem; margin: 4px 0 0 0;">Agency Budget Detail </p>
</div>

<a href="/budget-office" style="display:inline-block; margin: 12px 0; color: #C8122C; font-size: 0.9rem; text-decoration: none;">← Back to Budget Office</a>

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

<div style="display:flex; gap:0; margin: 16px 0 8px 0; border: 1px solid #D9DDE3; border-radius:6px; width:fit-content; overflow:hidden;">
    {#each [['latest','Latest Year'], ['trend','Trend Over Years']] as [val, label]}
        <button
            on:click={() => localView = val}
            style={'padding:7px 18px; font-size:0.875rem; cursor:pointer; border:none; border-right: 1px solid #D9DDE3; background: ' + (viewMode === val ? '#C8122C' : 'white') + '; color: ' + (viewMode === val ? 'white' : '#231F20') + '; font-weight: ' + (viewMode === val ? 600 : 400)}
        >{label}</button>
    {/each}
</div>

{#if viewMode == 'latest'}

<p style="font-size:1.1rem; font-weight:700; color:#231F20; margin: 16px 0 16px 0;">Latest Year FY{overview?.[0]?.max_year_label ?? ''}</p>

<Grid cols=4>
    <BigValue data={overview} value=latest_budget fmt=usd2compactviz title="Latest Year Budget"/>
    <BigValue data={overview} value=yoy_pct fmt='0.0"%"' title="YoY Change"/>
    <BigValue data={overview} value=cagr_5y_pct fmt='0.0"%"' title="5-Year CAGR"/>
    <BigValue data={overview} value=cagr_10y_pct fmt='0.0"%"' title="10-Year CAGR"/>
</Grid>

---



{/if}

{#if viewMode == 'latest'}


<div style="display:flex; gap:8px; margin: 8px 0 14px 0;">
    {#each [['unit','Units'],['program','Programs'],['subprogram','Subprograms']] as [val, label]}
        <button
            on:click={() => paretoLevel = val}
            style={'border-radius:14px; padding:6px 14px; font-size:0.9rem; cursor:pointer; border: ' + (paretoLevel === val ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)') + '; background: ' + (paretoLevel === val ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white') + '; color: ' + (paretoLevel === val ? '#C8122C' : '#231F20') + '; font-weight: ' + (paretoLevel === val ? 700 : 500)}
        >{label}</button>
    {/each}
</div>

## {paretoTitle}


{#if paretoData?.length > 0}
    <ParetoInsight data={paretoData} entityLabel={paretoLevel + 's'}/>
    <ParetoBarChart
        data={paretoData}
        title=""
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

{#if yearly_rollup?.length > 0 && yoy_detail?.length > 0}
    <Grid cols=2>
        <ECharts
            height="320px"
            config={{
                title: { text: 'Total budget by fiscal year', left: 'left', top: 0, textStyle: chartTitleStyle },
                grid: getChartGrid(),
                tooltip: {
                    trigger: 'axis',
                    formatter: (params) => {
                        if (!params || params.length === 0) return '';
                        const values = params.map(p => {
                            if (p.seriesType === 'bar') return `${p.marker} Budget: ${usdCompact(p.value)}`;
                            return `${p.marker} Trend: ${usdCompact(p.value)}`;
                        });
                        return `<b>${params[0].axisValue}</b><br/>${values.join('<br/>')}`;
                    }
                },
                xAxis: { type: 'category', data: yearly_rollup.map((d) => String(d.fiscal_year)) },
                yAxis: { type: 'value', axisLabel: { formatter: (v) => usdCompact(v) } },
                series: [
                    {
                        type: 'bar', barMaxWidth: 36,
                        data: trendResults.chartData,
                        label: {
                            show: true, position: 'top', distance: 5,
                            color: '#231F20', fontSize: 11,
                            formatter: (p) => usdCompact(p.value)
                        },
                        labelLayout: { hideOverlap: true },
                        itemStyle: { color: '#FFC838' }, z: 1
                    },
                    {
                        type: 'line', smooth: true, name: 'Trend',
                        data: trendResults.trendPoints,
                        lineStyle: { color: '#C8122C', width: 3 },
                        symbol: 'none', z: 2
                    }
                ]
            }}
        />
        <ECharts
            height="320px"
            config={{
                title: { text: 'Year-over-year budget change', left: 'left', top: 0, textStyle: chartTitleStyle },
                grid: getChartGrid(),
                tooltip: {
                    trigger: 'axis',
                    formatter: (params) => {
                        if (!params || params.length === 0) return '';
                        const p = params[0];
                        const v = Number(p.value) || 0;
                        return `<b>${p.axisValue}</b><br/>YoY: ${v.toFixed(1)}%`;
                    }
                },
                xAxis: { type: 'category', data: yoy_detail.map((d) => String(d.fiscal_year)) },
                yAxis: { type: 'value', axisLabel: { formatter: (v) => `${Number(v).toFixed(0)}%` } },
                series: [
                    {
                        type: 'bar',
                        data: yoy_detail.map((d) => Number(d.change_pct) || 0),
                        label: { show: true, position: 'top', formatter: (p) => `${(Number(p.value) || 0).toFixed(1)}%` },
                        itemStyle: { color: (p) => ((Number(p.value) || 0) >= 0 ? '#2EAD6B' : '#C8122C') }
                    }
                ]
            }}
        />
    </Grid>
{:else}
    <Alert status=warning>No fiscal year data available for this agency.</Alert>
{/if}

---



## Fund Composition Over Time

{#if fund_trend?.length > 0}
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 14px 0;">
        {#each fundSeriesNames as name}
            <button
                on:click={() => toggleFundSeries(name)}
                style={'border-radius:14px; padding:6px 10px; font-size:0.9rem; display:inline-flex; align-items:center; gap:8px; cursor:pointer; border: ' + (selectedFundSeries === name ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)') + '; background: ' + (selectedFundSeries === name ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white') + '; box-shadow: ' + (selectedFundSeries === name ? '0 4px 10px rgba(200,20,44,0.08)' : 'none')}
                aria-pressed={selectedFundSeries === name}
            >
                <span style={'width:10px; height:10px; border-radius:50%; background: ' + (fund_trend.find(function(d) { return d.fund_type === name; })?.fund_color ?? '#4C4743') + '; display:inline-block;'}></span>
                <span style={'color:' + (selectedFundSeries === name ? '#C8122C' : '#231F20') + '; font-weight:' + (selectedFundSeries === name ? 700 : 500)}>{name}</span>
            </button>
        {/each}
    </div>
    <ECharts
        height="420px"
        config={{
            tooltip: {
                trigger: 'item',
                formatter: function(param) {
                    if (!param) return '';
                    const hoveredFund = param.seriesName;
                    const rows = fundTrendYears.slice()
                        .sort(function(a, b) { return Number(b) - Number(a); })
                        .map(function(year) {
                            const row = fund_trend.find(function(d) {
                                return String(d.fiscal_year) === year && d.fund_type === hoveredFund;
                            });
                            const v = row ? row.spend : 0;
                            const yearTotal = fund_trend
                                .filter(function(d) { return String(d.fiscal_year) === year; })
                                .reduce(function(sum, d) { return sum + (d.spend || 0); }, 0);
                            const pct = yearTotal > 0 ? ((v / yearTotal) * 100).toFixed(1) : '0.0';
                            const fmt = Math.abs(v) >= 1e9
                                ? '$' + (v/1e9).toFixed(2) + 'B'
                                : Math.abs(v) >= 1e6
                                    ? '$' + (v/1e6).toFixed(1) + 'M'
                                    : '$' + Math.round(v).toLocaleString();
                            return year + ': ' + fmt + ' (' + pct + '%)';
                        });
                    return '<b>' + hoveredFund + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 64, right: 24, top: 20, bottom: 40 },
            xAxis: { type: 'category', boundaryGap: false, data: fundTrendYears },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: function(v) {
                        const n = Number(v) || 0;
                        return Math.abs(n) >= 1e9 ? '$' + (n/1e9).toFixed(0) + 'B' : '$' + (n/1e6).toFixed(0) + 'M';
                    }
                },
                splitLine: { lineStyle: { color: '#D9DDE3' } }
            },
            series: Array.from(fundSeriesNames, function(name) {
                const fundColor = fund_trend.find(function(d) { return d.fund_type === name; })?.fund_color ?? '#4C4743';
                const hasSelection = Boolean(selectedFundSeries);
                const isSelected = !hasSelection || selectedFundSeries === name;
                return {
                    name: name,
                    type: 'line',
                    stack: 'total',
                    smooth: false,
                    symbol: 'circle',
                    symbolSize: 30,
                    showSymbol: true,
                    lineStyle: { width: 0 },
                    itemStyle: { opacity: 0 },
                    areaStyle: { color: fundColor, opacity: isSelected ? 0.85 : 0.06 },
                    emphasis: { focus: 'series' },
                    blur: { areaStyle: { opacity: 0.06 }, lineStyle: { opacity: 0.06 } },
                    data: fundTrendYears.map(function(y) {
                        const row = fund_trend.find(function(d) {
                            return String(d.fiscal_year) === y && d.fund_type === name;
                        });
                        return row ? row.spend : 0;
                    })
                };
            })
        }}
    />
{:else}
    <Alert status=warning>No fund trend data available for this agency.</Alert>
{/if}

---

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
<div style="overflow-x:auto; border-radius:8px; border:1px solid #E5E7EB;">
    <table style="width:100%; border-collapse:collapse; font-size:0.875rem;">
        <thead>
            <tr style="background:#F9FAFB; border-bottom:2px solid #C8122C;">
                <th
                    on:click={() => setDrillSort('name')}
                    style="text-align:left; padding:10px 14px; font-weight:700; color:#231F20; min-width:280px; cursor:pointer; user-select:none;"
                >
                    Unit / Program / Subprogram
                    {#if drillSortCol === 'name'}{drillSortDir === -1 ? ' ↓' : ' ↑'}{/if}
                </th>
                {#each drillViewYears as yr}
                    <th
                        on:click={() => setDrillSort('FY' + yr)}
                        style="text-align:right; padding:10px 14px; font-weight:700; color:#231F20; white-space:nowrap; cursor:pointer; user-select:none;"
                    >
                        FY{yr}{#if drillSortCol === 'FY' + yr}{drillSortDir === -1 ? ' ↓' : ' ↑'}{/if}
                    </th>
                {/each}
            </tr>
        </thead>
        <tbody>
            <tr style="background:#FFF7F0; border-bottom:1px solid #E5E7EB;">
                <td style="padding:10px 14px; font-weight:700; color:#C8122C;">Total</td>
                {#each drillViewYears as yr}
                    <td style="text-align:right; padding:10px 14px; font-weight:700; color:#C8122C;">{formatAmount(grandTotal['FY' + yr])}</td>
                {/each}
            </tr>
            {#each filteredUnitRows as unit}
                <tr
                    on:click={() => toggleUnit(unit.name)}
                    style="border-bottom:1px solid #E5E7EB; cursor:pointer; background:white;"
                    onmouseenter="this.style.background='#F9FAFB'"
                    onmouseleave="this.style.background='white'"
                >
                    <td style="padding:10px 14px; font-weight:600; color:#231F20;">
                        <span style="margin-right:8px; font-size:0.75rem; color:#C8122C;">{expandedUnits[unit.name] ? '▼' : '▶'}</span>
                        {unit.name}
                    </td>
                    {#each drillViewYears as yr}
                        <td style="text-align:right; padding:10px 14px; font-weight:600; color:#231F20;">{formatAmount(unit['FY' + yr])}</td>
                    {/each}
                </tr>
                {#if expandedUnits[unit.name]}
                    {#each getFilteredPrograms(unit.name) as prog}
                        <tr
                            on:click={() => toggleProgram(unit.name, prog.name)}
                            style="border-bottom:1px solid #F3F4F6; cursor:pointer; background:#FAFAFA;"
                            onmouseenter="this.style.background='#F3F4F6'"
                            onmouseleave="this.style.background='#FAFAFA'"
                        >
                            <td style="padding:8px 14px 8px 36px; color:#374151;">
                                <span style="margin-right:8px; font-size:0.75rem; color:#6B7280;">{expandedPrograms[unit.name + '||' + prog.name] ? '▼' : '▶'}</span>
                                {prog.name}
                            </td>
                            {#each drillViewYears as yr}
                                <td style="text-align:right; padding:8px 14px; color:#374151;">{formatAmount(prog['FY' + yr])}</td>
                            {/each}
                        </tr>
                        {#if expandedPrograms[unit.name + '||' + prog.name]}
                            {#each getFilteredSubprograms(unit.name, prog.name) as sub}
                                <tr style="border-bottom:1px solid #F3F4F6; background:#F9FAFB;">
                                    <td style="padding:7px 14px 7px 60px; color:#6B7280; font-style:italic;">{sub.name}</td>
                                    {#each drillViewYears as yr}
                                        <td style="text-align:right; padding:7px 14px; color:#6B7280;">{formatAmount(sub['FY' + yr])}</td>
                                    {/each}
                                </tr>
                            {/each}
                        {/if}
                    {/each}
                {/if}
            {/each}
        </tbody>
    </table>
</div>
{:else}
    <Alert status=warning>No unit data available for this agency.</Alert>
{/if}

{/if}

