<script>
  import { goto } from '$app/navigation';
  export let data = [];

  // ── Constants ──────────────────────────────────────────────────────────────
  const LABEL_WIDTH   = 280;  // px, fixed left column
  const ROW_H         = 30;
  const GROUP_H       = 32;
  const HEADER_H      = 44;
  const TODAY         = new Date();

  const PHASE_COLOR = {
    'Procurement':    '#7F77DD',
    'Implementation': '#378ADD',
    'O&M':            '#639922',
  };
  const PHASE_OPACITY = { 'Procurement': 1, 'Implementation': 1, 'O&M': 0.75 };
  const PHASE_ORDER   = ['Procurement', 'Implementation', 'O&M'];

  // ── Collapse state ─────────────────────────────────────────────────────────
  let collapsed = new Set();
  function toggle(agency) {
    const next = new Set(collapsed);
    next.has(agency) ? next.delete(agency) : next.add(agency);
    collapsed = next;
  }
  function collapseAll() { collapsed = new Set(agencies.map(a => a.name)); }
  function expandAll()   { collapsed = new Set(); }

  // ── Filters ────────────────────────────────────────────────────────────────
  let filterPhase  = '';
  let filterAgency = '';

  // ── Derived data ───────────────────────────────────────────────────────────
  $: projects  = buildProjects(data);
  $: agencies  = buildAgencies(projects, filterPhase, filterAgency);
  $: minDate   = getMin(projects);
  $: maxDate   = getMax(projects);
  $: totalMs   = Math.max(maxDate - minDate, 1);
  $: todayPct  = clamp((TODAY - minDate) / totalMs * 100, 0, 100);
  $: yearTicks = buildYearTicks(minDate, maxDate);
  $: allAgencies = [...new Set((buildProjects(data)).map(p => p.agency))].sort();

  $: svgHeight = (() => {
    let h = HEADER_H;
    for (const ag of agencies) {
      h += GROUP_H;
      if (!collapsed.has(ag.name)) h += ag.projects.length * ROW_H;
    }
    return h + 2;
  })();

  function buildProjects(rows) {
    const map = new Map();
    for (const r of rows) {
      if (!map.has(r.mitdp_id)) {
        map.set(r.mitdp_id, {
          mitdp_id:        r.mitdp_id,
          project_title:   r.project_title,
          agency:          r.agency,
          current_phase:   r.current_phase,
          eac_label:       r.eac_label,
          remaining_label: r.remaining_label,
          time_remaining:  r.time_remaining,
          eac_midpoint:    r.eac_midpoint ?? null,
          phases: [],
        });
      }
      const p = map.get(r.mitdp_id);
      if (r.phase_start && r.phase_end) {
        p.phases.push({
          name:  r.phase_name,
          start: new Date(r.phase_start),
          end:   new Date(r.phase_end),
        });
      }
    }
    for (const p of map.values()) {
      p.phases.sort((a, b) => PHASE_ORDER.indexOf(a.name) - PHASE_ORDER.indexOf(b.name));
    }
    return [...map.values()];
  }

  function buildAgencies(projects, ph, ag) {
    const filtered = projects.filter(p =>
      (!ph || p.current_phase === ph) &&
      (!ag || p.agency === ag)
    );
    const map = new Map();
    for (const p of filtered) {
      if (!map.has(p.agency)) map.set(p.agency, { name: p.agency, eac: 0, projects: [] });
      const a = map.get(p.agency);
      if (p.eac_midpoint != null) a.eac += p.eac_midpoint;
      a.projects.push(p);
    }
    const result = [...map.values()].sort((a, b) => b.eac - a.eac);
    for (const a of result) {
      a.projects.sort((x, y) => {
        if (x.eac_midpoint == null && y.eac_midpoint == null) return 0;
        if (x.eac_midpoint == null) return 1;
        if (y.eac_midpoint == null) return -1;
        return y.eac_midpoint - x.eac_midpoint;
      });
    }
    return result;
  }

  function getMin(projects) {
    let m = TODAY;
    for (const p of projects)
      for (const ph of p.phases)
        if (ph.start < m) m = ph.start;
    return m;
  }
  function getMax(projects) {
    let m = new Date(0);
    for (const p of projects)
      for (const ph of p.phases)
        if (ph.end > m) m = ph.end;
    return m;
  }

  function buildYearTicks(min, max) {
    const ticks = [];
    for (let y = min.getFullYear(); y <= max.getFullYear() + 1; y++) {
      ticks.push({ year: y, pct: clamp((new Date(y, 0, 1) - min) / totalMs * 100, 0, 100) });
    }
    return ticks;
  }

  // Convert a date to % position in the track area
  // Track area starts at LABEL_WIDTH px; we express positions as % of full SVG width
  // but since SVG width is 100%, we need to offset by LABEL_WIDTH and scale remaining width
  // We use a CSS calc trick via foreignObject — instead just work in a virtual 1000px wide canvas
  // and let the SVG viewBox handle it. Simpler: express as "% of track" and set x with calc.
  function datePct(d) {
    return clamp((new Date(d) - minDate) / totalMs * 100, 0, 100);
  }

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function fmtDate(d) {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  }

  // ── Tooltip ────────────────────────────────────────────────────────────────
  let tooltip    = null;
  let tipX = 0, tipY = 0;

  function showTip(e, project, phase) {
    tooltip = { project, phase };
    tipX = e.clientX + 14;
    tipY = e.clientY + 14;
  }
  function moveTip(e) {
    if (!tooltip) return;
    tipX = e.clientX + 14;
    tipY = e.clientY + 14;
  }
  function hideTip() { tooltip = null; }

  // ── Compute row Y positions reactively ────────────────────────────────────
  function getRowY(agencyIdx, projectIdx) {
    let y = HEADER_H;
    for (let i = 0; i < agencyIdx; i++) {
      y += GROUP_H;
      if (!collapsed.has(agencies[i].name)) y += agencies[i].projects.length * ROW_H;
    }
    y += GROUP_H; // this agency's header
    y += projectIdx * ROW_H;
    return y;
  }

  function getGroupY(agencyIdx) {
    let y = HEADER_H;
    for (let i = 0; i < agencyIdx; i++) {
      y += GROUP_H;
      if (!collapsed.has(agencies[i].name)) y += agencies[i].projects.length * ROW_H;
    }
    return y;
  }
