---
title: "{params.tower}"
prerender: false
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 24px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 28px;">
    <p style="color: rgba(255,255,255,0.6); font-size: 0.8rem; margin: 0;"><a href="/technology" style="color: #FFC838; text-decoration: none;">💻 Technology</a> → Tower</p>
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.5rem; font-weight: 700; margin: 6px 0 0 0;">{params.tower}</h1>
</div>

```sql s
select
    case
        when abs(sum(it_amount)) >= 1000000000 then '$' || printf('%.2f', sum(it_amount) / 1000000000.0) || 'B'
        when abs(sum(it_amount)) >= 1000000 then '$' || printf('%.2f', sum(it_amount) / 1000000.0) || 'M'
        when abs(sum(it_amount)) >= 1000 then '$' || printf('%.2f', sum(it_amount) / 1000.0) || 'K'
        else '$' || printf('%.2f', sum(it_amount))
    end as it_budget_display,
    count(distinct agency_name) as agencies,
    count(distinct subprogram_name) as programs, count(distinct it_sub_tower) as sub_towers
from mbtsa.budget where is_it=true and it_tower='${(params.tower ?? '').replace(/'/g, "''")}'
```

<Grid cols=4>
    <BigValue data={s} value=it_budget_display title="IT Budget"/>
    <BigValue data={s} value=agencies title="Agencies"/>
    <BigValue data={s} value=programs title="Programs"/>
    <BigValue data={s} value=sub_towers title="Sub-Towers"/>
</Grid>

```sql subs
select it_sub_tower, sum(it_amount) as budget from mbtsa.budget
where is_it=true and it_tower='${(params.tower ?? '').replace(/'/g, "''")}' group by it_sub_tower order by budget desc
```

```sql trend
select fiscal_year, sum(it_amount) as budget from mbtsa.budget
where is_it=true and it_tower='${(params.tower ?? '').replace(/'/g, "''")}' group by fiscal_year order by fiscal_year
```

<Grid cols=2>
    <BarChart data={subs} x=it_sub_tower y=budget yFmt=usd2compactviz labels=true swapXY=true sort=false title="By sub-tower" colorPalette={['#C8122C','#FFC838','#3B7DD8']}/>
    <BarChart data={trend} x=fiscal_year y=budget yFmt=usd2compactviz labels=true title="By fiscal year" colorPalette={['#C8122C']}/>
</Grid>

```sql progs
select subprogram_name, agency_name, it_sub_tower, it_designation, sum(it_amount) as budget
from mbtsa.budget where is_it=true and it_tower='${(params.tower ?? '').replace(/'/g, "''")}'
group by subprogram_name, agency_name, it_sub_tower, it_designation order by budget desc
```

<DataTable data={progs} totalRow=true search=true rows=20 filter=true>
    <Column id=subprogram_name title="Subprogram"/>
    <Column id=agency_name title="Agency"/>
    <Column id=it_sub_tower title="Sub-Tower"/>
    <Column id=it_designation title="Designation"/>
    <Column id=budget title="IT Budget" fmt=usd2compactviz/>
</DataTable>

<p style="font-size: 0.75rem; color: #888; font-style: italic; text-align: center;">Data: Maryland Operating Budget, FY2020–FY2027 · TBM v5.0.1</p>
