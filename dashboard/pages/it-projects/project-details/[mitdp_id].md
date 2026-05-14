---
title:
prerender: false
---

<script>
  import ProjectGantt from '../../../../components/ProjectGantt.svelte';
  import AppropriationChart from '../../../../components/AppropriationChart.svelte';
</script>

```sql project
SELECT
    mitdp_id,
    project_title,
    "Agency"                        AS agency,
    "Phase"                         AS phase,
    project_summary,
    "Name"                          AS program_name,
    appropriation_code,
    est_total_cost_at_completion    AS eac_label,
    est_cost_remaining              AS remaining_label,
    "Project Time Remaining"        AS time_remaining,
    "Project Length"                AS project_length,
    "Start Year"                    AS start_year,
    "End Year"                      AS end_year,
    TRY_CAST("Procurement Start - Current"    AS TIMESTAMP)::DATE AS proc_start,
    TRY_CAST("Procurement End - Current"      AS TIMESTAMP)::DATE AS proc_end,
    TRY_CAST("Implementation Start - Current" AS TIMESTAMP)::DATE AS impl_start,
    TRY_CAST("Implementation End - Current"   AS TIMESTAMP)::DATE AS impl_end,
    TRY_CAST("O&M Start - Current"            AS TIMESTAMP)::DATE AS om_start,
    TRY_CAST("O&M End - Current"              AS TIMESTAMP)::DATE AS om_end
FROM mbtsa.mitdp_projects
WHERE mitdp_id = '${params.mitdp_id}'
```

```sql funding
WITH sub_rows AS (
    SELECT
        funding_type,
        prior_to_fy2025,
        actual_fy2025,
        appropriation_fy2026,
        allowance_fy2027,
        total_funding_to_date,
        CASE
            WHEN funding_type IN ('ITIF','Realigned ITIF','Agency Funds','Federal Funds','Reimbursable Funds')
                THEN 'Annual Appropriation'
            WHEN funding_type IN ('ITIF Realignment','Agency Funds Realignment','Agency Funds Realignmen')
                THEN 'Off-Cycle Adjustments'
        END AS parent_header
    FROM mbtsa.mitdp_funding
    WHERE mitdp_id = '${params.mitdp_id}'
      AND funding_type NOT IN ('Total','Annual Appropriation','Off-Cycle Adjustments')
      AND COALESCE(prior_to_fy2025, actual_fy2025, appropriation_fy2026, allowance_fy2027, total_funding_to_date) IS NOT NULL
),
headers_with_children AS (
    SELECT DISTINCT parent_header AS funding_type
    FROM sub_rows
    WHERE parent_header IS NOT NULL
)
SELECT
    f.funding_type,
    CASE f.funding_type
        WHEN 'Annual Appropriation'  THEN 'header'
        WHEN 'Off-Cycle Adjustments' THEN 'header'
        ELSE 'sub'
    END AS row_type,
    f.prior_to_fy2025,
    f.actual_fy2025,
    f.appropriation_fy2026,
    f.allowance_fy2027,
    f.total_funding_to_date
FROM mbtsa.mitdp_funding f
WHERE mitdp_id = '${params.mitdp_id}'
  AND funding_type != 'Total'
  AND (
    -- only include header if it has at least one non-null child
    (f.funding_type = 'Annual Appropriation'  AND EXISTS (SELECT 1 FROM headers_with_children WHERE funding_type = 'Annual Appropriation'))
    OR
    (f.funding_type = 'Off-Cycle Adjustments' AND EXISTS (SELECT 1 FROM headers_with_children WHERE funding_type = 'Off-Cycle Adjustments'))
    -- include sub-rows that have values
    OR COALESCE(f.prior_to_fy2025, f.actual_fy2025, f.appropriation_fy2026, f.allowance_fy2027, f.total_funding_to_date) IS NOT NULL
  )
  AND f.funding_type NOT IN ('Annual Appropriation','Off-Cycle Adjustments')
  OR (
    f.funding_type IN ('Annual Appropriation','Off-Cycle Adjustments')
    AND f.funding_type IN (SELECT funding_type FROM headers_with_children)
    AND f.mitdp_id = '${params.mitdp_id}'
  )
ORDER BY
    CASE f.funding_type
        WHEN 'Annual Appropriation'     THEN 1
        WHEN 'ITIF'                     THEN 2
        WHEN 'Realigned ITIF'           THEN 3
        WHEN 'Agency Funds'             THEN 4
        WHEN 'Federal Funds'            THEN 5
        WHEN 'Reimbursable Funds'       THEN 6
        WHEN 'Off-Cycle Adjustments'    THEN 7
        WHEN 'ITIF Realignment'         THEN 8
        WHEN 'Agency Funds Realignment' THEN 9
        WHEN 'Agency Funds Realignmen'  THEN 9
        ELSE 10
    END
```

