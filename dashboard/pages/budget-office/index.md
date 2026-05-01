---
title: Budget Office
sidebar_position: 3
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">🏛️ Budget Office View</h1>
    <p style="color: #FFC838; font-size: 0.95rem; margin: 4px 0 0 0;">Statewide Budget Analysis </p>
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

<Details title="🔍 Filters — click to expand" open=true>

<Grid cols=3>
    <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue="%"><DropdownOption value="%" valueLabel="All Years"/></Dropdown>
    <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%"><DropdownOption value="%" valueLabel="All Fund Types"/></Dropdown>
    <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%"><DropdownOption value="%" valueLabel="All Agencies"/></Dropdown>
</Grid>

</Details>

<Grid cols=1>
    <Dropdown name=f_view title="View" defaultValue="trend">
        <DropdownOption value="trend" valueLabel="Trend Over Years"/>
        <DropdownOption value="latest" valueLabel="Latest Year Snapshot"/>
    </Dropdown>
</Grid>

<Alert status=info>
    Switch between <b>Trend Over Years</b> and <b>Latest Year Snapshot</b> using the View selector above.
</Alert>

```sql filtered
select
    cast(b.fiscal_year as int) as fiscal_year,
    b.agency_code,
    b.agency_name,
    b.fund_type,
    b.total_budget_amount as amount
from mbtsa.agency_level b
where cast(b.fiscal_year as varchar) like '${selectedFy}'
    and coalesce(b.fund_type, '') like '${selectedFund}'
    and coalesce(b.agency_name, '') like '${selectedAgency}'
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
)
select
    b.start_year,
    b.max_year,
    max(case when o.year_rank = 2 then o.fiscal_year end) as prior_year,
    b.total_budget,
    max(case when o.year_rank = 1 then o.total_budget end) as latest_budget,
    max(case when o.year_rank = 2 then o.total_budget end) as prior_budget
from bounds b
left join ordered o on true
group by b.start_year, b.max_year, b.total_budget
```

```sql filtered_latest
select f.*
from ${filtered} f
cross join ${scope_meta} m
where f.fiscal_year = m.max_year
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

```sql snapshot_agencies
select agency_name, sum(amount) as spend
from ${filtered_latest}
where agency_name is not null
group by agency_name
order by spend desc
```

```sql snapshot_funds
select fund_type, sum(amount) as spend
from ${filtered_latest}
where fund_type is not null
group by fund_type
order by spend desc
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

```sql top_agencies
select agency_name, sum(amount) as total_agency_spend
from ${filtered}
where agency_name is not null
group by agency_name
order by total_agency_spend desc
limit 5
```

```sql agency_trend_raw
select
    f.fiscal_year,
    f.agency_name,
    sum(f.amount) as spend
from ${filtered} f
where f.agency_name is not null
group by f.fiscal_year, f.agency_name
```

