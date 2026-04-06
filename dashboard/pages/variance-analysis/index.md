---
title: Variance Analysis
sidebar_position: 5
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.7rem; font-weight: 700; margin: 0;">📊 Variance Analysis</h1>
    <p style="color: #FFC838; font-size: 0.95rem; margin: 4px 0 0 0;">Year-over-Year Budget Change · Full Hierarchy Drill-Down</p>
</div>

> **Automated variance analysis** replaces hours of manual spreadsheet work. Select two fiscal years, filter by any dimension, then drill down to object codes to trace every budget change.

```sql g_fy
select distinct fiscal_year as fy from mbtsa.budget order by fiscal_year desc
```
```sql latest_fy
select max(fiscal_year) as fy from mbtsa.budget
```
```sql prior_fy
select max(fiscal_year) - 1 as fy from mbtsa.budget
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
    <Dropdown name=compare_year title="Compare Year" data={g_fy} value=fy defaultValue={latest_fy[0].fy}/>
    <Dropdown name=base_year title="Base Year" data={g_fy} value=fy defaultValue={prior_fy[0].fy}/>
    <Dropdown name=drill_level title="Hierarchy Level" defaultValue="agency_name">
        <DropdownOption value="agency_name" valueLabel="Agency"/>
        <DropdownOption value="unit_name" valueLabel="Unit"/>
        <DropdownOption value="program_name" valueLabel="Program"/>
        <DropdownOption value="subprogram_name" valueLabel="Subprogram"/>
        <DropdownOption value="object_name" valueLabel="Object Code"/>
        <DropdownOption value="subobject_name" valueLabel="Subobject Code"/>
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

{#if activeFilters.length > 0}
<div style="margin: 12px 0 18px 0; padding: 10px 12px; background: #F8F4EF; border: 1px solid #E8E0D8; border-radius: 8px;">
    <div style="font-weight: 600; color: #231F20; margin-bottom: 8px;">Active Filters</div>
    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
        {#each activeFilters as filterItem}
            <button
                style="background: #FFFFFF; border: 1px solid #D8CEC4; color: #231F20; border-radius: 999px; padding: 4px 10px; font-size: 0.8rem; cursor: pointer;"
                on:click={() => clearFilter(filterItem.key, filterItem.defaultValue, filterItem.defaultLabel)}
            >
                {filterItem.title}: {filterItem.value} ×
            </button>
        {/each}
    </div>
</div>
{/if}

```sql filtered
select
        fiscal_year,
        fund_type,
        category_name,
        agency_name,
        unit_name,
        program_name,
        subprogram_name,
        object_name,
        subobject_name,
        amount
from mbtsa.budget
where fiscal_year in ('${inputs.compare_year.value}', '${inputs.base_year.value}')
  and fund_type like '${inputs.f_fund.value}'
  and category_name like '${inputs.f_cat.value}'
  and agency_name like '${inputs.f_agency.value}'
    and unit_name like '${inputs.f_unit.value}'
    and program_name like '${inputs.f_program.value}'
    and subprogram_name like '${inputs.f_subprogram.value}'
```

```sql variance_summary
with summary as (
    select
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end) as compare_total,
        sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as base_total,
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as total_change,
        round((sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end))
            * 100.0 / nullif(sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end), 0), 1) as total_change_pct,
        count(distinct ${inputs.drill_level.value}) as entities
    from ${filtered}
)
select
    compare_total,
    base_total,
    total_change,
    case
        when abs(total_change) >= 1000000000 then (case when total_change < 0 then '-' else '' end) || '$' || printf('%.2f', abs(total_change) / 1000000000.0) || 'B'
        when abs(total_change) >= 1000000 then (case when total_change < 0 then '-' else '' end) || '$' || printf('%.2f', abs(total_change) / 1000000.0) || 'M'
        when abs(total_change) >= 1000 then (case when total_change < 0 then '-' else '' end) || '$' || printf('%.2f', abs(total_change) / 1000.0) || 'K'
        else (case when total_change < 0 then '-' else '' end) || '$' || printf('%.2f', abs(total_change))
    end as total_change_display,
    total_change_pct,
    entities
from summary
```

<Grid cols=5>
    <BigValue data={variance_summary} value=compare_total fmt=usd2compactviz title="FY{inputs.compare_year.value}"/>
    <BigValue data={variance_summary} value=base_total fmt=usd2compactviz title="FY{inputs.base_year.value}"/>
    <BigValue data={variance_summary} value=total_change_display title="Change ($)"/>
    <BigValue data={variance_summary} value=total_change_pct fmt='0.0"%"' title="Change (%)"/>
    <BigValue data={variance_summary} value=entities title="Entities"/>
</Grid>

---

## Biggest increases

```sql top_increases
select ${inputs.drill_level.value} as entity,
    sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end) as compare_amt,
    sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as base_amt,
    sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
        - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as change_amt,
    round((sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
        - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end))
        * 100.0 / nullif(sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end), 0), 1) as change_pct
from ${filtered} group by ${inputs.drill_level.value}
having sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) > 0
   and (sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
    - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end)) > 0
order by change_amt desc limit 10
```

<BarChart data={top_increases} x=entity y=change_amt swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Top 10 increases" colorPalette={['#2EAD6B']}/>

## Biggest decreases

```sql top_decreases
select ${inputs.drill_level.value} as entity,
    sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
        - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as change_amt
