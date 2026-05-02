---
title: Variance Analysis
sidebar_position: 5
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 24px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.6rem; font-weight: 700; margin: 6px 0 0 0;">📊 Variance Analysis</h1>
    <p style="color: rgba(255,255,255,0.7); font-size: 0.85rem; margin: 4px 0 0 0;">Year-over-year change detection across agencies, units, and programs</p>
</div>

```sql g_fy_all
select distinct fiscal_year as fy from mbtsa.program_level order by fiscal_year desc
```
```sql g_agency
select distinct agency_name from mbtsa.program_level where agency_name is not null order by agency_name
```
```sql g_fund
select distinct fund_type from mbtsa.program_level where fund_type is not null order by fund_type
```

<Details title=" Filters  click to expand" open=true>
<Grid cols=3>
    <Dropdown name=f_year_a data={g_fy_all} value=fy title="Compare Year (A)" defaultValue="%"><DropdownOption value="%" valueLabel="Latest Year"/></Dropdown>
    <Dropdown name=f_year_b data={g_fy_all} value=fy title="Base Year (B)" defaultValue="%"><DropdownOption value="%" valueLabel="Prior Year"/></Dropdown>
    <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%"><DropdownOption value="%" valueLabel="All Agencies"/></Dropdown>
</Grid>
</Details>

```sql year_bounds
select
    max(fiscal_year)                                    as latest_year,
    max(fiscal_year) - 1                               as prior_year
from mbtsa.program_level
where total_budget_amount > 0
```

```sql agency_variance
with a as (
        select agency_name, sum(total_budget_amount) as spend_a
        from mbtsa.program_level
    where fiscal_year = (select latest_year from ${year_bounds})
      and coalesce(agency_name,'') like '${inputs.f_agency.value ?? "%"}'
    group by agency_name
),
b as (
        select agency_name, sum(total_budget_amount) as spend_b
        from mbtsa.program_level
    where fiscal_year = (select prior_year from ${year_bounds})
      and coalesce(agency_name,'') like '${inputs.f_agency.value ?? "%"}'
    group by agency_name
)
select
    coalesce(a.agency_name, b.agency_name) as agency_name,
    coalesce(a.spend_a, 0)                 as latest_year,
    coalesce(b.spend_b, 0)                 as prior_year,
    coalesce(a.spend_a, 0) - coalesce(b.spend_b, 0) as change_amt,
    round((coalesce(a.spend_a,0) - coalesce(b.spend_b,0)) * 100.0
          / nullif(b.spend_b, 0), 1)       as change_pct
from a full outer join b using (agency_name)
order by abs(change_amt) desc
```

```sql variance_summary
select
    count(case when change_pct > 10 then 1 end)   as agencies_up,
    count(case when change_pct < -10 then 1 end)  as agencies_down,
    sum(change_amt)                                as net_change,
    max(change_pct)                                as max_increase,
    min(change_pct)                                as max_decrease
from ${agency_variance}
```

<Grid cols=4>
    <BigValue data={variance_summary} value=net_change fmt=usd2compactviz title="Net YoY Change"/>
    <BigValue data={variance_summary} value=agencies_up title="Agencies Up >10%"/>
    <BigValue data={variance_summary} value=agencies_down title="Agencies Down >10%"/>
    <BigValue data={variance_summary} value=max_increase fmt='0.0"%"' title="Largest Increase"/>
</Grid>

---

## Agency-Level Variance

<DataTable data={agency_variance} totalRow=true search=true rows=20>
    <Column id=agency_name title="Agency"/>
    <Column id=latest_year title="Latest Year" fmt=usd2compactviz/>
    <Column id=prior_year title="Prior Year" fmt=usd2compactviz/>
    <Column id=change_amt title="Change ($)" fmt=usd2compactviz/>
    <Column id=change_pct title="Change (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>

---

## Top Increases

```sql top_increases
select agency_name, change_amt, change_pct
from ${agency_variance}
where change_pct > 0
order by change_pct desc
limit 10
```

<BarChart data={top_increases} x=agency_name y=change_pct swapXY=true sort=true yFmt='0.0"%"' labels=true title="Top 10 Budget Increases (%)" colorPalette={['#2EAD6B']}/>

## Top Decreases

```sql top_decreases
select agency_name, change_amt, change_pct
from ${agency_variance}
where change_pct < 0
order by change_pct asc
limit 10
```

<BarChart data={top_decreases} x=agency_name y=change_pct swapXY=true sort=false yFmt='0.0"%"' labels=true title="Top 10 Budget Decreases (%)" colorPalette={['#C8122C']}/>

---

## Program-Level Variance

```sql program_variance
with a as (
        select agency_name, unit_name, program_name, sum(total_budget_amount) as spend_a
        from mbtsa.program_level
    where fiscal_year = (select latest_year from ${year_bounds})
      and coalesce(agency_name,'') like '${inputs.f_agency.value ?? "%"}'
    group by agency_name, unit_name, program_name
),
b as (
        select agency_name, unit_name, program_name, sum(total_budget_amount) as spend_b
        from mbtsa.program_level
    where fiscal_year = (select prior_year from ${year_bounds})
      and coalesce(agency_name,'') like '${inputs.f_agency.value ?? "%"}'
    group by agency_name, unit_name, program_name
)
select
    coalesce(a.agency_name, b.agency_name)   as agency_name,
    coalesce(a.unit_name, b.unit_name)       as unit_name,
    coalesce(a.program_name, b.program_name) as program_name,
    coalesce(a.spend_a, 0)                   as latest_year,
    coalesce(b.spend_b, 0)                   as prior_year,
    coalesce(a.spend_a, 0) - coalesce(b.spend_b, 0) as change_amt,
    round((coalesce(a.spend_a,0) - coalesce(b.spend_b,0)) * 100.0
          / nullif(b.spend_b, 0), 1)         as change_pct
from a full outer join b using (agency_name, unit_name, program_name)
order by abs(change_amt) desc
```

<DataTable data={program_variance} totalRow=true search=true rows=25>
    <Column id=agency_name title="Agency"/>
    <Column id=unit_name title="Unit"/>
    <Column id=program_name title="Program"/>
    <Column id=latest_year title="Latest Year" fmt=usd2compactviz/>
    <Column id=prior_year title="Prior Year" fmt=usd2compactviz/>
    <Column id=change_amt title="Change ($)" fmt=usd2compactviz/>
    <Column id=change_pct title="Change (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>
