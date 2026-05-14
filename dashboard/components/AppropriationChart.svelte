<script>
  export let fundingTotal = [];
  export let costsTotal   = [];

  let mode = 'bar';

  function norm(arr, key) {
    const row = Array.from(arr || [])[0] || {};
    return Number(row[key]) || 0;
  }

  function cumsum(arr) {
    let s = 0;
    return arr.map(v => { s += (v || 0); return s; });
  }

  const labels = ['Prior FY2025', 'FY2025', 'FY2026', 'FY2027'];

  $: pApprop = [
    norm(fundingTotal, 'prior_to_fy2025'),
    norm(fundingTotal, 'actual_fy2025'),
    norm(fundingTotal, 'appropriation_fy2026'),
    norm(fundingTotal, 'allowance_fy2027')
  ];
  $: pSpend = [
    norm(costsTotal, 'prior_to_fy2025'),
    norm(costsTotal, 'actual_fy2025'),
    norm(costsTotal, 'spend_plan_fy2026'),
    norm(costsTotal, 'spend_plan_fy2027')
  ];
  $: isPlanned = [false, false, true, true];

  $: cApprop = cumsum(pApprop);
  $: cActual = [pSpend[0] || null, (pSpend[0]||0) + (pSpend[1]||0) || null, null, null];
  $: cPlan   = (() => {
    const base = (pSpend[0]||0) + (pSpend[1]||0);
    return [
      null,
      base || null,
      base + (pSpend[2]||0) || null,
      base + (pSpend[2]||0) + (pSpend[3]||0) || null
    ];
  })();

  // SVG constants
  const W = 720, H = 220;
  const PL = 54, PR = 12, PT = 14, PB = 38;
  const CW = W - PL - PR, CH = H - PT - PB;

  function fmtM(v) {
    if (!v && v !== 0) return '—';
    const abs = Math.abs(v);
    if (abs >= 1e9) return '$' + (v/1e9).toFixed(1) + 'B';
    if (abs >= 1e6) return '$' + (v/1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return '$' + (v/1e3).toFixed(0) + 'K';
    return '$0';
  }

  function fmtTick(v) {
    if (!v && v !== 0) return '';
    const abs = Math.abs(v);
    if (abs === 0) return '$0';
    if (abs >= 1e9) return '$' + (v/1e9).toFixed(v % 1e9 === 0 ? 0 : 1) + 'B';
    if (abs >= 1e6) {
      const n = v/1e6;
      return '$' + (Number.isInteger(n) ? n : n.toFixed(1)) + 'M';
    }
    if (abs >= 1e3) return '$' + (v/1e3).toFixed(0) + 'K';
    return '$0';
  }

  function niceMax(vals) {
    const m = Math.max(...vals.filter(v => v != null && v > 0), 1);
    const mag = Math.pow(10, Math.floor(Math.log10(m)));
    const step = Math.ceil(m / mag / 4) * mag;
    return step * Math.ceil(m * 1.15 / step);
  }

  function makeTicks(maxVal, n = 4) {
    const step = maxVal / n;
    return Array.from({length: n + 1}, (_, i) => i * step);
  }

  // Bar chart
  $: bMax   = niceMax([...pApprop, ...pSpend]);
  $: bTicks = makeTicks(bMax);
  $: gW     = CW / 4;
  $: bW     = gW * 0.3;
  $: bGap   = gW * 0.03;

  const bY  = (v, mx) => PT + CH - (v / mx) * CH;
  const bH  = (v, mx) => (v / mx) * CH;
  const bXa = (i)     => PL + gW * i + gW / 2 - bW - bGap / 2;
  const bXs = (i)     => PL + gW * i + gW / 2 + bGap / 2;

  // Cumulative chart
  $: cAll  = [...cApprop, ...cActual.filter(Boolean), ...cPlan.filter(Boolean)];
  $: cMax  = niceMax(cAll);
  $: cTicks = makeTicks(cMax);

  const lx = (i)    => PL + (i / 3) * CW;
  const ly = (v, mx) => v == null ? null : PT + CH - (v / mx) * CH;

  function polyPoints(data, mx) {
    return data.map((v, i) => v != null ? `${lx(i)},${ly(v, mx)}` : null)
               .filter(Boolean).join(' ');
  }

  // Tooltip
  let tip = null;
  let tipX = 0, tipY = 0;

  function onBarEnter(e, i) {
    const a = pApprop[i], s = pSpend[i], diff = a - s;
    tip = {
      title: labels[i],
      rows: [
        { c: '#7F77DD', l: 'Appropriation',                   v: fmtM(a) },
        { c: '#1D9E75', l: isPlanned[i] ? 'Planned spend' : 'Actual spend', v: fmtM(s) },
        { c: diff >= 0 ? '#888' : '#E24B4A', l: diff >= 0 ? 'Unspent' : 'Over-spent', v: fmtM(Math.abs(diff)) },
      ]
    };
    positionTip(e);
  }

  function onCumEnter(e, i) {
    tip = {
      title: labels[i],
      rows: [
        cApprop[i]  ? { c: '#7F77DD', l: 'Cumul. appropriation', v: fmtM(cApprop[i])  } : null,
        cActual[i]  ? { c: '#1D9E75', l: 'Cumul. actual spend',  v: fmtM(cActual[i])  } : null,
        cPlan[i]    ? { c: 'rgba(29,158,117,0.7)', l: 'Cumul. planned spend', v: fmtM(cPlan[i]) } : null,
      ].filter(Boolean)
    };
    positionTip(e);
  }

  function positionTip(e) {
    const svg = e.currentTarget.closest('svg');
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    tipX = e.clientX - r.left;
    tipY = e.clientY - r.top;
  }

  function hideTip() { tip = null; }
</script>

<div class="ac-wrap">
  <div class="btn-group">
    <button class:active={mode==='bar'}        on:click={() => mode='bar'}>By year</button>
    <button class:active={mode==='cumulative'} on:click={() => mode='cumulative'}>Cumulative</button>
  </div>

  <div class="legend">
    {#if mode === 'bar'}
      <span class="leg"><span class="sq" style="background:#7F77DD"></span>Appropriation</span>
      <span class="leg"><span class="sq" style="background:#1D9E75"></span>Actual spend</span>
      <span class="leg"><span class="sq" style="background:rgba(29,158,117,0.35);border:1px solid #1D9E75"></span>Planned spend</span>
    {:else}
      <span class="leg"><span class="ln" style="background:#7F77DD"></span>Cumul. appropriation</span>
      <span class="leg"><span class="ln" style="background:#1D9E75"></span>Cumul. actual spend</span>
      <span class="leg"><span class="da" style="border-color:#1D9E75"></span>Cumul. planned spend</span>
    {/if}
  </div>

  <div style="position:relative" on:mouseleave={hideTip}>
    <svg viewBox="0 0 {W} {H}" width="100%" style="overflow:visible;display:block"
         role="img" aria-label="Appropriation vs spend by fiscal year">

      {#if mode === 'bar'}
        {#each bTicks as t}
          {@const y = bY(t, bMax)}
          <line x1={PL} y1={y} x2={W-PR} y2={y} stroke="var(--grey-100,#eee)" stroke-width="0.5"/>
          <text x={PL-5} y={y+4} text-anchor="end" font-size="10" fill="var(--grey-400,#aaa)">{fmtTick(t)}</text>
        {/each}

        {#each pApprop as a, i}
          {#if a > 0}
            <rect x={bXa(i)} y={bY(a,bMax)} width={bW} height={bH(a,bMax)}
                  fill="#7F77DD" rx="2" style="cursor:pointer"
                  on:mouseenter={e => onBarEnter(e,i)} on:mouseleave={hideTip}/>
          {/if}
          {#if pSpend[i] > 0}
            <rect x={bXs(i)} y={bY(pSpend[i],bMax)} width={bW} height={bH(pSpend[i],bMax)}
                  fill={isPlanned[i] ? 'rgba(29,158,117,0.35)' : '#1D9E75'}
                  stroke={isPlanned[i] ? '#1D9E75' : 'none'} stroke-width="1"
                  rx="2" style="cursor:pointer"
                  on:mouseenter={e => onBarEnter(e,i)} on:mouseleave={hideTip}/>
          {/if}
          <text x={PL + gW*i + gW/2} y={H-PB+14} text-anchor="middle" font-size="10" fill="var(--grey-400,#aaa)">{labels[i]}</text>
        {/each}

      {:else}
        {#each cTicks as t}
          {@const y = ly(t, cMax)}
          <line x1={PL} y1={y} x2={W-PR} y2={y} stroke="var(--grey-100,#eee)" stroke-width="0.5"/>
          <text x={PL-5} y={y+4} text-anchor="end" font-size="10" fill="var(--grey-400,#aaa)">{fmtTick(t)}</text>
        {/each}

        <!-- Shaded gap between approp and actual -->
        {#each [0,1] as i}
          {#if cActual[i]}
            <rect x={lx(i)-1} y={ly(cApprop[i],cMax)}
                  width="2" height={ly(cActual[i],cMax) - ly(cApprop[i],cMax)}
                  fill="rgba(127,119,221,0.15)"/>
          {/if}
        {/each}

        <!-- Approp line -->
        <polyline points={polyPoints(cApprop, cMax)}
                  fill="none" stroke="#7F77DD" stroke-width="2.5" stroke-linejoin="round"/>
        {#each cApprop as v, i}
          <circle cx={lx(i)} cy={ly(v,cMax)} r="5" fill="#7F77DD" style="cursor:pointer"
            on:mouseenter={e => onCumEnter(e,i)} on:mouseleave={hideTip}/>
        {/each}

        <!-- Actual spend line -->
        <polyline points={polyPoints(cActual, cMax)}
                  fill="none" stroke="#1D9E75" stroke-width="2.5" stroke-linejoin="round"/>
        {#each cActual as v, i}
          {#if v != null}
            <circle cx={lx(i)} cy={ly(v,cMax)} r="5" fill="#1D9E75" style="cursor:pointer"
              on:mouseenter={e => onCumEnter(e,i)} on:mouseleave={hideTip}/>
          {/if}
        {/each}

        <!-- Planned line dashed -->
        <polyline points={polyPoints(cPlan, cMax)}
                  fill="none" stroke="#1D9E75" stroke-width="2" stroke-dasharray="6 4"
                  stroke-linejoin="round" opacity="0.65"/>
        {#each cPlan as v, i}
          {#if v != null}
            <circle cx={lx(i)} cy={ly(v,cMax)} r="4" fill="#1D9E75" opacity="0.65" style="cursor:pointer"
              on:mouseenter={e => onCumEnter(e,i)} on:mouseleave={hideTip}/>
          {/if}
        {/each}

        {#each labels as label, i}
          <text x={lx(i)} y={H-PB+14} text-anchor="middle" font-size="10" fill="var(--grey-400,#aaa)">{label}</text>
        {/each}
      {/if}

      <!-- Axes -->
      <line x1={PL} y1={PT} x2={PL} y2={H-PB} stroke="var(--grey-200,#ddd)" stroke-width="1"/>
      <line x1={PL} y1={H-PB} x2={W-PR} y2={H-PB} stroke="var(--grey-200,#ddd)" stroke-width="1"/>

      <!-- Tooltip -->
      {#if tip}
        {@const tw = 178}
        {@const th = tip.rows.length * 18 + 28}
        {@const tx = Math.min(tipX + 10, W - tw - 4)}
        {@const ty = Math.max(tipY - th - 10, PT)}
        <rect x={tx} y={ty} width={tw} height={th} rx="5" fill="var(--grey-800,#222)" opacity="0.92"/>
        <text x={tx+10} y={ty+17} font-size="11" font-weight="500" fill="white">{tip.title}</text>
        {#each tip.rows as row, ri}
          <circle cx={tx+10} cy={ty+30+ri*18} r="4" fill={row.c}/>
          <text x={tx+20} y={ty+34+ri*18} font-size="10" fill="#ccc">{row.l}</text>
          <text x={tx+tw-8} y={ty+34+ri*18} font-size="10" fill="white" font-weight="500" text-anchor="end">{row.v}</text>
        {/each}
      {/if}

    </svg>
  </div>

  <p class="note">
    {#if mode === 'bar'}Faded bars = planned &nbsp;·&nbsp; Hover for unspent balance
    {:else}Dashed line = planned &nbsp;·&nbsp; Hover points for details{/if}
  </p>
</div>

<style>
  .ac-wrap { padding: 4px 0 8px; }
  .btn-group { display:flex; border:0.5px solid var(--grey-300,#ccc); border-radius:6px; width:fit-content; overflow:hidden; margin-bottom:12px; }
  .btn-group button { padding:5px 14px; font-size:12px; border:none; background:transparent; color:var(--grey-500,#777); cursor:pointer; font-family:inherit; }
  .btn-group button:not(:last-child) { border-right:0.5px solid var(--grey-300,#ccc); }
  .btn-group button.active { background:var(--grey-800,#222); color:#fff; font-weight:500; }
  .legend { display:flex; gap:16px; margin-bottom:10px; font-size:11px; color:var(--grey-500,#777); flex-wrap:wrap; align-items:center; }
  .leg { display:flex; align-items:center; gap:5px; }
  .sq { width:9px; height:9px; border-radius:2px; flex-shrink:0; }
  .ln { width:20px; height:3px; border-radius:2px; flex-shrink:0; }
  .da { width:20px; height:0; border-top:2.5px dashed; flex-shrink:0; }
  .note { font-size:11px; color:var(--grey-400,#aaa); margin-top:6px; text-align:center; }
</style>