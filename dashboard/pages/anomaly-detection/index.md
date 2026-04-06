---
title: Anomaly Detection
sidebar_position: 6
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">🔍 Anomaly Detection</h1>
    <p style="color: #FFC838; font-size: 0.95rem; margin: 4px 0 0 0;">Unusual Budget Patterns · Full Hierarchy Drill-Down</p>
</div>

> **Automated anomaly flagging** surfaces budget that deviates significantly from historical patterns. Filter by any dimension, select sensitivity, then drill to the source.

```sql g_fy
select
    cast(cast(fiscal_year as bigint) as varchar) as fy
from mbtsa.anomalies
group by 1
order by cast(fy as int)
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

<script>
    import { getInputContext } from '@evidence-dev/sdk/utils/svelte';

    const inputStore = getInputContext();

    const clearFilter = (key, defaultValue, defaultLabel) => {
        inputStore.update((allInputs) => {
            allInputs[key] = {
                label: defaultLabel,
                value: defaultValue,
                rawValues: [{ label: defaultLabel, value: defaultValue }]
            };
            return allInputs;
        });
    };

    $: activeFilters = [
        { key: 'f_cat', title: 'Category', value: $inputStore?.f_cat?.label, defaultValue: '%', defaultLabel: 'All Categories' },
        { key: 'f_fund', title: 'Fund Type', value: $inputStore?.f_fund?.label, defaultValue: '%', defaultLabel: 'All Fund Types' },
        { key: 'f_agency', title: 'Agency', value: $inputStore?.f_agency?.label, defaultValue: '%', defaultLabel: 'All Agencies' },
        { key: 'f_unit', title: 'Unit', value: $inputStore?.f_unit?.label, defaultValue: '%', defaultLabel: 'All Units' },
        { key: 'f_program', title: 'Program', value: $inputStore?.f_program?.label, defaultValue: '%', defaultLabel: 'All Programs' },
        { key: 'f_subprogram', title: 'Subprogram', value: $inputStore?.f_subprogram?.label, defaultValue: '%', defaultLabel: 'All Subprograms' }
    ].filter((filterItem) => {
        if (!filterItem.value) return false;
        return filterItem.value !== filterItem.defaultLabel && filterItem.value !== filterItem.defaultValue;
    });
</script>
<Grid cols=4>
    <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue="%"><DropdownOption value="%" valueLabel="All Years"/></Dropdown>
    <Dropdown name=anomaly_level title="Hierarchy Level" defaultValue="agency_name">
        <DropdownOption value="agency_name" valueLabel="Agency"/>
        <DropdownOption value="unit_name" valueLabel="Unit"/>
        <DropdownOption value="program_name" valueLabel="Program"/>
        <DropdownOption value="subprogram_name" valueLabel="Subprogram"/>
        <DropdownOption value="object_name" valueLabel="Object Code"/>
        <DropdownOption value="subobject_name" valueLabel="Subobject Code"/>
    </Dropdown>
    <Dropdown name=threshold title="Deviation Threshold" defaultValue="30">
        <DropdownOption value="20" valueLabel="> 20%"/>
        <DropdownOption value="30" valueLabel="> 30%"/>
        <DropdownOption value="50" valueLabel="> 50%"/>
        <DropdownOption value="75" valueLabel="> 75%"/>
        <DropdownOption value="100" valueLabel="> 100%"/>
    </Dropdown>
    
    
</Grid>



<Details title="🔍 Filters — click to expand" open=true>

<Grid cols=3>
    <Dropdown name=f_cat data={g_cat} value=category_name title="Category" defaultValue="%"><DropdownOption value="%" valueLabel="All Categories"/></Dropdown>
    <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%"><DropdownOption value="%" valueLabel="All Fund Types"/></Dropdown>
    <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%"><DropdownOption value="%" valueLabel="All Agencies"/></Dropdown>
    <Dropdown name=f_unit data={g_unit} value=unit_name title="Unit" defaultValue="%"><DropdownOption value="%" valueLabel="All Units"/></Dropdown>
    <Dropdown name=f_program data={g_program} value=program_name title="Program" defaultValue="%"><DropdownOption value="%" valueLabel="All Programs"/></Dropdown>
    <Dropdown name=f_subprogram data={g_subprogram} value=subprogram_name title="Subprogram" defaultValue="%"><DropdownOption value="%" valueLabel="All Subprograms"/></Dropdown>
</Grid>

</Details>

```sql base_anomalies
select *
from mbtsa.anomalies
where anomaly_level = '${inputs.anomaly_level.value}'
    and (
        '${inputs.f_fy.value}' = '%'
        or cast(cast(fiscal_year as bigint) as varchar) = '${inputs.f_fy.value}'
    )
    and (
        '${inputs.f_agency.value}' = '%'
        or agency_names ilike '%' || '${inputs.f_agency.value}' || '%'
    )
    and (
        '${inputs.f_fund.value}' = '%'
        or fund_types ilike '%' || '${inputs.f_fund.value}' || '%'
    )
    and (
        '${inputs.f_cat.value}' = '%'
        or category_names ilike '%' || '${inputs.f_cat.value}' || '%'
    )
    and year_count > 1
