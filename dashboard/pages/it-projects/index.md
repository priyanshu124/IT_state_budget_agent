---
title: IT Development Projects
sidebar_position: 5
---

<script>
  import GanttChart from '../../components/GanttChart.svelte';
  import MiniCharts from '../../components/MiniCharts.svelte';
</script>

```sql all_projects
SELECT
    mitdp_id,
    project_title,
    "Agency"                     AS agency,
    "Phase"                      AS phase,
    "Start Year"                 AS start_year,
    "End Year"                   AS end_year,
    est_total_cost_at_completion AS eac_label,
    est_cost_remaining           AS remaining_label,
    "Project Time Remaining"     AS time_remaining,
    "Project Length"             AS project_length
FROM mbtsa.mitdp_projects
ORDER BY agency, project_title
```

```sql portfolio_totals
SELECT
    ROUND(SUM(
        CASE WHEN est_total_cost_at_completion = 'TBD' THEN 0
             ELSE (
                TRY_CAST(replace(string_split(replace(est_total_cost_at_completion, '$', ''), ' - ')[1], 'M', '') AS FLOAT) +
                TRY_CAST(replace(string_split(replace(est_total_cost_at_completion, '$', ''), ' - ')[2], 'M', '') AS FLOAT)
             ) / 2.0
        END
    )) AS total_eac,
    ROUND(SUM(
        CASE WHEN est_cost_remaining = 'TBD' THEN 0
             ELSE (
                TRY_CAST(replace(string_split(replace(est_cost_remaining, '$', ''), ' - ')[1], 'M', '') AS FLOAT) +
                TRY_CAST(replace(string_split(replace(est_cost_remaining, '$', ''), ' - ')[2], 'M', '') AS FLOAT)
             ) / 2.0
        END
    )) AS total_remaining
FROM mbtsa.mitdp_projects
```

```sql gantt_data
WITH base AS (
    SELECT
        mitdp_id,
        project_title,
        "Agency"                     AS agency,
        "Phase"                      AS current_phase,
        est_total_cost_at_completion AS eac_label,
        est_cost_remaining           AS remaining_label,
        "Project Time Remaining"     AS time_remaining,
        CASE
            WHEN est_total_cost_at_completion = 'TBD' THEN NULL
            ELSE (
                TRY_CAST(replace(string_split(replace(est_total_cost_at_completion, '$', ''), ' - ')[1], 'M', '') AS FLOAT) +
                TRY_CAST(replace(string_split(replace(est_total_cost_at_completion, '$', ''), ' - ')[2], 'M', '') AS FLOAT)
            ) / 2.0
        END AS eac_midpoint,
        TRY_CAST("Procurement Start - Current"    AS TIMESTAMP)::DATE AS proc_start,
        TRY_CAST("Procurement End - Current"      AS TIMESTAMP)::DATE AS proc_end,
        TRY_CAST("Implementation Start - Current" AS TIMESTAMP)::DATE AS impl_start,
        TRY_CAST("Implementation End - Current"   AS TIMESTAMP)::DATE AS impl_end,
        TRY_CAST("O&M Start - Current"            AS TIMESTAMP)::DATE AS om_start,
        TRY_CAST("O&M End - Current"              AS TIMESTAMP)::DATE AS om_end
    FROM mbtsa.mitdp_projects
)
SELECT mitdp_id, project_title, agency, current_phase,
       eac_label, remaining_label, time_remaining, eac_midpoint,
       'Procurement'    AS phase_name, proc_start AS phase_start, proc_end AS phase_end
FROM base
UNION ALL
SELECT mitdp_id, project_title, agency, current_phase,
       eac_label, remaining_label, time_remaining, eac_midpoint,
       'Implementation' AS phase_name, impl_start, impl_end
FROM base
UNION ALL
SELECT mitdp_id, project_title, agency, current_phase,
       eac_label, remaining_label, time_remaining, eac_midpoint,
       'O&M'            AS phase_name, om_start, om_end
FROM base
ORDER BY agency, mitdp_id, phase_start
```

