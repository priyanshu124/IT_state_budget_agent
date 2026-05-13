---
title: Technology
sidebar_position: 3
---

<div style="background: linear-gradient(135deg, #ede5f8 0%, #d4bef0 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #802cd7; margin-bottom: 0; display:flex; align-items:flex-end; justify-content:space-between; gap:24px; flex-wrap:wrap;">
    <div>
        <h1 style="color: #211030; font-size: 1.7rem; font-weight: 700; margin: 0;">💻 Technology View</h1>
        <p style="color: #6321a5; font-size: 0.95rem; margin: 4px 0 0 0;">IT Spending Analysis · TBM v5.0.1 Classification</p>
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
select distinct fiscal_year as fy from mbtsa.subprogram_level order by fiscal_year
```

```sql g_fund
select distinct fund_type from mbtsa.subprogram_level where fund_type is not null order by fund_type
```

```sql g_agency
select distinct agency_name from mbtsa.subprogram_level where agency_name is not null order by agency_name
```

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

```sql filtered
select
    cast(t.fiscal_year as int) as fiscal_year,
    t.agency_code,
    t.agency_name,
    t.program_name,
    t.subprogram_name,
    t.fund_type,
    t.it_tower,
    t.it_sub_tower,
    t.it_designation,
    t.total_budget_amount as amount
