---
title: Agency Detail
prerender: false
---

```sql yearly_rollup
select
    cast(fiscal_year as int) as fiscal_year,
    sum(total_budget_amount) as total_it_spend
from mbtsa.cost_pool_level
where is_it = true
    and '${params.agency}' not in ('', 'undefined')
    and agency_name = '${params.agency}'
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
    b.total_it_spend,
    max(case when o.year_rank = 1 then o.total_it_spend end) as latest_it_spend,
    max(case when o.year_rank = 2 then o.total_it_spend end) as prior_it_spend,
    max(case when o.year_rank = 2 then o.fiscal_year end) as prior_year
from bounds b
left join ordered o on true
where b.max_year is not null
group by b.start_year, b.max_year, b.total_it_spend
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
        end, 1
    ) as cagr_5y_pct,
    round(
        case
            when spend_10y_ago > 0 and latest_it_spend > 0
                then (power(latest_it_spend / spend_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
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
            (total_it_spend - lag(total_it_spend) over (order by fiscal_year)) * 100.0
            / nullif(lag(total_it_spend) over (order by fiscal_year), 0),
            1
        ),
        0
    ) as change_pct
from ${yearly_rollup}
order by fiscal_year
```

```sql filtered_latest
select
    cast(fiscal_year as int) as fiscal_year,
    agency_code,
    agency_name,
    program_name,
    subprogram_name,
    fund_type,
    it_tower,
    it_sub_tower,
    it_designation,
    total_budget_amount as amount
from mbtsa.cost_pool_level
where is_it = true
    and agency_name = '${params.agency}'
    and fiscal_year = (select max_year from ${scope_meta})
```

```sql metrics_latest
select
    count(distinct program_name) as it_programs,
    count(distinct it_tower) as towers,
    count(distinct fund_type) as fund_types,
    count(distinct case when it_designation = 'SHADOW_IT' then subprogram_name end) as shadow_count
from ${filtered_latest}
```

```sql tower_breakdown_latest
select it_tower, sum(amount) as spend
from ${filtered_latest}
where it_tower is not null
group by it_tower
order by spend desc
```

```sql subprogram_breakdown_latest
select subprogram_name, sum(amount) as spend
from ${filtered_latest}
where subprogram_name is not null
group by subprogram_name
order by spend desc
```

```sql top_towers_trend
select
    it_tower,
    sum(total_budget_amount) as total_it_spend
from mbtsa.cost_pool_level
where is_it = true
    and '${params.agency}' not in ('', 'undefined')
    and agency_name = '${params.agency}'
    and it_tower is not null
group by it_tower
order by total_it_spend desc
limit 10
```

```sql tower_trend
with tower_spend as (
    select
        cast(fiscal_year as int) as fiscal_year,
        it_tower,
        sum(total_budget_amount) as spend
    from mbtsa.cost_pool_level
    where is_it = true
        and '${params.agency}' not in ('', 'undefined')
        and agency_name = '${params.agency}'
        and it_tower in (select it_tower from ${top_towers_trend})
    group by fiscal_year, it_tower
)
select
    t.fiscal_year,
    t.it_tower,
    t.spend,
    t.spend / nullif(y.total_it_spend, 0) as pct_of_total
from tower_spend t
left join ${yearly_rollup} y on y.fiscal_year = t.fiscal_year
order by t.fiscal_year
```

```sql program_drill
select
    program_name,
    fiscal_year,
    sum(total_budget_amount) as spend
from mbtsa.cost_pool_level
where is_it = true
    and '${params.agency}' not in ('', 'undefined')
    and agency_name = '${params.agency}'
    and program_name is not null
group by program_name, fiscal_year
order by program_name, fiscal_year
```

```sql subprogram_detail
select
    program_name,
    subprogram_name,
    it_tower,
    it_designation,
    fund_type,
    cast(fiscal_year as int) as fiscal_year,
    sum(total_budget_amount) as spend
from mbtsa.cost_pool_level
where is_it = true
    and '${params.agency}' not in ('', 'undefined')
    and agency_name = '${params.agency}'
group by program_name, subprogram_name, it_tower, it_designation, fund_type, fiscal_year
order by fiscal_year desc, spend desc
```

```sql pivot_programs
select
    program_name,
    cast(fiscal_year as int) as fiscal_year,
    sum(total_budget_amount) as spend
from mbtsa.cost_pool_level
where is_it = true
    and '${params.agency}' not in ('', 'undefined')
    and agency_name = '${params.agency}'
    and program_name is not null
group by program_name, fiscal_year
order by program_name, fiscal_year
```

