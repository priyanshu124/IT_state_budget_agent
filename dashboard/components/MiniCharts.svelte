<script>
  export let phaseData    = [];
  export let agencyCosts  = [];  // [{agency, total_eac, remaining_eac, project_count}]
  export let activeByYear = [];  // [{year, active_projects}]

  const PHASE_COLOR = {
    'Implementation': '#378ADD',
    'Procurement':    '#7F77DD',
    'O&M':            '#639922',
    'Planning':       '#BA7517',
    'Closeout':       '#888780',
    'Closed':         '#888780',
    'Not started':    '#E24B4A',
  };

  // Stacked order bottom → top: impl, proc, om, plan, other
  const STACK = [
    { key: 'impl',  color: '#378ADD', label: 'Implementation' },
    { key: 'proc',  color: '#7F77DD', label: 'Procurement'    },
    { key: 'om',    color: '#639922', label: 'O&M'            },
    { key: 'plan',  color: '#BA7517', label: 'Planning'       },
    { key: 'other', color: '#888780', label: 'Other'          },
  ];

  function norm(data, ...numKeys) {
    return Array.from(data || []).map(row => {
      const r = { ...row };
      for (const k of numKeys) r[k] = Number(r[k]) || 0;
      return r;
    });
  }

  $: phases   = norm(phaseData,    'count');
  $: agencies = norm(agencyCosts,  'total_eac', 'remaining_eac', 'project_count');
  $: active   = norm(activeByYear, 'active_projects', 'year', 'impl', 'proc', 'om', 'plan', 'other');

  $: agencyMax  = Math.max(...agencies.map(d => d.total_eac), 1);
  $: activeMax  = Math.max(...active.map(d => d.active_projects), 1);

  $: donutSlices = buildDonut(phases);
  function buildDonut(data) {
    const total = data.reduce((s, d) => s + d.count, 0);
    if (!total) return [];
    const cx = 80, cy = 80, r = 64, ir = 38;
    const slices = [];
    let angle = -Math.PI / 2;
    for (const d of data) {
      const sweep = (d.count / total) * 2 * Math.PI;
      if (sweep === 0) continue;
      const c0 = [Math.cos(angle), Math.sin(angle)];
      const c1 = [Math.cos(angle + sweep), Math.sin(angle + sweep)];
      const large = sweep > Math.PI ? 1 : 0;
      slices.push({
        path: `M ${cx+r*c0[0]} ${cy+r*c0[1]} A ${r} ${r} 0 ${large} 1 ${cx+r*c1[0]} ${cy+r*c1[1]} L ${cx+ir*c1[0]} ${cy+ir*c1[1]} A ${ir} ${ir} 0 ${large} 0 ${cx+ir*c0[0]} ${cy+ir*c0[1]} Z`,
        color: PHASE_COLOR[d.phase] || '#ccc',
        label: d.phase, count: d.count,
        pct: Math.round(d.count / total * 100),
      });
      angle += sweep;
    }
    return slices;
  }

  function shortAgency(name) {
    return (name || '')
      .replace('Maryland Department of Health', 'MD Dept. Health')
      .replace('Maryland State Board of Elections', 'MD Board of Elections')
      .replace('Department of Information Technology', 'Dept. of IT')
      .replace('Department of General Services', 'Dept. General Services')
      .replace('Department of the Environment', 'Dept. Environment')
      .replace('Department of Education', 'Dept. Education')
      .replace('Maryland Higher Education Commission', 'MD Higher Ed Commission')
      .replace('Department of Assessments and Taxation', 'Dept. Assessments & Tax')
      .replace('Department of Labor', 'Dept. Labor')
      .replace('Comptroller of Maryland', 'Comptroller');
  }

  // Active by year SVG
  const AW = 400, AH = 160, APT = 16, APB = 28, APL = 28, APR = 8;
  $: aBarArea = AH - APT - APB;
  $: aBarW    = active.length > 0 ? Math.max(1, (AW - APL - APR) / active.length - 1) : 10;
  $: aTicks   = (() => {
    const step = activeMax > 40 ? 20 : activeMax > 20 ? 10 : 5;
    const ticks = [];
    for (let v = 0; v <= activeMax; v += step) ticks.push(v);
    return ticks;
  })();

  let hoveredSlice  = null;
  let hoveredAgency = null;
  let hoveredActive = null;