```

```sql anomaly_kpis
with base as (
    select *
    from ${base_anomalies}
),
flagged as (
    select *
    from base
    where abs_deviation_pct > ${inputs.threshold.value}
),
base_totals as (
    select sum(spend) as total_budget
    from base
)
select
    count(*) as flagged_anomaly_count,
    round(
        100.0 * sum(f.spend)
        / nullif(max(bt.total_budget), 0),
        1
    ) as flagged_budget_share_pct,
    round(
        100.0 * sum(case when f.abs_deviation_pct >= 75 then 1 else 0 end)
        / nullif(count(*), 0),
        1
    ) as severe_anomaly_rate_pct
from flagged f
cross join base_totals bt
```

<div style="display: flex; flex-wrap: wrap; gap: 10px; margin: 8px 0 10px 0;">
    <span title="Count of rows in the current filtered scope where absolute deviation exceeds the selected Deviation Threshold." style="font-size: 0.8rem; color: #4A5568; background: #F8F4EF; border: 1px solid #E8E0D8; border-radius: 999px; padding: 5px 10px; cursor: help;">Flagged Anomalies ⓘ</span>
    <span title="Percent of total budget in the current filtered scope that is tied to flagged rows above the selected threshold." style="font-size: 0.8rem; color: #4A5568; background: #F8F4EF; border: 1px solid #E8E0D8; border-radius: 999px; padding: 5px 10px; cursor: help;">Flagged Budget Share ⓘ</span>
    <span title="Percent of flagged rows with absolute deviation at or above 75%, indicating more extreme anomalies." style="font-size: 0.8rem; color: #4A5568; background: #F8F4EF; border: 1px solid #E8E0D8; border-radius: 999px; padding: 5px 10px; cursor: help;">Severe Anomaly Rate ⓘ</span>
</div>

<Grid cols=3>
    <BigValue data={anomaly_kpis} value=flagged_anomaly_count title="Flagged Anomalies"/>
    <BigValue data={anomaly_kpis} value=flagged_budget_share_pct fmt='0.0"%"' title="Flagged Budget Share"/>
    <BigValue data={anomaly_kpis} value=severe_anomaly_rate_pct fmt='0.0"%"' title="Severe Anomaly Rate"/>
</Grid>

---

## Anomalies by fiscal year

```sql anomaly_by_year
select
    cast(cast(fiscal_year as bigint) as int) as fiscal_year_num,
    cast(cast(fiscal_year as bigint) as varchar) as fiscal_year,
    count(*) as anomaly_count,
    sum(spend) as total_budget
