<script>
  export let data = [];

  const PHASE_COLOR = {
    'Procurement':    '#7F77DD',
    'Implementation': '#378ADD',
    'O&M':            '#639922',
  };

  const TODAY = new Date();

  $: project = Array.from(data)[0] || {};

  $: phases = [
    project.proc_start && project.proc_end ? { name: 'Procurement',    start: new Date(project.proc_start), end: new Date(project.proc_end) } : null,
    project.impl_start && project.impl_end ? { name: 'Implementation', start: new Date(project.impl_start), end: new Date(project.impl_end) } : null,
    project.om_start   && project.om_end   ? { name: 'O&M',            start: new Date(project.om_start),   end: new Date(project.om_end)   } : null,
  ].filter(Boolean);

  $: minDate  = phases.reduce((m, p) => p.start < m ? p.start : m, phases[0]?.start || TODAY);
  $: maxDate  = phases.reduce((m, p) => p.end   > m ? p.end   : m, phases[0]?.end   || TODAY);
  $: totalMs  = Math.max(maxDate - minDate, 1);
  $: todayPct = Math.max(0, Math.min(100, (TODAY - minDate) / totalMs * 100));

  $: yearTicks = (() => {
    const ticks = [];
    for (let y = minDate.getFullYear(); y <= maxDate.getFullYear() + 1; y++) {
      const pct = Math.max(0, Math.min(100, (new Date(y, 0, 1) - minDate) / totalMs * 100));
      ticks.push({ year: y, pct });
    }
    return ticks;
  })();

  function datePct(d) {
    return Math.max(0, Math.min(100, (new Date(d) - minDate) / totalMs * 100));
  }

  function fmtDate(d) {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
</script>

{#if phases.length > 0}
<div class="timeline-wrap">

  <!-- Year header -->
  <div class="tl-header">
    <div class="tl-label-col"></div>
    <div class="tl-track">
      {#each yearTicks as tick}
        <div class="yr-mark" style="left:{tick.pct}%">
          <div class="yr-line"></div>
          <div class="yr-label">{tick.year}</div>
        </div>
      {/each}
      <!-- Today -->
      <div class="today-mark" style="left:{todayPct}%">
        <div class="today-line"></div>
        <div class="today-label">Today</div>
      </div>
    </div>
  </div>

  <!-- Phase rows -->
  {#each phases as phase}
    {@const left  = datePct(phase.start)}
    {@const width = Math.max(datePct(phase.end) - left, 1)}
    <div class="tl-row">
      <div class="tl-label-col">
        <span class="phase-dot" style="background:{PHASE_COLOR[phase.name]}"></span>
        {phase.name}
      </div>
      <div class="tl-track">
        {#each yearTicks as tick}
          <div class="yr-grid" style="left:{tick.pct}%"></div>
        {/each}
        <div class="today-grid" style="left:{todayPct}%"></div>
        <div class="phase-bar"
             style="left:{left}%; width:{width}%; background:{PHASE_COLOR[phase.name]}">
          <span class="bar-dates">{fmtDate(phase.start)} – {fmtDate(phase.end)}</span>
        </div>
      </div>
      <div class="tl-dates-col">
        <span>{fmtDate(phase.start)}</span>
        <span class="dates-sep">→</span>
        <span>{fmtDate(phase.end)}</span>
      </div>
    </div>
  {/each}

</div>
{:else}
  <div class="empty">No phase date data available</div>
{/if}

<style>
  .timeline-wrap { padding: 4px 0 8px; }
  .empty { font-size: 12px; color: var(--grey-400, #aaa); padding: 12px 0; }

  .tl-header, .tl-row {
    display: grid;
    grid-template-columns: 130px 1fr 260px;
    align-items: center;
    gap: 0;
  }
  .tl-header { margin-bottom: 4px; }

  .tl-label-col {
    font-size: 11px; font-weight: 500;
    color: var(--grey-600, #555);
    display: flex; align-items: center; gap: 6px;
    padding-right: 12px;
  }
  .phase-dot { width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }

  .tl-track {
    position: relative; height: 36px;
    border-left: 1px solid var(--grey-100, #eee);
  }
  .tl-header .tl-track { height: 20px; }

  .yr-mark {
    position: absolute; top: 0; bottom: 0;
    display: flex; flex-direction: column;
  }
  .yr-line  { width: 1px; height: 100%; background: var(--grey-100, #eee); }
  .yr-label {
    position: absolute; bottom: 0;
    font-size: 9px; color: var(--grey-400, #aaa);
    transform: translateX(-50%);
    white-space: nowrap;
  }
  .yr-grid {
    position: absolute; top: 0; bottom: 0;
    width: 1px; background: var(--grey-100, #eee);
    pointer-events: none;
  }
  .today-mark, .today-grid {
    position: absolute; top: 0; bottom: 0;
    width: 2px; background: #E24B4A;
    pointer-events: none;
  }
  .today-label {
    position: absolute; top: 0; left: 4px;
    font-size: 9px; font-weight: 600; color: #E24B4A;
    white-space: nowrap;
  }
  .today-grid { width: 1px; background: rgba(226,75,74,0.4); }

  .phase-bar {
    position: absolute; top: 50%; transform: translateY(-50%);
    height: 22px; border-radius: 4px;
    display: flex; align-items: center; overflow: hidden;
    min-width: 4px;
  }
  .bar-dates {
    font-size: 9px; color: rgba(255,255,255,0.9);
    padding: 0 7px; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
    font-weight: 500;
  }

  .tl-dates-col {
    display: flex; align-items: center; gap: 4px;
    font-size: 10px; color: var(--grey-400, #999);
    padding-left: 12px; white-space: nowrap;
  }
  .dates-sep { color: var(--grey-300, #ccc); }
</style>