```sql pivot_subprograms
select
    program_name,
    subprogram_name,
    cast(fiscal_year as int) as fiscal_year,
    sum(total_budget_amount) as spend
from mbtsa.cost_pool_level
where is_it = true
    and '${params.agency}' not in ('', 'undefined')
    and agency_name = '${params.agency}'
    and program_name is not null
    and subprogram_name is not null
group by program_name, subprogram_name, fiscal_year
order by program_name, subprogram_name, fiscal_year
```

```sql pivot_cost_pools
select
    program_name,
    subprogram_name,
    cost_pool as cost_pool,
    cast(fiscal_year as int) as fiscal_year,
    sum(total_budget_amount) as spend
from mbtsa.cost_pool_level
where is_it = true
    and '${params.agency}' not in ('', 'undefined')
    and agency_name = '${params.agency}'
    and program_name is not null
    and subprogram_name is not null
    and cost_pool is not null
group by program_name, subprogram_name, cost_pool, fiscal_year
order by program_name, subprogram_name, cost_pool, fiscal_year
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
    const usdCompact = (value) => {
        const num = Number(value) || 0;
        const abs = Math.abs(num);
        if (abs >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
        if (abs >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
        if (abs >= 1e3) return `$${(num / 1e3).toFixed(2)}K`;
        return `$${num.toFixed(2)}`;
    };

    const towerChartTitleStyle = { fontSize: 14, fontWeight: 600, color: '#211030' };
    const getTowerChartGrid = () => ({
        top: '15%', right: '4%', bottom: '11%', left: '8%', containLabel: true
    });

    const calculateTrendResults = (data) => {
        if (!data || data.length < 2) return { chartData: [], trendPoints: [] };
        const values = data.map((d) => Number(d.total_it_spend) || 0);
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

    const formatAmount = (v) => {
        const n = Number(v) || 0;
        if (n === 0) return '-';
        if (Math.abs(n) >= 1e9) return '$' + (n/1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return '$' + (n/1e6).toFixed(2) + 'M';
        return '$' + (n/1e3).toFixed(2) + 'K';
    };

    let selectedTower = null;
    let programSearchTerm = '';
    let programPivotView = '5y';



    let drillYearView = '5y';
    let expandedPrograms = {};
    let expandedTowers = {};

    let drillSortCol = null;
    let drillSortDir = 1;

    const setDrillSort = (col) => {
        if (drillSortCol === col) {
            drillSortDir = drillSortDir * -1;
        } else {
            drillSortCol = col;
            drillSortDir = -1;
        }
    };

    $: viewMode = readInputValue($inputStore?.f_view, 'trend');
    $: trendResults = calculateTrendResults(yearly_rollup);
    $: towerTrendYears = [...new Set(tower_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
    $: highlightedTowerNames = (top_towers_trend ?? []).slice(0, 3).map((t) => t.it_tower);

    $: drillYears = [...new Set((pivot_programs ?? []).map(d => d.fiscal_year))].sort((a, b) => a - b);

    $: drillViewYears = (() => {
        if (drillYearView === '3y') return drillYears.slice(-3);
        if (drillYearView === '5y') return drillYears.slice(-5);
        return drillYears;
    })();

    // Program rows (level 1)
    $: towerPivotRows = Object.values(
        (pivot_programs ?? []).reduce(function(acc, row) {
            if (!acc[row.program_name]) acc[row.program_name] = { name: row.program_name };
            acc[row.program_name]['FY' + row.fiscal_year] = (acc[row.program_name]['FY' + row.fiscal_year] || 0) + row.spend;
            return acc;
        }, {})
    ).sort((a, b) => (b['FY' + drillYears[drillYears.length - 1]] || 0) - (a['FY' + drillYears[drillYears.length - 1]] || 0));

    // Subprogram rows per program (level 2)
    $: programPivotRows = (pivot_subprograms ?? []).reduce(function(acc, row) {
        const pKey = row.program_name;
        const sKey = row.subprogram_name;
        if (!acc[pKey]) acc[pKey] = {};
        if (!acc[pKey][sKey]) acc[pKey][sKey] = { name: sKey };
        acc[pKey][sKey]['FY' + row.fiscal_year] = (acc[pKey][sKey]['FY' + row.fiscal_year] || 0) + row.spend;
        return acc;
    }, {});

    // Cost pool rows per program+subprogram (level 3)
    $: subprogramPivotRows = (pivot_cost_pools ?? []).reduce(function(acc, row) {
        const pKey = row.program_name;
        const sKey = row.subprogram_name;
        const cKey = row.cost_pool;
        if (!acc[pKey]) acc[pKey] = {};
        if (!acc[pKey][sKey]) acc[pKey][sKey] = {};
        if (!acc[pKey][sKey][cKey]) acc[pKey][sKey][cKey] = { name: cKey };
        acc[pKey][sKey][cKey]['FY' + row.fiscal_year] = (acc[pKey][sKey][cKey]['FY' + row.fiscal_year] || 0) + row.spend;
        return acc;
    }, {});

    $: grandTotal = drillViewYears.reduce(function(acc, yr) {
        acc['FY' + yr] = towerPivotRows.reduce((s, r) => s + (r['FY' + yr] || 0), 0);
        return acc;
    }, {});

    $: sortedTowerPivotRows = drillSortCol
    ? towerPivotRows.slice().sort(function(a, b) {
        const aVal = a[drillSortCol] || 0;
        const bVal = b[drillSortCol] || 0;
        if (drillSortCol === 'name') return drillSortDir * String(aVal).localeCompare(String(bVal));
        return drillSortDir * (Number(bVal) - Number(aVal));
    })
    : towerPivotRows;

    const sortRows = (rows, col, dir) => {
        if (!col) return rows;
        return rows.slice().sort(function(a, b) {
            const aVal = a[col] || 0;
            const bVal = b[col] || 0;
            if (col === 'name') return dir * String(aVal).localeCompare(String(bVal));
            return dir * (Number(bVal) - Number(aVal));
        });
    };

    const getSortedPrograms = (towerName) => {
        const progs = Object.values(programPivotRows[towerName] ?? {});
        return sortRows(progs, drillSortCol, drillSortDir);
    };

    const getSortedSubprograms = (towerName, progName) => {
        const subs = Object.values(subprogramPivotRows[towerName]?.[progName] ?? {});
        return sortRows(subs, drillSortCol, drillSortDir);
    };

    const toggleProgram = (name) => {
        expandedPrograms = { ...expandedPrograms, [name]: !expandedPrograms[name] };
    };
    const toggleTower = (prog, tower) => {
        const key = prog + '||' + tower;
        expandedTowers = { ...expandedTowers, [key]: !expandedTowers[key] };
    };

</script>

<div style="background: linear-gradient(135deg, #802cd7 0%, #211030 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #b376f6; margin-bottom: 0;">
    <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">🏛️ {params.agency}</h1>
    <p style="color: #b376f6; font-size: 0.95rem; margin: 4px 0 0 0;">Agency IT Spend Detail · TBM v5.0.1 Classification</p>
</div>

<a href="/technology" style="display:inline-block; margin: 12px 0; color: #802cd7; font-size: 0.9rem; text-decoration: none;">← Back to Technology View</a>


<Grid cols=1>
    <Dropdown name=f_view title="View" defaultValue="trend">
        <DropdownOption value="trend" valueLabel="Trend Over Years"/>
        <DropdownOption value="latest" valueLabel="Latest Year Snapshot"/>
    </Dropdown>
</Grid>

{#if viewMode == 'trend'}
## Fiscal Overview

{#if yearly_rollup?.length > 0 && yoy_detail?.length > 0}
    <Grid cols=2>
        <ECharts
            height="320px"
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
                xAxis: { type: 'category', data: yearly_rollup.map((d) => String(d.fiscal_year)) },
                yAxis: { type: 'value', axisLabel: { formatter: (v) => usdCompact(v) } },
                series: [
                    {
                        type: 'bar', barMaxWidth: 36,
                        data: trendResults.chartData,
                        label: {
                            show: true, position: 'top', distance: 5,
                            color: '#211030', fontSize: 11,
                            formatter: (p) => usdCompact(p.value)
                        },
                        labelLayout: { hideOverlap: true },
                        itemStyle: { color: '#b376f6' }, z: 1
                    },
                    {
                        type: 'line', smooth: true, name: 'Trend',
                        data: trendResults.trendPoints,
                        lineStyle: { color: '#802cd7', width: 3 },
                        symbol: 'none', z: 2
                    }
                ]
            }}
        />
        <ECharts
            height="320px"
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
                        itemStyle: { color: (p) => ((Number(p.value) || 0) >= 0 ? '#2EAD6B' : '#802cd7') }
                    }
                ]
            }}
        />
    </Grid>
{:else}
    <Alert status=warning>No fiscal year data available for this agency.</Alert>
{/if}

---



---

## Tower Trends (Top 10)

{#if tower_trend?.length > 0}
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 14px 0;">
        {#each top_towers_trend as t}
            <button
                on:click={() => selectedTower = selectedTower === t.it_tower ? null : t.it_tower}
                style={`border-radius:14px; padding:6px 10px; font-size:0.9rem; display:inline-flex; align-items:center; gap:8px; cursor:pointer; border: ${selectedTower === t.it_tower ? '2px solid #802cd7' : '1px solid rgba(36,41,46,0.06)'}; background: ${selectedTower === t.it_tower ? 'linear-gradient(90deg,#f3ecfd,#ede0fc)' : 'white'}; box-shadow: ${selectedTower === t.it_tower ? '0 4px 10px rgba(128,44,215,0.08)' : 'none'}`}
                aria-pressed={selectedTower === t.it_tower}
            >
                <span style={`width:10px; height:10px; border-radius:50%; background: ${t.it_tower === highlightedTowerNames[0] ? '#802cd7' : t.it_tower === highlightedTowerNames[1] ? '#b376f6' : t.it_tower === highlightedTowerNames[2] ? '#211030' : '#C9CED6'}; display:inline-block;`}></span>
                <span style={`color:${selectedTower === t.it_tower ? '#802cd7' : '#211030'}; font-weight:${selectedTower === t.it_tower ? 700 : 500}`}>{t.it_tower}</span>
            </button>
        {/each}
    </div>
    <ECharts
        height="480px"
        config={{
            title: { text: 'Top 10 towers over time', left: 'left', top: 0, textStyle: { fontSize: 14, fontWeight: 600, color: '#211030' } },
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
                            const fmtV = Math.abs(v) >= 1e9
                                ? '$' + (v/1e9).toFixed(2) + 'B'
                                : Math.abs(v) >= 1e6
                                    ? '$' + (v/1e6).toFixed(1) + 'M'
                                    : '$' + Math.round(v).toLocaleString();
                            return year + ': ' + fmtV + ' (' + pct + '%)';
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
                        return Math.abs(n) >= 1e9 ? `$${(n/1e9).toFixed(0)}B` : `$${(n/1e6).toFixed(0)}M`;
                    }
                },
                splitLine: { lineStyle: { color: '#e2d9f3' } }
            },
            series: top_towers_trend.map((tower) => {
                const towerName = tower.it_tower;
                const years = towerTrendYears;
                const isHighlighted = highlightedTowerNames.includes(towerName);
                const hasTowerSelection = Boolean(selectedTower);
                const isSelectedTower = selectedTower === towerName;
                const isSelected = !hasTowerSelection || isSelectedTower;
                const baseColor = isHighlighted
                    ? (towerName === highlightedTowerNames[0] ? '#802cd7'
                        : towerName === highlightedTowerNames[1] ? '#b376f6'
                        : '#211030')
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
                        backgroundColor: 'rgba(255,255,255,0.92)',
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
                        focus: 'series', scale: true,
                        lineStyle: { color: isHighlighted ? baseColor : '#3B7DD8', width: 4, opacity: 1 },
                        itemStyle: { color: isHighlighted ? baseColor : '#3B7DD8', opacity: 1 },
                        label: { show: false }
                    },
                    blur: { lineStyle: { opacity: 0.06 }, itemStyle: { opacity: 0.06 } },
                    data: years.map((y) => {
                        const point = tower_trend.find((d) => String(d.fiscal_year) === y && d.it_tower === towerName);
                        return { value: point?.spend ?? 0, pct: point?.pct_of_total ?? 0 };
                    })
                };
            })
        }}
    />
{:else}
    <Alert status=warning>No tower trend data available for this agency.</Alert>
{/if}

---

## Program Drill down

<div style="display:flex; gap:8px; margin: 8px 0 14px 0;">
    {#each [['3y','Last 3 Years'],['5y','Last 5 Years'],['all','All Years']] as [val, label]}
        <button
            on:click={() => drillYearView = val}
            style={'border-radius:14px; padding:6px 14px; font-size:0.9rem; cursor:pointer; border: ' + (drillYearView === val ? '2px solid #802cd7' : '1px solid rgba(36,41,46,0.06)') + '; background: ' + (drillYearView === val ? 'linear-gradient(90deg,#f3ecfd,#ede0fc)' : 'white') + '; color: ' + (drillYearView === val ? '#802cd7' : '#211030') + '; font-weight: ' + (drillYearView === val ? 700 : 500)}
        >{label}</button>
    {/each}
</div>

{#if towerPivotRows?.length > 0}
<div style="overflow-x:auto; border-radius:8px; border:1px solid #E5E7EB;">
    <table style="width:100%; border-collapse:collapse; font-size:0.875rem;">
        <!-- Header -->
        <thead>
            <tr style="background:#F9FAFB; border-bottom:2px solid #802cd7;">
                <th
                    on:click={() => setDrillSort('name')}
                    style="text-align:left; padding:10px 14px; font-weight:700; color:#211030; min-width:280px; cursor:pointer; user-select:none;"
                >
                    Program / Subprogram / Cost Pool
                    {#if drillSortCol === 'name'}{drillSortDir === -1 ? ' ↓' : ' ↑'}{/if}
                </th>
                {#each drillViewYears as yr}
                    <th
                        on:click={() => setDrillSort('FY' + yr)}
                        style="text-align:right; padding:10px 14px; font-weight:700; color:#211030; white-space:nowrap; cursor:pointer; user-select:none;"
                    >
                        FY{yr}{#if drillSortCol === 'FY' + yr}{drillSortDir === -1 ? ' ↓' : ' ↑'}{/if}
                    </th>
                {/each}
            </tr>
        </thead>
        <tbody>
            <!-- Grand Total -->
            <tr style="background:#FFF7F0; border-bottom:1px solid #E5E7EB;">
                <td style="padding:10px 14px; font-weight:700; color:#802cd7;">Total</td>
                {#each drillViewYears as yr}
                    <td style="text-align:right; padding:10px 14px; font-weight:700; color:#802cd7;">{formatAmount(grandTotal['FY' + yr])}</td>
                {/each}
            </tr>
            <!-- Towers (level 1) -->
            {#each sortedTowerPivotRows as tower}
                <tr
                    on:click={() => toggleProgram(tower.name)}
                    style="border-bottom:1px solid #E5E7EB; cursor:pointer; background:white;"
                    onmouseenter="this.style.background='#F9FAFB'"
                    onmouseleave="this.style.background='white'"
                >
                    <td style="padding:10px 14px; font-weight:600; color:#211030;">
                        <span style="margin-right:8px; font-size:0.75rem; color:#802cd7;">{expandedPrograms[tower.name] ? '▼' : '▶'}</span>
                        {tower.name}
                    </td>
                    {#each drillViewYears as yr}
                        <td style="text-align:right; padding:10px 14px; font-weight:600; color:#211030;">{formatAmount(tower['FY' + yr])}</td>
                    {/each}
                </tr>
                <!-- Programs (level 2) -->
                {#if expandedPrograms[tower.name]}
                    {#each getSortedPrograms(tower.name) as prog}
                        <tr
                            on:click={() => toggleTower(tower.name, prog.name)}
                            style="border-bottom:1px solid #F3F4F6; cursor:pointer; background:#FAFAFA;"
                            onmouseenter="this.style.background='#F3F4F6'"
                            onmouseleave="this.style.background='#FAFAFA'"
                        >
                            <td style="padding:8px 14px 8px 36px; color:#374151;">
                                <span style="margin-right:8px; font-size:0.75rem; color:#6B7280;">{expandedTowers[tower.name + '||' + prog.name] ? '▼' : '▶'}</span>
                                {prog.name}
                            </td>
                            {#each drillViewYears as yr}
                                <td style="text-align:right; padding:8px 14px; color:#374151;">{formatAmount(prog['FY' + yr])}</td>
                            {/each}
                        </tr>
                        <!-- Subprograms (level 3) -->
                        {#if expandedTowers[tower.name + '||' + prog.name]}
                            {#each getSortedSubprograms(tower.name, prog.name) as sub}
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
    <Alert status=warning>No program data available for this agency.</Alert>
{/if}
{/if}


{#if viewMode == 'latest'}
## Latest Year Snapshot

{#if tower_breakdown_latest?.length > 0}
    <Grid cols=2>
        <BarChart data={tower_breakdown_latest} x=it_tower y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by Tower — Latest Year" colorPalette={['#802cd7','#b376f6','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C','#E74C3C','#95A5A6','#34495E']}/>
        {#if subprogram_breakdown_latest?.length > 0}
            <BarChart data={subprogram_breakdown_latest} x=subprogram_name y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by Subprogram — Latest Year" colorPalette={['#802cd7','#b376f6','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C']}/>
        {:else}
            <Alert status=warning>No subprogram data available.</Alert>
        {/if}
    </Grid>
{:else}
    <Alert status=warning>No tower data available for this agency.</Alert>
{/if}
{/if}