from mbtsa.subprogram_level t
where t.is_it = true
    and (
        '${selectedFy}' in ('%', '', 'undefined')
        or '${selectedFy}' like '(select%'
        or cast(t.fiscal_year as varchar) = '${selectedFy}'
    )
    and (
        '${selectedFund}' in ('%', '', 'undefined')
        or '${selectedFund}' like '(select%'
        or lower(coalesce(t.fund_type, '')) like lower('${selectedFund}')
    )
    and (
        '${selectedAgency}' in ('%', '', 'undefined')
        or '${selectedAgency}' like '(select%'
        or lower(coalesce(t.agency_name, '')) like lower('${selectedAgency}')
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
    max(case when o.fiscal_year = s.chosen_year then o.total_budget end) as latest_it_spend,
    max(case when o.fiscal_year = s.chosen_year - 1 then o.total_budget end) as prior_it_spend,
    s.chosen_year - 1 as prior_year,
    b.total_budget,
    max(case when o.year_rank = 2 then o.fiscal_year end) as prior_max_year
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
        y_5.total_budget as spend_5y_ago,
        y_10.total_budget as spend_10y_ago
    from ${scope_meta} m
    left join ${yearly_rollup} y_5 on y_5.fiscal_year = m.max_year - 5
    left join ${yearly_rollup} y_10 on y_10.fiscal_year = m.max_year - 10
)
select
    total_budget as total_it_spend,
    latest_it_spend,
    latest_it_spend - coalesce(prior_it_spend, 0) as dollar_change,
    round((latest_it_spend - coalesce(prior_it_spend, 0)) * 100.0 / nullif(prior_it_spend, 0), 1) as yoy_pct,
    round(
        case
            when spend_5y_ago > 0 and latest_it_spend > 0
                then (power(latest_it_spend / spend_5y_ago, 1.0 / 5.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(
        case
            when spend_10y_ago > 0 and latest_it_spend > 0
                then (power(latest_it_spend / spend_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
            else null
        end,
        1
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
        first_value(total_budget) over (order by fiscal_year) as base_spend,
        last_value(total_budget) over (order by fiscal_year rows between unbounded preceding and unbounded following) as final_spend,
        row_number() over (order by fiscal_year) - 1 as yr_idx,
        count(*) over () - 1 as total_years
    from ${yearly_rollup}
),
cagr_calc as (
    select
        fiscal_year,
        total_budget,
        base_spend,
        final_spend,
        yr_idx,
        total_years,
        round(
            case when total_years > 0 and base_spend > 0 and final_spend > 0
                then (power(final_spend / base_spend, 1.0 / total_years) - 1.0) * 100.0
                else null
            end, 2
        ) as cagr_pct
    from base
)
select
    fiscal_year,
    total_budget,
    round(base_spend * power(1.0 + cagr_pct / 100.0, yr_idx), 2) as cagr_trend,
    -- CPI-based inflation multipliers anchored to first year in data
    -- Using US CPI annual averages; first year in data = multiplier 1.000
    round(base_spend * case fiscal_year
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

```sql snapshot_towers
select
    it_tower,
    sum(amount) as spend,
    round(sum(amount) * 100.0 / nullif(sum(sum(amount)) over (), 0), 1) as pct_of_total,
    sum(sum(amount)) over (order by sum(amount) desc rows between unbounded preceding and current row) as cumulative,
    sum(sum(amount)) over () as grand_total
from ${filtered_latest}
where it_tower is not null
group by it_tower
order by spend desc
```

```sql snapshot_subprograms
select
    subprogram_name,
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

```sql tower_snapshot
with latest as (
    select it_tower, sum(amount) as latest_spend
    from ${filtered_latest}
    where it_tower is not null and trim(it_tower) <> ''
    group by it_tower
),
prior as (
    select it_tower, sum(amount) as prior_spend
    from ${filtered_prior}
    where it_tower is not null and trim(it_tower) <> ''
    group by it_tower
),
hist_5y as (
    select f.it_tower, sum(f.amount) as spend_5y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.it_tower is not null and trim(f.it_tower) <> ''
        and f.fiscal_year = m.max_year - 5
    group by f.it_tower
),
hist_10y as (
    select f.it_tower, sum(f.amount) as spend_10y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.it_tower is not null and trim(f.it_tower) <> ''
        and f.fiscal_year = m.max_year - 10
    group by f.it_tower
)
select
    l.it_tower,
    l.latest_spend,
    coalesce(p.prior_spend, 0) as prior_spend,
    l.latest_spend - coalesce(p.prior_spend, 0) as dollar_change,
    round((l.latest_spend - coalesce(p.prior_spend, 0)) * 100.0 / nullif(p.prior_spend, 0), 1) as yoy_change_pct,
    round(case when h5.spend_5y_ago > 0 and l.latest_spend > 0
        then (power(l.latest_spend / h5.spend_5y_ago, 1.0/5.0) - 1.0) * 100.0
        else null end, 1) as cagr_5y_pct,
    round(case when h10.spend_10y_ago > 0 and l.latest_spend > 0
        then (power(l.latest_spend / h10.spend_10y_ago, 1.0/10.0) - 1.0) * 100.0
        else null end, 1) as cagr_10y_pct,
    round(l.latest_spend * 100.0 / nullif(m.latest_it_spend, 0), 1) as latest_year_pct
from latest l
left join prior p using (it_tower)
left join hist_5y h5 using (it_tower)
left join hist_10y h10 using (it_tower)
cross join ${scope_meta} m
order by l.latest_spend desc
```


```sql agency_movers
with latest as (
    select agency_name, sum(amount) as latest_spend
    from ${filtered_latest}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
),
prior as (
    select agency_name, sum(amount) as prior_spend
    from ${filtered_prior}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
)
select
    l.agency_name,
    l.latest_spend,
    coalesce(p.prior_spend, 0) as prior_spend,
    l.latest_spend - coalesce(p.prior_spend, 0) as dollar_change,
    round((l.latest_spend - coalesce(p.prior_spend, 0)) * 100.0 / nullif(p.prior_spend, 0), 1) as pct_change
from latest l
left join prior p using (agency_name)
order by abs(l.latest_spend - coalesce(p.prior_spend, 0)) desc
limit 20
```

```sql agency_latest
with latest as (
    select agency_name, sum(amount) as latest_spend
    from ${filtered_latest}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
),
prior as (
    select agency_name, sum(amount) as prior_spend
    from ${filtered_prior}
    where agency_name is not null and trim(agency_name) <> ''
    group by agency_name
),
hist_5y as (
    select f.agency_name, sum(f.amount) as spend_5y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.agency_name is not null and trim(f.agency_name) <> ''
        and f.fiscal_year = m.max_year - 5
    group by f.agency_name
),
hist_10y as (
    select f.agency_name, sum(f.amount) as spend_10y_ago
    from ${filtered} f cross join ${scope_meta} m
    where f.agency_name is not null and trim(f.agency_name) <> ''
        and f.fiscal_year = m.max_year - 10
    group by f.agency_name
)
select
    l.agency_name,
    '/technology/agencies/' || replace(l.agency_name, ' ', '%20') as agency_link,
    l.latest_spend,
    l.latest_spend - coalesce(p.prior_spend, 0) as dollar_change,
    round((l.latest_spend - coalesce(p.prior_spend, 0)) * 100.0 / nullif(p.prior_spend, 0), 1) as yoy_change_pct,
    round(
        case when h5.spend_5y_ago > 0 and l.latest_spend > 0
            then (power(l.latest_spend / h5.spend_5y_ago, 1.0/5.0) - 1.0) * 100.0
            else null end, 1
    ) as cagr_5y_pct,
    round(
        case when h10.spend_10y_ago > 0 and l.latest_spend > 0
            then (power(l.latest_spend / h10.spend_10y_ago, 1.0/10.0) - 1.0) * 100.0
            else null end, 1
    ) as cagr_10y_pct,
    round(l.latest_spend * 100.0 / nullif(m.latest_it_spend, 0), 1) as latest_year_pct
from latest l
left join prior p using (agency_name)
left join hist_5y h5 using (agency_name)
left join hist_10y h10 using (agency_name)
cross join ${scope_meta} m
order by l.latest_spend desc
```

```sql top_towers_trend
select
    it_tower,
    sum(amount) as total_it_spend
from ${filtered}
where it_tower is not null
group by it_tower
order by total_it_spend desc
limit 10
```

```sql tower_trend
with tower_spend as (
    select
        f.fiscal_year,
        f.it_tower,
        sum(f.amount) as spend
    from ${filtered} f
    where f.it_tower in (select it_tower from ${top_towers_trend})
    group by f.fiscal_year, f.it_tower
),
yearly_totals as (
    select fiscal_year, total_budget as total_it_spend
    from ${yearly_rollup}
)
select
    t.fiscal_year,
    t.it_tower,
    t.spend,
    t.spend / nullif(y.total_it_spend, 0) as pct_of_total
from tower_spend t
left join yearly_totals y on y.fiscal_year = t.fiscal_year
order by t.fiscal_year
```

```sql top_agencies_trend
select agency_name, sum(amount) as total_it_spend
from ${filtered}
where agency_name is not null
group by agency_name
order by total_it_spend desc
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
    let selectedTower = null;
    let selectedAgencyLine = null;

    $: selectedFy = selectedValue($inputStore?.f_fy, false);
    $: selectedFund = selectedValue($inputStore?.f_fund);
    $: selectedAgency = selectedValue($inputStore?.f_agency);
    $: viewMode = localView;
    $: trendResults = calculateTrendResults(yearly, 'total_budget');
    $: cagrPct = fiscal_overview_cagr?.[0]?.cagr_pct != null ? Number(fiscal_overview_cagr[0].cagr_pct).toFixed(1) : null;

    $: towerTrendYears = [...new Set(tower_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: highlightedTowerNames = (top_towers_trend ?? []).slice(0, 3).map((t) => t.it_tower);

    $: agencyLineTrendYears = [...new Set((agency_trend_lines ?? []).map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: highlightedAgencyNames = (top_agencies_trend ?? []).slice(0, 3).map(a => a.agency_name);

    $: agencyTableColumns = [
        { id: 'agency_name', title: 'Agency', align: 'left' },
        { id: 'latest_spend', title: `Latest Year (${overview?.[0]?.max_year_label ?? 'N/A'})`, fmt: 'money', sortable: true },
        { id: 'latest_year_pct', title: '% of IT Total', fmt: 'pct', sortable: true },
        { id: 'dollar_change', title: 'YoY Change ($)', fmt: 'money', conditional: true, sortable: true },
        { id: 'yoy_change_pct', title: 'YoY Change (%)', fmt: 'pct', conditional: true, sortable: true },
    ];

    $: towerTableColumns = [
        { id: 'it_tower', title: 'IT Tower', align: 'left' },
        { id: 'latest_spend', title: `Latest Year (${overview?.[0]?.max_year_label ?? 'N/A'})`, fmt: 'money', sortable: true },
        { id: 'latest_year_pct', title: '% of IT Total', fmt: 'pct', sortable: true },
        { id: 'dollar_change', title: 'YoY Change ($)', fmt: 'money', conditional: true, sortable: true },
        { id: 'yoy_change_pct', title: 'YoY Change (%)', fmt: 'pct', conditional: true, sortable: true },
    ];

    $: pivotYears = [...new Set((agency_drill ?? []).map(d => d.fiscal_year))].sort((a, b) => a - b);
    $: tower_agency_pivot = Object.values(
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
        ? tower_agency_pivot.filter(function(r) {
            return r.agency_name.toLowerCase().includes(searchTerm.toLowerCase());
        })
        : tower_agency_pivot;
    $: sortedPivot = pivotViewYears.length > 0
        ? filteredPivot.slice().sort(function(a, b) {
            const lastYr = 'FY' + pivotViewYears[pivotViewYears.length - 1];
            return (b[lastYr] || 0) - (a[lastYr] || 0);
        }).map(function(r) {
            return Object.assign({}, r, {
                agency_link: '/technology/agencies/' + encodeURIComponent(r.agency_name)
            });
        })
        : filteredPivot.map(function(r) {
            return Object.assign({}, r, {
                agency_link: '/technology/agencies/' + encodeURIComponent(r.agency_name)
            });
        });

    const toggleTower = (name) => {
        selectedTower = selectedTower === name ? null : name;
    };

    const toggleAgencyLine = (name) => {
        selectedAgencyLine = selectedAgencyLine === name ? null : name;
    };
</script>

{#if viewMode == 'latest'}

<div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin:16px 0;">
    <div style="background:var(--nxt-surface); border:1px solid var(--nxt-border); border-left:4px solid #C8122C; border-radius:8px; padding:16px 28px; min-width:200px; text-align:center;">
        <div style="font-size:11px; font-weight:500; color:#6B7280; text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px;">Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})</div>
        <div style="font-size:1.8rem; font-weight:700; color:#231F20;">{(() => { const n = Number(overview?.[0]?.latest_it_spend)||0; const abs=Math.abs(n); if(abs>=1e9) return '$'+(abs/1e9).toFixed(2)+'B'; if(abs>=1e6) return '$'+(abs/1e6).toFixed(1)+'M'; return '$'+Math.round(abs).toLocaleString(); })()}</div>
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

## Top IT Towers by Spend — Latest Year

{#if snapshot_towers?.length > 0}
    <ParetoInsight data={snapshot_towers} entityLabel="IT towers"/>
    <ParetoBarChart
        data={snapshot_towers}
        title=""
        barField="spend"
        labelField="it_tower"
        pctField="pct_of_total"
        cumulativeField="cumulative"
        totalField="grand_total"
        height="420px"
    />
{:else}
    <Alert status=warning>No IT tower spend data available for this filter selection.</Alert>
{/if}

---

## Top IT Programs by Spend — Latest Year

{#if snapshot_subprograms?.length > 0}
    <ParetoInsight data={snapshot_subprograms} entityLabel="IT programs"/>
    <ParetoBarChart
        data={snapshot_subprograms}
        title=""
        barField="spend"
        labelField="subprogram_name"
        pctField="pct_of_total"
        cumulativeField="cumulative"
        totalField="grand_total"
        height="420px"
    />
{:else}
    <Alert status=warning>No IT program spend data available for this filter selection.</Alert>
{/if}

---

## IT Tower Breakdown — Latest Year

{#if tower_snapshot?.length > 0}
    <ConditionalTable
        data={tower_snapshot}
        columns={towerTableColumns}
        search={true}
        defaultSort="latest_spend"
        defaultDir={-1}
    />
{:else}
    <Alert status=warning>No IT tower breakdown data available for this filter selection.</Alert>
{/if}

---

## IT Spend Changes — Year over Year

<Alert status=info>Agencies sorted by absolute dollar change in IT spend from prior year.</Alert>

<BudgetChangesChart
    data={agency_movers}
    labelField="agency_name"
    title="Biggest IT spend changes vs prior year"
    height="520px"
    limit={10}
/>

---

## Agency IT Spend Drill-Down — Click a row to open the Agency page

{#if agency_latest?.length > 0}
    <ConditionalTable
        data={agency_latest}
        columns={agencyTableColumns}
        linkField="agency_link"
        search={true}
        defaultSort="latest_spend"
        defaultDir={-1}
    />
{:else}
    <Alert status=warning>No agency IT spend data available for this filter selection.</Alert>
{/if}

{/if}

{#if viewMode == 'trend'}

---

## Fiscal Overview

<TrendOverview
    yearly={yearly}
    yoyDetail={yoy_detail}
    fiscalOverviewCagr={fiscal_overview_cagr}
    {cagrPct}
    {chartHeight}
/>

---

## IT Tower Composition Over Time

{#if tower_trend?.length > 0}
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 14px 0;">
        {#each top_towers_trend as t}
            <button
                on:click={() => toggleTower(t.it_tower)}
                style={`border-radius:14px; padding:6px 10px; font-size:0.9rem; display:inline-flex; align-items:center; gap:8px; cursor:pointer; border: ${selectedTower === t.it_tower ? '2px solid #C8122C' : '1px solid var(--nxt-border)'}; background: ${selectedTower === t.it_tower ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'var(--nxt-surface)'}; box-shadow: ${selectedTower === t.it_tower ? '0 4px 10px rgba(200,20,44,0.08)' : 'none'}`}
                aria-pressed={selectedTower === t.it_tower}
            >
                <span style={`width:10px; height:10px; border-radius:50%; background: ${t.it_tower === highlightedTowerNames[0] ? '#C8122C' : t.it_tower === highlightedTowerNames[1] ? '#FFC838' : t.it_tower === highlightedTowerNames[2] ? '#231F20' : '#C9CED6'}; display:inline-block;`}></span>
                <span style={`color:${selectedTower === t.it_tower ? '#C8122C' : '#231F20'}; font-weight:${selectedTower === t.it_tower ? 700 : 500}`}>{t.it_tower}</span>
            </button>
        {/each}
    </div>
    <ECharts
        height="480px"
        config={{
            tooltip: {
                trigger: 'item',
                formatter: function(param) {
                    if (!param) return '';
                    const hoveredTower = param.seriesName;
                    const rows = towerTrendYears.slice()
                        .sort(function(a, b) { return Number(b) - Number(a); })
                        .map(function(year) {
                            const point = tower_trend.find(function(d) {
                                return String(d.fiscal_year) === year && d.it_tower === hoveredTower;
                            });
                            const v = point ? point.spend : 0;
                            const pct = point ? (point.pct_of_total * 100).toFixed(1) : '0.0';
                            return year + ': ' + usdCompact(v) + ' (' + pct + '%)';
                        });
                    return '<b>' + hoveredTower + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 56, right: 24, top: 20, bottom: 40 },
            xAxis: { type: 'category', data: towerTrendYears },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: (v) => {
                        const n = Number(v) || 0;
                        return Math.abs(n) >= 1e9 ? `$${(n / 1e9).toFixed(0)}B` : `$${(n / 1e6).toFixed(0)}M`;
                    }
                },
                splitLine: { lineStyle: { color: '#D9DDE3' } }
            },
            series: top_towers_trend.map((tower) => {
                const towerName = tower.it_tower;
                const isHighlighted = highlightedTowerNames.includes(towerName);
                const hasTowerSelection = Boolean(selectedTower);
                const isSelectedTower = selectedTower === towerName;
                const isSelected = !hasTowerSelection || isSelectedTower;
                const baseColor = isHighlighted
                    ? (towerName === highlightedTowerNames[0] ? '#C8122C'
                        : towerName === highlightedTowerNames[1] ? '#FFC838'
                        : '#231F20')
                    : '#C9CED6';
                return {
                    name: towerName,
                    type: 'line',
                    smooth: false,
                    symbol: 'circle',
                    symbolSize: hasTowerSelection ? (isSelectedTower ? (isHighlighted ? 12 : 11) : 4) : (isHighlighted ? 7 : 6),
                    showSymbol: true,
                    lineStyle: {
                        color: baseColor,
                        width: hasTowerSelection ? (isSelectedTower ? (isHighlighted ? 6 : 5) : 1) : (isHighlighted ? 3 : 2),
                        opacity: isSelected ? 1 : 0.06
                    },
                    itemStyle: { color: baseColor, opacity: isSelected ? 1 : 0.06 },
                    label: {
                        show: isHighlighted,
                        position: 'top',
                        offset: [0, -10],
                        backgroundColor: 'rgba(255, 255, 255, 0.92)',
                        padding: [2, 5],
                        borderRadius: 3,
                        lineHeight: 14,
                        color: baseColor,
                        fontWeight: isHighlighted ? 700 : 500,
                        formatter: (params) => {
                            const middleIndex = Math.floor(towerTrendYears.length / 2);
                            return params.dataIndex === middleIndex ? towerName : '';
                        }
                    },
                    emphasis: {
                        focus: 'series',
                        scale: true,
                        lineStyle: { color: isHighlighted ? baseColor : '#3B7DD8', width: 4, opacity: 1 },
                        itemStyle: { color: isHighlighted ? baseColor : '#3B7DD8', opacity: 1 },
                        label: { show: false }
                    },
                    blur: {
                        lineStyle: { opacity: 0.06 },
                        itemStyle: { opacity: 0.06 }
                    },
                    data: towerTrendYears.map((y) => {
                        const point = tower_trend.find((d) => String(d.fiscal_year) === y && d.it_tower === towerName);
                        return { value: point?.spend ?? 0, pct: point?.pct_of_total ?? 0 };
                    })
                };
            })
        }}
    />
{:else}
    <Alert status=warning>No IT tower trend data available for this filter selection.</Alert>
{/if}

---

## Top IT Agencies — Trend Over Time

{#if agency_trend_lines?.length > 0}
    <AgencyTrendChart
        agencies={top_agencies_trend}
        trendLines={agency_trend_lines}
        years={agencyLineTrendYears}
        title="Top IT Agencies by Spend — Trend Over Time"
        entityLabel="agency"
        topN={5}
        height="520px"
    />
{:else}
    <Alert status=warning>No agency IT spend trend data available for this filter selection.</Alert>
{/if}

---

## Agency IT Spending by Year — Click on Agency to drill to its specific page

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
    <Alert status=warning>No agency IT spend data available for this filter selection.</Alert>
{/if}

{/if}