```sql phase_dist
SELECT "Phase" AS phase, COUNT(*) AS count
FROM mbtsa.mitdp_projects
GROUP BY "Phase"
ORDER BY count DESC
```

```sql agency_costs
SELECT
    "Agency" AS agency,
    COUNT(*) AS project_count,
    ROUND(SUM(
        CASE WHEN est_total_cost_at_completion = 'TBD' THEN 0
             ELSE (
                TRY_CAST(replace(string_split(replace(est_total_cost_at_completion, '$', ''), ' - ')[1], 'M', '') AS FLOAT) +
                TRY_CAST(replace(string_split(replace(est_total_cost_at_completion, '$', ''), ' - ')[2], 'M', '') AS FLOAT)
             ) / 2.0
        END
    )) AS total_eac,
    ROUND(SUM(
        CASE WHEN est_cost_remaining = 'TBD' THEN 0
             ELSE (
                TRY_CAST(replace(string_split(replace(est_cost_remaining, '$', ''), ' - ')[1], 'M', '') AS FLOAT) +
                TRY_CAST(replace(string_split(replace(est_cost_remaining, '$', ''), ' - ')[2], 'M', '') AS FLOAT)
             ) / 2.0
        END
    )) AS remaining_eac
FROM mbtsa.mitdp_projects
GROUP BY "Agency"
ORDER BY total_eac DESC
LIMIT 10
```

```sql active_by_year
WITH years AS (
    SELECT unnest(range(2012, 2036)) AS yr
),
projects AS (
    SELECT "Start Year" AS start_yr, "End Year" AS end_yr, "Phase" AS phase
    FROM mbtsa.mitdp_projects
)
SELECT
    y.yr                                                                        AS year,
    COUNT(*)                                                                    AS active_projects,
    COUNT(*) FILTER (WHERE p.phase = 'Implementation')                         AS impl,
    COUNT(*) FILTER (WHERE p.phase = 'Procurement')                            AS proc,
    COUNT(*) FILTER (WHERE p.phase = 'O&M')                                    AS om,
    COUNT(*) FILTER (WHERE p.phase = 'Planning')                               AS plan,
    COUNT(*) FILTER (WHERE p.phase NOT IN ('Implementation','Procurement','O&M','Planning')) AS other
FROM years y
JOIN projects p ON y.yr >= p.start_yr AND y.yr <= p.end_yr
GROUP BY y.yr
ORDER BY y.yr
```

---

## IT Portfolio Overview

<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-val">{all_projects.length}</div>
    <div class="kpi-lbl">Total IT Projects</div>
    <div class="kpi-sub">{new Set(all_projects.map(p => p.agency)).size} agencies</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">${(Math.round(portfolio_totals[0].total_eac / 100) / 10).toFixed(1)}B</div>
    <div class="kpi-lbl">Est. Total Portfolio Cost</div>
    <div class="kpi-sub">${portfolio_totals[0].total_remaining >= 1000 ? (Math.round(portfolio_totals[0].total_remaining / 100) / 10).toFixed(1) + "B" : Math.round(portfolio_totals[0].total_remaining) + "M"} remaining to spend</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{all_projects.filter(p => p.phase === 'Implementation').length}</div>
    <div class="kpi-lbl">In Implementation</div>
    <div class="kpi-sub">{Math.round(all_projects.filter(p => p.phase === 'Implementation').length / all_projects.length * 100)}% of portfolio</div>
  </div>
  <div class="kpi-card kpi-card--alert">
    <div class="kpi-val">{all_projects.filter(p => p.time_remaining?.startsWith('0 to 1') || p.time_remaining?.startsWith('0 to 2')).length}</div>
    <div class="kpi-lbl">Closing Within 2 Years</div>
    <div class="kpi-sub">{all_projects.filter(p => p.time_remaining?.startsWith('0 to 1')).length} closing within 1 yr</div>
  </div>
