---
# title: Budget Office
sidebar_position: 1
---

<div style="background: linear-gradient(135deg, #ede5f8 0%, #d4bef0 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #802cd7; margin-bottom: 0; display:flex; align-items:flex-end; justify-content:space-between; gap:24px; flex-wrap:wrap;">
    <div>
        <h1 style="color: #211030; font-size: 1.7rem; font-weight: 700; margin: 0;">🏛️ Budget Office View</h1>
        <p style="color: #6321a5; font-size: 0.95rem; margin: 4px 0 0 0;">Statewide Budget Analysis</p>
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

```sql g_fy
select distinct fiscal_year as fy from mbtsa.agency_level order by fiscal_year
```

```sql g_fund
select distinct fund_type from mbtsa.agency_level where fund_type is not null order by fund_type
```

```sql g_agency
select distinct agency_name from mbtsa.agency_level where agency_name is not null order by agency_name
```




```sql filtered
select
    cast(b.fiscal_year as int) as fiscal_year,
    b.agency_code,
    b.agency_name,
    b.fund_type,
    b.total_budget_amount as amount
from mbtsa.agency_level b
where (
    '${selectedFund}' in ('%', '', 'undefined')
    or '${selectedFund}' like '(select%'
    or lower(coalesce(b.fund_type, '')) like '${selectedFund}'
)
and (
    '${selectedAgency}' in ('%', '', 'undefined')
    or '${selectedAgency}' like '(select%'
    or lower(coalesce(b.agency_name, '')) like '${selectedAgency}'
)
```

```sql yearly_rollup
select fiscal_year, sum(amount) as total_budget
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
),
selected_year as (
    select
        case
            when '${selectedFy}' in ('%', '', 'undefined') then max(fiscal_year)
            when '${selectedFy}' like '(select%' then max(fiscal_year)
            else cast('${selectedFy}' as int)
        end as chosen_year
    from ${yearly_rollup}
)
select
    b.start_year,
    b.max_year,
    s.chosen_year as display_year,
    max(case when o.fiscal_year = s.chosen_year then o.total_budget end) as latest_budget,
    max(case when o.fiscal_year = s.chosen_year - 1 then o.total_budget end) as prior_budget,
    s.chosen_year - 1 as prior_year,
    b.total_budget
from bounds b
cross join selected_year s
left join ordered o on true
where b.max_year is not null
group by b.start_year, b.max_year, b.total_budget, s.chosen_year
```

```sql filtered_latest
select f.*
from ${filtered} f
cross join ${scope_meta} m
where f.fiscal_year = m.display_year
```

```sql filtered_prior
select f.*
from ${filtered} f
cross join ${scope_meta} m
where f.fiscal_year = m.prior_year
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
    coalesce(cast(display_year as varchar), 'N/A') as max_year_label
from points
```

```sql yearly
select fiscal_year, total_budget
from ${yearly_rollup}
order by fiscal_year
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
    -- CPI-based inflation multipliers anchored to first year in data
    -- Using US CPI annual averages; first year in data = multiplier 1.000
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

```sql snapshot_agencies
select
    agency_name,
    sum(amount) as spend,
    round(sum(amount) * 100.0 / nullif(sum(sum(amount)) over (), 0), 1) as pct_of_total,
    sum(sum(amount)) over (order by sum(amount) desc rows between unbounded preceding and current row) as cumulative,
    sum(sum(amount)) over () as grand_total