</script>

<div class="grid-2x2">

  <!-- Phase donut -->
  <div class="chart-card">
    <div class="chart-title">Projects by Phase</div>
    {#if donutSlices.length > 0}
      <div class="donut-wrap">
        <svg viewBox="0 0 160 160" width="160" height="160">
          {#each donutSlices as slice, i}
            <path d={slice.path} fill={slice.color}
                  opacity={hoveredSlice === i ? 0.75 : 1}
                  stroke="#fff" stroke-width="1.5"
                  on:mouseenter={() => hoveredSlice = i}
                  on:mouseleave={() => hoveredSlice = null}
                  style="cursor:pointer" />
          {/each}
          {#if hoveredSlice !== null}
            <text x="80" y="76"  text-anchor="middle" class="dc-val">{donutSlices[hoveredSlice].count}</text>
            <text x="80" y="91"  text-anchor="middle" class="dc-lbl">{donutSlices[hoveredSlice].pct}%</text>
          {:else}
            <text x="80" y="76"  text-anchor="middle" class="dc-val">{phases.reduce((s,d)=>s+d.count,0)}</text>
            <text x="80" y="91"  text-anchor="middle" class="dc-lbl">PROJECTS</text>
          {/if}
        </svg>
        <div class="donut-legend">
          {#each donutSlices as slice, i}
            <div class="dl-item"
                 on:mouseenter={() => hoveredSlice = i}
                 on:mouseleave={() => hoveredSlice = null}>
              <span class="dl-dot" style="background:{slice.color}"></span>
              <span class="dl-label">{slice.label}</span>
              <span class="dl-count">{slice.count}</span>
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <div class="empty">No data</div>
    {/if}
  </div>

  <!-- Active projects by year -->
  <div class="chart-card">
    <div class="chart-title">Active Projects by Year</div>
    <div class="chart-sub">Simultaneous project load across the portfolio</div>
    {#if active.length > 0}
      <svg viewBox="0 0 {AW} {AH}" class="full-svg">
        {#each aTicks as tick}
          {@const ty = APT + aBarArea - (tick / activeMax) * aBarArea}
          <line x1={APL} y1={ty} x2={AW-APR} y2={ty} stroke="#eee" stroke-width="1"/>
          <text x={APL-3} y={ty+3} text-anchor="end" font-size="8" fill="#bbb">{tick}</text>
        {/each}

        {#each active as row, i}
          {@const x     = APL + i * ((AW - APL - APR) / active.length)}
          {@const total = row.active_projects}
          {@const isTdy = row.year === 2026}

          <!-- Today marker line (behind bars) -->
          {#if isTdy}
            <line x1={x + aBarW/2} y1={APT} x2={x + aBarW/2} y2={AH-APB}
                  stroke="#E24B4A" stroke-width="1.5" stroke-dasharray="3 2"/>
          {/if}

          <!-- Stacked phase segments bottom → top -->
          {#each (() => {
            const segs = [];
            let cumY = APT + aBarArea;
            for (const s of STACK) {
              const cnt = row[s.key] || 0;
              if (cnt === 0) continue;
              const h = (cnt / activeMax) * aBarArea;
              cumY -= h;
              segs.push({ ...s, cnt, h, y: cumY });
            }
            return segs;
          })() as seg}
            <rect
              x={x} y={seg.y} width={aBarW} height={seg.h}
              fill={seg.color}
              opacity={hoveredActive === i ? 0.75 : 0.9}
              on:mouseenter={() => hoveredActive = i}
              on:mouseleave={() => hoveredActive = null}
              style="cursor:pointer"
            />
          {/each}

          <!-- Hover tooltip -->
          {#if hoveredActive === i && total > 0}
            {@const tipW = 108}
            {@const tipH = STACK.filter(s => row[s.key] > 0).length * 13 + 20}
            {@const tipX = Math.min(x, AW - tipW - 4)}
            {@const topY = APT + aBarArea - (total / activeMax) * aBarArea}
            <rect x={tipX} y={topY - tipH - 4} width={tipW} height={tipH}
                  rx="4" fill="#1a1a18" opacity="0.9"/>
            <text x={tipX + tipW/2} y={topY - tipH + 10}
                  text-anchor="middle" font-size="9" fill="white" font-weight="600">
              {row.year}: {total} active
            </text>
            {#each STACK.filter(s => row[s.key] > 0) as s, si}
              <rect x={tipX + 6} y={topY - tipH + 16 + si*13} width={7} height={7} rx="1" fill={s.color}/>
              <text x={tipX + 16} y={topY - tipH + 23 + si*13}
                    font-size="8" fill="#ddd">{s.label}: {row[s.key]}</text>
            {/each}
          {/if}

          <!-- Year label every 2 years -->
          {#if i % 2 === 0}
            <text x={x + aBarW/2} y={AH - APB + 11}
                  text-anchor="middle" font-size="8" fill="#aaa">{row.year}</text>
          {/if}
        {/each}
      </svg>
      <div class="active-meta">
        <div class="stack-legend">
          {#each STACK as s}
            <span class="sl-item">
              <span class="sl-dot" style="background:{s.color}"></span>{s.label}
            </span>
          {/each}
        </div>
        <span style="color:#E24B4A; font-size:10px; white-space:nowrap">▌ 2026</span>
      </div>
    {:else}
      <div class="empty">No data</div>
    {/if}
  </div>

  <!-- Combined agency cost chart: total + remaining grouped -->
  <div class="chart-card chart-wide">
    <div class="chart-title">Cost by Agency ($M) — Total vs. Remaining</div>
    <div class="chart-sub">
      <span class="leg-inline" style="background:#7F77DD"></span> Total EAC &nbsp;
      <span class="leg-inline" style="background:#E24B4A"></span> Remaining
    </div>
    {#if agencies.length > 0}
      <div class="grouped-chart">
        {#each agencies as row, i}
          {@const totalW    = agencyMax > 0 ? (row.total_eac     / agencyMax) * 100 : 0}
          {@const remainW   = agencyMax > 0 ? (row.remaining_eac / agencyMax) * 100 : 0}
          {@const spent     = row.total_eac - row.remaining_eac}
          {@const spentPct  = row.total_eac > 0 ? Math.round(spent / row.total_eac * 100) : 0}
          <div class="grouped-row"
               on:mouseenter={() => hoveredAgency = i}
               on:mouseleave={() => hoveredAgency = null}>
            <div class="grouped-lbl" title={row.agency}>{shortAgency(row.agency)}</div>
            <div class="grouped-bars">
              <!-- Total bar -->
              <div class="gbar-wrap">
                <div class="gbar" style="width:{totalW}%; background:#7F77DD; opacity:{hoveredAgency===i ? 0.75:1}">
                  {#if hoveredAgency === i}
                    <span class="gbar-tip">${row.total_eac}M total</span>
                  {/if}
                </div>
              </div>
              <!-- Remaining bar -->
              <div class="gbar-wrap">
                <div class="gbar" style="width:{remainW}%; background:#E24B4A; opacity:{hoveredAgency===i ? 0.75:1}">
                  {#if hoveredAgency === i}
                    <span class="gbar-tip">${row.remaining_eac}M remaining</span>
                  {/if}
                </div>
              </div>
            </div>
            <div class="grouped-vals">
              <span class="gv-total">${row.total_eac}M</span>
              <span class="gv-remain">${row.remaining_eac}M</span>
            </div>
            <!-- Spent % badge on hover -->
            {#if hoveredAgency === i}
              <div class="spent-badge">{spentPct}% spent</div>
            {/if}
          </div>
        {/each}
      </div>
    {:else}
      <div class="empty">No data</div>
    {/if}
  </div>

</div>

<style>
  .grid-2x2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin: 16px 0 24px;
  }
  /* wide card spans both columns */
  .chart-wide { grid-column: 1 / -1; }

  .chart-card {
    background: var(--grey-0, #fff);
    border: 1px solid var(--grey-200, #e5e3dc);
    border-radius: 10px;
    padding: 16px 18px;
    min-width: 0;
  }
  .chart-title {
    font-size: 12px; font-weight: 600;
    color: var(--grey-700, #333); margin-bottom: 2px;
  }
  .chart-sub {
    font-size: 11px; color: var(--grey-400, #999); margin-bottom: 12px;
    display: flex; align-items: center; gap: 4px;
  }
  .leg-inline {
    display: inline-block; width: 10px; height: 10px;
    border-radius: 2px; vertical-align: middle;
  }
  .empty { font-size: 12px; color: var(--grey-400, #aaa); padding: 20px 0; text-align: center; }

  /* Donut */
  .donut-wrap { display: flex; align-items: center; gap: 14px; }
  .donut-legend { display: flex; flex-direction: column; gap: 5px; }
  .dl-item {
    display: flex; align-items: center; gap: 6px; font-size: 11px;
    cursor: default; padding: 1px 4px; border-radius: 4px; transition: background 0.1s;
  }
  .dl-item:hover { background: var(--grey-50, #f5f5f5); }
  .dl-dot   { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }
  .dl-label { color: var(--grey-600, #555); flex: 1; white-space: nowrap; }
  .dl-count { color: var(--grey-800, #222); font-weight: 600; min-width: 20px; text-align: right; }
  .dc-val   { font-size: 20px; font-weight: 600; fill: var(--grey-800, #222); }
  .dc-lbl   { font-size: 8px; fill: var(--grey-400, #999); text-transform: uppercase; letter-spacing: 0.06em; }

  /* Active by year */
  .full-svg { display: block; width: 100%; overflow: visible; }
  .active-meta {
    display: flex; justify-content: space-between;
    font-size: 10px; color: var(--grey-400, #999); margin-top: 4px;
  }
  .active-meta strong { color: var(--grey-700, #444); }

  /* Grouped agency chart */
  .grouped-chart { display: flex; flex-direction: column; gap: 10px; }
  .grouped-row {
    display: grid;
    grid-template-columns: 160px 1fr 100px;
    align-items: center; gap: 10px;
    cursor: default; position: relative;
    padding: 2px 0;
  }
  .grouped-lbl {
    font-size: 11px; color: var(--grey-600, #555);
    text-align: right; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }
  .grouped-bars { display: flex; flex-direction: column; gap: 3px; }
  .gbar-wrap {
    height: 11px; background: var(--grey-100, #f0f0f0);
    border-radius: 3px; overflow: visible; position: relative;
  }
  .gbar {
    height: 100%; border-radius: 3px;
    transition: opacity 0.1s; position: relative;
    display: flex; align-items: center;
    min-width: 3px;
  }
  .gbar-tip {
    position: absolute; left: calc(100% + 6px);
    font-size: 10px; color: var(--grey-600, #555);
    white-space: nowrap; pointer-events: none;
  }
  .grouped-vals {
    display: flex; flex-direction: column; gap: 3px;
  }
  .gv-total  { font-size: 11px; font-weight: 600; color: #7F77DD; }
  .gv-remain { font-size: 11px; font-weight: 600; color: #E24B4A; }
  .spent-badge {
    position: absolute; right: -68px; top: 50%; transform: translateY(-50%);
    font-size: 10px; color: var(--grey-400, #999);
    background: var(--grey-50, #f5f5f5);
    border: 1px solid var(--grey-200, #e0e0e0);
    border-radius: 4px; padding: 1px 6px;
    white-space: nowrap;
  }
</style>