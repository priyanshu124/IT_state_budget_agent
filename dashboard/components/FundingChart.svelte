<script>
  export let data = [];
  export let type = 'funding'; // 'funding' | 'costs'

  function norm(rows) {
    return Array.from(rows || []).map(r => {
      const o = { ...r };
      for (const k of Object.keys(o)) {
        if (k !== 'funding_type') o[k] = Number(o[k]) || 0;
      }
      return o;
    });
  }

  $: rows = norm(data).filter(r => r.funding_type !== 'Total');

  $: cols = type === 'funding'
    ? [
        { key: 'prior_to_fy2025',       label: 'Prior FY25', color: '#7F77DD' },
        { key: 'actual_fy2025',          label: 'FY25 Actual', color: '#378ADD' },
        { key: 'appropriation_fy2026',   label: 'FY26 Approp', color: '#1D9E75' },
        { key: 'allowance_fy2027',       label: 'FY27 Allow', color: '#BA7517' },
      ]
    : [
        { key: 'prior_to_fy2025',        label: 'Prior FY25', color: '#7F77DD' },
        { key: 'actual_fy2025',          label: 'FY25 Actual', color: '#378ADD' },
        { key: 'spend_plan_fy2026',      label: 'FY26 Plan', color: '#1D9E75' },
        { key: 'spend_plan_fy2027',      label: 'FY27 Plan', color: '#BA7517' },
        { key: 'projected_outyears',     label: 'Outyears', color: '#888780' },
      ];

  // Max value across all rows and columns for scaling
  $: maxVal = Math.max(
    ...rows.flatMap(r => cols.map(c => r[c.key] || 0)),
    1
  );

  function fmtM(v) {
    if (!v || v === 0) return '—';
    if (v >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
    if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
    return '$' + (v / 1e3).toFixed(0) + 'K';
  }

  let hovered = null;
</script>

{#if rows.length > 0}
<div class="chart-wrap">

  <!-- Legend -->
  <div class="legend">
    {#each cols as col}
      <span class="leg-item">
        <span class="leg-dot" style="background:{col.color}"></span>
        {col.label}
      </span>
    {/each}
  </div>

  <!-- Grouped bars per funding source -->
  <div class="bar-groups">
    {#each rows as row, ri}
      <div class="bar-group"
           on:mouseenter={() => hovered = ri}
           on:mouseleave={() => hovered = null}>
        <div class="group-label">{row.funding_type}</div>
        <div class="bars">
          {#each cols as col}
            {@const val = row[col.key] || 0}
            {@const w = (val / maxVal) * 100}
            <div class="bar-row">
              <div class="bar-track">
                <div class="bar-fill"
                     style="width:{w}%; background:{col.color}; opacity:{hovered === ri ? 0.75 : 1}">
                </div>
              </div>
              <div class="bar-val">{fmtM(val)}</div>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>

</div>
{:else}
  <div class="empty">No data available</div>
{/if}

<style>
  .chart-wrap { margin-bottom: 4px; }
  .empty { font-size: 12px; color: var(--grey-400, #aaa); padding: 8px 0; }

  .legend { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .leg-item { display: flex; align-items: center; gap: 5px; font-size: 10px; color: var(--grey-500, #777); }
  .leg-dot  { width: 8px; height: 8px; border-radius: 2px; }

  .bar-groups { display: flex; flex-direction: column; gap: 10px; }
  .bar-group { cursor: default; }
  .group-label {
    font-size: 11px; font-weight: 500;
    color: var(--grey-600, #555);
    margin-bottom: 4px;
  }
  .bars { display: flex; flex-direction: column; gap: 2px; }
  .bar-row { display: grid; grid-template-columns: 1fr 56px; align-items: center; gap: 6px; }
  .bar-track {
    height: 10px; background: var(--grey-100, #f0f0f0);
    border-radius: 3px; overflow: hidden;
  }
  .bar-fill { height: 100%; border-radius: 3px; transition: opacity 0.1s; min-width: 2px; }
  .bar-val  { font-size: 10px; font-variant-numeric: tabular-nums; color: var(--grey-500, #777); text-align: right; }
</style>