from ${base_anomalies}
where abs_deviation_pct > ${inputs.threshold.value}
group by 1, 2
order by fiscal_year_num
```

> Spikes in anomaly counts often align with program restructuring, or new Governor's Allowance proposals.

<Grid cols=2>
    <BarChart data={anomaly_by_year} x=fiscal_year y=anomaly_count sort=false labels=true title="Anomaly count by fiscal year" colorPalette={['#C8122C']}/>
    <BarChart data={anomaly_by_year} x=fiscal_year y=total_budget sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Flagged budget by year" colorPalette={['#FFC838']}/>
</Grid>

---

## Top positive anomalies (budget spikes)

```sql positive_anomalies
select
    entity,
    cast(cast(fiscal_year as bigint) as varchar) as fiscal_year,
    spend as budget,
    avg_spend as avg_budget,
    deviation_pct
from ${base_anomalies}
where deviation_pct > ${inputs.threshold.value}
order by deviation_pct desc
limit 15
```

<BarChart data={positive_anomalies} x=entity y=deviation_pct swapXY=true sort=false yFmt='0.0"%"' labels=true title="Biggest budget spikes" colorPalette={['#C8122C']}/>

<DataTable data={positive_anomalies} search=true rows=15>
    <Column id=entity title="Entity"/>
    <Column id=fiscal_year title="Year"/>
    <Column id=budget title="Actual Budget" fmt=usd2compactvizsigned/>
    <Column id=avg_budget title="Historical Avg" fmt=usd2compactvizsigned/>
    <Column id=deviation_pct title="Deviation (%)" fmt='0.0"%"' contentType=colorscale/>
</DataTable>

---

## Top negative anomalies (budget drops)

```sql negative_anomalies
select
    entity,
    cast(cast(fiscal_year as bigint) as varchar) as fiscal_year,
    spend as budget,
    avg_spend as avg_budget,
    deviation_pct
from ${base_anomalies}
where deviation_pct < -${inputs.threshold.value}
order by deviation_pct asc
limit 15
```

<BarChart data={negative_anomalies} x=entity y=deviation_pct swapXY=true sort=false yFmt='0.0"%"' labels=true title="Biggest budget drops" colorPalette={['#3B7DD8']}/>

<DataTable data={negative_anomalies} search=true rows=15>
    <Column id=entity title="Entity"/>
    <Column id=fiscal_year title="Year"/>
    <Column id=budget title="Actual Budget" fmt=usd2compactvizsigned/>
    <Column id=avg_budget title="Historical Avg" fmt=usd2compactvizsigned/>
    <Column id=deviation_pct title="Deviation (%)" fmt='0.0"%"' contentType=colorscale/>
</DataTable>

---

## Deep drill-down: trace anomaly to source

> Full hierarchy showing every flagged line item down to subobject level.

```sql deep_anomalies
select
    agency_name,
    unit_name,
    program_name,
    subprogram_name,
    object_name,
    subobject_name,
    fund_type,
    fiscal_year,
    spend as budget,
    avg_spend as avg_budget,
    deviation_pct
from mbtsa.anomalies_deep
where (
        '${inputs.f_fy.value}' = '%'
        or cast(cast(fiscal_year as bigint) as varchar) = '${inputs.f_fy.value}'
    )
  and agency_name like '${inputs.f_agency.value}'
  and fund_type like '${inputs.f_fund.value}'
  and (
    '${inputs.f_cat.value}' = '%'
        or category_names ilike '%' || '${inputs.f_cat.value}' || '%'
  )
  and abs_deviation_pct > ${inputs.threshold.value}
  and year_count > 1
order by abs_deviation_pct desc
limit 50
```

<DataTable data={deep_anomalies} search=true rows=25>
    <Column id=agency_name title="Agency"/>
    <Column id=unit_name title="Unit"/>
    <Column id=program_name title="Program"/>
    <Column id=subprogram_name title="Subprogram"/>
    <Column id=object_name title="Object"/>
    <Column id=fund_type title="Fund"/>
    <Column id=fiscal_year title="Year"/>
    <Column id=budget title="Actual Budget" fmt=usd2compactvizsigned/>
    <Column id=avg_budget title="Historical Avg" fmt=usd2compactvizsigned/>
    <Column id=deviation_pct title="Deviation (%)" fmt='0.0"%"' contentType=colorscale/>
</DataTable>

