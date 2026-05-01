---
title: Technology
sidebar_position: 4
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">💻 Technology View</h1>
    <p style="color: #FFC838; font-size: 0.95rem; margin: 4px 0 0 0;">IT Spending Analysis · TBM v5.0.1 Classification</p>
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
```sql g_tower
select distinct it_tower from mbtsa.subprogram_level where is_it=true and it_tower is not null order by it_tower
```
```sql g_desig
select distinct it_designation from mbtsa.subprogram_level where is_it=true and it_designation is not null order by it_designation
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
    and cast(t.fiscal_year as varchar) like '${selectedFy}'
    and coalesce(t.fund_type, '') like '${selectedFund}'
    and coalesce(t.agency_name, '') like '${selectedAgency}'
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
group by b.start_year, b.max_year, b.total_it_spend
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
    const towerChartTitleStyle = {
        fontSize: 14,
        fontWeight: 600,
        color: '#231F20'
    };
    const getTowerChartGrid = () => ({
        top: '15%',
        right: '4%',
        bottom: '11%',
        left: '8%',
        containLabel: true
    });

    $: selectedFy = selectedValue($inputStore?.f_fy);
    $: selectedFund = selectedValue($inputStore?.f_fund);
    $: selectedAgency = selectedValue($inputStore?.f_agency);
    $: viewMode = readInputValue($inputStore?.f_view, 'trend');
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

    ```sql snapshot_towers
    select it_tower, sum(amount) as spend from ${filtered_latest} where it_tower is not null group by it_tower order by spend desc
    ```

    ```sql snapshot_subprograms
    select subprogram_name, sum(amount) as spend from ${filtered_latest} where subprogram_name is not null group by subprogram_name order by spend desc
    ```

    {#if snapshot_towers?.length > 0}
        <BarChart data={snapshot_towers} x=it_tower y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by tower — Latest Year" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C','#E74C3C','#95A5A6','#34495E']}/>
    {:else}
        <Alert status=warning>No tower spend data available for this filter selection.</Alert>
    {/if}

    {#if snapshot_subprograms?.length > 0}
        <BarChart data={snapshot_subprograms} x=subprogram_name y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by subprogram — Latest Year" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C']}/>
    {:else}
        <Alert status=warning>No subprogram spend data available for this filter selection.</Alert>
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

    {#if yearly?.length > 0}
        <ECharts
            height={towerChartHeight}
            config={{
                title: {
                    text: 'Total IT spend by fiscal year',
                    left: 'left',
                    top: 0,
                    textStyle: towerChartTitleStyle
                },
                grid: getTowerChartGrid(),
                tooltip: {
                    trigger: 'axis',
                    formatter: (params) => {
                        if (!params || params.length === 0) return '';
                        const p = params[0];
                        return `<b>${p.axisValue}</b><br/>IT Spend: ${usdCompact(p.value)}`;
                    }
                },
                xAxis: {
                    type: 'category',
                    data: yearly.map((d) => String(d.fiscal_year))
                },
                yAxis: {
                    type: 'value',
                    axisLabel: {
                        formatter: (v) => usdCompact(v)
                    }
                },
                series: [
                    {
                        type: 'bar',
                        barMaxWidth: 36,
                        data: yearly.map((d) => Number(d.total_it_spend) || 0),
                        label: {
                            show: true,
                            position: 'top',
                            distance: 5,
                            color: '#231F20',
                            fontSize: 11,
                            formatter: (p) => usdCompact(p.value)
                        },
                        labelLayout: {
                            hideOverlap: true
                        },
                        itemStyle: {
                            color: '#FFC838'
                        }
                    }
                ]
            }}
        />
    {:else}
        <Alert status=warning>No fiscal-year IT spend data available for this filter selection.</Alert>
    {/if}

    {#if yoy_detail?.length > 0}
        <ECharts
            height={towerChartHeight}
            config={{
                title: {
                    text: 'Year-over-year IT spend change',
                    left: 'left',
                    top: 0,
                    textStyle: towerChartTitleStyle
                },
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
                xAxis: {
                    type: 'category',
                    data: yoy_detail.map((d) => String(d.fiscal_year))
                },
                yAxis: {
                    type: 'value',
                    axisLabel: {
                        formatter: (v) => `${Number(v).toFixed(0)}%`
                    }
                },
                series: [
                    {
                        type: 'bar',
                        data: yoy_detail.map((d) => Number(d.change_pct) || 0),
                        label: {
                            show: true,
                            position: 'top',
                            formatter: (p) => `${(Number(p.value) || 0).toFixed(1)}%`
                        },
                        itemStyle: {
                            color: (p) => ((Number(p.value) || 0) >= 0 ? '#2EAD6B' : '#C8122C')
                        }
                    }
                ]
            }}
        />
    {:else}
        <Alert status=warning>Year-over-year IT spend change is unavailable for this filter selection.</Alert>
    {/if}

---

## Tower Trends (Top 10)

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
    select
        f.fiscal_year,
        f.it_tower,
        sum(f.amount) as spend
    from ${filtered} f
    where f.it_tower in (select it_tower from ${top_towers_trend})
    group by f.fiscal_year, f.it_tower
    order by f.fiscal_year
    ```

    {#if tower_trend?.length > 0}
        <ECharts
            height="520px"
            config={{
                color: ['#C8122C','#FFC838','#231F20','#E04B3F','#C99A06','#6F2030','#5B5148','#F26A3D','#A7842A','#8A3C4A'],
                title: {
                    text: 'Top 10 towers over time',
                    left: 'left',
                    top: 0,
                    textStyle: {
                        fontSize: 14,
                        fontWeight: 600,
                        color: '#231F20'
                    }
                },
                tooltip: {
                    trigger: 'axis',
                    formatter: (params) => {
                        if (!params || params.length === 0) return '';
                        const year = params[0].axisValue;
                        const lines = params.map((p) => {
                            const v = Number(p.value) || 0;
                            const money = Math.abs(v) >= 1e9
                                ? `$${(v / 1e9).toFixed(2)}B`
                                : Math.abs(v) >= 1e6
                                    ? `$${(v / 1e6).toFixed(1)}M`
                                    : `$${Math.round(v).toLocaleString()}`;
                            return `${p.marker} ${p.seriesName}: ${money}`;
                        });
                        return [`<b>${year}</b>`, ...lines].join('<br/>');
                    }
                },
                legend: {
                    type: 'plain',
                    orient: 'horizontal',
                    left: 'center',
                    top: 24,
                    itemGap: 12,
                    textStyle: {
                        fontSize: 11,
                        lineHeight: 14
                    },
                    formatter: (name) => {
                        const raw = String(name || '');
                        const maxLen = 22;
                        if (raw.length <= maxLen) return raw;
                        const splitAt = raw.lastIndexOf(' ', maxLen);
                        if (splitAt > 8) return `${raw.slice(0, splitAt).trim()}\n${raw.slice(splitAt + 1).trim()}`;
                        return `${raw.slice(0, maxLen)}\n${raw.slice(maxLen)}`;
                    }
                },
                grid: {
                    left: 64,
                    right: 24,
                    top: 170,
                    bottom: 46
                },
                xAxis: {
                    type: 'category',
                    data: [...new Set(tower_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b))
                },
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
                    const years = [...new Set(tower_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
                    return {
                        name: towerName,
                        type: 'line',
                        smooth: false,
                        symbol: 'circle',
                        symbolSize: 6,
                        data: years.map((y) => tower_trend.find((d) => String(d.fiscal_year) === y && d.it_tower === towerName)?.spend ?? 0)
                    };
                })
            }}
        />
    {:else}
        <Alert status=warning>No tower trend data is available for this filter selection.</Alert>
    {/if}

---

## Designation Breakdown

    ```sql desig
    select it_designation, sum(amount) as spend, count(distinct subprogram_name) as programs from ${filtered} group by it_designation order by spend desc
    ```

    {#if desig?.length > 0}
        <Grid cols=2>
            <BarChart data={desig} x=it_designation y=spend yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="IT Spend by designation" colorPalette={['#C8122C','#FFC838','#3B7DD8','#E67E22']}/>
            <DataTable data={desig} totalRow=true search=true>
                <Column id=it_designation title="Designation"/>
                <Column id=spend title="IT Spend" fmt=usd2compactviz/>
                <Column id=programs title="Programs"/>
            </DataTable>
        </Grid>
    {:else}
        <Alert status=warning>No designation breakdown data available for this filter selection.</Alert>
    {/if}

---

## Top IT Agencies by Spend

    ```sql agency_it
    select agency_name, sum(amount) as spend from ${filtered} group by agency_name order by spend desc limit 15
    ```

    {#if agency_it?.length > 0}
        <BarChart data={agency_it} x=agency_name y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Top 15 IT agencies by spend" colorPalette={['#C8122C']}/>
    {:else}
        <Alert status=warning>No agency spend data available for this filter selection.</Alert>
    {/if}

---

## Tower Explorer — Click to Drill Down

    <Alert status=info>Click a tower to see sub-towers, agencies, and programs.</Alert>

    ```sql tower_drill
    select it_tower, '/technology/towers/' || replace(it_tower, ' ', '%20') as tower_link,
        sum(amount) as spend, count(distinct agency_name) as agencies, count(distinct subprogram_name) as programs
    from ${filtered} where it_tower is not null group by it_tower order by spend desc
    ```

    {#if tower_drill?.length > 0}
        <DataTable data={tower_drill} link=tower_link totalRow=true search=true>
            <Column id=it_tower title="Tower"/>
            <Column id=spend title="IT Spend" fmt=usd2compactviz/>
            <Column id=agencies title="Agencies"/>
            <Column id=programs title="Programs"/>
        </DataTable>
    {:else}
        <Alert status=warning>No tower explorer data available for this filter selection.</Alert>
    {/if}

{/if}
