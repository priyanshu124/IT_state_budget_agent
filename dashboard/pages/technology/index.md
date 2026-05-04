---
title: Technology
sidebar_position: 4
---

<div style="background: linear-gradient(135deg, #ede5f8 0%, #d4bef0 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #802cd7; margin-bottom: 0;">
    <h1 style="color: #211030; font-size: 1.7rem; font-weight: 700; margin: 0;">💻 Technology View</h1>
    <p style="color: #6321a5; font-size: 0.95rem; margin: 4px 0 0 0;">IT Spending Analysis · TBM v5.0.1 Classification</p>
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
    and ('${selectedFy}' in ('%', '', 'undefined') or cast(t.fiscal_year as varchar) like '${selectedFy}')
    and ('${selectedFund}' in ('%', '', 'undefined') or coalesce(t.fund_type, '') like '${selectedFund}')
    and ('${selectedAgency}' in ('%', '', 'undefined') or coalesce(t.agency_name, '') like '${selectedAgency}')
```

```sql yearly_rollup
select fiscal_year, sum(amount) as total_it_spend
from ${filtered}
group by fiscal_year
order by fiscal_year
```

```sql scope_meta
with ordered as (
    select
        fiscal_year,
        total_it_spend,
        row_number() over (order by fiscal_year desc) as year_rank
    from ${yearly_rollup}
),
bounds as (
    select
        min(fiscal_year) as start_year,
        max(fiscal_year) as max_year,
        sum(total_it_spend) as total_it_spend
    from ${yearly_rollup}
)
select
    b.start_year,
    b.max_year,
    max(case when o.year_rank = 2 then o.fiscal_year end) as prior_year,
    b.total_it_spend,
    max(case when o.year_rank = 1 then o.total_it_spend end) as latest_it_spend,
    max(case when o.year_rank = 2 then o.total_it_spend end) as prior_it_spend
from bounds b
left join ordered o on true
where b.max_year is not null
group by b.start_year, b.max_year, b.total_it_spend
```

```sql filtered_latest
select f.*
from ${filtered} f
cross join ${scope_meta} m
where f.fiscal_year = m.max_year
```

```sql overview
with points as (
    select
        m.*,
        y_5.total_it_spend as spend_5y_ago,
        y_10.total_it_spend as spend_10y_ago
    from ${scope_meta} m
    left join ${yearly_rollup} y_5 on y_5.fiscal_year = m.max_year - 5
    left join ${yearly_rollup} y_10 on y_10.fiscal_year = m.max_year - 10
)
select
    total_it_spend,
    latest_it_spend,
    round((latest_it_spend - prior_it_spend) * 100.0 / nullif(prior_it_spend, 0), 1) as yoy_pct,
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
    coalesce(cast(max_year as varchar), 'N/A') as max_year_label
from points
```

```sql filtered_for_metrics
select
    count(distinct agency_code) as it_agencies,
    count(distinct subprogram_name) as it_programs,
    count(distinct it_tower) as towers,
    count(distinct case when it_designation='SHADOW_IT' then subprogram_name end) as shadow_count
from ${filtered_latest}
```

```sql snapshot_towers
select it_tower, sum(amount) as spend
from ${filtered_latest}
where it_tower is not null
group by it_tower
order by spend desc
```

```sql snapshot_subprograms
select subprogram_name, sum(amount) as spend
from ${filtered_latest}
where subprogram_name is not null
group by subprogram_name
order by spend desc
```

```sql yearly
select fiscal_year, total_it_spend
from ${yearly_rollup}
order by fiscal_year
```

```sql yoy_detail
select
    fiscal_year,
    coalesce(
        round(
            (total_it_spend - lag(total_it_spend) over (order by fiscal_year)) * 100.0
            / nullif(lag(total_it_spend) over (order by fiscal_year), 0),
            1
        ),
        0
    ) as change_pct
