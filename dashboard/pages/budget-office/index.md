---
title: Budget Office
sidebar_position: 3
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">🏛️ Budget Office View</h1>
    <p style="color: #FFC838; font-size: 0.95rem; margin: 4px 0 0 0;">State of Maryland — Operating Budget Overview</p>
</div>

```sql g_fy
select distinct fiscal_year as fy from mbtsa.budget order by fiscal_year
```
```sql g_fund
select distinct fund_type from mbtsa.budget where fund_type is not null order by fund_type
```
```sql g_cat
select distinct category_name from mbtsa.budget where category_name is not null order by category_name
```
```sql g_agency
select distinct agency_name from mbtsa.budget where agency_name is not null order by agency_name
```
```sql g_unit
select distinct unit_name from mbtsa.budget where unit_name is not null order by unit_name
```
```sql g_program
select distinct program_name from mbtsa.budget where program_name is not null order by program_name
```
```sql g_subprogram
select distinct subprogram_name from mbtsa.budget where subprogram_name is not null order by subprogram_name
```

<Details title="🔍 Filters — click to expand" open=true>

<Grid cols=4>
    <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue={['%']} multiple=true><DropdownOption value="%" valueLabel="All Years"/></Dropdown>
    <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%"><DropdownOption value="%" valueLabel="All Fund Types"/></Dropdown>
    <Dropdown name=f_cat data={g_cat} value=category_name title="Category" defaultValue="%"><DropdownOption value="%" valueLabel="All Categories"/></Dropdown>
    <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%"><DropdownOption value="%" valueLabel="All Agencies"/></Dropdown>
</Grid>
<Grid cols=3>
    <Dropdown name=f_unit data={g_unit} value=unit_name title="Unit" defaultValue="%"><DropdownOption value="%" valueLabel="All Units"/></Dropdown>
    <Dropdown name=f_program data={g_program} value=program_name title="Program" defaultValue="%"><DropdownOption value="%" valueLabel="All Programs"/></Dropdown>
    <Dropdown name=f_subprogram data={g_subprogram} value=subprogram_name title="Subprogram" defaultValue="%"><DropdownOption value="%" valueLabel="All Subprograms"/></Dropdown>
</Grid>

</Details>

