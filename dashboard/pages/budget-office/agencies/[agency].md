---
title: "{params.agency}"
prerender: false
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 24px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 28px;">
    <p style="color: rgba(255,255,255,0.6); font-size: 0.8rem; margin: 0;"><a href="/budget-office" style="color: #FFC838; text-decoration: none;">🏛️ Budget Office</a> → Agency</p>
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.5rem; font-weight: 700; margin: 6px 0 0 0;">{params.agency}</h1>
</div>

```sql g_fy
select distinct fiscal_year as fy
from mbtsa.budget
where agency_name = '${(params.agency ?? '').replace(/'/g, "''")}'
order by fiscal_year
```

<Grid cols=1>
    <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue="%" multiple=true><DropdownOption value="%" valueLabel="All Years"/></Dropdown>
</Grid>

```sql scope_filtered
with fy_filter as (
    select '${(((Array.isArray(inputs.f_fy.rawValues) ? inputs.f_fy.rawValues.map((v) => String(v?.value ?? v)).filter((v) => v && v !== "undefined" && v !== "null").join(",") : "") || String(inputs.f_fy.value ?? "%")).replace(/'/g, "''"))}' as fy_csv
)
select *
from mbtsa.budget b
cross join fy_filter f
where b.agency_name = '${(params.agency ?? '').replace(/'/g, "''")}'
  and (
      list_contains(string_split(f.fy_csv, ','), '%')
      or cast(cast(b.fiscal_year as bigint) as varchar) in (
          select trim(value)
          from unnest(string_split(f.fy_csv, ',')) as years(value)
          where trim(value) <> ''
      )
  )
```

```sql kpi
select
    sum(amount) as total_budget
from ${scope_filtered}
```

```sql yoy
with yearly as (
    select cast(fiscal_year as int) as fiscal_year, sum(amount) as total_budget
    from ${scope_filtered}
    group by 1
),
latest as (
    select max(fiscal_year) as latest_year
    from yearly
),
prior as (
    select max(y.fiscal_year) as prior_year
    from yearly y
    cross join latest l
    where y.fiscal_year < l.latest_year
)
select
    yl.total_budget as latest,
    yp.total_budget as prior,
    round((yl.total_budget - yp.total_budget) * 100.0 / nullif(yp.total_budget, 0), 1) as yoy_pct
from latest l
left join prior p on true
left join yearly yl on yl.fiscal_year = l.latest_year
left join yearly yp on yp.fiscal_year = p.prior_year
```

```sql cagr_5y
with yearly as (
    select cast(fiscal_year as int) as fiscal_year, sum(amount) as total_budget
    from ${scope_filtered}
    group by 1
),
bounds as (
    select min(fiscal_year) as start_year, max(fiscal_year) as end_year
    from yearly
),
points as (
    select
        b.start_year,
        b.end_year,
        y_start.total_budget as start_budget,
        y_end.total_budget as end_budget
    from bounds b
    left join yearly y_start on y_start.fiscal_year = b.start_year
    left join yearly y_end on y_end.fiscal_year = b.end_year
)
select
    round(
        case
            when start_budget > 0 and end_budget > 0 and end_year > start_year
                then (power(end_budget / start_budget, 1.0 / (end_year - start_year)) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct
from points
```

```sql selected_year_meta
select
    coalesce(cast(max(cast(fiscal_year as int)) as varchar), 'N/A') as max_year
from ${scope_filtered}
```

<Grid cols=4>
    <BigValue data={kpi} value=total_budget fmt=usd2compactviz title="Total Budget"/>
    <BigValue data={yoy} value=latest fmt=usd2compactviz title="Latest Year ({selected_year_meta?.[0]?.max_year ?? 'N/A'})"/>
    <BigValue data={yoy} value=yoy_pct fmt='0.0"%"' title="YoY Change"/>
    <BigValue data={cagr_5y} value=cagr_5y_pct fmt='0.0"%"' title="CAGR (Selected Years)"/>
</Grid>

```sql trend
select fiscal_year, sum(amount) as budget
from ${scope_filtered}
group by fiscal_year
order by fiscal_year
```