from ${yearly_rollup}
order by fiscal_year
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
    select fiscal_year, total_it_spend
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

    const inputStore = getInputContext();

    const readInputValue = (entry, fallback = '%') => {
        const candidates = [
            entry?.rawValues?.[0]?.value,
            entry?.rawValue?.value,
            entry?.value?.value,
            entry?.value,
            entry?.rawValue,
            entry?.rawValues?.[0]?.label,
            entry?.label,
            entry?.rawValues?.[0]
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

    const towerChartHeight = '320px';
    const towerChartTitleStyle = { fontSize: 14, fontWeight: 600, color: '#231F20' };
    const getTowerChartGrid = () => ({
        top: '15%', right: '4%', bottom: '11%', left: '8%', containLabel: true
    });

    const calculateTrendResults = (data) => {
        if (!data || data.length < 2) return { chartData: [], growthRate: 0, trendPoints: [] };

        const years = data.map((d) => Number(d.fiscal_year) || 0);
        const values = data.map((d) => Number(d.total_it_spend) || 0);
        const x = Array.from({ length: data.length }, (_, i) => i + 1);
        const validPoints = x.map((xi, i) => ({ x: xi, y: values[i] })).filter((p) => p.y > 0);

        if (validPoints.length < 2) return { chartData: values, growthRate: 0, trendPoints: values };

        const lnX = validPoints.map((p) => Math.log(p.x));
        const lnY = validPoints.map((p) => Math.log(p.y));
        const count = validPoints.length;
        const sumLnX = lnX.reduce((t, v) => t + v, 0);
        const sumLnY = lnY.reduce((t, v) => t + v, 0);
        const sumLnXLnY = lnX.reduce((t, v, i) => t + v * lnY[i], 0);
        const sumLnX2 = lnX.reduce((t, v) => t + v * v, 0);
        const denominator = count * sumLnX2 - sumLnX * sumLnX;

        if (Math.abs(denominator) < 1e-10) return { chartData: values, growthRate: 0, trendPoints: values };

        const b = (count * sumLnXLnY - sumLnX * sumLnY) / denominator;
        const a = Math.exp((sumLnY - b * sumLnX) / count);
        const trendPoints = x.map((xi) => a * Math.pow(xi, b));
        const growthRate = years.length > 1 && values[0] > 0 && values[values.length - 1] > 0
            ? (Math.pow(values[values.length - 1] / values[0], 1 / (values.length - 1)) - 1) * 100
            : 0;

        return { chartData: values, growthRate, trendPoints };
    };

    let selectedTower = null;
    let selectedAgencySeries = null;
    let pivotYearView = '5y';
    let searchTerm = '';

    $: selectedFy = selectedValue($inputStore?.f_fy);
    $: selectedFund = selectedValue($inputStore?.f_fund);
    $: selectedAgency = selectedValue($inputStore?.f_agency);
    $: viewMode = readInputValue($inputStore?.f_view, 'trend');
    $: trendResults = calculateTrendResults(yearly);
    $: towerTrendYears = [...new Set(tower_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: highlightedTowerNames = (top_towers_trend ?? []).slice(0, 3).map((t) => t.it_tower);
    $: agencyTrendYears = [...new Set(agency_trend.map(d => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: agencySeriesNames = [...(top_agencies ?? []).map(a => a.agency_name), 'Others'];
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

    const toggleAgencySeries = (name) => {
        selectedAgencySeries = selectedAgencySeries === name ? null : name;
    };
</script>

{#if viewMode == 'latest'}

<Grid cols=4>
    <BigValue data={overview} value=latest_it_spend fmt=usd2compactviz title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})"/>
    <BigValue data={overview} value=yoy_pct fmt='0.0"%"' title="YoY Change"/>
    <BigValue data={overview} value=cagr_5y_pct fmt='0.0"%"' title="5-Year CAGR"/>
    <BigValue data={overview} value=cagr_10y_pct fmt='0.0"%"' title="10-Year CAGR"/>
</Grid>

---

## Latest Year Snapshot

{#if snapshot_towers?.length > 0}
    <Grid cols=2>
        <BarChart data={snapshot_towers} x=it_tower y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by tower — Latest Year" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C','#E74C3C','#95A5A6','#34495E']}/>
        {#if snapshot_subprograms?.length > 0}
            <BarChart data={snapshot_subprograms} x=subprogram_name y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by subprogram — Latest Year" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C']}/>
        {:else}
            <Alert status=warning>No subprogram spend data available for this filter selection.</Alert>
        {/if}
    </Grid>
{:else}
    <Alert status=warning>No tower spend data available for this filter selection.</Alert>
{/if}

---

## Latest Year Metrics

<Grid cols=4>
    <BigValue data={filtered_for_metrics} value=it_agencies title="IT Agencies"/>
    <BigValue data={filtered_for_metrics} value=it_programs title="IT Programs"/>
    <BigValue data={filtered_for_metrics} value=towers title="IT Towers"/>
    <BigValue data={filtered_for_metrics} value=shadow_count title="Shadow IT Programs"/>
</Grid>

{/if}

{#if viewMode == 'trend'}

---

## Fiscal Overview

{#if yearly?.length > 0 && yoy_detail?.length > 0}
    <Grid cols=2>
        <ECharts
            height={towerChartHeight}
            config={{
                title: { text: 'Total IT spend by fiscal year', left: 'left', top: 0, textStyle: towerChartTitleStyle },
                grid: getTowerChartGrid(),
                tooltip: {
                    trigger: 'axis',
                    formatter: (params) => {
                        if (!params || params.length === 0) return '';
                        const values = params.map(p => {
                            if (p.seriesType === 'bar') return `${p.marker} Spend: ${usdCompact(p.value)}`;
                            return `${p.marker} Trend: ${usdCompact(p.value)}`;
                        });
                        return `<b>${params[0].axisValue}</b><br/>${values.join('<br/>')}`;
                    }
                },
                xAxis: { type: 'category', data: yearly.map((d) => String(d.fiscal_year)) },
                yAxis: { type: 'value', axisLabel: { formatter: (v) => usdCompact(v) } },
                series: [
                    {
                        type: 'bar',
                        barMaxWidth: 36,
                        data: trendResults.chartData,
                        label: {
                            show: true, position: 'top', distance: 5,
                            color: '#231F20', fontSize: 11,
                            formatter: (p) => usdCompact(p.value)
                        },
                        labelLayout: { hideOverlap: true },
                        itemStyle: { color: '#FFC838' },
                        z: 1
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
            height={towerChartHeight}
            config={{
                title: { text: 'Year-over-year IT spend change', left: 'left', top: 0, textStyle: towerChartTitleStyle },
                grid: getTowerChartGrid(),
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
    <Alert status=warning>No fiscal-year IT spend data available for this filter selection.</Alert>
{/if}

---

## Tower Trends (Top 10)

{#if tower_trend?.length > 0}
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 14px 0;">
        {#each top_towers_trend as t}
            <button
                on:click={() => toggleTower(t.it_tower)}
                style={`border-radius:14px; padding:6px 10px; font-size:0.9rem; display:inline-flex; align-items:center; gap:8px; cursor:pointer; border: ${selectedTower === t.it_tower ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)'}; background: ${selectedTower === t.it_tower ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white'}; box-shadow: ${selectedTower === t.it_tower ? '0 4px 10px rgba(200,20,44,0.08)' : 'none'}`}
                aria-pressed={selectedTower === t.it_tower}
            >
                <span style={`width:10px; height:10px; border-radius:50%; background: ${t.it_tower === highlightedTowerNames[0] ? '#C8122C' : t.it_tower === highlightedTowerNames[1] ? '#FFC838' : t.it_tower === highlightedTowerNames[2] ? '#231F20' : '#C9CED6'}; display:inline-block;`}></span>
                <span style={`color:${selectedTower === t.it_tower ? '#C8122C' : '#231F20'}; font-weight:${selectedTower === t.it_tower ? 700 : 500}`}>{t.it_tower}</span>
            </button>
        {/each}
    </div>
    <ECharts
        height="520px"
        config={{
            title: { text: 'Top 10 towers over time', left: 'left', top: 0, textStyle: { fontSize: 14, fontWeight: 600, color: '#231F20' } },
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
                            const fmt = Math.abs(v) >= 1e9
                                ? '$' + (v/1e9).toFixed(2) + 'B'
                                : Math.abs(v) >= 1e6
                                    ? '$' + (v/1e6).toFixed(1) + 'M'
                                    : '$' + Math.round(v).toLocaleString();
                            return year + ': ' + fmt + ' (' + pct + '%)';
                        });
                    return '<b>' + hoveredTower + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 56, right: 24, top: 86, bottom: 46 },
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
                const years = towerTrendYears;
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
                    symbolSize: hasTowerSelection
                        ? (isSelectedTower ? (isHighlighted ? 12 : 11) : 4)
                        : (isHighlighted ? 7 : 6),
                    showSymbol: true,
                    lineStyle: {
                        color: baseColor,
                        width: hasTowerSelection
                            ? (isSelectedTower ? (isHighlighted ? 6 : 5) : 1)
                            : (isHighlighted ? 3 : 2),
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
                            const middleIndex = Math.floor(years.length / 2);
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
                    data: years.map((y) => {
                        const point = tower_trend.find((d) => String(d.fiscal_year) === y && d.it_tower === towerName);
                        return { value: point?.spend ?? 0, pct: point?.pct_of_total ?? 0 };
                    })
                };
            })
        }}
    />
{:else}
    <Alert status=warning>No tower trend data is available for this filter selection.</Alert>
{/if}

---

## Top IT Agencies by Spend — Trend Over Time

{#if agency_trend?.length > 0}
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 14px 0;">
        {#each agencySeriesNames as name}
            <button
                on:click={() => toggleAgencySeries(name)}
                style={'border-radius:14px; padding:6px 10px; font-size:0.9rem; display:inline-flex; align-items:center; gap:8px; cursor:pointer; border: ' + (selectedAgencySeries === name ? '2px solid #C8122C' : '1px solid rgba(36,41,46,0.06)') + '; background: ' + (selectedAgencySeries === name ? 'linear-gradient(90deg,#FFF7F7,#FFECEC)' : 'white') + '; box-shadow: ' + (selectedAgencySeries === name ? '0 4px 10px rgba(200,20,44,0.08)' : 'none')}
                aria-pressed={selectedAgencySeries === name}
            >
                <span style={'width:10px; height:10px; border-radius:50%; background: ' + (['#C8122C','#FFC838','#231F20','#E04B3F','#C99A06','#C9CED6'][agencySeriesNames.indexOf(name)] ?? '#C9CED6') + '; display:inline-block;'}></span>
                <span style={'color:' + (selectedAgencySeries === name ? '#C8122C' : '#231F20') + '; font-weight:' + (selectedAgencySeries === name ? 700 : 500)}>{name}</span>
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
                    const hoveredAgency = param.seriesName;
                    const rows = agencyTrendYears.slice()
                        .sort(function(a, b) { return Number(b) - Number(a); })
                        .map(function(year) {
                            const row = agency_trend.find(function(d) {
                                return String(d.fiscal_year) === year && d.agency_name === hoveredAgency;
                            });
                            const v = row ? row.spend : 0;
                            const yearTotal = agency_trend
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
                    return '<b>' + hoveredAgency + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 64, right: 24, top: 20, bottom: 40 },
            xAxis: { type: 'category', boundaryGap: false, data: agencyTrendYears },
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
            color: ['#C8122C','#FFC838','#231F20','#E04B3F','#C99A06','#C9CED6'],
            series: Array.from(agencySeriesNames, function(name, idx) {
                const seriesColor = ['#C8122C','#FFC838','#231F20','#E04B3F','#C99A06','#C9CED6'][idx] ?? '#C9CED6';
                const hasSelection = Boolean(selectedAgencySeries);
                const isSelected = !hasSelection || selectedAgencySeries === name;
                const isOthers = name === 'Others';
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
                    areaStyle: { opacity: isSelected ? (isOthers ? 0.45 : 0.85) : 0.06 },
                    emphasis: { focus: 'series' },
                    blur: { areaStyle: { opacity: 0.06 }, lineStyle: { opacity: 0.06 } },
                    data: agencyTrendYears.map(function(y) {
                        const row = agency_trend.find(function(d) {
                            return String(d.fiscal_year) === y && d.agency_name === name;
                        });
                        return row ? row.spend : 0;
                    })
                };
            })
        }}
    />
{:else}
    <Alert status=warning>No agency trend data available for this filter selection.</Alert>
{/if}

---

## Agency IT Spend by Year

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