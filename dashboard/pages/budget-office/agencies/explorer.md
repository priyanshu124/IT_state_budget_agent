---
title: Agency Explorer
prerender: false
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 24px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <p style="color: rgba(255,255,255,0.7); font-size: 0.8rem; margin: 0;"><a href="/budget-office" style="color: #FFC838; text-decoration: none;">Budget Office</a> -> IT Agencies</p>
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.6rem; font-weight: 700; margin: 6px 0 0 0;">IT Agencies</h1>
</div>

```sql g_tower
select distinct it_tower
from mbtsa.subprogram_level
where is_it=true and it_tower is not null
order by it_tower
```

```sql g_program
select distinct program_name
from mbtsa.subprogram_level
where is_it=true and program_name is not null
order by program_name
```

```sql g_subprogram
select distinct subprogram_name
from mbtsa.subprogram_level
where is_it=true and subprogram_name is not null
order by subprogram_name
```

<Details title="🔍 Filters — click to expand" open=true>

<Grid cols=3>
    <Dropdown name=f_tower data={g_tower} value=it_tower title="Tower" defaultValue="%"><DropdownOption value="%" valueLabel="All Towers"/></Dropdown>
    <Dropdown name=f_program data={g_program} value=program_name title="Program" defaultValue="%"><DropdownOption value="%" valueLabel="All Programs"/></Dropdown>
    <Dropdown name=f_subprogram data={g_subprogram} value=subprogram_name title="Subprogram" defaultValue="%"><DropdownOption value="%" valueLabel="All Subprograms"/></Dropdown>
</Grid>

</Details>

```sql filtered
select
    t.agency_code,
    t.agency_name,
    t.program_name,
    t.subprogram_name,
    t.it_tower,
    t.it_sub_tower,
    t.it_designation,
    t.total_budget_amount as amount
from mbtsa.subprogram_level t
where t.is_it = true
    and (coalesce(t.it_tower, '') like '${selectedTower}' or t.it_tower is null)
    and (coalesce(t.program_name, '') like '${selectedProgram}' or t.program_name is null)
    and (coalesce(t.subprogram_name, '') like '${selectedSubprogram}' or t.subprogram_name is null)
```

```sql agency_summary
select
    agency_name,
    '/budget-office/agencies/' || replace(agency_name, ' ', '%20') as agency_link,
    sum(amount) as it_spend,
    count(distinct it_tower) as tower_count,
    count(distinct program_name) as program_count,
    count(distinct subprogram_name) as subprogram_count,
    count(distinct case when it_designation='SHADOW_IT' then subprogram_name end) as shadow_it_count
from ${filtered}
where agency_name is not null
group by agency_name
order by it_spend desc
```

<script>
    import { getInputContext } from '@evidence-dev/sdk/utils/svelte';

    const inputStore = getInputContext();
    const urlParams = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '');

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

    $: selectedTower = urlParams.get('tower') 
        ? decodeURIComponent(urlParams.get('tower')).toLowerCase().replace(/'/g, "''")
        : readInputValue($inputStore?.f_tower, '%').replace(/'/g, "''");
    
    $: selectedProgram = readInputValue($inputStore?.f_program, '%').replace(/'/g, "''");
    
    $: selectedSubprogram = readInputValue($inputStore?.f_subprogram, '%').replace(/'/g, "''");

    $: filterContext = (() => {
        const parts = [];
        if (selectedTower !== '%') parts.push(`Tower: ${selectedTower}`);
        if (selectedProgram !== '%') parts.push(`Program: ${selectedProgram}`);
        if (selectedSubprogram !== '%') parts.push(`Subprogram: ${selectedSubprogram}`);
        return parts.length > 0 ? parts.join(' | ') : 'All IT Agencies';
    })();
</script>

{#if selectedTower !== '%' || selectedProgram !== '%' || selectedSubprogram !== '%'}
    <Alert status=info>
        <b>Filtered by:</b> {filterContext}
    </Alert>
{/if}

---

## IT Agencies

{#if agency_summary?.length > 0}
    <DataTable data={agency_summary} link=agency_link totalRow=true search=true>
        <Column id=agency_name title="Agency"/>
        <Column id=it_spend title="IT Spend" fmt=usd2compactviz/>
        <Column id=tower_count title="Towers"/>
        <Column id=program_count title="Programs"/>
        <Column id=subprogram_count title="Subprograms"/>
        <Column id=shadow_it_count title="Shadow IT"/>
    </DataTable>
{:else}
    <Alert status=warning>No IT agencies found for this filter selection.</Alert>
{/if}
