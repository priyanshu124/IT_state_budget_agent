<script>
    import * as echarts from 'echarts';

    // ── Props — backward-compatible with budget office agency page ────────────
    // Budget office passes: filteredUnitRows, drillViewYears, drillYears,
    //   grandTotal, unitPivotRows, getFilteredPrograms, getFilteredSubprograms
    // Technology page additionally passes: getFilteredCostPools, level labels

    export let filteredUnitRows = [];
    export let drillViewYears = [];
    export let drillYears = [];
    export let grandTotal = {};
    export let unitPivotRows = [];              // kept for compatibility, unused internally
    export let getFilteredPrograms = () => [];
    export let getFilteredSubprograms = () => [];
    export let getFilteredCostPools = null;     // null = 3-level mode (budget office default)

    // Labels — budget office never passes these so defaults match its header exactly
    export let level1Label = 'Unit';
    export let level2Label = 'Program';
    export let level3Label = 'Subprogram';
    export let level4Label = 'Cost Pool';

    // Accent color — budget office red by default; tech page can pass purple
    export let accentColor = '#C8122C';

    // ── Expand state ──────────────────────────────────────────────────────────
    let expandedUnits = {};
    let expandedPrograms = {};
    let expandedSubprograms = {};

    function toggleUnit(name) {
        expandedUnits = { ...expandedUnits, [name]: !expandedUnits[name] };
    }
    function toggleProgram(unit, prog) {
        const key = unit + '||' + prog;
        expandedPrograms = { ...expandedPrograms, [key]: !expandedPrograms[key] };
    }
    function toggleSubprogram(unit, prog, sub) {
        const key = unit + '||' + prog + '||' + sub;
        expandedSubprograms = { ...expandedSubprograms, [key]: !expandedSubprograms[key] };
    }

    // ── Sorting ───────────────────────────────────────────────────────────────
    function sortByLatest(rows) {
        if (!rows?.length) return rows ?? [];
        const latestYr = drillViewYears[drillViewYears.length - 1];
        return rows.slice().sort((a, b) =>
            (Number(b['FY' + latestYr]) || 0) - (Number(a['FY' + latestYr]) || 0)
        );
    }

    // Returns true if the row has spend in at least one visible year
    function hasAnySpend(row) {
        return drillViewYears.some(yr => (Number(row['FY' + yr]) || 0) > 0);
    }

    $: sortedUnits = sortByLatest(filteredUnitRows).filter(hasAnySpend);

    // ── Formatting ────────────────────────────────────────────────────────────
    function formatAmount(v) {
        const n = Number(v) || 0;
        if (n === 0) return '—';
        if (Math.abs(n) >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
        return '$' + (n / 1e3).toFixed(0) + 'K';
    }

    function getYoy(row, yr, viewYears) {
        const i = viewYears.indexOf(yr);
        if (i <= 0) return null;
        const curr = Number(row['FY' + yr]) || 0;
        const prev = Number(row['FY' + viewYears[i - 1]]) || 0;
        return prev > 0 ? (curr - prev) / prev * 100 : null;
    }

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

    // ── Sparkline (ECharts Svelte action) ────────────────────────────────────
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

    $: headerLabel = getFilteredCostPools
        ? `${level1Label} · ${level2Label} · ${level3Label} · ${level4Label}`
        : `${level1Label} · ${level2Label} · ${level3Label}`;
</script>

<div style="overflow-x:auto; border-radius:8px; border:1px solid var(--nxt-border,#E5E7EB); background:var(--nxt-surface,#fff);">
    <table style="width:100%; border-collapse:collapse; font-size:0.875rem;">

        <!-- ── Header ── -->
        <thead>
            <tr style="background:var(--nxt-pink,#FDF4FF); border-bottom:2px solid {accentColor};">
                <th style="text-align:left; padding:10px 14px; font-weight:700; color:#231F20; min-width:280px;">
                    {headerLabel}
                </th>
                <th style="padding:10px 8px; font-weight:500; color:#6B7280; font-size:0.75rem; min-width:90px; white-space:nowrap;">
                    Trend ({drillYears[0]}–{drillYears[drillYears.length - 1]})
                </th>
                {#each drillViewYears as yr, i}
                    <th style={'text-align:right; padding:10px 14px; font-weight:700; color:#231F20; white-space:nowrap;' + (i === drillViewYears.length - 1 ? ' border-left:2px solid ' + accentColor + ';' : '')}>
                        FY{yr}{#if i === drillViewYears.length - 1} ↓{/if}
                    </th>
                {/each}
            </tr>
        </thead>

        <tbody>

            <!-- ── Total row ── -->
            <tr style="background:var(--nxt-pink,#FDF4FF); border-bottom:1px solid var(--nxt-border,#E5E7EB);">
                <td style="padding:10px 14px; font-weight:700; color:{accentColor};">Total</td>
                <td></td>
                {#each drillViewYears as yr, i}
                    {@const yoy = i === 0 ? null : (() => {
                        const curr = Number(grandTotal['FY' + yr]) || 0;
                        const prev = Number(grandTotal['FY' + drillViewYears[i - 1]]) || 0;
                        return prev > 0 ? (curr - prev) / prev * 100 : null;
                    })()}
                    {@const ps = i > 0 ? pillStyle(yoy) : null}
                    <td style={'text-align:right; padding:10px 14px; font-weight:700; background:' + (ps ? ps.bg : 'transparent')}>
                        <span style={'color:' + accentColor}>{formatAmount(grandTotal['FY' + yr])}</span>
                    </td>
                {/each}
            </tr>

            <!-- ── Level 1 rows ── -->
            {#each sortedUnits as unit}
                <tr
                    on:click={() => toggleUnit(unit.name)}
                    style="border-bottom:1px solid var(--nxt-border,#E5E7EB); cursor:pointer; background:var(--nxt-surface,#fff);"
                    onmouseenter="this.style.background='var(--nxt-pink,#FDF4FF)'"
                    onmouseleave="this.style.background='var(--nxt-surface,#fff)'"
                >
                    <td style="padding:10px 14px; font-weight:600; color:#231F20;">
                        <span style="margin-right:8px; font-size:0.75rem; color:{accentColor};">{expandedUnits[unit.name] ? '▼' : '▶'}</span>
                        {unit.name}
                    </td>
                    <td style="padding:4px 8px;">
                        <div use:sparkline={unit} style="width:90px; height:24px;"></div>
                    </td>
                    {#each drillViewYears as yr, i}
                        {@const yoy = getYoy(unit, yr, drillViewYears)}
                        {@const ps = i > 0 ? pillStyle(yoy) : null}
                        <td style={'text-align:right; padding:10px 14px; background:' + (ps ? ps.bg : 'transparent')}>
                            <span style="font-weight:600; color:#231F20;">{formatAmount(unit['FY' + yr])}</span>
                        </td>
                    {/each}
                </tr>

                <!-- ── Level 2 rows ── -->
                {#if expandedUnits[unit.name]}
                    {#each sortByLatest(getFilteredPrograms(unit.name)).filter(hasAnySpend) as prog}
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
                                    <span style="color:#374151;">{formatAmount(prog['FY' + yr])}</span>
                                </td>
                            {/each}
                        </tr>

                        <!-- ── Level 3 rows ── -->
                        {#if expandedPrograms[unit.name + '||' + prog.name]}
                            {#each sortByLatest(getFilteredSubprograms(unit.name, prog.name)).filter(hasAnySpend) as sub}
                                <tr
                                    on:click={() => getFilteredCostPools ? toggleSubprogram(unit.name, prog.name, sub.name) : null}
                                    style={'border-bottom:1px solid #F3F4F6; background:#F7F2FC;' + (getFilteredCostPools ? ' cursor:pointer;' : '')}
                                    onmouseenter="this.style.background='#EDE5F8'"
                                    onmouseleave="this.style.background='#F7F2FC'"
                                >
                                    <td style="padding:7px 14px 7px 60px; color:#6B7280; font-style:italic;">
                                        {#if getFilteredCostPools}
                                            <span style="margin-right:8px; font-size:0.75rem; color:#9CA3AF;">{expandedSubprograms[unit.name + '||' + prog.name + '||' + sub.name] ? '▼' : '▶'}</span>
                                        {/if}
                                        {sub.name}
                                    </td>
                                    <td style="padding:4px 8px;">
                                        <div use:sparkline={sub} style="width:90px; height:24px;"></div>
                                    </td>
                                    {#each drillViewYears as yr, i}
                                        {@const yoy = getYoy(sub, yr, drillViewYears)}
                                        {@const ps = i > 0 ? pillStyle(yoy) : null}
                                        <td style={'text-align:right; padding:7px 14px; background:' + (ps ? ps.bg : 'transparent')}>
                                            <span style="color:#6B7280;">{formatAmount(sub['FY' + yr])}</span>
                                        </td>
                                    {/each}
                                </tr>

                                <!-- ── Level 4 rows (cost pools) — only rendered when getFilteredCostPools is passed ── -->
                                {#if getFilteredCostPools && expandedSubprograms[unit.name + '||' + prog.name + '||' + sub.name]}
                                    {#each sortByLatest(getFilteredCostPools(unit.name, prog.name, sub.name)).filter(hasAnySpend) as cp}
                                        <tr
                                            style="border-bottom:1px solid #F3F4F6; background:#F0EAF9;"
                                            onmouseenter="this.style.background='#E8DFF5'"
                                            onmouseleave="this.style.background='#F0EAF9'"
                                        >
                                            <td style="padding:6px 14px 6px 84px; color:#9CA3AF; font-size:0.8rem;">
                                                {cp.name}
                                            </td>
                                            <td style="padding:4px 8px;">
                                                <div use:sparkline={cp} style="width:90px; height:24px;"></div>
                                            </td>
                                            {#each drillViewYears as yr, i}
                                                {@const yoy = getYoy(cp, yr, drillViewYears)}
                                                {@const ps = i > 0 ? pillStyle(yoy) : null}
                                                <td style={'text-align:right; padding:6px 14px; background:' + (ps ? ps.bg : 'transparent')}>
                                                    <span style="color:#9CA3AF; font-size:0.8rem;">{formatAmount(cp['FY' + yr])}</span>
                                                </td>
                                            {/each}
                                        </tr>
                                    {/each}
                                {/if}

                            {/each}
                        {/if}
                    {/each}
                {/if}
            {/each}

        </tbody>
    </table>
</div>