```sql agency_trend
select
    fiscal_year,
    case
        when agency_name in (select agency_name from ${top_agencies})
            then agency_name
        else 'Others'
    end as agency_name,
    sum(spend) as spend
from ${agency_trend_raw}
group by fiscal_year, agency_name
order by fiscal_year, agency_name
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

```sql agency_snapshot
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
    round((l.latest_budget - p.prior_budget) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_change_pct,
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

    const selectedValue = (entry) => readInputValue(entry, '%').replace(/'/g, "''");

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
    

    let selectedAgencySeries = null;
    let pivotYearView = '5y';
    let searchTerm = '';
    let selectedFundSeries = null;

    let selectedAgencyLine = null;



    const toggleAgencyLine = (name) => {
        selectedAgencyLine = selectedAgencyLine === name ? null : name;
    };

    const toggleFundSeries = (name) => {
        selectedFundSeries = selectedFundSeries === name ? null : name;
    };



    $: selectedFy = selectedValue($inputStore?.f_fy);
    $: selectedFund = selectedValue($inputStore?.f_fund);
    $: selectedAgency = selectedValue($inputStore?.f_agency);
    $: viewMode = readInputValue($inputStore?.f_view, 'trend');
    $: trendResults = calculateTrendResults(yearly, 'total_budget');
    $: agencyTrendYears = [...new Set(agency_trend.map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: agencySeriesNames = [...(top_agencies ?? []).map(a => a.agency_name), 'Others'];
    $: fundTrendYears = [...new Set(fund_trend.map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: fundSeriesNames = [...new Set(fund_trend.map(d => d.fund_type))].sort((a, b) => {
        const ra = fund_trend.find(d => d.fund_type === a)?.fund_rank ?? 99;
        const rb = fund_trend.find(d => d.fund_type === b)?.fund_rank ?? 99;
        return ra - rb;
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

    const toggleAgencySeries = (name) => {
        selectedAgencySeries = selectedAgencySeries === name ? null : name;
    };
</script>

{#if viewMode == 'latest'}

<Grid cols=4>
    <BigValue data={overview} value=latest_budget fmt=usd2compactviz title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})"/>
    <BigValue data={overview} value=yoy_pct fmt='0.0"%"' title="YoY Change"/>
    <BigValue data={overview} value=cagr_5y_pct fmt='0.0"%"' title="5-Year CAGR"/>
    <BigValue data={overview} value=cagr_10y_pct fmt='0.0"%"' title="10-Year CAGR"/>
</Grid>

---

## Latest Year Snapshot

{#if snapshot_agencies?.length > 0}
    <Grid cols=2>
        <BarChart data={snapshot_agencies} x=agency_name y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Budget by Agency — Latest Year" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C','#E74C3C','#95A5A6','#34495E']}/>
        {#if snapshot_funds?.length > 0}
            <BarChart data={snapshot_funds} x=fund_type y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Budget by Fund Type — Latest Year" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C']}/>
        {:else}
            <Alert status=warning>No fund type data available for this filter selection.</Alert>
        {/if}
    </Grid>
{:else}
    <Alert status=warning>No agency snapshot data available for this filter selection.</Alert>
{/if}

---

## Agency Snapshot Table

<Alert status=info>Click an agency row to open that agency's detail page.</Alert>

{#if agency_snapshot?.length > 0}
    <DataTable data={agency_snapshot} link=agency_link totalRow=true search=true rows=15>
        <Column id=agency_name title="Agency"/>
        <Column id=latest_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
        <Column id=latest_year_pct title="% of Total" fmt='0.0"%"'/>
        <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
        <Column id=cagr_5y_pct title="5-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
        <Column id=cagr_10y_pct title="10-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
    </DataTable>
{:else}
    <Alert status=warning>No agency snapshot data available for this filter selection.</Alert>
{/if}

{/if}

{#if viewMode == 'trend'}

---

## Fiscal Overview

{#if yearly?.length > 0 && yoy_detail?.length > 0}
    <Grid cols=2>
        <ECharts
            height={chartHeight}
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
                xAxis: { type: 'category', data: yearly.map((d) => String(d.fiscal_year)) },
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
            height={chartHeight}
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
{:else if yearly?.length > 0}
    <Alert status=warning>Fiscal overview data is incomplete for this filter selection.</Alert>
{:else}
    <Alert status=warning>No fiscal-year budget data available for this filter selection.</Alert>
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
    <Alert status=warning>No fund trend data available for this filter selection.</Alert>
{/if}

---

## Top Agencies by Budget — Trend Over Time

{#if agency_trend_lines?.length > 0}
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 14px 0;">
        {#each top_agencies_trend as a}
            <button
                on:click={() => toggleAgencyLine(a.agency_name)}
                style={`border-radius:14px; padding:6px 10px; font-size:0.9rem; display:inline-flex; align-items:center; gap:8px; cursor:pointer; border: ${selectedAgencyLine === a.agency_name ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)'}; background: ${selectedAgencyLine === a.agency_name ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white'}; box-shadow: ${selectedAgencyLine === a.agency_name ? '0 4px 10px rgba(200,20,44,0.08)' : 'none'}`}
                aria-pressed={selectedAgencyLine === a.agency_name}
            >
                <span style={`width:10px; height:10px; border-radius:50%; background: ${a.agency_name === highlightedAgencyNames[0] ? '#C8122C' : a.agency_name === highlightedAgencyNames[1] ? '#FFC838' : a.agency_name === highlightedAgencyNames[2] ? '#231F20' : '#C9CED6'}; display:inline-block;`}></span>
                <span style={`color:${selectedAgencyLine === a.agency_name ? '#C8122C' : '#231F20'}; font-weight:${selectedAgencyLine === a.agency_name ? 700 : 500}`}>{a.agency_name}</span>
            </button>
        {/each}
    </div>
    <ECharts
        height="520px"
        config={{
            title: { text: 'Top 10 agencies over time', left: 'left', top: 0, textStyle: { fontSize: 14, fontWeight: 600, color: '#231F20' } },
            tooltip: {
                trigger: 'item',
                formatter: function(param) {
                    if (!param) return '';
                    const hoveredAgency = param.seriesName;
                    const rows = agencyLineTrendYears.slice()
                        .sort(function(a, b) { return Number(b) - Number(a); })
                        .map(function(year) {
                            const point = agency_trend_lines.find(function(d) {
                                return String(d.fiscal_year) === year && d.agency_name === hoveredAgency;
                            });
                            const v = point ? point.spend : 0;
                            const fmt = Math.abs(v) >= 1e9
                                ? '$' + (v/1e9).toFixed(2) + 'B'
                                : Math.abs(v) >= 1e6
                                    ? '$' + (v/1e6).toFixed(1) + 'M'
                                    : '$' + Math.round(v).toLocaleString();
                            return year + ': ' + fmt;
                        });
                    return '<b>' + hoveredAgency + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 56, right: 24, top: 86, bottom: 46 },
            xAxis: { type: 'category', data: agencyLineTrendYears },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: (v) => {
                        const n = Number(v) || 0;
                        return Math.abs(n) >= 1e9 ? `$${(n/1e9).toFixed(0)}B` : `$${(n/1e6).toFixed(0)}M`;
                    }
                },
                splitLine: { lineStyle: { color: '#D9DDE3' } }
            },
            series: top_agencies_trend.map((agency) => {
                const agencyName = agency.agency_name;
                const years = agencyLineTrendYears;
                const isHighlighted = highlightedAgencyNames.includes(agencyName);
                const hasSelection = Boolean(selectedAgencyLine);
                const isSelectedAgency = selectedAgencyLine === agencyName;
                const isSelected = !hasSelection || isSelectedAgency;
                const baseColor = isHighlighted
                    ? (agencyName === highlightedAgencyNames[0] ? '#C8122C'
                        : agencyName === highlightedAgencyNames[1] ? '#FFC838'
                        : '#231F20')
                    : '#C9CED6';
                return {
                    name: agencyName,
                    type: 'line',
                    smooth: false,
                    symbol: 'circle',
                    symbolSize: hasSelection
                        ? (isSelectedAgency ? (isHighlighted ? 12 : 11) : 4)
                        : (isHighlighted ? 7 : 6),
                    showSymbol: true,
                    lineStyle: {
                        color: baseColor,
                        width: hasSelection
                            ? (isSelectedAgency ? (isHighlighted ? 6 : 5) : 1)
                            : (isHighlighted ? 3 : 2),
                        opacity: isSelected ? 1 : 0.06
                    },
                    itemStyle: { color: baseColor, opacity: isSelected ? 1 : 0.06 },
                    label: {
                        show: isHighlighted,
                        position: 'top',
                        offset: [0, -10],
                        backgroundColor: 'rgba(255,255,255,0.92)',
                        padding: [2, 5],
                        borderRadius: 3,
                        lineHeight: 14,
                        color: baseColor,
                        fontWeight: isHighlighted ? 700 : 500,
                        formatter: (params) => {
                            const middleIndex = Math.floor(years.length / 2);
                            return params.dataIndex === middleIndex ? agencyName : '';
                        }
                    },
                    emphasis: {
                        focus: 'series', scale: true,
                        lineStyle: { color: isHighlighted ? baseColor : '#3B7DD8', width: 4, opacity: 1 },
                        itemStyle: { color: isHighlighted ? baseColor : '#3B7DD8', opacity: 1 },
                        label: { show: false }
                    },
                    blur: { lineStyle: { opacity: 0.06 }, itemStyle: { opacity: 0.06 } },
                    data: years.map((y) => {
                        const point = agency_trend_lines.find(d => String(d.fiscal_year) === y && d.agency_name === agencyName);
                        return point ? point.spend : 0;
                    })
                };
            })
        }}
    />
{:else}
    <Alert status=warning>No agency trend data available for this filter selection.</Alert>
{/if}

---

## Agency Budget by Year

<div style="display:flex; gap:8px; margin: 8px 0 14px 0;">
    {#each [['3y','Last 3 Years'],['5y','Last 5 Years'],['all','All Years']] as [val, label]}
        <button
            on:click={() => pivotYearView = val}
            style={'border-radius:14px; padding:6px 14px; font-size:0.9rem; cursor:pointer; border: ' + (pivotYearView === val ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)') + '; background: ' + (pivotYearView === val ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white') + '; color: ' + (pivotYearView === val ? '#C8122C' : '#231F20') + '; font-weight: ' + (pivotYearView === val ? 700 : 500)}
        >{label}</button>
    {/each}
</div>

<input
    bind:value={searchTerm}
    placeholder="Search agencies..."
    style="border: 1px solid #D9DDE3; border-radius: 8px; padding: 8px 12px; font-size: 0.9rem; width: 280px; margin-bottom: 12px;"
/>

{#if sortedPivot?.length > 0}
    <DataTable data={sortedPivot} link=agency_link>
        <Column id=agency_name title="Agency"/>
        {#each pivotViewYears as yr}
            <Column id={'FY' + yr} title={'FY' + yr} fmt=usd2compactviz/>
        {/each}
    </DataTable>
{:else}
    <Alert status=warning>No agency data available for this filter selection.</Alert>
{/if}

{/if}