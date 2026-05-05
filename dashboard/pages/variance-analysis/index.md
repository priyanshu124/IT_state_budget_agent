---
title: 
sidebar_position: 4
---

<div style="background: linear-gradient(135deg, #ede5f8 0%, #d4bef0 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #802cd7; margin-bottom: 0; margin-top: -8px;">
    <h1 style="color: #211030; font-size: 1.7rem; font-weight: 700; margin: 0;">📊 Variance Analysis</h1>
    <p style="color: #6321a5; font-size: 0.95rem; margin: 4px 0 0 0;">Year-over-year change detection — compare any two years at any hierarchy level</p>
</div>

```sql g_agency
select distinct agency_name from mbtsa.subprogram_level where agency_name is not null order by agency_name
```
```sql g_fy_all
select distinct fiscal_year as fy from mbtsa.subprogram_level where total_budget_amount > 0 order by fiscal_year desc
```
```sql g_unit
select distinct unit_name as u
from mbtsa.subprogram_level
where unit_name is not null
  and lower(coalesce(agency_name,'')) like '${selectedAgency}'
order by unit_name
```
```sql g_program
select distinct program_name as p
from mbtsa.subprogram_level
where program_name is not null
  and lower(coalesce(agency_name,'')) like '${selectedAgency}'
  and coalesce(unit_name,'') ilike '${selectedUnit}'
order by program_name
```
```sql g_fund
select distinct fund_type from mbtsa.subprogram_level where fund_type is not null order by fund_type
```

