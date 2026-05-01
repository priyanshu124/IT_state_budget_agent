---
title: Budget Office
sidebar_position: 3
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 24px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.6rem; font-weight: 700; margin: 6px 0 0 0;">Budget Office View</h1>
</div>

```sql g_fy
select distinct fiscal_year as fy
from mbtsa.agency_level
order by fiscal_year
```
```sql g_fund
select distinct fund_type
from mbtsa.agency_level
where fund_type is not null
order by fund_type
```
```sql g_agency
select distinct agency_name
from mbtsa.agency_level
where agency_name is not null
order by agency_name
```

<Details title=" Filters  click to expand" open=true>

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
    b.fund_type,
    b.agency_name,
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
        end,
        1
    ) as cagr_5y_pct,
    round(
        case
            when budget_10y_ago > 0 and latest_budget > 0
                then (power(latest_budget / budget_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_10y_pct,
    coalesce(cast(max_year as varchar), 'N/A') as max_year_label
from points
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
    select distinct fund_type
    from ${filtered}
    where fund_type is not null
),
matches as (
    select
        d.fund_type,
        r.fund_rank,
        r.fund_color,
        row_number() over (
            partition by d.fund_type
            order by r.fund_rank
        ) as rank_order
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
left join matches m
    on m.fund_type = d.fund_type
    and m.rank_order = 1
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

    // Shared fiscal chart layout so both charts stay visually aligned and easy to tune.
    const fiscalChartHeightPx = 300;
    const fiscalChartHeight = `${fiscalChartHeightPx}px`;
    const fiscalChartTitleStyle = {
        fontSize: 14,
        fontWeight: 600,
        color: '#231F20'
    };
    const getFiscalChartGrid = () => ({
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
        <BigValue data={overview} value=latest_budget fmt=usd2compactviz title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})"/>
        <BigValue data={overview} value=yoy_pct fmt='0.0"%"' title="YoY Change"/>
        <BigValue data={overview} value=cagr_5y_pct fmt='0.0"%"' title="5-Year CAGR"/>
        <BigValue data={overview} value=cagr_10y_pct fmt='0.0"%"' title="10-Year CAGR"/>
    </Grid>
{/if}

{#if viewMode == 'trend'}

---

## Fiscal overview

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

<Grid cols=2>
    {#if yearly?.length > 0}
        <ECharts
            height={fiscalChartHeight}
            config={{
                title: {
                    text: 'Total budget by fiscal year',
                    left: 'left',
                    top: 0,
                    textStyle: fiscalChartTitleStyle
                },
                grid: getFiscalChartGrid(),
                tooltip: {
                    trigger: 'axis',
                    formatter: (params) => {
                        if (!params || params.length === 0) return '';
                        const p = params[0];
                        return `<b>${p.axisValue}</b><br/>Budget: ${usdCompact(p.value)}`;
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
                        data: yearly.map((d) => Number(d.total_budget) || 0),
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
        <Alert status=warning>No fiscal-year totals available for this filter selection.</Alert>
    {/if}
    {#if yoy_detail?.length > 0}
        <ECharts
            height={fiscalChartHeight}
            config={{
                title: {
                    text: 'Year-over-year change',
                    left: 'left',
                    top: 0,
                    textStyle: fiscalChartTitleStyle
                },
                grid: getFiscalChartGrid(),
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
        <Alert status=warning>Year-over-year change is unavailable for this filter selection.</Alert>
    {/if}
</Grid>

---

## Agency trends (top 10)

```sql top_agencies_trend
select
    agency_name,
    sum(amount) as total_budget
from ${filtered}
group by agency_name
order by total_budget desc
limit 10
```

```sql agency_trend
select
    f.fiscal_year,
    f.agency_name,
    sum(f.amount) as spend
from ${filtered} f
where f.agency_name in (select agency_name from ${top_agencies_trend})
group by f.fiscal_year, f.agency_name
order by f.fiscal_year
```

{#if agency_trend?.length > 0}
    <ECharts
        height="520px"
        config={{
            color: ['#C8122C','#FFC838','#231F20','#E04B3F','#C99A06','#6F2030','#5B5148','#F26A3D','#A7842A','#8A3C4A'],
            title: {
            text: 'Top 10 agencies over time',
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
                data: [...new Set(agency_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b))
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
            series: top_agencies_trend.map((agency) => {
                const agencyName = agency.agency_name;
                const years = [...new Set(agency_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
                return {
                    name: agencyName,
                    type: 'line',
                    smooth: false,
                    symbol: 'circle',
                    symbolSize: 6,
                    data: years.map((y) => agency_trend.find((d) => String(d.fiscal_year) === y && d.agency_name === agencyName)?.spend ?? 0)
                };
            })
        }}
    />
{:else}
    <Alert status=warning>No agency trend data is available for this filter selection.</Alert>
{/if}

{/if}

{#if viewMode == 'latest'}

---

## Agency snapshot

```sql agency_snapshot
with latest as (
    select
        agency_name,
        sum(amount) as latest_year_budget
    from ${filtered_latest}
    where agency_name is not null
      and trim(agency_name) <> ''
    group by agency_name
),
prior as (
    select
        agency_name,
        sum(amount) as prior_year_budget
    from ${filtered_prior}
    where agency_name is not null
      and trim(agency_name) <> ''
    group by agency_name
),
hist_5y as (
    select
        f.agency_name,
        sum(f.amount) as budget_5y_ago
    from ${filtered} f
    cross join ${scope_meta} m
    where f.agency_name is not null
      and trim(f.agency_name) <> ''
      and f.fiscal_year = (m.max_year - 5)
    group by f.agency_name
),
hist_10y as (
    select
        f.agency_name,
        sum(f.amount) as budget_10y_ago
    from ${filtered} f
    cross join ${scope_meta} m
    where f.agency_name is not null
      and trim(f.agency_name) <> ''
      and f.fiscal_year = (m.max_year - 10)
    group by f.agency_name
)
select
    l.agency_name,
    '/budget-office/agencies/' || replace(l.agency_name, ' ', '%20') as agency_link,
    l.latest_year_budget as total_budget,
    l.latest_year_budget,
    round(
        (l.latest_year_budget - p.prior_year_budget) * 100.0
        / nullif(p.prior_year_budget, 0),
        1
    ) as yoy_change_pct,
    round(
        case
            when h5.budget_5y_ago > 0 and l.latest_year_budget > 0
                then (power(l.latest_year_budget / h5.budget_5y_ago, 1.0 / 5.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(
        case
            when h10.budget_10y_ago > 0 and l.latest_year_budget > 0
                then (power(l.latest_year_budget / h10.budget_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_10y_pct,
    round(
        l.latest_year_budget * 100.0
        / nullif(m.latest_budget, 0),
        1
    ) as latest_year_pct
from latest l
left join prior p using (agency_name)
left join hist_5y h5 using (agency_name)
left join hist_10y h10 using (agency_name)
cross join ${scope_meta} m
order by l.latest_year_budget desc
```

```sql agency_snapshot_top10
select *
from ${agency_snapshot}
order by latest_year_budget desc
limit 10
```

```sql agency_snapshot_table
select *
from ${agency_snapshot}
order by latest_year_budget desc
limit 200
```

```sql agency_by_fund
with agency_fund as (
    select
        f.agency_name,
        f.fund_type,
        sum(f.amount) as spend,
        coalesce(fp.fund_rank, 99) as fund_rank
    from ${filtered_latest} f
    left join ${fund_profile} fp on fp.fund_type = f.fund_type
    group by f.agency_name, f.fund_type, fp.fund_rank
)
select af.agency_name, af.fund_type, af.spend
from agency_fund af
join (
    select agency_name, sum(spend) as latest_year_budget
    from agency_fund
    group by agency_name
    order by latest_year_budget desc
       limit 10
) t using (agency_name)
order by t.latest_year_budget desc, af.fund_rank, af.spend desc
```

<Grid cols=2>
    {#if agency_snapshot?.length > 0}
        <BarChart data={agency_snapshot_top10} x=agency_name y=latest_year_budget swapXY=true sort=false height=420 yFmt=usd2compactviz xFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz xAxisLabels=true yAxisLabels=false title="Latest year budget by agency" colorPalette={['#C8122C']}/>
    {:else}
        <Alert status=warning>No agency totals available for this filter selection.</Alert>
    {/if}
    {#if agency_by_fund?.length > 0}
        <BarChart data={agency_by_fund} x=agency_name y=spend series=fund_type type=stacked100 swapXY=true sort=false height=420 title="How each agency is funded" colorPalette={['#C8122C','#FFC838','#2EAD6B','#9B1C31','#B08A00','#6A1B2A','#1ABC9C','#F08C46','#5B8FF9','#8A3C4A']} yFmt=pct1 legend=false xAxisLabels=true yAxisLabels=true/>
    {:else}
        <Alert status=warning>No agency-by-fund breakdown is available for this filter selection.</Alert>
    {/if}
</Grid>

{/if}

---

## Fund type analysis

```sql fund_summary
with latest as (
    select
        fund_type,
        sum(amount) as latest_year_budget
    from ${filtered_latest}
    group by fund_type
),
prior as (
    select
        fund_type,
        sum(amount) as prior_year_budget
    from ${filtered_prior}
    group by fund_type
),
hist_5y as (
    select
        f.fund_type,
        sum(f.amount) as budget_5y_ago
    from ${filtered} f
    cross join ${scope_meta} m
    where f.fiscal_year = (m.max_year - 5)
    group by f.fund_type
),
hist_10y as (
    select
        f.fund_type,
        sum(f.amount) as budget_10y_ago
    from ${filtered} f
    cross join ${scope_meta} m
    where f.fiscal_year = (m.max_year - 10)
    group by f.fund_type
)
select
    l.fund_type,
    l.latest_year_budget as total_spend,
    l.latest_year_budget,
    round(
        (l.latest_year_budget - p.prior_year_budget) * 100.0
        / nullif(p.prior_year_budget, 0),
        1
    ) as yoy_change_pct,
    round(
        case
            when h5.budget_5y_ago > 0 and l.latest_year_budget > 0
                then (power(l.latest_year_budget / h5.budget_5y_ago, 1.0 / 5.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(
        case
            when h10.budget_10y_ago > 0 and l.latest_year_budget > 0
                then (power(l.latest_year_budget / h10.budget_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_10y_pct,
    round(
        l.latest_year_budget * 100.0
        / nullif(m.latest_budget, 0),
        1
    ) as latest_year_pct,
    coalesce(fp.fund_rank, 99) as fund_rank,
    coalesce(fp.fund_color, '#4C4743') as fund_color
from latest l
left join prior p using (fund_type)
left join hist_5y h5 using (fund_type)
left join hist_10y h10 using (fund_type)
cross join ${scope_meta} m
left join ${fund_profile} fp on fp.fund_type = l.fund_type
order by total_spend desc
```

```sql fund_trend
select
    f.fiscal_year,
    f.fund_type,
    sum(f.amount) as spend,
    coalesce(fp.fund_rank, 99) as fund_rank
from ${filtered} f
left join ${fund_profile} fp on fp.fund_type = f.fund_type
group by f.fiscal_year, f.fund_type, fp.fund_rank
order by f.fiscal_year, fund_rank
```

> Maryland draws from **different funding sources**. General Funds are state revenue. Federal Funds support Medicaid and SNAP. ARPA/CARES/CRRSA provided temporary pandemic relief peaking in FY2021-22.

{#if viewMode == 'latest'}
    <Grid cols=1>
        <ECharts
            height="390px"
            config={{
                title: {
                    text: 'Fund type share',
                    left: 'center',
                    top: 0,
                    textStyle: {
                        fontSize: 14,
                        fontWeight: 600,
                        color: '#231F20'
                    }
                },
                tooltip: {
                    trigger: 'item',
                    formatter: (p) => {
                        const v = Number(p.value) || 0;
                        const money = Math.abs(v) >= 1e9
                            ? `$${(v / 1e9).toFixed(2)}B`
                            : Math.abs(v) >= 1e6
                                ? `$${(v / 1e6).toFixed(1)}M`
                                : `$${Math.round(v).toLocaleString()}`;
                        return `${p.name}: ${money} (${p.percent}%)`;
                    }
                },
                legend: {
                    type: 'scroll',
                    orient: 'horizontal',
                    left: 'center',
                    top: 24,
                    textStyle: { fontSize: 11 },
                    formatter: (name) => (name && name.length > 28 ? `${name.slice(0, 28)}...` : name)
                },
                series: [
                    {
                        name: 'Fund Type Share',
                        type: 'pie',
                        radius: ['40%', '66%'],
                        center: ['50%', '56%'],
                        avoidLabelOverlap: true,
                        minAngle: 2,
                        itemStyle: {
                            borderColor: '#FFFFFF',
                            borderWidth: 2
                        },
                        label: {
                            formatter: (p) => (p.percent >= 6 ? `${p.percent}%` : '')
                        },
                        data: fund_summary.map((d) => ({
                            name: d.fund_type,
                            value: d.total_spend,
                            itemStyle: { color: d.fund_color }
                        }))
                    }
                ]
            }}
        />
    </Grid>

    {#if fund_summary?.length > 0}
        <DataTable data={fund_summary} totalRow=true search=true>
            <Column id=fund_type title="Fund Type"/>
            <Column id=latest_year_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
            <Column id=latest_year_pct title="% of Latest Year" fmt='0.0"%"'/>
            <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_5y_pct title="5-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_10y_pct title="10-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
        </DataTable>
    {:else}
        <Alert status=warning>No fund summary data is available for this filter selection.</Alert>
    {/if}

    ---

    ## Agency snapshot table

    <Alert status=info>Click an agency row to open that agency's detail page.</Alert>

    {#if agency_snapshot?.length > 0}
        <DataTable data={agency_snapshot_table} link=agency_link totalRow=true rows=12 search=true>
            <Column id=agency_name title="Agency"/>
            <Column id=latest_year_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
            <Column id=latest_year_pct title="% of Latest Year" fmt='0.0"%"'/>
            <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_5y_pct title="5-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_10y_pct title="10-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
        </DataTable>
    {:else}
        <Alert status=warning>No agency table data is available for this filter selection.</Alert>
    {/if}
{:else}
    <ECharts
        height="420px"
        config={{
            title: {
                text: 'Fund composition over time',
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
                axisPointer: { type: 'shadow' },
                formatter: (params) => {
                    if (!params || params.length === 0) return '';
                    const year = params[0].axisValue;
                    const lines = params
                        .filter((p) => Number(p.value) !== 0)
                        .map((p) => {
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
                type: 'scroll',
                orient: 'horizontal',
                left: 'center',
                top: 22,
                textStyle: { fontSize: 11 },
                formatter: (name) => (name && name.length > 22 ? `${name.slice(0, 22)}...` : name)
            },
            grid: {
                left: 64,
                right: 24,
                top: 70,
                bottom: 46
            },
            xAxis: {
                type: 'category',
                data: [...new Set(fund_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b))
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
            series: [...new Set(fund_trend.map((d) => d.fund_type))]
                .sort((a, b) => {
                    const ra = fund_trend.find((d) => d.fund_type === a)?.fund_rank ?? 99;
                    const rb = fund_trend.find((d) => d.fund_type === b)?.fund_rank ?? 99;
                    return ra - rb;
                })
                .map((fund) => {
                    const color = fund_summary.find((d) => d.fund_type === fund)?.fund_color ?? '#4C4743';
                    const years = [...new Set(fund_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
                    return {
                        name: fund,
                        type: 'bar',
                        stack: 'total',
                        emphasis: { focus: 'series' },
                        itemStyle: { color },
                        data: years.map((y) => fund_trend.find((d) => String(d.fiscal_year) === y && d.fund_type === fund)?.spend ?? 0)
                    };
                })
        }}
    />

---

## Agency trend table

<Alert status=info>Click an agency row to open that agency's detail page.</Alert>

<Grid cols=1>
    <Dropdown name=f_agency_table_view title="Table View" defaultValue="5">
        <DropdownOption value="3" valueLabel="3 Years"/>
        <DropdownOption value="5" valueLabel="5 Years"/>
        <DropdownOption value="all" valueLabel="All Years"/>
    </Dropdown>
</Grid>

```sql agency_trend_table
with base as (
    select
        f.agency_name,
        cast(f.fiscal_year as int) as fiscal_year,
        sum(f.amount) as spend
    from ${filtered} f
    where f.agency_name is not null
      and trim(f.agency_name) <> ''
    group by f.agency_name, cast(f.fiscal_year as int)
),
meta as (
    select max_year
    from ${scope_meta}
)
select
    b.agency_name,
    '/budget-office/agencies/' || replace(b.agency_name, ' ', '%20') as agency_link,
    sum(case when b.fiscal_year = m.max_year - 10 then b.spend else 0 end) as fy_m10,
    sum(case when b.fiscal_year = m.max_year - 9 then b.spend else 0 end) as fy_m9,
    sum(case when b.fiscal_year = m.max_year - 8 then b.spend else 0 end) as fy_m8,
    sum(case when b.fiscal_year = m.max_year - 7 then b.spend else 0 end) as fy_m7,
    sum(case when b.fiscal_year = m.max_year - 6 then b.spend else 0 end) as fy_m6,
    sum(case when b.fiscal_year = m.max_year - 5 then b.spend else 0 end) as fy_m5,
    sum(case when b.fiscal_year = m.max_year - 4 then b.spend else 0 end) as fy_m4,
    sum(case when b.fiscal_year = m.max_year - 3 then b.spend else 0 end) as fy_m3,
    sum(case when b.fiscal_year = m.max_year - 2 then b.spend else 0 end) as fy_m2,
    sum(case when b.fiscal_year = m.max_year - 1 then b.spend else 0 end) as fy_m1,
    sum(case when b.fiscal_year = m.max_year then b.spend else 0 end) as fy_m0
from base b
cross join meta m
group by b.agency_name, m.max_year
order by fy_m0 desc
limit 100
```

{#if agency_trend_table?.length > 0}
    {#if (inputs.f_agency_table_view?.value ?? '5') == '3'}
        <DataTable data={agency_trend_table} link=agency_link totalRow=true rows=20 search=true>
            <Column id=agency_name title="Agency"/>
            <Column id=fy_m2 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 2}" fmt=usd2compactviz/>
            <Column id=fy_m1 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 1}" fmt=usd2compactviz/>
            <Column id=fy_m0 title="FY {overview?.[0]?.max_year_label ?? 'N/A'}" fmt=usd2compactviz/>
        </DataTable>
    {:else if (inputs.f_agency_table_view?.value ?? '5') == '5'}
        <DataTable data={agency_trend_table} link=agency_link totalRow=true rows=20 search=true>
            <Column id=agency_name title="Agency"/>
            <Column id=fy_m4 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 4}" fmt=usd2compactviz/>
            <Column id=fy_m3 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 3}" fmt=usd2compactviz/>
            <Column id=fy_m2 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 2}" fmt=usd2compactviz/>
            <Column id=fy_m1 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 1}" fmt=usd2compactviz/>
            <Column id=fy_m0 title="FY {overview?.[0]?.max_year_label ?? 'N/A'}" fmt=usd2compactviz/>
        </DataTable>
    {:else}
        <DataTable data={agency_trend_table} link=agency_link totalRow=true rows=20 search=true>
            <Column id=agency_name title="Agency"/>
            <Column id=fy_m10 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 10}" fmt=usd2compactviz/>
            <Column id=fy_m9 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 9}" fmt=usd2compactviz/>
            <Column id=fy_m8 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 8}" fmt=usd2compactviz/>
            <Column id=fy_m7 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 7}" fmt=usd2compactviz/>
            <Column id=fy_m6 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 6}" fmt=usd2compactviz/>
            <Column id=fy_m5 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 5}" fmt=usd2compactviz/>
            <Column id=fy_m4 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 4}" fmt=usd2compactviz/>
            <Column id=fy_m3 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 3}" fmt=usd2compactviz/>
            <Column id=fy_m2 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 2}" fmt=usd2compactviz/>
            <Column id=fy_m1 title="FY {Number(overview?.[0]?.max_year_label ?? 0) - 1}" fmt=usd2compactviz/>
            <Column id=fy_m0 title="FY {overview?.[0]?.max_year_label ?? 'N/A'}" fmt=usd2compactviz/>
        </DataTable>
    {/if}
{:else}
    <Alert status=warning>No agency trend table data is available for this filter selection.</Alert>
{/if}
{/if}