```sql funding_total
SELECT
    prior_to_fy2025,
    actual_fy2025,
    appropriation_fy2026,
    allowance_fy2027,
    total_funding_to_date
FROM mbtsa.mitdp_funding
WHERE mitdp_id = '${params.mitdp_id}'
  AND funding_type = 'Total'
```

```sql dev_costs
SELECT
    funding_type,
    prior_to_fy2025,
    actual_fy2025,
    spend_plan_fy2026,
    spend_plan_fy2027,
    projected_outyears
FROM mbtsa.mitdp_dev_costs
WHERE mitdp_id = '${params.mitdp_id}'
  AND funding_type NOT IN ('Total', 'Project Costs, All Time')
  AND COALESCE(prior_to_fy2025, actual_fy2025, spend_plan_fy2026, spend_plan_fy2027, projected_outyears) IS NOT NULL
ORDER BY COALESCE(actual_fy2025, 0) DESC
```

```sql dev_costs_total
SELECT
    prior_to_fy2025,
    actual_fy2025,
    spend_plan_fy2026,
    spend_plan_fy2027,
    projected_outyears
FROM mbtsa.mitdp_dev_costs
WHERE mitdp_id = '${params.mitdp_id}'
  AND funding_type = 'Total'
```

<!-- ── Header ─────────────────────────────────────────────── -->

<div style="background: linear-gradient(135deg, #ede5f8 0%, #d4bef0 100%); padding: 24px 32px; border-radius: 12px; border-bottom: 4px solid #802cd7; margin-bottom: 0;">
  <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap;">
    <div>
      <h1 style="color: #211030; font-size: 1.5rem; font-weight: 700; margin: 0 0 4px 0; line-height:1.3;">
        🖥️ {project?.[0]?.project_title ?? ''}
      </h1>
      <p style="color: #6321a5; font-size: 0.9rem; margin: 0;">{project?.[0]?.agency ?? ''}</p>
    </div>
    <span style="font-size:11px; font-family:monospace; background:#802cd7; border-radius:5px; padding:4px 12px; color:#fff; font-weight:700; letter-spacing:0.06em; white-space:nowrap; flex-shrink:0;">
      {project?.[0]?.mitdp_id ?? ''}
    </span>
  </div>
  <div style="display:flex; gap:8px; margin-top:16px; flex-wrap:nowrap; align-items:center;">
    <span class="phase-badge phase-{(project?.[0]?.phase ?? '').toLowerCase().replace(/[^a-z]/g,'-')}" style="font-size:12px; padding:4px 14px; border-radius:20px; font-weight:600; white-space:nowrap;">
      {project?.[0]?.phase ?? ''}
    </span>
    <span style="font-size:12px; padding:4px 12px; border-radius:20px; background:rgba(128,44,215,0.15); border:1px solid #802cd7; color:#3C1473; font-weight:500; white-space:nowrap;">
      {project?.[0]?.project_length ?? ''}
    </span>
    <span style="font-size:12px; padding:4px 12px; border-radius:20px; background:rgba(128,44,215,0.15); border:1px solid #802cd7; color:#3C1473; font-weight:500; white-space:nowrap;">
      {project?.[0]?.time_remaining ?? ''} remaining
    </span>
  </div>
</div>

<a href="/it-projects" style="display:inline-block; margin: 12px 0; color: #6321a5; font-size: 0.9rem; text-decoration: none;">← Back to IT Portfolio</a>

<!-- ── KPIs ─────────────────────────────────────────────────── -->

<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-val">{project?.[0]?.eac_label}</div>
    <div class="kpi-lbl">Est. Total Cost at Completion</div>
    <div class="kpi-sub">{project?.[0]?.remaining_label} remaining</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">${((funding_total?.[0]?.total_funding_to_date ?? 0) / 1e6).toFixed(1)}M</div>
    <div class="kpi-lbl">Total Funding to Date</div>
    <div class="kpi-sub">
      FY2026: ${((funding_total?.[0]?.appropriation_fy2026 ?? 0) / 1e6).toFixed(1)}M ·
      FY2027: ${((funding_total?.[0]?.allowance_fy2027 ?? 0) / 1e6).toFixed(1)}M
    </div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">${((dev_costs_total?.[0]?.actual_fy2025 ?? 0) / 1e6).toFixed(1)}M</div>
    <div class="kpi-lbl">FY2025 Actual Spend</div>
    <div class="kpi-sub">FY2026 plan: ${((dev_costs_total?.[0]?.spend_plan_fy2026 ?? 0) / 1e6).toFixed(1)}M</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{project?.[0]?.start_year} – {project?.[0]?.end_year}</div>
    <div class="kpi-lbl">Project Timeline</div>
    <div class="kpi-sub">{project?.[0]?.program_name}</div>
  </div>