from ${filtered_latest}
where agency_name is not null
group by agency_name
order by spend desc
limit 10
```

```sql fund_rules
select *
from (
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
) as rules(pattern, fund_rank, fund_color, is_like)
```

```sql fund_profile
with distinct_funds as (
    select distinct fund_type from ${filtered} where fund_type is not null
),
matches as (
    select
        d.fund_type,
        r.fund_rank,
        r.fund_color,
        row_number() over (partition by d.fund_type order by r.fund_rank) as rank_order
    from distinct_funds d
    join ${fund_rules} r
        on (
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

```sql fund_snapshot
with latest as (
    select fund_type, sum(amount) as latest_budget
    from ${filtered_latest}
    where fund_type is not null and trim(fund_type) <> ''
    group by fund_type
),
prior as (
    select fund_type, sum(amount) as prior_budget
    from ${filtered_prior}
    where fund_type is not null and trim(fund_type) <> ''
    group by fund_type
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
    coalesce(p.prior_budget, 0) as prior_budget,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_change_pct,
    round(case when h5.budget_5y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h5.budget_5y_ago, 1.0/5.0) - 1.0) * 100.0
        else null end, 1) as cagr_5y_pct,
    round(case when h10.budget_10y_ago > 0 and l.latest_budget > 0
        then (power(l.latest_budget / h10.budget_10y_ago, 1.0/10.0) - 1.0) * 100.0
        else null end, 1) as cagr_10y_pct,
    round(l.latest_budget * 100.0 / nullif(m.latest_budget, 0), 1) as latest_year_pct,
    coalesce(fp.fund_color, '#4C4743') as fund_color
from latest l
left join prior p using (fund_type)
left join hist_5y h5 using (fund_type)
left join hist_10y h10 using (fund_type)
cross join ${scope_meta} m
left join ${fund_profile} fp on fp.fund_type = l.fund_type
order by l.latest_budget desc
```

```sql agency_movers
with latest as (
    select agency_name, sum(amount) as latest_budget
    from ${filtered_latest}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
),
prior as (
    select agency_name, sum(amount) as prior_budget
    from ${filtered_prior}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
)
select
    l.agency_name,
    l.latest_budget,
    coalesce(p.prior_budget, 0) as prior_budget,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as pct_change
from latest l
left join prior p using (agency_name)
order by abs(l.latest_budget - coalesce(p.prior_budget, 0)) desc
limit 20
```

```sql fund_trend
select
    f.fiscal_year,
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

```sql top_agencies_trend
select agency_name, sum(amount) as total_budget
from ${filtered}
where agency_name is not null
group by agency_name
order by total_budget desc
limit 10
```

```sql agency_trend_lines
select
    f.fiscal_year,
    f.agency_name,
    sum(f.amount) as spend
from ${filtered} f
where f.agency_name in (select agency_name from ${top_agencies_trend})
    and f.agency_name is not null
group by f.fiscal_year, f.agency_name
order by f.fiscal_year
```

```sql agency_drill
select
    agency_name,
    fiscal_year,
    sum(amount) as spend
from ${filtered}
where agency_name is not null
group by agency_name, fiscal_year
order by agency_name, fiscal_year
```

```sql agency_latest
with latest as (
    select agency_name, sum(amount) as latest_budget
    from ${filtered_latest}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
),
prior as (
    select agency_name, sum(amount) as prior_budget
    from ${filtered_prior}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
),
hist_5y as (
    select f.agency_name, sum(f.amount) as budget_5y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.agency_name is not null and trim(f.agency_name) <> ''
        and f.fiscal_year = m.max_year - 5
    group by f.agency_name
),
hist_10y as (
    select f.agency_name, sum(f.amount) as budget_10y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.agency_name is not null and trim(f.agency_name) <> ''
        and f.fiscal_year = m.max_year - 10
    group by f.agency_name
)
select
    l.agency_name,
    '/budget-office/agencies/' || replace(l.agency_name, ' ', '%20') as agency_link,
    l.latest_budget,
    l.latest_budget - coalesce(p.prior_budget, 0) as dollar_change,
    round((l.latest_budget - coalesce(p.prior_budget, 0)) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_change_pct,
    round(
        case when h5.budget_5y_ago > 0 and l.latest_budget > 0
            then (power(l.latest_budget / h5.budget_5y_ago, 1.0/5.0) - 1.0) * 100.0
            else null end, 1
    ) as cagr_5y_pct,
    round(
        case when h10.budget_10y_ago > 0 and l.latest_budget > 0
            then (power(l.latest_budget / h10.budget_10y_ago, 1.0/10.0) - 1.0) * 100.0
            else null end, 1
    ) as cagr_10y_pct,
    round(l.latest_budget * 100.0 / nullif(m.latest_budget, 0), 1) as latest_year_pct
from latest l
left join prior p using (agency_name)
left join hist_5y h5 using (agency_name)
left join hist_10y h10 using (agency_name)
cross join ${scope_meta} m
order by l.latest_budget desc
```

<script>
    import { getInputContext } from '@evidence-dev/sdk/utils/svelte';
    import { goto } from '$app/navigation';

    const inputStore = getInputContext();

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

    const selectedValue = (entry, lower = true) => {
        const val = readInputValue(entry, '%').replace(/'/g, "''");
        return lower ? val.toLowerCase() : val;
    };

    const usdCompact = (value) => {
        const num = Number(value) || 0;
        const abs = Math.abs(num);
        if (abs >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
        if (abs >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
        if (abs >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
        return `$${num.toFixed(2)}`;
    };

    const chartHeight = '320px';
    const chartTitleStyle = { fontSize: 14, fontWeight: 600, color: '#231F20' };
    const getChartGrid = () => ({ top: '15%', right: '4%', bottom: '11%', left: '8%', containLabel: true });

    const calculateTrendResults = (data, valueKey) => {
        if (!data || data.length < 2) return { chartData: [], trendPoints: [] };
        const values = data.map((d) => Number(d[valueKey]) || 0);
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

    const sparkline = (row, years) => {
        const vals = years.map(y => row['FY' + y] || 0);
        const max = Math.max(...vals);
        if (max === 0) return '';
        const w = 48;
        const h = 16;
        const points = vals.map((v, i) => {
            const x = (i / (vals.length - 1)) * w;
            const y = h - (v / max) * h;
            return x + ',' + y;
        }).join(' ');
        const last = vals[vals.length - 1];
        const prev = vals[vals.length - 2] ?? last;
        const color = last >= prev ? '#2EAD6B' : '#C8122C';
        return '<svg width="' + w + '" height="' + h + '" style="display:inline-block;vertical-align:middle;margin-left:8px;"><polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linejoin="round"/><circle cx="' + (w) + '" cy="' + (h - (last/max)*h) + '" r="2" fill="' + color + '"/></svg>';
    };

    const cellTint = (row, yr, allYears) => {
        const idx = allYears.indexOf(yr);
        if (idx <= 0) return '';
        const curr = row['FY' + yr] || 0;
        const prev = row['FY' + allYears[idx - 1]] || 0;
        if (prev === 0) return '';
        const pct = (curr - prev) / prev * 100;
        if (pct >= 15) return 'background:rgba(46,173,107,0.18);';
        if (pct >= 8) return 'background:rgba(46,173,107,0.11);';
        if (pct >= 3) return 'background:rgba(46,173,107,0.06);';
        if (pct > 0) return 'background:rgba(46,173,107,0.03);';
        if (pct <= -15) return 'background:rgba(200,18,44,0.18);';
        if (pct <= -8) return 'background:rgba(200,18,44,0.11);';
        if (pct <= -3) return 'background:rgba(200,18,44,0.06);';
        return 'background:rgba(200,18,44,0.03);';
    };

    let localView = 'trend';
    let pivotYearView = '3y';
    let searchTerm = '';
    let selectedFundSeries = null;
    let selectedAgencyLine = null;

    $: selectedFy = selectedValue($inputStore?.f_fy, false);
    $: selectedFund = selectedValue($inputStore?.f_fund);
    $: selectedAgency = selectedValue($inputStore?.f_agency);


    $: agencyTableColumns = [
        { id: 'agency_name', title: 'Agency', align: 'left' },
        { id: 'latest_budget', title: `Latest Year (${overview?.[0]?.max_year_label ?? 'N/A'})`, fmt: 'money', sortable: true },
        { id: 'latest_year_pct', title: '% of Total', fmt: 'pct', sortable: true },
        { id: 'dollar_change', title: 'YoY Change ($)', fmt: 'money', conditional: true, sortable: true },
        { id: 'yoy_change_pct', title: 'YoY Change (%)', fmt: 'pct', conditional: true, sortable: true },

    ];

    $: fundTableColumns = [
        { id: 'fund_type', title: 'Fund Type', align: 'left' },
        { id: 'latest_budget', title: `Latest Year (${overview?.[0]?.max_year_label ?? 'N/A'})`, fmt: 'money', sortable: true },
        { id: 'latest_year_pct', title: '% of Total', fmt: 'pct', sortable: true },
        { id: 'dollar_change', title: 'YoY Change ($)', fmt: 'money', conditional: true, sortable: true },
        { id: 'yoy_change_pct', title: 'YoY Change (%)', fmt: 'pct', conditional: true, sortable: true }
    ];

    const toggleAgencyLine = (name) => {
        selectedAgencyLine = selectedAgencyLine === name ? null : name;
    };

    const toggleFundSeries = (name) => {
        selectedFundSeries = selectedFundSeries === name ? null : name;
    };

    const fundTypeDescriptions = {
        'Federal Funds': 'Federal aid and grant funding used to support state programs.',
        'General Funds': 'State general revenue used for core operations and services.',
        'Special Funds': 'Dedicated or restricted funds assigned to specific purposes.',
        'American Rescue Plan Act of 21': 'Federal recovery funding from the American Rescue Plan Act.',
        'Coronavirus Aid, Relief, and Economic Security Act': 'Federal emergency relief funding from the CARES Act.',
        'Coronavirus Response and Relief Sup Act': 'Federal pandemic response funding from the CRRSA Act.',
        'Federal Funds (COVID)': 'Federal COVID-era relief and recovery funding.',
        'Current Unrestricted Funds': 'Current-year unrestricted dollars available for use.',
        'Current Restricted Funds': 'Current-year restricted dollars tied to specific requirements.',
        'Federal Funds (ARRA)': 'Federal stimulus funding from the American Recovery and Reinvestment Act.'
    };

    $: selectedFy = selectedValue($inputStore?.f_fy);
    $: selectedFund = selectedValue($inputStore?.f_fund);
    $: selectedAgency = selectedValue($inputStore?.f_agency);
    $: viewMode = localView;
    $: trendResults = calculateTrendResults(yearly, 'total_budget');
    $: cagrPct = fiscal_overview_cagr?.[0]?.cagr_pct != null ? Number(fiscal_overview_cagr[0].cagr_pct).toFixed(1) : null;
    $: fundTrendYears = [...new Set(fund_trend.map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: fundSeriesTotals = fund_trend.reduce((acc, row) => {
        const key = row.fund_type ?? 'Unknown';
        acc[key] = (acc[key] || 0) + (Number(row.spend) || 0);
        return acc;
    }, {});
    $: fundSeriesNames = [...new Set(fund_trend.map(d => d.fund_type))].sort((a, b) => {
        const totalDiff = (fundSeriesTotals[b] || 0) - (fundSeriesTotals[a] || 0);
        if (Math.abs(totalDiff) > 0.000001) return totalDiff;
        return String(a).localeCompare(String(b));
    });
    $: agencyLineTrendYears = [...new Set((agency_trend_lines ?? []).map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: highlightedAgencyNames = (top_agencies_trend ?? []).slice(0, 3).map(a => a.agency_name);
    $: pivotYears = [...new Set((agency_drill ?? []).map(d => d.fiscal_year))].sort((a, b) => a - b);
    $: agency_pivot = Object.values(
        (agency_drill ?? []).reduce(function(acc, row) {
            const key = row.agency_name;
            if (!acc[key]) acc[key] = { agency_name: row.agency_name };
            acc[key]['FY' + row.fiscal_year] = (acc[key]['FY' + row.fiscal_year] || 0) + row.spend;
            return acc;
        }, {})
    );
    $: pivotViewYears = (() => {
        if (pivotYearView === '3y') return pivotYears.slice(-3);
        if (pivotYearView === '5y') return pivotYears.slice(-5);
        return pivotYears;
    })();
    $: filteredPivot = searchTerm
        ? agency_pivot.filter(function(r) {
            return r.agency_name.toLowerCase().includes(searchTerm.toLowerCase());
        })
        : agency_pivot;
    $: sortedPivot = pivotViewYears.length > 0
        ? filteredPivot.slice().sort(function(a, b) {
            const lastYr = 'FY' + pivotViewYears[pivotViewYears.length - 1];
            return (b[lastYr] || 0) - (a[lastYr] || 0);
        }).map(function(r) {
            return Object.assign({}, r, {
                agency_link: '/budget-office/agencies/' + encodeURIComponent(r.agency_name)
            });
        })
        : filteredPivot.map(function(r) {
            return Object.assign({}, r, {
                agency_link: '/budget-office/agencies/' + encodeURIComponent(r.agency_name)
            });
        });
</script>


<div id="page-filters">
    <Details title="🔍 Filters" open=false>
        <Grid cols=3>
            <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Years"/>
            </Dropdown>
            <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Fund Types"/>
            </Dropdown>
            <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Agencies"/>
            </Dropdown>
        </Grid>
    </Details>
</div>

<FilterSidebar title="⚙ Filters" targetId="page-filters"/>

<div style="display:none;">
    <Dropdown name=f_view title="View" defaultValue="trend">
        <DropdownOption value="trend" valueLabel="Trend Over Years"/>
        <DropdownOption value="latest" valueLabel="Latest Year Snapshot"/>
    </Dropdown>
</div>

{#if viewMode == 'latest'}

<div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin:16px 0;">
    <div style="background:var(--nxt-surface); border:1px solid var(--nxt-border); border-left:4px solid #C8122C; border-radius:8px; padding:16px 28px; min-width:200px; text-align:center;">
        <div style="font-size:11px; font-weight:500; color:#6B7280; text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px;">Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})</div>
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
## Top 10 agencies by budget — Latest Year

{#if snapshot_agencies?.length > 0}
    <ParetoInsight data={snapshot_agencies} entityLabel="agencies"/>
    <ParetoBarChart
        data={snapshot_agencies}
        title=""
        barField="spend"
        labelField="agency_name"
        pctField="pct_of_total"
        cumulativeField="cumulative"
        totalField="grand_total"
        height="420px"
    />
{:else}
    <Alert status=warning>No agency snapshot data available for this filter selection.</Alert>
{/if}

---

## Fund type share — Latest Year

{#if fund_snapshot?.length > 0}
    <DonutFundSnapshot
        data={fund_snapshot}
        fund_profile={fund_profile}
        title=""
        height="420px"
        nameField="fund_type"
        valueField="latest_budget"
        pctField="latest_year_pct"
    />
    <ConditionalTable
        data={fund_snapshot}
        columns={fundTableColumns}
        search={true}
        defaultSort="latest_budget"
        defaultDir={-1}
    />
{:else}
    <Alert status=warning>No fund type data available for this filter selection.</Alert>
{/if}

---

## Budget Changes — Year over Year

<Alert status=info>Agencies sorted by absolute dollar change from prior year.</Alert>

<BudgetChangesChart
    data={agency_movers}
    labelField="agency_name"
    title="Biggest budget changes vs prior year"
    height="520px"
    limit={10}
/>

---

## Agency Drill-Down Table — Click a row to open the Agency page

{#if agency_latest?.length > 0}
    <ConditionalTable
        data={agency_latest}
        columns={agencyTableColumns}
        linkField="agency_link"
        search={true}
        defaultSort="latest_budget"
        defaultDir={-1}
    />
{:else}
    <Alert status=warning>No agency data available for this filter selection.</Alert>
{/if}

{/if}

{#if viewMode == 'trend'}

---

## Fiscal Overview

<TrendOverview
    {yearly}
    yoyDetail={yoy_detail}
    fiscalOverviewCagr={fiscal_overview_cagr}
    {cagrPct}
    {chartHeight}
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
    <Alert status=warning>No fund trend data available for this filter selection.</Alert>
{/if}
---

## Top Agencies by Budget — Trend Over Time

{#if agency_trend_lines?.length > 0}
    <AgencyTrendChart
        agencies={top_agencies_trend}
        trendLines={agency_trend_lines}
        years={agencyLineTrendYears}
        title="Top Agencies by Budget — Trend Over Time"
        entityLabel="agency"
        topN={5}
        height="520px"
    />
{:else}
    <Alert status=warning>No agency trend data available for this filter selection.</Alert>
{/if}

---

## Agency Budget by Year - Click on Agency to drill to its specific Page

<div style="display:flex; gap:8px; margin: 8px 0 14px 0;">
    {#each [['3y','Last 3 Years'],['5y','Last 5 Years'],['all','All Years']] as [val, label]}
        <button
            on:click={() => pivotYearView = val}
            style={'border-radius:14px; padding:6px 14px; font-size:0.9rem; cursor:pointer; border: ' + (pivotYearView === val ? '2px solid #C8122C' : '1px solid var(--nxt-border)') + '; background: ' + (pivotYearView === val ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'var(--nxt-surface)') + '; color: ' + (pivotYearView === val ? '#C8122C' : '#231F20') + '; font-weight: ' + (pivotYearView === val ? 700 : 500)}
        >{label}</button>
    {/each}
</div>

<input
    bind:value={searchTerm}
    placeholder="Search agencies..."
    style="border: 1px solid var(--nxt-border); border-radius: 8px; padding: 8px 12px; font-size: 0.9rem; width: 280px; margin-bottom: 12px; background:var(--nxt-surface); color:var(--nxt-text);"
/>

{#if sortedPivot?.length > 0}
<div style="overflow-x:auto; border-radius:8px; border:1px solid var(--nxt-border); background:var(--nxt-surface);">
    <table style="width:100%; border-collapse:collapse; font-size:0.875rem;">
        <thead>
            <tr style="background:var(--nxt-pink); border-bottom:2px solid #C8122C;">
                <th style="text-align:left; padding:10px 14px; font-weight:700; color:#231F20; min-width:260px;">Agency</th>
                {#each pivotViewYears as yr}
                    <th style="text-align:right; padding:10px 14px; font-weight:700; color:#231F20; white-space:nowrap;">FY{yr}</th>
                {/each}
                <th style="padding:10px 8px;"></th>
            </tr>
        </thead>
        <tbody>
            {#each sortedPivot as row, i}
                <tr
                    on:click={() => goto(row.agency_link)}
                    style={'border-bottom:1px solid #F3F4F6; cursor:pointer; background:' + (i % 2 === 0 ? 'var(--nxt-surface)' : '#f7f2fc') + ';'}
                    onmouseenter="this.style.background='var(--nxt-pink)'"
                    onmouseleave={'this.style.background=' + (i % 2 === 0 ? "'var(--nxt-surface)'" : "'#f7f2fc'") + ''}
                >
                    <td style="padding:9px 14px; color:#231F20; font-weight:500;">
                        {row.agency_name}
                        {@html sparkline(row, pivotViewYears)}
                    </td>
                    {#each pivotViewYears as yr}
                        <td style={'text-align:right; padding:9px 14px; color:#231F20; ' + cellTint(row, yr, pivotViewYears)}>
                            {(row['FY' + yr] ?? 0) >= 1e9
                                ? '$' + ((row['FY' + yr])/1e9).toFixed(2) + 'B'
                                : (row['FY' + yr] ?? 0) >= 1e6
                                    ? '$' + ((row['FY' + yr])/1e6).toFixed(1) + 'M'
                                    : (row['FY' + yr] ?? 0) >= 1e3
                                        ? '$' + ((row['FY' + yr])/1e3).toFixed(0) + 'K'
                                        : '-'}
                        </td>
                    {/each}
                    <td style="padding:9px 8px; color:#C8122C; font-size:0.8rem;">›</td>
                </tr>
            {/each}
        </tbody>
    </table>
</div>
{:else}
    <Alert status=warning>No agency data available for this filter selection.</Alert>
{/if}

{/if}