```sql filtered
with fy_filter as (
    select '${(((Array.isArray(inputs.f_fy.rawValues) ? inputs.f_fy.rawValues.map((v) => String(v?.value ?? v)).filter((v) => v && v !== "undefined" && v !== "null").join(",") : "") || "%").replace(/'/g, "''"))}' as fy_csv
)
select
    cast(b.fiscal_year as int) as fiscal_year,
    b.fund_type,
    b.category_name,
    b.agency_name,
    b.unit_name,
    b.program_name,
    b.subprogram_name,
    b.amount
from mbtsa.budget b
cross join fy_filter f
where (
        list_contains(string_split(f.fy_csv, ','), '%')
        or cast(cast(b.fiscal_year as bigint) as varchar) in (
            select trim(value)
            from unnest(string_split(f.fy_csv, ',')) as years(value)
            where trim(value) <> ''
        )
    )
    and b.fund_type like '${(inputs.f_fund.value ?? "%").replace(/'/g, "''")}'
    and b.category_name like '${(inputs.f_cat.value ?? "%").replace(/'/g, "''")}'
    and b.agency_name like '${(inputs.f_agency.value ?? "%").replace(/'/g, "''")}'
    and b.unit_name like '${(inputs.f_unit.value ?? "%").replace(/'/g, "''")}'
    and b.program_name like '${(inputs.f_program.value ?? "%").replace(/'/g, "''")}'
    and b.subprogram_name like '${(inputs.f_subprogram.value ?? "%").replace(/'/g, "''")}'
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

```sql overview
with points as (
    select
        m.*, 
        y_start.total_budget as start_budget,
        y_end.total_budget as end_budget
    from ${scope_meta} m
    left join ${yearly_rollup} y_start on y_start.fiscal_year = m.start_year
    left join ${yearly_rollup} y_end on y_end.fiscal_year = m.max_year
)
select
    total_budget,
    latest_budget,
    round((latest_budget - prior_budget) * 100.0 / nullif(prior_budget, 0), 1) as yoy_pct,
    round(
        case
            when start_budget > 0 and end_budget > 0 and max_year > start_year
                then (power(end_budget / start_budget, 1.0 / (max_year - start_year)) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
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
        ('american rescue plan act%', 4, '#3B7DD8', true),
        ('coronavirus aid, relief, and economic security act%', 5, '#E67E22', true),
        ('coronavirus response and relief sup act%', 6, '#8E44AD', true),
        ('federal funds (covid)%', 7, '#1ABC9C', true)
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
    coalesce(m.fund_color, '#95A5A6') as fund_color
from distinct_funds d
left join matches m
    on m.fund_type = d.fund_type
    and m.rank_order = 1
```

<Grid cols=4>
    <BigValue data={overview} value=total_budget fmt=usd2compactviz title="Total Budget"/>
    <BigValue data={overview} value=latest_budget fmt=usd2compactviz title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})"/>
    <BigValue data={overview} value=yoy_pct fmt='0.0"%"' title="YoY Change"/>
    <BigValue data={overview} value=cagr_5y_pct fmt='0.0"%"' title="CAGR (Selected Years)"/>
</Grid>

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
        <BarChart data={yearly} x=fiscal_year y=total_budget yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Total budget by fiscal year" colorPalette={['#C8122C']}/>
    {:else}
        <Alert status=warning>No fiscal-year totals available for this filter selection.</Alert>
    {/if}
    {#if yoy_detail?.length > 0}
        <BarChart data={yoy_detail} x=fiscal_year y=change_pct yFmt='0.0"%"' labels=true title="Year-over-year change (%)" colorPalette={['#2EAD6B','#C8122C']}/>
    {:else}
        <Alert status=warning>Year-over-year change is unavailable for this filter selection.</Alert>
    {/if}
</Grid>

---

## Where the money goes

```sql categories
select
    f.category_name,
    sum(f.amount) as total_spend,
    sum(case when f.fiscal_year = m.max_year then f.amount else 0 end) as latest_year_budget,
    round(
        (
            sum(case when f.fiscal_year = m.max_year then f.amount else 0 end)
            - sum(case when f.fiscal_year = m.prior_year then f.amount else 0 end)
        ) * 100.0
        / nullif(sum(case when f.fiscal_year = m.prior_year then f.amount else 0 end), 0),
        1
    ) as yoy_change_pct,
    round(
        case
            when sum(case when f.fiscal_year = m.start_year then f.amount else 0 end) > 0
             and sum(case when f.fiscal_year = m.max_year then f.amount else 0 end) > 0
             and m.max_year > m.start_year
                then (
                    power(
                        sum(case when f.fiscal_year = m.max_year then f.amount else 0 end)
                        / sum(case when f.fiscal_year = m.start_year then f.amount else 0 end),
                        1.0 / (m.max_year - m.start_year)
                    ) - 1.0
                ) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(sum(f.amount) * 100.0 / nullif(m.total_budget, 0), 1) as budget_pct
from ${filtered} f
cross join ${scope_meta} m
group by f.category_name, m.start_year, m.max_year, m.prior_year, m.total_budget
order by total_spend desc
```

```sql cat_by_fund
with cat_fund as (
    select
        f.category_name,
        f.fund_type,
        sum(f.amount) as spend,
        coalesce(fp.fund_rank, 99) as fund_rank
    from ${filtered} f
    left join ${fund_profile} fp on fp.fund_type = f.fund_type
    group by f.category_name, f.fund_type, fp.fund_rank
)
select cf.category_name, cf.fund_type, cf.spend
from cat_fund cf
join (
    select category_name, sum(spend) as total_budget
    from cat_fund
    group by category_name
) ct using (category_name)
order by ct.total_budget desc, cf.fund_rank, cf.spend desc
```

<Grid cols=2>
    {#if categories?.length > 0}
        <BarChart data={categories} x=category_name y=total_spend swapXY=true sort=false height=420 yFmt=usd2compactviz xFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz xAxisLabels=true yAxisLabels=false title="Total budget by category" colorPalette={['#C8122C']}/>
    {:else}
        <Alert status=warning>No category totals available for this filter selection.</Alert>
    {/if}
    {#if cat_by_fund?.length > 0}
        <BarChart data={cat_by_fund} x=category_name y=spend series=fund_type type=stacked100 swapXY=true sort=false height=420 title="How each category is funded" colorPalette={['#C8122C','#FFC838','#2EAD6B','#3B7DD8','#E67E22','#8E44AD','#1ABC9C','#95A5A6']} yFmt=pct1 legend=false xAxisLabels=true yAxisLabels=true/>
    {:else}
        <Alert status=warning>No category-by-fund breakdown is available for this filter selection.</Alert>
    {/if}
</Grid>

{#if categories?.length > 0}
    <DataTable data={categories} totalRow=true rows=12 search=true>
        <Column id=category_name title="Category"/>
        <Column id=total_spend title="Total Budget" fmt=usd2compactviz/>
        <Column id=budget_pct title="% of Total" fmt='0.0"%"'/>
        <Column id=latest_year_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
        <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
        <Column id=cagr_5y_pct title="CAGR (Selected Years)" fmt='0.0"%"' totalAgg="-"/>
    </DataTable>
{:else}
    <Alert status=warning>No category table data is available for this filter selection.</Alert>
{/if}

---

## Fund type analysis

```sql fund_summary
select
    f.fund_type,
    sum(f.amount) as total_spend,
    sum(case when f.fiscal_year = m.max_year then f.amount else 0 end) as latest_year_budget,
    round(
        (
            sum(case when f.fiscal_year = m.max_year then f.amount else 0 end)
            - sum(case when f.fiscal_year = m.prior_year then f.amount else 0 end)
        ) * 100.0
        / nullif(sum(case when f.fiscal_year = m.prior_year then f.amount else 0 end), 0),
        1
    ) as yoy_change_pct,
    round(
        case
            when sum(case when f.fiscal_year = m.start_year then f.amount else 0 end) > 0
             and sum(case when f.fiscal_year = m.max_year then f.amount else 0 end) > 0
             and m.max_year > m.start_year
                then (
                    power(
                        sum(case when f.fiscal_year = m.max_year then f.amount else 0 end)
                        / sum(case when f.fiscal_year = m.start_year then f.amount else 0 end),
                        1.0 / (m.max_year - m.start_year)
                    ) - 1.0
                ) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(sum(f.amount) * 100.0 / nullif(m.total_budget, 0), 1) as pct,
    coalesce(fp.fund_rank, 99) as fund_rank,
    coalesce(fp.fund_color, '#95A5A6') as fund_color
from ${filtered} f
cross join ${scope_meta} m
left join ${fund_profile} fp on fp.fund_type = f.fund_type
group by f.fund_type, m.start_year, m.max_year, m.prior_year, m.total_budget, fp.fund_rank, fp.fund_color
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

> Maryland draws from **7 funding sources**. General Funds are own-source revenue. Federal Funds support Medicaid and SNAP. ARPA/CARES/CRRSA provided temporary pandemic relief peaking in FY2021-22.

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
                const color = fund_summary.find((d) => d.fund_type === fund)?.fund_color ?? '#95A5A6';
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

{#if fund_summary?.length > 0}
    <DataTable data={fund_summary} totalRow=true search=true>
        <Column id=fund_type title="Fund Type"/>
        <Column id=total_spend title="Total Budget" fmt=usd2compactviz/>
        <Column id=pct title="% of Total" fmt='0.0"%"'/>
        <Column id=latest_year_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
        <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
        <Column id=cagr_5y_pct title="CAGR (Selected Years)" fmt='0.0"%"' totalAgg="-"/>
    </DataTable>
{:else}
    <Alert status=warning>No fund summary data is available for this filter selection.</Alert>
{/if}

---

## Category trends (top 6)

```sql top_categories
select category_name
from ${categories}
order by total_spend desc
limit 6
```

```sql cat_trend
select
    f.fiscal_year,
    f.category_name,
    sum(f.amount) as spend
from ${filtered} f
where f.category_name in (select category_name from ${top_categories})
group by f.fiscal_year, f.category_name
order by f.fiscal_year
```

{#if cat_trend?.length > 0}
    <LineChart data={cat_trend} x=fiscal_year y=spend series=category_name yFmt=usd2compactviz markers=true title="Top 6 categories over time" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD']}/>
{:else}
    <Alert status=warning>No category trend data is available for this filter selection.</Alert>
{/if}

---

## Budget explorer — click to drill down

<Alert status=info>Click any agency to drill into: Agency → Unit → Program → Subprogram.</Alert>

```sql agency_drill
select
    f.agency_name,
    '/budget-office/agencies/' || f.agency_name as agency_link,
    sum(f.amount) as total_budget,
    sum(case when f.fiscal_year = m.max_year then f.amount else 0 end) as latest_year_budget,
    round(
        (
            sum(case when f.fiscal_year = m.max_year then f.amount else 0 end)
            - sum(case when f.fiscal_year = m.prior_year then f.amount else 0 end)
        ) * 100.0
        / nullif(sum(case when f.fiscal_year = m.prior_year then f.amount else 0 end), 0),
        1
    ) as yoy_change_pct,
    round(
        case
            when sum(case when f.fiscal_year = m.start_year then f.amount else 0 end) > 0
             and sum(case when f.fiscal_year = m.max_year then f.amount else 0 end) > 0
             and m.max_year > m.start_year
                then (
                    power(
                        sum(case when f.fiscal_year = m.max_year then f.amount else 0 end)
                        / sum(case when f.fiscal_year = m.start_year then f.amount else 0 end),
                        1.0 / (m.max_year - m.start_year)
                    ) - 1.0
                ) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(sum(f.amount) * 100.0 / nullif(m.total_budget, 0), 1) as budget_pct
from ${filtered} f
cross join ${scope_meta} m
group by f.agency_name, m.start_year, m.max_year, m.prior_year, m.total_budget
order by total_budget desc
```

{#if agency_drill?.length > 0}
    <DataTable data={agency_drill} link=agency_link totalRow=true search=true rows=20>
        <Column id=agency_name title="Agency"/>
        <Column id=total_budget title="Total Budget" fmt=usd2compactviz/>
        <Column id=budget_pct title="% of Total" fmt='0.0"%"'/>
        <Column id=latest_year_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
        <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
        <Column id=cagr_5y_pct title="CAGR (Selected Years)" fmt='0.0"%"' totalAgg="-"/>
    </DataTable>
{:else}
    <Alert status=warning>No agency drilldown data is available for this filter selection.</Alert>
{/if}