<script>
    import { getInputContext } from '@evidence-dev/sdk/utils/svelte';
    const inputStore = getInputContext();

    let ctrlBarEl;
    let ctrlBarFixed = '';
    let ctrlBarSpacerH = '0px';

    let chipBarEl;
    let chipBarFixed = '';
    let chipBarSpacerH = '0px';

    onMount(() => {
        const header  = document.querySelector('header');
        const sidebar = document.querySelector('aside') ?? document.querySelector('nav');
        const headerH = header  ? header.offsetHeight  : 64;
        const sidebarW = sidebar ? sidebar.offsetWidth : 0;
        ctrlBarFixed = `position:fixed; top:${headerH}px; left:${sidebarW}px; right:0; z-index:100;`;
        // measure bar height after next tick so the element is rendered
        requestAnimationFrame(() => {
            if (ctrlBarEl) {
                ctrlBarSpacerH = ctrlBarEl.offsetHeight + 'px';
            }
        });
    });

    const readInputValue = (entry, fallback = '%') => {
        if (!entry) return fallback;
        try {
            const s = JSON.stringify(entry);
            if (s.includes('an input has not been set') || s.includes('select null')) return fallback;
        } catch(e) {}
        const candidates = [
            entry?.rawValues?.[0]?.value, entry?.rawValue?.value,            entry?.value?.value, entry?.value, entry?.rawValue,
            entry?.rawValues?.[0]?.label, entry?.label, entry?.rawValues?.[0]
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

    const selectedValue = (entry, lower = true) => {
        const val = readInputValue(entry, '%').replace(/'/g, "''");
        return lower ? val.toLowerCase() : val;
    };

    $: selectedAgency  = (() => {
        const val = selectedValue($inputStore?.f_agency);
        if (!val || val === 'undefined') return '%';
        return val;
    })();
    $: selectedUnit    = (() => { const v = selectedValue($inputStore?.f_unit);    return (!v || v === 'undefined') ? '%' : v; })();
    $: selectedProgram = (() => { const v = selectedValue($inputStore?.f_program); return (!v || v === 'undefined') ? '%' : v; })();
    $: selectedFund    = (() => { const v = selectedValue($inputStore?.f_fund);    return (!v || v === 'undefined') ? '%' : v; })();
    const isRealFilter = (v) => v && v !== '%' && v !== 'undefined' && !v.includes('select null') && !v.includes('an input has not been set');

    $: hasActiveFilters = isRealFilter(selectedAgency) || isRealFilter(selectedUnit) || isRealFilter(selectedProgram) || isRealFilter(selectedFund);
    $: selectedYearA   = selectedValue($inputStore?.f_year_a, false);
    $: selectedYearB   = selectedValue($inputStore?.f_year_b, false);
    $: selectedLevel   = readInputValue($inputStore?.f_level, 'agency');

    $: yearALabel = (selectedYearA && selectedYearA !== '%') ? selectedYearA : (year_bounds?.[0]?.latest_year ?? 'Latest Year');
    $: yearBLabel = (selectedYearB && selectedYearB !== '%') ? selectedYearB : (year_bounds?.[0]?.prior_year  ?? 'Prior Year');

    $: levelLabel = selectedLevel === 'unit' ? 'Unit'
        : selectedLevel === 'program' ? 'Program'
        : selectedLevel === 'subprogram' ? 'Subprogram'
        : 'Agency';

    $: activeLabelField = selectedLevel === 'unit' ? 'unit_name'
        : selectedLevel === 'program' ? 'program_name'
        : selectedLevel === 'subprogram' ? 'subprogram_name'
        : 'agency_name';

    $: activeVariance = selectedLevel === 'unit'       ? (unit_variance       ?? [])
        : selectedLevel === 'program'    ? (program_variance    ?? [])
        : selectedLevel === 'subprogram' ? (subprogram_variance ?? [])
        : (agency_variance ?? []);

    let threshold = 10; // now controlled by slider

    const fmtMoney = (v, sign = false) => {
        const n = Number(v) || 0;
        const abs = Math.abs(n);
        const s = n > 0 ? (sign ? '+' : '') : n < 0 ? '-' : '';
        if (abs >= 1e9) return s + '$' + (abs / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return s + '$' + (abs / 1e6).toFixed(1) + 'M';
        if (abs >= 1e3) return s + '$' + (abs / 1e3).toFixed(0) + 'K';
        return s + '$' + abs.toLocaleString();
    };

    $: kpi = (() => {
        const rows = activeVariance;
        if (!rows.length) return { net_change: 0, total_increased: 0, total_decreased: 0, items_up: 0, items_down: 0, total_count: 0, top_mover_name: '—', top_mover_amt: 0 };
        const top = rows.slice().sort((a,b) => Math.abs(Number(b.change_amt)) - Math.abs(Number(a.change_amt)))[0];
        return {
            total_increased: rows.filter(r => Number(r.change_amt) > 0).reduce((s,r) => s + Number(r.change_amt), 0),
            total_decreased: rows.filter(r => Number(r.change_amt) < 0).reduce((s,r) => s + Number(r.change_amt), 0),
            net_change:      rows.reduce((s,r) => s + Number(r.change_amt), 0),
            items_up:        rows.filter(r => Number(r.change_pct) > threshold).length,
            items_down:      rows.filter(r => Number(r.change_pct) < -threshold).length,
            total_count:     rows.length,
            top_mover_name:  top ? (top[activeLabelField] ?? '—') : '—',
            top_mover_amt:   top ? Number(top.change_amt) : 0
        };
    })();

    $: npCount = (activeVariance ?? []).filter(r => Number(r.prior_year) === 0 && Number(r.latest_year) > 0).length;
    $: epCount = (activeVariance ?? []).filter(r => Number(r.latest_year) === 0 && Number(r.prior_year) > 0).length;

    $: netColor  = Number(kpi.net_change) >= 0 ? '#1A7340' : '#C8122C';
    $: netBg     = Number(kpi.net_change) >= 0 ? 'rgba(46,173,107,0.06)' : 'rgba(200,18,44,0.06)';
    $: netBorder = Number(kpi.net_change) >= 0 ? '#2EAD6B' : '#C8122C';

    $: varianceInsight = (() => {
        if (!kpi.total_count) return '';
        const net = Number(kpi.net_change) || 0;
        const dir = net >= 0 ? 'increase' : 'decrease';
        const top = kpi.top_mover_name && kpi.top_mover_name !== '—' ? ' · Top mover: ' + kpi.top_mover_name : '';
        return kpi.items_up + ' ' + levelLabel.toLowerCase() + 's grew >' + threshold + '% · ' + kpi.items_down + ' cut >' + threshold + '% · Net ' + dir + ': ' + fmtMoney(net, true) + top;
    })();
</script>

<!-- Fixed control bar — measured and positioned via onMount -->
<div bind:this={ctrlBarEl} style={ctrlBarFixed + 'background:var(--nxt-surface); box-shadow:0 2px 14px rgba(99,33,165,0.08); border-bottom:1px solid var(--nxt-border); padding:8px 24px; display:flex; align-items:center; gap:16px; flex-wrap:wrap;'}>

  <!-- View By — dark/gold input group -->
  <div style="display:flex; align-items:stretch; border:2px solid #231F20; border-radius:8px; overflow:hidden;">
    <div style="background:#231F20; padding:0 10px; display:flex; align-items:center;">
      <span style="color:#FFC838; font-size:0.68rem; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; white-space:nowrap;">View By</span>
    </div>
    <Dropdown name=f_level defaultValue="agency">
        <DropdownOption value="agency"     valueLabel="Agency"/>
        <DropdownOption value="unit"       valueLabel="Unit"/>
        <DropdownOption value="program"    valueLabel="Program"/>
        <DropdownOption value="subprogram" valueLabel="Subprogram"/>
    </Dropdown>
  </div>

  <span style="color:#CBD5E1; font-size:0.8rem; font-weight:600; flex-shrink:0;">|</span>

  <!-- Year A — blue input group -->
  <div style="display:flex; align-items:stretch; border:2px solid #0369A1; border-radius:8px; overflow:hidden;">
    <div style="background:#0369A1; padding:0 10px; display:flex; align-items:center;">
      <span style="color:white; font-size:0.68rem; font-weight:800; letter-spacing:0.06em; white-space:nowrap;">Year A</span>
    </div>
    <Dropdown name=f_year_a data={g_fy_all} value=fy defaultValue="%"><DropdownOption value="%" valueLabel="Latest"/></Dropdown>
  </div>

  <span style="color:#9CA3AF; font-size:0.8rem; font-weight:700; flex-shrink:0;">vs</span>

  <!-- Year B — red input group -->
  <div style="display:flex; align-items:stretch; border:2px solid #C8122C; border-radius:8px; overflow:hidden;">
    <div style="background:#C8122C; padding:0 10px; display:flex; align-items:center;">
      <span style="color:white; font-size:0.68rem; font-weight:800; letter-spacing:0.06em; white-space:nowrap;">Year B</span>
    </div>
    <Dropdown name=f_year_b data={g_fy_all} value=fy defaultValue="%"><DropdownOption value="%" valueLabel="Prior"/></Dropdown>
  </div>

  <span style="color:#CBD5E1; font-size:0.8rem; font-weight:600; flex-shrink:0;">|</span>

  <!-- Threshold slider -->
  <div style="display:flex; align-items:center; gap:10px;">
    <div style="background:#231F20; padding:4px 10px; border-radius:6px;">
      <span style="color:#FFC838; font-size:0.68rem; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; white-space:nowrap;">Threshold</span>
    </div>
    <input
      type="range"
      min="5"
      max="100"
      step="5"
      bind:value={threshold}
      style="width:120px; accent-color:#C8122C; cursor:pointer;"
    />
    <span style="font-size:0.85rem; font-weight:700; color:#231F20; min-width:36px;">{threshold}%</span>
  </div>

  </div>

{#if hasActiveFilters}
<div bind:this={chipBarEl} style={chipBarFixed + 'background:var(--nxt-pink); border-bottom:1px solid var(--nxt-border); padding:6px 24px; display:flex; flex-wrap:wrap; gap:6px; align-items:center;'}>
    <span style="font-size:0.7rem; font-weight:700; color:#6B7280; text-transform:uppercase; margin-right:4px;">Active Filters:</span>
    {#if isRealFilter(selectedAgency)}
        <span style="background:var(--nxt-surface); border:1px solid #C8122C; border-radius:20px; padding:3px 10px; font-size:0.75rem; color:#C8122C; font-weight:600; white-space:nowrap;">Agency: {selectedAgency}</span>
    {/if}
    {#if isRealFilter(selectedUnit)}
        <span style="background:var(--nxt-surface); border:1px solid #C8122C; border-radius:20px; padding:3px 10px; font-size:0.75rem; color:#C8122C; font-weight:600; white-space:nowrap;">Unit: {selectedUnit}</span>
    {/if}
    {#if isRealFilter(selectedProgram)}
        <span style="background:var(--nxt-surface); border:1px solid #C8122C; border-radius:20px; padding:3px 10px; font-size:0.75rem; color:#C8122C; font-weight:600; white-space:nowrap;">Program: {selectedProgram}</span>
    {/if}
    {#if isRealFilter(selectedFund)}
        <span style="background:var(--nxt-surface); border:1px solid #C8122C; border-radius:20px; padding:3px 10px; font-size:0.75rem; color:#C8122C; font-weight:600; white-space:nowrap;">Fund: {selectedFund}</span>
    {/if}
</div>
{/if}

<!-- Spacer pushes content below the fixed bar -->
<div style="height:{ctrlBarSpacerH};"></div>


<!-- Collapsible filters -->
<Details title="🔍 Filters" open=false>
    <div style="display:flex; flex-wrap:wrap; gap:12px; padding:8px 0;">
        <div style="flex:1; min-width:200px; max-width:300px;">
            <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Agencies"/>
            </Dropdown>
        </div>
        <div style="flex:1; min-width:200px; max-width:300px;">
            <Dropdown name=f_unit data={g_unit} value=u title="Unit" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Units"/>
            </Dropdown>
        </div>
        <div style="flex:1; min-width:200px; max-width:300px;">
            <Dropdown name=f_program data={g_program} value=p title="Program" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Programs"/>
            </Dropdown>
        </div>
        <div style="flex:1; min-width:160px; max-width:240px;">
            <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%">
                <DropdownOption value="%" valueLabel="All Fund Types"/>
            </Dropdown>
        </div>
    </div>

</Details>

```sql year_bounds
select max(fiscal_year) as latest_year, max(fiscal_year) - 1 as prior_year
from mbtsa.subprogram_level
where total_budget_amount > 0
```

```sql selected_years
select
    case when '${selectedYearA}' in ('%', '', 'undefined') or '${selectedYearA}' like '(select%' then 
        (select latest_year from ${year_bounds}) else cast('${selectedYearA}' as int) end as year_a,
    case when '${selectedYearB}' in ('%', '', 'undefined') or '${selectedYearB}' like '(select%' then 
        (select prior_year  from ${year_bounds}) else cast('${selectedYearB}' as int) end as year_b
```

```sql agency_variance
with a as (
    select agency_code, agency_name, sum(total_budget_amount) as spend_a
    from mbtsa.subprogram_level
    where fiscal_year = (select year_a from ${selected_years})
            and lower(coalesce(agency_name,'')) like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(fund_type,''))   like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name
),
b as (
    select agency_code, agency_name, sum(total_budget_amount) as spend_b
    from mbtsa.subprogram_level
    where fiscal_year = (select year_b from ${selected_years})
            and lower(coalesce(agency_name,'')) like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(fund_type,''))   like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name
)
select
    coalesce(a.agency_code, b.agency_code) as agency_code,
    coalesce(a.agency_name, b.agency_name) as agency_name,
    coalesce(a.spend_a, 0)                 as latest_year,
    coalesce(b.spend_b, 0)                 as prior_year,
    coalesce(a.spend_a, 0) - coalesce(b.spend_b, 0) as change_amt,
    round((coalesce(a.spend_a,0) - coalesce(b.spend_b,0)) * 100.0 / nullif(b.spend_b, 0), 1) as change_pct
from a full outer join b using (agency_code, agency_name)
order by abs(change_amt) desc
```

```sql unit_variance
with a as (
    select agency_code, agency_name, unit_name, sum(total_budget_amount) as spend_a
    from mbtsa.subprogram_level
    where fiscal_year = (select year_a from ${selected_years})
            and lower(coalesce(agency_name,'')) like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))   like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(fund_type,''))   like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name, unit_name
),
b as (
    select agency_code, agency_name, unit_name, sum(total_budget_amount) as spend_b
    from mbtsa.subprogram_level
    where fiscal_year = (select year_b from ${selected_years})
            and lower(coalesce(agency_name,'')) like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))   like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(fund_type,''))   like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name, unit_name
)
select
    coalesce(a.agency_code, b.agency_code) as agency_code,
    coalesce(a.agency_name, b.agency_name) as agency_name,
    coalesce(a.unit_name, b.unit_name) as unit_name,
    coalesce(a.spend_a, 0)             as latest_year,
    coalesce(b.spend_b, 0)             as prior_year,
    coalesce(a.spend_a, 0) - coalesce(b.spend_b, 0) as change_amt,
    round((coalesce(a.spend_a,0) - coalesce(b.spend_b,0)) * 100.0 / nullif(b.spend_b, 0), 1) as change_pct
from a full outer join b using (agency_code, agency_name, unit_name)
order by abs(change_amt) desc
```

```sql program_variance
with a as (
    select agency_code, agency_name, unit_name, program_name, sum(total_budget_amount) as spend_a
    from mbtsa.subprogram_level
    where fiscal_year = (select year_a from ${selected_years})
            and lower(coalesce(agency_name,''))  like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))    like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(fund_type,''))    like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name, unit_name, program_name
),
b as (
    select agency_code, agency_name, unit_name, program_name, sum(total_budget_amount) as spend_b
    from mbtsa.subprogram_level
    where fiscal_year = (select year_b from ${selected_years})
            and lower(coalesce(agency_name,''))  like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))    like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(fund_type,''))    like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name, unit_name, program_name
)
select
    coalesce(a.agency_code,  b.agency_code)  as agency_code,
    coalesce(a.agency_name,  b.agency_name)  as agency_name,
    coalesce(a.unit_name,    b.unit_name)    as unit_name,
    coalesce(a.program_name, b.program_name) as program_name,
    coalesce(a.spend_a, 0)                   as latest_year,
    coalesce(b.spend_b, 0)                   as prior_year,
    coalesce(a.spend_a, 0) - coalesce(b.spend_b, 0) as change_amt,
    round((coalesce(a.spend_a,0) - coalesce(b.spend_b,0)) * 100.0 / nullif(b.spend_b, 0), 1) as change_pct
from a full outer join b using (agency_code, agency_name, unit_name, program_name)
order by abs(change_amt) desc
```

```sql subprogram_variance
with a as (
    select agency_code, agency_name, unit_name, program_name, subprogram_name, sum(total_budget_amount) as spend_a
    from mbtsa.subprogram_level
    where fiscal_year = (select year_a from ${selected_years})
            and lower(coalesce(agency_name,''))  like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))    like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(program_name,'')) like case when '${selectedProgram}' like '(select%' then '%' else '${selectedProgram}' end
            and lower(coalesce(fund_type,''))    like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name, unit_name, program_name, subprogram_name
),
b as (
    select agency_code, agency_name, unit_name, program_name, subprogram_name, sum(total_budget_amount) as spend_b
    from mbtsa.subprogram_level
    where fiscal_year = (select year_b from ${selected_years})
            and lower(coalesce(agency_name,''))  like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))    like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(program_name,'')) like case when '${selectedProgram}' like '(select%' then '%' else '${selectedProgram}' end
            and lower(coalesce(fund_type,''))    like case when '${selectedFund}' like '(select%' then '%' else '${selectedFund}' end
    group by agency_code, agency_name, unit_name, program_name, subprogram_name
)
select
    coalesce(a.agency_code,     b.agency_code)     as agency_code,
    coalesce(a.agency_name,     b.agency_name)     as agency_name,
    coalesce(a.unit_name,       b.unit_name)       as unit_name,
    coalesce(a.program_name,    b.program_name)    as program_name,
    coalesce(a.subprogram_name, b.subprogram_name) as subprogram_name,
    coalesce(a.spend_a, 0)                         as latest_year,
    coalesce(b.spend_b, 0)                         as prior_year,
    coalesce(a.spend_a, 0) - coalesce(b.spend_b, 0) as change_amt,
    round((coalesce(a.spend_a,0) - coalesce(b.spend_b,0)) * 100.0 / nullif(b.spend_b, 0), 1) as change_pct
from a full outer join b using (agency_code, agency_name, unit_name, program_name, subprogram_name)
order by abs(change_amt) desc
```
```sql new_programs
select
    agency_name, unit_name, program_name,
    latest_year as budget,
    count(*) over () as new_count
from ${program_variance}
where prior_year = 0 and latest_year > 0
order by latest_year desc
limit 10
```

```sql eliminated_programs
select
    agency_name, unit_name, program_name,
    prior_year as budget,
    count(*) over () as elim_count
from ${program_variance}
where latest_year = 0 and prior_year > 0
order by prior_year desc
limit 10
```

```sql fund_variance
with a as (
    select fund_type, sum(total_budget_amount) as spend_a
    from mbtsa.subprogram_level
    where fiscal_year = (select year_a from ${selected_years})
            and lower(coalesce(agency_name,''))  like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))    like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(program_name,'')) like case when '${selectedProgram}' like '(select%' then '%' else '${selectedProgram}' end
            and fund_type is not null
    group by fund_type
),
b as (
    select fund_type, sum(total_budget_amount) as spend_b
    from mbtsa.subprogram_level
    where fiscal_year = (select year_b from ${selected_years})
            and lower(coalesce(agency_name,''))  like case when '${selectedAgency}' like '(select%' then '%' else '${selectedAgency}' end
            and lower(coalesce(unit_name,''))    like case when '${selectedUnit}' like '(select%' then '%' else '${selectedUnit}' end
            and lower(coalesce(program_name,'')) like case when '${selectedProgram}' like '(select%' then '%' else '${selectedProgram}' end
            and fund_type is not null
    group by fund_type
)
select
    coalesce(a.fund_type, b.fund_type) as fund_type,
    coalesce(a.spend_a, 0)             as latest_year,
    coalesce(b.spend_b, 0)             as prior_year,
    coalesce(a.spend_a, 0) - coalesce(b.spend_b, 0) as change_amt,
    round((coalesce(a.spend_a,0) - coalesce(b.spend_b,0)) * 100.0 / nullif(b.spend_b, 0), 1) as change_pct
from a full outer join b using (fund_type)
order by abs(change_amt) desc
```

<div style="display:grid; grid-template-columns:1.4fr 1fr 1fr 1fr; gap:12px; margin:16px 0 16px;">

    <div style={'border-radius:10px; padding:18px 20px; background:' + netBg + '; border:1.5px solid ' + netBorder + '; display:flex; flex-direction:column; justify-content:space-between; min-height:110px;'}>
        <span style="font-size:0.7rem; font-weight:700; letter-spacing:0.08em; color:#6B7280; text-transform:uppercase;">Net Budget Change</span>
        <div>
            <div style={'font-size:2rem; font-weight:800; line-height:1.1; color:' + netColor + ';'}>{fmtMoney(kpi.net_change, true)}</div>
            <div style="font-size:0.75rem; color:#9CA3AF; margin-top:4px;">FY{yearALabel} vs FY{yearBLabel} · {levelLabel} level</div>
        </div>
    </div>

    <div style="border-radius:10px; padding:18px 20px; background:var(--nxt-surface); border:1.5px solid var(--nxt-border); border-top:3px solid #231F20; display:flex; flex-direction:column; justify-content:space-between; min-height:110px;">
        <span style="font-size:0.7rem; font-weight:700; letter-spacing:0.08em; color:#6B7280; text-transform:uppercase;">{levelLabel}s Changed &gt;{threshold}%</span>
        <div>
            <div style="display:flex; align-items:baseline; gap:10px;">
                <span style="font-size:1.6rem; font-weight:800; color:#1A7340;">↑{kpi.items_up ?? 0}</span>
                <span style="font-size:1.6rem; font-weight:800; color:#C8122C;">↓{kpi.items_down ?? 0}</span>
                <span style="font-size:0.85rem; color:#9CA3AF;">of {kpi.total_count ?? '?'}</span>
            </div>
            <div style="font-size:0.75rem; color:#9CA3AF; margin-top:4px;">{fmtMoney(kpi.total_increased, true)} gained · {fmtMoney(kpi.total_decreased, true)} lost</div>
        </div>
    </div>

    <div style="border-radius:10px; padding:18px 20px; background:var(--nxt-surface); border:1.5px solid var(--nxt-border); border-top:3px solid #0EA5E9; display:flex; flex-direction:column; justify-content:space-between; min-height:110px;">
        <span style="font-size:0.7rem; font-weight:700; letter-spacing:0.08em; color:#6B7280; text-transform:uppercase;">New {levelLabel}s</span>
        <div>
            <div style="font-size:1.8rem; font-weight:800; color:#0369A1;">+{npCount}</div>
            <div style="font-size:0.75rem; color:#9CA3AF; margin-top:4px;">in FY{yearALabel}</div>
        </div>
    </div>

    <div style="border-radius:10px; padding:18px 20px; background:var(--nxt-surface); border:1.5px solid var(--nxt-border); border-top:3px solid #F59E0B; display:flex; flex-direction:column; justify-content:space-between; min-height:110px;">
        <span style="font-size:0.7rem; font-weight:700; letter-spacing:0.08em; color:#6B7280; text-transform:uppercase;">Eliminated {levelLabel}s</span>
        <div>
            <div style="font-size:1.8rem; font-weight:800; color:#B45309;">-{epCount}</div>
            <div style="font-size:0.75rem; color:#9CA3AF; margin-top:4px;">from FY{yearBLabel}</div>
        </div>
    </div>

</div>



---


## Top Movers

<VarianceDivergingChart data={activeVariance} labelField={activeLabelField} valueField="change_pct" title="{levelLabel} Budget Changes — FY{yearALabel} vs FY{yearBLabel} (%)" limit=14 threshold={threshold}/>

---

## New & Eliminated Programs



<div>

<p style="font-weight:700; color:#2EAD6B; margin-bottom:8px;">🟢 New {levelLabel}s in FY{yearALabel}</p>
{#if activeVariance.filter(r => Number(r.prior_year) === 0 && Number(r.latest_year) > 0).length > 0}
<DataTable data={activeVariance.filter(r => Number(r.prior_year) === 0 && Number(r.latest_year) > 0 && !activeVariance.some(x => x[activeLabelField] === r[activeLabelField] && Number(x.latest_year) === 0 && Number(x.prior_year) > 0)).slice(0,10)} rows=10>
svelte    <Column id=agency_code title="Code"/>
    <Column id=agency_name title="Agency"/>
    <Column id={activeLabelField} title={levelLabel}/>
    <Column id=latest_year title="Budget" fmt=usd2compactviz/>
</DataTable>
{:else}
<p style="color:#6B7280; font-size:0.875rem; padding:12px 0;">No new {levelLabel.toLowerCase()}s in FY{yearALabel}</p>
{/if}
</div>
<div style="margin-top:16px;">
<p style="font-weight:700; color:#C8122C; margin-bottom:8px;">🔴 Eliminated {levelLabel}s from FY{yearBLabel}</p>
{#if activeVariance.filter(r => Number(r.latest_year) === 0 && Number(r.prior_year) > 0).length > 0}
<DataTable data={activeVariance.filter(r => Number(r.latest_year) === 0 && Number(r.prior_year) > 0 && !activeVariance.some(x => x[activeLabelField] === r[activeLabelField] && Number(x.prior_year) === 0 && Number(x.latest_year) > 0)).slice(0,10)} rows=10>
svelte    <Column id=agency_code title="Code"/>
    <Column id=agency_name title="Agency"/>
    <Column id={activeLabelField} title={levelLabel}/>
    <Column id=prior_year title="Last Budget" fmt=usd2compactviz/>
</DataTable>
{:else}
<p style="color:#6B7280; font-size:0.875rem; padding:12px 0;">No eliminated {levelLabel.toLowerCase()}s from FY{yearBLabel}</p>
{/if}
</div>

---

## {levelLabel}-Level Variance

{#if selectedLevel === 'agency'}
<DataTable data={agency_variance} totalRow=true search=true rows=20>
    <Column id=agency_name title="Agency"/>
    <Column id=latest_year title="FY{yearALabel}" fmt=usd2compactviz/>
    <Column id=prior_year  title="FY{yearBLabel}" fmt=usd2compactviz/>
    <Column id=change_amt  title="Change ($)" fmt=usd2compactviz/>
    <Column id=change_pct  title="Change (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>
{:else if selectedLevel === 'unit'}
<DataTable data={unit_variance} totalRow=true search=true rows=20>
    <Column id=unit_name   title="Unit"/>
    <Column id=latest_year title="FY{yearALabel}" fmt=usd2compactviz/>
    <Column id=prior_year  title="FY{yearBLabel}" fmt=usd2compactviz/>
    <Column id=change_amt  title="Change ($)" fmt=usd2compactviz/>
    <Column id=change_pct  title="Change (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>
{:else if selectedLevel === 'program'}
<DataTable data={program_variance} totalRow=true search=true rows=25>
    <Column id=agency_name  title="Agency"/>
    <Column id=unit_name    title="Unit"/>
    <Column id=program_name title="Program"/>
    <Column id=latest_year  title="FY{yearALabel}" fmt=usd2compactviz/>
    <Column id=prior_year   title="FY{yearBLabel}" fmt=usd2compactviz/>
    <Column id=change_amt   title="Change ($)" fmt=usd2compactviz/>
    <Column id=change_pct   title="Change (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>
{:else}
<DataTable data={subprogram_variance} totalRow=true search=true rows=25>
    <Column id=agency_name     title="Agency"/>
    <Column id=unit_name       title="Unit"/>
    <Column id=program_name    title="Program"/>
    <Column id=subprogram_name title="Subprogram"/>
    <Column id=latest_year     title="FY{yearALabel}" fmt=usd2compactviz/>
    <Column id=prior_year      title="FY{yearBLabel}" fmt=usd2compactviz/>
    <Column id=change_amt      title="Change ($)" fmt=usd2compactviz/>
    <Column id=change_pct      title="Change (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>
{/if}

---


## Fund Type Shift



<DataTable data={fund_variance} totalRow=true>
    <Column id=fund_type   title="Fund Type"/>
    <Column id=latest_year title="FY{yearALabel}" fmt=usd2compactviz/>
    <Column id=prior_year  title="FY{yearBLabel}" fmt=usd2compactviz/>
    <Column id=change_amt  title="Change ($)" fmt=usd2compactviz/>
    <Column id=change_pct  title="Change (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>