</script>

<svelte:window on:mousemove={moveTip} />

<!-- Controls -->
<div class="controls">
  <div class="legend">
    {#each Object.entries(PHASE_COLOR) as [name, color]}
      <span class="leg"><span class="leg-dot" style="background:{color}"></span>{name}</span>
    {/each}
    <span class="leg"><span class="leg-dot today-marker"></span>Today</span>
  </div>
  <div class="ctrl-right">
    <select bind:value={filterAgency}>
      <option value="">All agencies</option>
      {#each allAgencies as a}<option value={a}>{a}</option>{/each}
    </select>
    <select bind:value={filterPhase}>
      <option value="">All phases</option>
      {#each ['Implementation','Procurement','O&M','Planning','Not started','Closeout','Closed'] as ph}
        <option value={ph}>{ph}</option>
      {/each}
    </select>
    <button class="btn" on:click={expandAll}>Expand all</button>
    <button class="btn" on:click={collapseAll}>Collapse all</button>
  </div>
</div>

<!-- Gantt -->
<div class="gantt-outer">
  <div class="gantt-scroll">
    <div class="gantt-container" style="min-width: 900px;">

      <!-- Fixed label column header -->
      <div class="gantt-head">
        <div class="head-label">Project</div>
        <div class="head-track">
          <!-- Year labels -->
          {#each yearTicks as tick}
            <div class="yr-label" style="left: {tick.pct}%">{tick.year}</div>
            <div class="yr-line {tick.year === TODAY.getFullYear() + (TODAY.getMonth() >= 0 ? 0 : -1) ? '' : ''}"
                 style="left: {tick.pct}%"></div>
          {/each}
          <!-- Today marker -->
          <div class="today-line" style="left: {todayPct}%">
            <div class="today-label">Today</div>
          </div>
        </div>
      </div>

      <!-- Body -->
      {#each agencies as ag, ai}
        <!-- Agency group row -->
        <div class="group-row" on:click={() => toggle(ag.name)} role="button" tabindex="0"
             on:keydown={e => e.key === 'Enter' && toggle(ag.name)}>
          <div class="group-label">
            <span class="chevron" class:closed={collapsed.has(ag.name)}>▾</span>
            <span class="group-name">{ag.name}</span>
            <span class="group-meta">{ag.projects.length} projects · ${ag.eac.toLocaleString()}M</span>
          </div>
          <div class="group-track">
            <!-- Year grid lines in group row -->
            {#each yearTicks as tick}
              <div class="yr-line" style="left: {tick.pct}%"></div>
            {/each}
            <div class="today-line" style="left: {todayPct}%"></div>
          </div>
        </div>

        <!-- Project rows -->
        {#if !collapsed.has(ag.name)}
          {#each ag.projects as project, pi}
            <div class="proj-row" class:row-alt={pi % 2 === 1}
                 on:click={() => goto(`/it-projects/project-details/${project.mitdp_id}`)}
                 role="button" tabindex="0"
                 on:keydown={e => e.key === 'Enter' && goto(`/it-projects/project-details/${project.mitdp_id}`)}>
              <div class="proj-label">
                <div class="proj-title" title={project.project_title}>
                  {project.project_title.length > 36
                    ? project.project_title.slice(0, 34) + '…'
                    : project.project_title}
                </div>
                <div class="proj-id">{project.mitdp_id}</div>
              </div>
              <div class="proj-track">
                <!-- Year grid lines -->
                {#each yearTicks as tick}
                  <div class="yr-line" style="left: {tick.pct}%"></div>
                {/each}
                <!-- Today line -->
                <div class="today-line" style="left: {todayPct}%"></div>
                <!-- Phase bars -->
                {#each project.phases as phase}
                  {@const left  = datePct(phase.start)}
                  {@const width = Math.max(datePct(phase.end) - left, 0.3)}
                  <div
                    class="phase-bar"
                    style="
                      left: {left}%;
                      width: {width}%;
                      background: {PHASE_COLOR[phase.name] || '#aaa'};
                      opacity: {PHASE_OPACITY[phase.name] ?? 1};
                    "
                    on:mouseenter={e => showTip(e, project, phase)}
                    on:mouseleave={hideTip}
                    role="img"
                    aria-label="{project.project_title} — {phase.name}"
                  >
                    <span class="bar-label">{fmtDate(phase.start)} – {fmtDate(phase.end)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
        {/if}
      {/each}

    </div>
  </div>
</div>

<!-- Tooltip -->
{#if tooltip}
  <div class="tooltip" style="left: {tipX}px; top: {tipY}px">
    <div class="tt-title">{tooltip.project.project_title}</div>
    <div class="tt-id">{tooltip.project.mitdp_id}</div>
    <div class="tt-body">
      <div class="tt-row"><span>Agency</span><span>{tooltip.project.agency}</span></div>
      <div class="tt-row"><span>Current phase</span><span>{tooltip.project.current_phase}</span></div>
      <div class="tt-row">
        <span>Phase</span>
        <span style="color:{PHASE_COLOR[tooltip.phase.name]};font-weight:600">{tooltip.phase.name}</span>
      </div>
      <div class="tt-row"><span>Start</span><span>{fmtDate(tooltip.phase.start)}</span></div>
      <div class="tt-row"><span>End</span><span>{fmtDate(tooltip.phase.end)}</span></div>
      <div class="tt-row tt-sep"><span>Total cost</span><span>{tooltip.project.eac_label}</span></div>
      <div class="tt-row"><span>Remaining</span><span>{tooltip.project.remaining_label}</span></div>
      <div class="tt-row"><span>Time left</span><span>{tooltip.project.time_remaining}</span></div>
    </div>
  </div>
{/if}

<style>
  /* ── Controls ── */
  .controls {
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 10px; padding: 10px 0 12px;
  }
  .legend { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
  .leg { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--grey-600, #555); }
  .leg-dot { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
  .today-marker { background: #E24B4A; border-radius: 50%; }
  .ctrl-right { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  select {
    font-size: 12px; padding: 5px 8px; border-radius: 6px;
    border: 1px solid var(--grey-300, #ccc);
    background: var(--grey-50, #f9f9f9);
    color: var(--grey-800, #222); cursor: pointer;
  }
  .btn {
    font-size: 11px; padding: 5px 10px; border-radius: 6px; cursor: pointer;
    border: 1px solid var(--grey-300, #ccc);
    background: var(--grey-50, #fff);
    color: var(--grey-700, #333);
  }
  .btn:hover { background: var(--grey-100, #f0f0f0); }

  /* ── Outer wrapper ── */
  .gantt-outer {
    border: 1px solid var(--grey-200, #e0e0e0);
    border-radius: 8px;
    overflow: hidden;
  }
  .gantt-scroll {
    overflow-x: auto;
    overflow-y: auto;
    max-height: 75vh;
  }
  .gantt-container { display: flex; flex-direction: column; }

  /* ── Header ── */
  .gantt-head {
    display: flex;
    position: sticky; top: 0; z-index: 20;
    background: var(--grey-50, #f9f9f8);
    border-bottom: 1px solid var(--grey-200, #e0e0e0);
    min-height: 44px;
  }
  .head-label {
    width: 280px; min-width: 280px;
    padding: 0 12px;
    font-size: 10px; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase;
    color: var(--grey-400, #999);
    border-right: 1px solid var(--grey-200, #e0e0e0);
    display: flex; align-items: center;
    position: sticky; left: 0; background: inherit; z-index: 21;
  }
  .head-track {
    flex: 1; position: relative; overflow: hidden;
  }
  .yr-label {
    position: absolute; bottom: 6px;
    font-size: 10px; font-weight: 500;
    color: var(--grey-400, #aaa);
    transform: translateX(-50%);
    white-space: nowrap; pointer-events: none;
  }

  /* ── Grid lines ── */
  .yr-line {
    position: absolute; top: 0; bottom: 0; width: 0;
    border-left: 1px solid var(--grey-100, #eee);
    pointer-events: none;
  }
  .today-line {
    position: absolute; top: 0; bottom: 0; width: 0;
    border-left: 2px dashed #E24B4A;
    pointer-events: none; z-index: 2;
  }
  .today-label {
    position: absolute; top: 2px; left: 4px;
    font-size: 9px; font-weight: 600; color: #E24B4A;
    white-space: nowrap;
  }

  /* ── Group rows ── */
  .group-row {
    display: flex; align-items: stretch;
    min-height: 32px;
    background: var(--grey-100, #f3f2ef);
    border-bottom: 1px solid var(--grey-200, #e0e0e0);
    cursor: pointer; user-select: none;
  }
  .group-row:hover { background: var(--grey-150, #ebe9e4); }
  .group-label {
    width: 280px; min-width: 280px;
    padding: 0 10px;
    display: flex; align-items: center; gap: 6px;
    border-right: 1px solid var(--grey-200, #e0e0e0);
    position: sticky; left: 0; background: inherit; z-index: 10;
  }
  .chevron {
    font-size: 10px; color: var(--grey-400, #999);
    transition: transform 0.15s; display: inline-block;
  }
  .chevron.closed { transform: rotate(-90deg); }
  .group-name { font-size: 11px; font-weight: 600; color: var(--grey-800, #222); }
  .group-meta { font-size: 10px; color: var(--grey-400, #999); margin-left: 2px; }
  .group-track { flex: 1; position: relative; }

  /* ── Project rows ── */
  .proj-row {
    display: flex; align-items: stretch;
    min-height: 30px;
    background: var(--grey-0, #fff);
    border-bottom: 1px solid var(--grey-100, #f0f0f0);
    transition: background 0.08s;
    cursor: pointer;
  }
  .proj-row:hover { background: #EFF6FF; }
  .proj-row:hover .proj-title { color: #378ADD; text-decoration: underline; }
  .proj-row.row-alt { background: var(--grey-25, #fcfcfb); }
  .proj-label {
    width: 280px; min-width: 280px;
    padding: 4px 10px 4px 20px;
    display: flex; flex-direction: column; justify-content: center;
    border-right: 1px solid var(--grey-100, #eee);
    position: sticky; left: 0; background: inherit; z-index: 10;
  }
  .proj-title {
    font-size: 11px; font-weight: 500;
    color: var(--grey-800, #222);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 250px;
  }
  .proj-id {
    font-size: 9px; color: var(--grey-400, #aaa);
    margin-top: 1px;
  }
  .proj-track { flex: 1; position: relative; }

  /* ── Phase bars ── */
  .phase-bar {
    position: absolute;
    top: 50%; transform: translateY(-50%);
    height: 16px; border-radius: 3px;
    cursor: pointer; overflow: hidden;
    display: flex; align-items: center;
    transition: filter 0.12s;
    min-width: 3px;
  }
  .phase-bar:hover { filter: brightness(1.15); }
  .bar-label {
    font-size: 8px; color: #fff; padding: 0 4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    font-weight: 500; letter-spacing: 0.01em;
  }

  /* ── Tooltip ── */
  .tooltip {
    position: fixed; z-index: 9999;
    background: var(--grey-0, #fff);
    border: 1px solid var(--grey-200, #ddd);
    border-radius: 8px; padding: 12px 14px;
    font-size: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.12);
    max-width: 300px; pointer-events: none;
  }
  .tt-title { font-weight: 600; font-size: 13px; color: var(--grey-900, #111); margin-bottom: 2px; line-height: 1.3; }
  .tt-id    { font-size: 10px; color: var(--grey-400, #999); margin-bottom: 8px; }
  .tt-body  { display: flex; flex-direction: column; gap: 3px; }
  .tt-row   { display: flex; justify-content: space-between; gap: 12px; font-size: 11px; }
  .tt-row span:first-child { color: var(--grey-500, #777); }
  .tt-row span:last-child  { color: var(--grey-800, #222); font-weight: 500; text-align: right; }
  .tt-sep { margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--grey-100, #eee); }
</style>