```sql by_fund
select
    fund_type,
    sum(amount) as budget,
    case
        when lower(fund_type) = 'federal funds' then 1
        when lower(fund_type) = 'general funds' then 2
        when lower(fund_type) = 'special funds' then 3
        when lower(fund_type) like 'american rescue plan act%' then 4
        when lower(fund_type) like 'coronavirus aid, relief, and economic security act%' then 5
        when lower(fund_type) like 'coronavirus response and relief sup act%' then 6
        when lower(fund_type) like 'federal funds (covid)%' then 7
        else 99
    end as fund_rank,
    case
        when lower(fund_type) = 'federal funds' then '#C8122C'
        when lower(fund_type) = 'general funds' then '#FFC838'
        when lower(fund_type) = 'special funds' then '#2EAD6B'
        when lower(fund_type) like 'american rescue plan act%' then '#3B7DD8'
        when lower(fund_type) like 'coronavirus aid, relief, and economic security act%' then '#E67E22'
        when lower(fund_type) like 'coronavirus response and relief sup act%' then '#8E44AD'
        when lower(fund_type) like 'federal funds (covid)%' then '#1ABC9C'
        else '#95A5A6'
    end as fund_color
from ${scope_filtered}
group by fund_type
order by fund_rank, budget desc
```

<Grid cols=2>
    <BarChart data={trend} x=fiscal_year y=budget yFmt=usd2compactviz labels=true height=360 title="Budget by fiscal year" colorPalette={['#C8122C']}/>
    <ECharts
        height="360px"
        config={{
            title: {
                text: 'By fund type',
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
                    data: by_fund.map((d) => ({
                        name: d.fund_type,
                        value: d.budget,
                        itemStyle: { color: d.fund_color }
                    }))
                }
            ]
        }}
    />
</Grid>

---

## Units — click to drill down

```sql units
with latest as (
    select max(cast(fiscal_year as int)) as fy
    from ${scope_filtered}
),
prior as (
    select max(cast(fiscal_year as int)) as fy
    from ${scope_filtered}
    where cast(fiscal_year as int) < (select fy from latest)
),
bounds as (
    select min(cast(fiscal_year as int)) as start_year, max(cast(fiscal_year as int)) as end_year
    from ${scope_filtered}
),
totals as (
    select sum(amount) as all_budget
    from ${scope_filtered}
)
select
    unit_name,
    '/budget-office/units/' || unit_name || '?agency=' || '${(params.agency ?? '').replace(/'/g, "''")}' as unit_link,
    sum(amount) as total_budget,
    sum(case when cast(fiscal_year as int) = l.fy then amount else 0 end) as latest_year_budget,
    round(
        (
            sum(case when cast(fiscal_year as int) = l.fy then amount else 0 end)
            - sum(case when cast(fiscal_year as int) = p.fy then amount else 0 end)
        ) * 100.0
        / nullif(sum(case when cast(fiscal_year as int) = p.fy then amount else 0 end), 0),
        1
    ) as yoy_change_pct,
    round(
        case
            when sum(case when cast(fiscal_year as int) = b.start_year then amount else 0 end) > 0
             and sum(case when cast(fiscal_year as int) = b.end_year then amount else 0 end) > 0
             and b.end_year > b.start_year
                then (
                    power(
                        sum(case when cast(fiscal_year as int) = b.end_year then amount else 0 end)
                        / sum(case when cast(fiscal_year as int) = b.start_year then amount else 0 end),
                        1.0 / (b.end_year - b.start_year)
                    ) - 1.0
                ) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(sum(amount) * 100.0 / nullif((select all_budget from totals), 0), 1) as budget_pct
from ${scope_filtered}
cross join latest l
cross join prior p
cross join bounds b
group by unit_name, l.fy, p.fy, b.start_year, b.end_year
order by total_budget desc
```

<DataTable data={units} link=unit_link totalRow=true search=true filter=true>
    <Column id=unit_name title="Unit"/>
    <Column id=total_budget title="Total Budget" fmt=usd2compactviz/>
    <Column id=budget_pct title="% of Total" fmt='0.0"%"'/>
    <Column id=latest_year_budget title="Latest Year ({selected_year_meta?.[0]?.max_year ?? 'N/A'})" fmt=usd2compactviz/>
    <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
    <Column id=cagr_5y_pct title="CAGR (Selected Years)" fmt='0.0"%"' totalAgg="-"/>
</DataTable>

<p style="font-size: 0.75rem; color: #888; font-style: italic; text-align: center;">Data: Maryland Operating Budget, FY2020–FY2027</p>