</div>

---

## Charts

<MiniCharts phaseData={phase_dist} agencyCosts={agency_costs} activeByYear={active_by_year} />

---

## Attention Needed

<div class="alerts">
  <div class="alert alert--red">
    <span class="adot adot--red"></span>
    <div>
      <div class="alert-title">5 projects ending within 1 year</div>
      <div class="alert-sub">CBIS, OneStop Portal, EPHR, BHASO, UCA — closeout or O&M transitions imminent</div>
    </div>
  </div>
  <div class="alert alert--red">
    <span class="adot adot--red"></span>
    <div>
      <div class="alert-title">FMIS: $300M–$325M remaining</div>
      <div class="alert-sub">Largest single commitment — still in procurement, ends 2032</div>
    </div>
  </div>
  <div class="alert alert--amber">
    <span class="adot adot--amber"></span>
    <div>
      <div class="alert-title">MDH holds 38% of all projects (23/60)</div>
      <div class="alert-sub">Concentrated risk — Medicaid Modernization alone has 14 sub-projects</div>
    </div>
  </div>
  <div class="alert alert--amber">
    <span class="adot adot--amber"></span>
    <div>
      <div class="alert-title">1 project with TBD cost estimate</div>
      <div class="alert-sub">Statewide Permitting Platform (DPSCS-17-CCHII) — budget unresolved</div>
    </div>
  </div>
  <div class="alert alert--blue">
    <span class="adot adot--blue"></span>
    <div>
      <div class="alert-title">11 projects in procurement</div>
      <div class="alert-sub">Vendor decisions approaching for FMIS, 2026 Voting System, VREAM</div>
    </div>
  </div>
  <div class="alert alert--blue">
    <span class="adot adot--blue"></span>
    <div>
      <div class="alert-title">2029–2030 wave: 26 completions</div>
      <div class="alert-sub">Major O&M transitions and budget reallocation upcoming simultaneously</div>
    </div>
  </div>
</div>

---

## Project Timeline

<GanttChart data={gantt_data} />

---

## All Projects

<DataTable
  data={all_projects}
  search=true
  rows=15
/>

<style>
  .kpi-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 16px 0 24px;
  }
  .kpi-card {
    background: var(--grey-50, #f7f6f3);
    border-radius: 8px;
    padding: 16px 18px;
    border: 1px solid var(--grey-200, #e5e3dc);
  }
  .kpi-card--alert { border-color: #fca5a5; background: #fff5f5; }
  .kpi-val  { font-size: 28px; font-weight: 600; line-height: 1.1; color: var(--grey-900, #1a1a18); }
  .kpi-lbl  { font-size: 12px; color: var(--grey-600, #5f5e5a); margin-top: 5px; }
  .kpi-sub  {
    font-size: 11px; font-weight: 600;
    color: var(--grey-800, #1a1a18);
    margin-top: 4px;
    padding: 2px 6px;
    background: rgba(0,0,0,0.05);
    border-radius: 4px;
    display: inline-block;
  }
  .kpi-card--alert .kpi-sub {
    background: rgba(226,75,74,0.12);
    color: #C93B3A;
  }

  .alerts {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin: 16px 0 24px;
  }
  .alert {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 11px 13px; border-radius: 8px; border: 1px solid; font-size: 12px;
  }
  .alert--red   { background: #fff5f5; border-color: #fca5a5; }
  .alert--amber { background: #fffbeb; border-color: #fcd34d; }
  .alert--blue  { background: #eff6ff; border-color: #93c5fd; }
  .adot { width: 7px; height: 7px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; display: block; }
  .adot--red   { background: #E24B4A; }
  .adot--amber { background: #EF9F27; }
  .adot--blue  { background: #378ADD; }
  .alert-title { font-weight: 600; color: var(--grey-900, #1a1a18); }
  .alert-sub   { color: var(--grey-600, #5f5e5a); font-size: 11px; margin-top: 2px; }
</style>