from ${filtered} group by ${inputs.drill_level.value}
having sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) > 0
   and (sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
    - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end)) < 0
order by change_amt asc limit 10
```

<BarChart data={top_decreases} x=entity y=change_amt swapXY=true sort=false yFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz title="Top 10 decreases" colorPalette={['#C8122C']}/>

---

## Full variance table

```sql full_variance
with raw as (
    select ${inputs.drill_level.value} as entity,
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end) as compare_amt,
        sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as base_amt,
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as change_amt,
        round((sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end))
            * 100.0 / nullif(sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end), 0), 1) as change_pct
    from ${filtered} group by ${inputs.drill_level.value}
    having sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) > 0
)
select
    entity,
    compare_amt,
    base_amt,
    change_amt,
    case
        when abs(change_amt) >= 1000000000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000000000.0) || 'B'
        when abs(change_amt) >= 1000000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000000.0) || 'M'
        when abs(change_amt) >= 1000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000.0) || 'K'
        else (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt))
    end as change_amt_display,
    change_pct
from raw
order by abs(change_amt) desc
```

<DataTable data={full_variance} totalRow=true search=true rows=20>
    <Column id=entity title="Entity"/>
    <Column id=compare_amt title="FY{inputs.compare_year.value}" fmt=usd2compactviz/>
    <Column id=base_amt title="FY{inputs.base_year.value}" fmt=usd2compactviz/>
    <Column id=change_amt_display title="Change ($)" totalAgg="-"/>
    <Column id=change_pct title="Change (%)" fmt='0.0"%"' contentType=colorscale totalAgg="-"/>
</DataTable>

---

## Budget hierarchy drill-down

> Click an agency to open the full Agency → Unit → Program → Subprogram drill path.

```sql variance_agency_drill
with raw as (
    select
        agency_name,
        '/budget-office/agencies/' || agency_name as agency_link,
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end) as compare_amt,
        sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as base_amt,
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as change_amt,
        round((sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end))
            * 100.0 / nullif(sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end), 0), 1) as change_pct
    from ${filtered}
    group by agency_name
    having abs(sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end)) > 0
)
select
    agency_name,
    agency_link,
    compare_amt,
    base_amt,
    change_amt,
    case
        when abs(change_amt) >= 1000000000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000000000.0) || 'B'
        when abs(change_amt) >= 1000000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000000.0) || 'M'
        when abs(change_amt) >= 1000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000.0) || 'K'
        else (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt))
    end as change_amt_display,
    change_pct
from raw
order by abs(change_amt) desc
```

<DataTable data={variance_agency_drill} link=agency_link search=true rows=20 totalRow=true>
    <Column id=agency_name title="Agency"/>
    <Column id=compare_amt title="FY{inputs.compare_year.value}" fmt=usd2compactviz/>
    <Column id=base_amt title="FY{inputs.base_year.value}" fmt=usd2compactviz/>
    <Column id=change_amt_display title="Change ($)" totalAgg="-"/>
    <Column id=change_pct title="Change (%)" fmt='0.0"%"' contentType=colorscale totalAgg="-"/>
</DataTable>

---

## Drill-down: trace the source

> Full hierarchy showing exactly which line items caused each variance.

```sql deep_variance
with raw as (
    select agency_name, unit_name, program_name, subprogram_name, object_name, fund_type,
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end) as compare_amt,
        sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as base_amt,
        sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end) as change_amt,
        round((sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end))
            * 100.0 / nullif(sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end), 0), 1) as change_pct
    from ${filtered}
    group by agency_name, unit_name, program_name, subprogram_name, object_name, fund_type
    having abs(sum(case when fiscal_year = '${inputs.compare_year.value}' then amount else 0 end)
            - sum(case when fiscal_year = '${inputs.base_year.value}' then amount else 0 end)) > 0
)
select
    agency_name,
    unit_name,
    program_name,
    subprogram_name,
    object_name,
    fund_type,
    compare_amt,
    base_amt,
    change_amt,
    case
        when abs(change_amt) >= 1000000000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000000000.0) || 'B'
        when abs(change_amt) >= 1000000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000000.0) || 'M'
        when abs(change_amt) >= 1000 then (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt) / 1000.0) || 'K'
        else (case when change_amt < 0 then '-' else '' end) || '$' || printf('%.2f', abs(change_amt))
    end as change_amt_display,
    change_pct
from raw
order by abs(change_amt) desc
```

<DataTable data={deep_variance} search=true rows=25 totalRow=true>
    <Column id=agency_name title="Agency"/>
    <Column id=unit_name title="Unit"/>
    <Column id=program_name title="Program"/>
    <Column id=subprogram_name title="Subprogram"/>
    <Column id=object_name title="Object"/>
    <Column id=fund_type title="Fund"/>
    <Column id=compare_amt title="FY{inputs.compare_year.value}" fmt=usd2compactviz/>
    <Column id=base_amt title="FY{inputs.base_year.value}" fmt=usd2compactviz/>
    <Column id=change_amt_display title="Change ($)" totalAgg="-"/>
    <Column id=change_pct title="Change (%)" fmt='0.0"%"' contentType=colorscale totalAgg="-"/>
</DataTable>

