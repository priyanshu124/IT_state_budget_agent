---
title: Technology
sidebar_position: 4
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">💻 Technology View</h1>
    <p style="color: #FFC838; font-size: 0.95rem; margin: 4px 0 0 0;">IT Spending Analysis · TBM v5.0.1 Classification</p>
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
```sql g_tower
select distinct it_tower from mbtsa.budget where is_it=true and it_tower is not null order by it_tower
```
```sql g_desig
select distinct it_designation from mbtsa.budget where is_it=true and it_designation is not null order by it_designation
```

<Details title="🔍 Filters — click to expand" open=true>

<Grid cols=4>
    <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue="%"><DropdownOption value="%" valueLabel="All Years"/></Dropdown>
    <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%"><DropdownOption value="%" valueLabel="All Agencies"/></Dropdown>
    <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%"><DropdownOption value="%" valueLabel="All Fund Types"/></Dropdown>
    <Dropdown name=f_cat data={g_cat} value=category_name title="Category" defaultValue="%"><DropdownOption value="%" valueLabel="All Categories"/></Dropdown>
</Grid>
<Grid cols=2>
    <Dropdown name=f_tower data={g_tower} value=it_tower title="Tower" defaultValue="%"><DropdownOption value="%" valueLabel="All Towers"/></Dropdown>
    <Dropdown name=f_desig data={g_desig} value=it_designation title="Designation" defaultValue="%"><DropdownOption value="%" valueLabel="All Designations"/></Dropdown>
</Grid>

</Details>

```sql filtered
select
        fiscal_year,
        agency_code,
        agency_name,
        subprogram_name,
        fund_type,
        category_name,
        it_tower,
        it_designation,
        cost_pool,
        amount,
        it_amount
from mbtsa.budget
where is_it = true
  and cast(fiscal_year as varchar) like '${inputs.f_fy.value}'
  and fund_type like '${inputs.f_fund.value}'
  and category_name like '${inputs.f_cat.value}'
  and agency_name like '${inputs.f_agency.value}'
  and (it_tower like '${inputs.f_tower.value}' or it_tower is null)
  and (it_designation like '${inputs.f_desig.value}' or it_designation is null)
```

```sql k
select sum(it_amount) as it_spend, count(distinct agency_code) as it_agencies,
    count(distinct subprogram_name) as it_programs, count(distinct it_tower) as towers,
    count(distinct case when it_designation='SHADOW_IT' then subprogram_name end) as shadow
from ${filtered}
```

```sql it_pct
select round(sum(it_amount)*100.0/nullif(sum(amount),0),1) as it_pct from mbtsa.budget
```

<Grid cols=6>
    <BigValue data={k} value=it_spend fmt=usd2compactviz title="IT Spend"/>
    <BigValue data={it_pct} value=it_pct fmt='0.0"%"' title="IT % of Budget"/>
    <BigValue data={k} value=it_agencies title="IT Agencies"/>
    <BigValue data={k} value=it_programs title="IT Programs"/>
    <BigValue data={k} value=towers title="TBM Towers"/>
    <BigValue data={k} value=shadow title="Shadow IT"/>
</Grid>

---

## IT spend by tower & cost pool

```sql towers
select it_tower, sum(it_amount) as spend from ${filtered} where it_tower is not null group by it_tower order by spend desc
```

```sql pools
select cost_pool, sum(it_amount) as spend from ${filtered} where cost_pool is not null group by cost_pool order by spend desc
```

<Grid cols=2>
    <BarChart data={towers} x=it_tower y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by tower" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C','#E74C3C','#95A5A6','#34495E']}/>
    <BarChart data={pools} x=cost_pool y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by cost pool" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C']}/>
</Grid>

---

## Tower trends

```sql tower_trend
select fiscal_year, it_tower, sum(it_amount) as spend from ${filtered} where it_tower is not null group by fiscal_year, it_tower order by fiscal_year
```

<AreaChart data={tower_trend} x=fiscal_year y=spend series=it_tower yFmt=usd2compactviz title="Tower spend over time" colorPalette={['#C8122C','#FFC838','#3B7DD8','#2EAD6B','#E67E22','#8E44AD','#1ABC9C','#E74C3C','#95A5A6','#34495E']}/>

---

## Designation breakdown

```sql desig
select it_designation, sum(it_amount) as spend, count(distinct subprogram_name) as programs from ${filtered} group by it_designation order by spend desc
```

<Grid cols=2>
    <BarChart data={desig} x=it_designation y=spend yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Spend by designation" colorPalette={['#C8122C','#FFC838','#3B7DD8','#E67E22']}/>
    <DataTable data={desig} totalRow=true search=true>
        <Column id=it_designation title="Designation"/>
        <Column id=spend title="IT Spend" fmt=usd2compactviz/>
        <Column id=programs title="Programs"/>
    </DataTable>
</Grid>

---

## Top IT agencies

```sql agency_it
select agency_name, sum(it_amount) as spend from ${filtered} group by agency_name order by spend desc limit 15
```

<BarChart data={agency_it} x=agency_name y=spend swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Top 15 IT agencies" colorPalette={['#C8122C']}/>

---

## Tower explorer — click to drill down

<Alert status=info>Click a tower to see sub-towers, agencies, and programs.</Alert>

```sql tower_drill
select it_tower, '/technology/towers/' || it_tower as tower_link,
    sum(it_amount) as spend, count(distinct agency_name) as agencies, count(distinct subprogram_name) as programs
from ${filtered} where it_tower is not null group by it_tower order by spend desc
```

<DataTable data={tower_drill} link=tower_link totalRow=true search=true>
    <Column id=it_tower title="Tower"/>
    <Column id=spend title="IT Spend" fmt=usd2compactviz/>
    <Column id=agencies title="Agencies"/>
    <Column id=programs title="Programs"/>
</DataTable>
