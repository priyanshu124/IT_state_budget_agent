<script>
    import * as echarts from 'echarts';

    // ── Props — exact variables from _agency_.md ──────────────────────────────
    export let filteredUnitRows = [];       // already sorted+filtered by parent
    export let drillViewYears = [];         // visible year columns e.g. [2025,2026,2027]
    export let drillYears = [];             // ALL years for sparkline e.g. [2017..2027]
    export let grandTotal = {};             // { FY2025: x, FY2026: y }
    export let unitPivotRows = [];          // needed to check if any data exists
    export let getFilteredPrograms = () => [];
    export let getFilteredSubprograms = () => [];
    // ── Local expand state ────────────────────────────────────────────────────
    let expandedUnits = {};
    let expandedPrograms = {};

    function toggleUnit(name) {
        expandedUnits = { ...expandedUnits, [name]: !expandedUnits[name] };
    }
    function toggleProgram(unit, prog) {
        const key = unit + '||' + prog;
        expandedPrograms = { ...expandedPrograms, [key]: !expandedPrograms[key] };
    }

    // Always sort by latest year amount descending
    function sortByLatest(rows) {
        if (!rows || !rows.length) return rows;
        const latestYr = drillViewYears[drillViewYears.length - 1];
        return rows.slice().sort((a, b) =>
            (Number(b['FY' + latestYr]) || 0) - (Number(a['FY' + latestYr]) || 0)
        );
    }

    $: sortedUnits = sortByLatest(filteredUnitRows);

    // ── Formatting ────────────────────────────────────────────────────────────
    function formatAmount(v) {
        const n = Number(v) || 0;
        if (n === 0) return '—';
        if (Math.abs(n) >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
        return '$' + (n / 1e3).toFixed(0) + 'K';
    }

    // ── YoY helpers ───────────────────────────────────────────────────────────
    function getYoy(row, yr, viewYears) {
        const i = viewYears.indexOf(yr);
        if (i <= 0) return null;
        const curr = Number(row['FY' + yr]) || 0;
        const prev = Number(row['FY' + viewYears[i - 1]]) || 0;
        return prev > 0 ? (curr - prev) / prev * 100 : null;
    }

    // Dollar cell — no color, neutral
    function dollarStyle() {
        return { bg: 'transparent', color: '#231F20', fontWeight: 600 };
    }

    // Light background tint only — text always black
    function pillStyle(pct) {
        if (pct === null) return null;
        let bg;
        if      (pct >= 15)  bg = 'rgba(46,173,107,0.10)';
        else if (pct >= 8)   bg = 'rgba(46,173,107,0.07)';
        else if (pct >= 3)   bg = 'rgba(46,173,107,0.04)';
        else if (pct >= 0)   bg = 'rgba(46,173,107,0.02)';
        else if (pct >= -3)  bg = 'rgba(200,18,44,0.03)';
        else if (pct >= -8)  bg = 'rgba(200,18,44,0.05)';
        else if (pct >= -15) bg = 'rgba(200,18,44,0.07)';
        else                 bg = 'rgba(200,18,44,0.10)';
        return { bg };
    }

    function fmtPct(n) {
        return (n >= 0 ? '+' : '') + n.toFixed(0) + '%';
    }

    // ── Sparkline action ──────────────────────────────────────────────────────
    function sparkline(el, row) {
        let sc = null;
        let observer = null;

        function render() {
            const w = el.offsetWidth;
            if (w < 10) return;
            const data = drillYears.map(yr => Number(row['FY' + yr]) || 0);
            if (!data.some(v => v > 0)) return;
            if (!sc) sc = echarts.init(el, null, { width: w, height: 24 });
            else sc.resize({ width: w, height: 24 });

            // Color based on latest YoY
            const lastTwo = drillYears.slice(-2);
            const curr = Number(row['FY' + lastTwo[1]]) || 0;
            const prev = Number(row['FY' + lastTwo[0]]) || 0;
            const trending = prev > 0 ? curr >= prev : true;
            const color = trending ? '#2EAD6B' : '#C8122C';

            sc.setOption({
                grid: { top: 1, bottom: 1, left: 1, right: 1 },
                xAxis: { type: 'category', data: drillYears.map(String), show: false },
                yAxis: { type: 'value', show: false },
                series: [{
                    type: 'line', data, smooth: false, symbol: 'none',
                    lineStyle: { color, width: 1.5 },
                    areaStyle: { color: trending ? 'rgba(46,173,107,0.10)' : 'rgba(200,18,44,0.08)' }
                }]
            }, true);
        }

        if (typeof ResizeObserver !== 'undefined') {
            observer = new ResizeObserver(() => render());
            observer.observe(el);
        } else {
            setTimeout(render, 200);
        }

        return {
            update(newRow) { row = newRow; render(); },
            destroy() { observer?.disconnect(); sc?.dispose(); }
        };
    }
</script>

<div style="overflow-x:auto; border-radius:8px; border:1px solid var(--nxt-border,#E5E7EB); background:var(--nxt-surface,#fff);">
    <table style="width:100%; border-collapse:collapse; font-size:0.875rem;">
        <thead>
            <tr style="background:var(--nxt-pink,#FDF4FF); border-bottom:2px solid #C8122C;">
                <th style="text-align:left; padding:10px 14px; font-weight:700; color:#231F20; min-width:280px;">
                    Unit / Program / Subprogram
                </th>
                <th style="padding:10px 8px; font-weight:500; color:#6B7280; font-size:0.75rem; min-width:90px; white-space:nowrap;">
                    Trend ({drillYears[0]}–{drillYears[drillYears.length - 1]})
                </th>
                {#each drillViewYears as yr, i}
                    <th style={'text-align:right; padding:10px 14px; font-weight:700; color:#231F20; white-space:nowrap;' + (i === drillViewYears.length - 1 ? ' border-left:2px solid #C8122C;' : '')}>
                        FY{yr}{#if i === drillViewYears.length - 1} ↓{/if}
                    </th>
                {/each}
            </tr>
        </thead>
        <tbody>

            <!-- Total row -->
            <tr style="background:var(--nxt-pink,#FDF4FF); border-bottom:1px solid var(--nxt-border,#E5E7EB);">
                <td style="padding:10px 14px; font-weight:700; color:#C8122C;">Total</td>
                <td></td>
                {#each drillViewYears as yr, i}
                    {@const yoy = i === 0 ? null : (() => {
                        const curr = Number(grandTotal['FY' + yr]) || 0;
                        const prev = Number(grandTotal['FY' + drillViewYears[i-1]]) || 0;
                        return prev > 0 ? (curr - prev) / prev * 100 : null;
                    })()}
                    {@const ps = i > 0 ? pillStyle(yoy) : null}
                    <td style={'text-align:right; padding:10px 14px; font-weight:700; background:' + (ps ? ps.bg : 'transparent')}>
                        <span style={'color:' + '#C8122C'}>{formatAmount(grandTotal['FY' + yr])}</span>
                    </td>
                {/each}
            </tr>

            <!-- Unit rows -->
            {#each sortedUnits as unit}
                <tr
                    on:click={() => toggleUnit(unit.name)}
                    style="border-bottom:1px solid var(--nxt-border,#E5E7EB); cursor:pointer; background:var(--nxt-surface,#fff);"
                    onmouseenter="this.style.background='var(--nxt-pink,#FDF4FF)'"
                    onmouseleave="this.style.background='var(--nxt-surface,#fff)'"
                >
                    <td style="padding:10px 14px; font-weight:600; color:#231F20;">
                        <span style="margin-right:8px; font-size:0.75rem; color:#C8122C;">{expandedUnits[unit.name] ? '▼' : '▶'}</span>
                        {unit.name}
                    </td>
                    <td style="padding:4px 8px;">
                        <div use:sparkline={unit} style="width:90px; height:24px;"></div>
                    </td>
                    {#each drillViewYears as yr, i}
                        {@const yoy = getYoy(unit, yr, drillViewYears)}
                        {@const ps = i > 0 ? pillStyle(yoy) : null}
                        <td style={'text-align:right; padding:10px 14px; background:' + (ps ? ps.bg : 'transparent')}>
                            <span style={'font-weight:600; color:' + '#231F20'}>{formatAmount(unit['FY' + yr])}</span>
                        </td>
                    {/each}
                </tr>

                <!-- Program rows -->
                {#if expandedUnits[unit.name]}
                    {#each sortByLatest(getFilteredPrograms(unit.name)) as prog}
                        <tr
                            on:click={() => toggleProgram(unit.name, prog.name)}
                            style="border-bottom:1px solid #F3F4F6; cursor:pointer; background:#FAFAFA;"
                            onmouseenter="this.style.background='#F3F4F6'"
                            onmouseleave="this.style.background='#FAFAFA'"
                        >
                            <td style="padding:8px 14px 8px 36px; color:#374151;">
                                <span style="margin-right:8px; font-size:0.75rem; color:#6B7280;">{expandedPrograms[unit.name + '||' + prog.name] ? '▼' : '▶'}</span>
                                {prog.name}
                            </td>
                            <td style="padding:4px 8px;">
                                <div use:sparkline={prog} style="width:90px; height:24px;"></div>
                            </td>
                            {#each drillViewYears as yr, i}
                                {@const yoy = getYoy(prog, yr, drillViewYears)}
                                {@const ps = i > 0 ? pillStyle(yoy) : null}
                                <td style={'text-align:right; padding:8px 14px; background:' + (ps ? ps.bg : 'transparent')}>
                                    <span style={'color:' + '#374151'}>{formatAmount(prog['FY' + yr])}</span>
                                </td>
                            {/each}
                        </tr>

                        <!-- Subprogram rows -->
                        {#if expandedPrograms[unit.name + '||' + prog.name]}
                            {#each sortByLatest(getFilteredSubprograms(unit.name, prog.name)) as sub}
                                <tr style="border-bottom:1px solid #F3F4F6; background:#F7F2FC;">
                                    <td style="padding:7px 14px 7px 60px; color:#6B7280; font-style:italic;">{sub.name}</td>
                                    <td style="padding:4px 8px;">
                                        <div use:sparkline={sub} style="width:90px; height:24px;"></div>
                                    </td>
                                    {#each drillViewYears as yr, i}
                                        {@const yoy = getYoy(sub, yr, drillViewYears)}
                                        {@const ps = i > 0 ? pillStyle(yoy) : null}
                                        <td style={'text-align:right; padding:7px 14px; background:' + (ps ? ps.bg : 'transparent')}>
                                            <span style={'color:' + '#6B7280'}>{formatAmount(sub['FY' + yr])}</span>
                                        </td>
                                    {/each}
                                </tr>
                            {/each}
                        {/if}
                    {/each}
                {/if}
            {/each}

        </tbody>
    </table>
</div>