</div>

<!-- ── Summary ───────────────────────────────────────────────── -->

{#if project?.[0]?.project_summary}
<div class="section-card">
  <div class="section-title">Project Summary</div>
  <p class="summary-text">{project?.[0]?.project_summary}</p>
  {#if project?.[0]?.appropriation_code}
    <div class="approp-code">Appropriation code: <strong>{project?.[0]?.appropriation_code}</strong></div>
  {/if}
</div>
{/if}

<!-- ── Phase timeline ─────────────────────────────────────────── -->

<div class="section-card">
  <div class="section-title">Phase Timeline</div>
  <ProjectGantt data={project} />
</div>

<!-- ── Funding & Costs ───────────────────────────────────────── -->

<div class="section-card" style="margin-bottom:12px">
  <div class="section-title">Appropriation vs Spend</div>
  <div class="section-sub">Funding authorized vs actual and planned development costs</div>
  <AppropriationChart
    fundingTotal={funding_total}
    costsTotal={dev_costs_total}
  />
</div>

<div class="two-col">

  <div class="section-card">
    <div class="section-title">Funding by Source</div>
    <div class="section-sub">Appropriations by fiscal year</div>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Prior FY2025</th>
            <th>FY2025 Actual</th>
            <th>FY2026 Approp.</th>
            <th>FY2027 Allow.</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {#each funding as row}
            {#if row.row_type === 'header'}
              <tr class="section-row">
                <td colspan="6" class="section-label">{row.funding_type}</td>
              </tr>
            {:else}
              <tr class="sub-row">
                <td class="sub-label">{row.funding_type}</td>
                <td class="num">{row.prior_to_fy2025 ? '$' + (row.prior_to_fy2025/1e6).toFixed(1) + 'M' : '—'}</td>
                <td class="num">{row.actual_fy2025 ? '$' + (row.actual_fy2025/1e6).toFixed(1) + 'M' : '—'}</td>
                <td class="num">{row.appropriation_fy2026 ? '$' + (row.appropriation_fy2026/1e6).toFixed(1) + 'M' : '—'}</td>
                <td class="num">{row.allowance_fy2027 ? '$' + (row.allowance_fy2027/1e6).toFixed(1) + 'M' : '—'}</td>
                <td class="num total-col">{row.total_funding_to_date ? '$' + (row.total_funding_to_date/1e6).toFixed(1) + 'M' : '—'}</td>
              </tr>
            {/if}
          {/each}
          <tr class="grand-total-row">
            <td>Total</td>
            <td class="num">{funding_total?.[0]?.prior_to_fy2025 ? '$' + (funding_total[0].prior_to_fy2025/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num">{funding_total?.[0]?.actual_fy2025 ? '$' + (funding_total[0].actual_fy2025/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num">{funding_total?.[0]?.appropriation_fy2026 ? '$' + (funding_total[0].appropriation_fy2026/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num">{funding_total?.[0]?.allowance_fy2027 ? '$' + (funding_total[0].allowance_fy2027/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num total-col">{funding_total?.[0]?.total_funding_to_date ? '$' + (funding_total[0].total_funding_to_date/1e6).toFixed(1) + 'M' : '—'}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div class="section-card">
    <div class="section-title">Development Costs</div>
    <div class="section-sub">Actual spend vs. plan by fiscal year</div>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Prior FY2025</th>
            <th>FY2025 Actual</th>
            <th>FY2026 Plan</th>
            <th>FY2027 Plan</th>
            <th>Outyears</th>
          </tr>
        </thead>
        <tbody>
          {#each dev_costs as row}
          <tr>
            <td>{row.funding_type}</td>
            <td class="num">{row.prior_to_fy2025 ? '$' + (row.prior_to_fy2025/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num">{row.actual_fy2025 ? '$' + (row.actual_fy2025/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num">{row.spend_plan_fy2026 ? '$' + (row.spend_plan_fy2026/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num">{row.spend_plan_fy2027 ? '$' + (row.spend_plan_fy2027/1e6).toFixed(1) + 'M' : '—'}</td>
            <td class="num">{row.projected_outyears ? '$' + (row.projected_outyears/1e6).toFixed(1) + 'M' : '—'}</td>
          </tr>
          {/each}
          <tr class="total-row">
            <td>Total</td>
            <td class="num">${(dev_costs_total?.[0]?.prior_to_fy2025/1e6).toFixed(1)}M</td>
            <td class="num">${(dev_costs_total?.[0]?.actual_fy2025/1e6).toFixed(1)}M</td>
            <td class="num">${(dev_costs_total?.[0]?.spend_plan_fy2026/1e6).toFixed(1)}M</td>
            <td class="num">${(dev_costs_total?.[0]?.spend_plan_fy2027/1e6).toFixed(1)}M</td>
            <td class="num">${(dev_costs_total?.[0]?.projected_outyears/1e6).toFixed(1)}M</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

</div>



<style>
  /* Header */

  .meta-tag {
    font-size: 11px; padding: 3px 8px;
    background: var(--grey-100, #f0efea);
    border-radius: 4px; color: var(--grey-600, #555);
  }


  /* Phase badges */
  .phase-badge { font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: 500; }
  .phase-implementation { background: #E6F1FB; color: #0C447C; }
  .phase-procurement    { background: #EEEDFE; color: #3C3489; }
  .phase-o-m            { background: #EAF3DE; color: #27500A; }
  .phase-planning       { background: #FAEEDA; color: #633806; }
  .phase-closeout, .phase-closed { background: #F1EFE8; color: #444441; }
  .phase-not-started    { background: #FCEBEB; color: #791F1F; }

  /* KPIs */
  .kpi-row {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 10px; margin-bottom: 16px;
  }
  .kpi-card {
    background: var(--grey-50, #f7f6f3);
    border: 1px solid var(--grey-200, #e5e3dc);
    border-radius: 8px; padding: 14px 16px;
  }
  .kpi-val { font-size: 20px; font-weight: 600; color: var(--grey-900, #1a1a18); line-height: 1.2; }
  .kpi-lbl { font-size: 11px; color: var(--grey-500, #777); margin-top: 4px; }
  .kpi-sub {
    font-size: 10px; font-weight: 600;
    color: var(--grey-700, #333);
    margin-top: 3px; padding: 1px 5px;
    background: rgba(0,0,0,0.05);
    border-radius: 3px; display: inline-block;
  }

  /* Sections */
  .section-card {
    background: var(--grey-0, #fff);
    border: 1px solid var(--grey-200, #e5e3dc);
    border-radius: 10px; padding: 18px 20px;
    margin-bottom: 12px;
  }
  .section-title { font-size: 13px; font-weight: 600; color: var(--grey-800, #222); margin-bottom: 2px; }
  .section-sub   { font-size: 11px; color: var(--grey-400, #999); margin-bottom: 12px; }
  .summary-text  { font-size: 13px; color: var(--grey-700, #444); line-height: 1.6; }
  .approp-code   { font-size: 11px; color: var(--grey-400, #999); margin-top: 10px; }

  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

  /* Tables */
  .data-table-wrap { overflow-x: auto; margin-top: 14px; }
  .data-table { width: 100%; border-collapse: collapse; font-size: 11px; }
  .data-table th {
    text-align: left; font-weight: 500; font-size: 10px;
    color: var(--grey-400, #999); padding: 6px 8px;
    border-bottom: 1px solid var(--grey-100, #eee);
    white-space: nowrap;
  }
  .data-table td { padding: 6px 8px; border-bottom: 0.5px solid var(--grey-100, #f0f0f0); color: var(--grey-700, #444); }
  .data-table tr:hover td { background: var(--grey-50, #fafaf8); }
  .data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
  .data-table .total-col { font-weight: 600; color: var(--grey-800, #222); }
  .total-row td { font-weight: 600; border-top: 1px solid var(--grey-200, #e0e0e0); border-bottom: none; color: var(--grey-800, #222); }
  .grand-total-row td {
    font-weight: 700;
    border-top: 2px solid var(--grey-400, #888);
    border-bottom: none;
    color: var(--grey-900, #111);
    background: var(--grey-50, #f7f6f3);
    padding-top: 8px;
    padding-bottom: 8px;
  }
  .section-row td { background: var(--grey-100, #f0efea); font-weight: 600; font-size: 11px; color: var(--grey-700, #333); padding: 5px 10px; border-bottom: none; }
  .section-label { text-transform: uppercase; letter-spacing: 0.04em; font-size: 10px; }
  .sub-row td { padding-left: 18px; }
  .sub-label { color: var(--grey-600, #555); }

</style>