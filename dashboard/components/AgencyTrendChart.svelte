<script>
    import * as echarts from 'echarts';
    import { onMount, onDestroy } from 'svelte';

    export let agencies = [];
    export let trendLines = [];
    export let years = [];
    export let topN = 5;
    export let height = '480px';
    export let title = 'Agency Budget — Trend Over Time';
    export let entityLabel = 'agency';

    const COLORS = ['#C8122C', '#FFC838', '#231F20', '#2EAD6B', '#5B8FF9'];
    const getColor = (idx) => COLORS[idx] ?? COLORS[COLORS.length - 1];

    let chartEl;
    let mainChart;
    let activeView = 'dollars';
    let selectedName = null;

    function getSpend(name, year) {
        const row = trendLines.find(d => String(d.fiscal_year) === String(year) && d.agency_name === name);
        return row ? Number(row.spend) || 0 : 0;
    }

    function getDollarData(name) {
        return years.map(y => getSpend(name, y));
    }

    function getYoyData(name) {
        const vals = getDollarData(name);
        return vals.map((v, i) => {
            if (i === 0) return null;
            const prev = vals[i - 1];
            if (!prev || prev === 0) return null;
            return parseFloat(Math.max(-100, Math.min(200, (v - prev) / prev * 100)).toFixed(1));
        });
    }

    function usd(v) {
        const n = Number(v) || 0;
        if (Math.abs(n) >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
        return '$' + Math.round(n).toLocaleString();
    }

    // Compute insight metrics for each agency
    function getInsights(name) {
        const dollars = getDollarData(name);
        const yoy = getYoyData(name).filter(v => v !== null);
        const latest = dollars[dollars.length - 1] || 0;
        const avgYoy = yoy.length ? (yoy.reduce((a, b) => a + b, 0) / yoy.length) : null;
        const bestYear = yoy.length ? years[getYoyData(name).indexOf(Math.max(...yoy)) ] : null;
        const worstYear = yoy.length ? years[getYoyData(name).indexOf(Math.min(...yoy))] : null;
        const bestVal = yoy.length ? Math.max(...yoy) : null;
        const worstVal = yoy.length ? Math.min(...yoy) : null;
        // 3-year trend: compare last 3 years avg vs prior 3 years avg
        const last3 = dollars.slice(-3).filter(v => v > 0);
        const prior3 = dollars.slice(-6, -3).filter(v => v > 0);
        const last3Avg = last3.length ? last3.reduce((a, b) => a + b, 0) / last3.length : 0;
        const prior3Avg = prior3.length ? prior3.reduce((a, b) => a + b, 0) / prior3.length : 0;
        const momentum = prior3Avg > 0 ? ((last3Avg - prior3Avg) / prior3Avg * 100).toFixed(1) : null;
        return { latest, avgYoy, bestYear, worstYear, bestVal, worstVal, momentum };
    }

    $: topAgencies = agencies.slice(0, topN);
    $: bottomAgencies = agencies.slice(topN);

    $: bottomStats = (trendLines, bottomAgencies.map(agency => {
        const name = agency.agency_name;
        const dollars = getDollarData(name);
        const yoyVals = getYoyData(name);
        const latest = dollars[dollars.length - 1] || 0;
        const ins = getInsights(name);
        return { name, dollars, yoyVals, latest, ins };
    }));

    function buildConfig() {
        const isYoy = activeView === 'yoy';
        const hasSel = Boolean(selectedName);

        return {
            grid: { left: 60, right: 170, top: 16, bottom: 40 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255,255,255,0.97)',
                borderColor: '#E5E7EB', borderWidth: 1,
                textStyle: { color: '#231F20', fontSize: 12 },
                formatter: function(params) {
                    if (!params || !params.length) return '';
                    const yr = params[0].axisValue;
                    const yearTotal = isYoy ? null :
                        trendLines.filter(d => String(d.fiscal_year) === String(yr))
                            .reduce((s, d) => s + (Number(d.spend) || 0), 0);
                    const rows = params
                        .filter(p => p.value !== null && p.value !== 0)
                        .sort((a, b) => (Number(b.value) || 0) - (Number(a.value) || 0))
                        .map(p => {
                            const v = Number(p.value) || 0;
                            const fmt = isYoy
                                ? (v > 0 ? '+' : '') + v.toFixed(1) + '% YoY'
                                : usd(v) + (yearTotal > 0 ? ' (' + ((v / yearTotal) * 100).toFixed(1) + '%)' : '');
                            return p.marker + ' ' + p.seriesName + ': ' + fmt;
                        });
                    return '<b>FY' + yr + '</b><br/>' + rows.join('<br/>');
                }
            },
            xAxis: {
                type: 'category', data: years,
                axisLine: { lineStyle: { color: '#E5E7EB' } },
                axisTick: { show: false },
                axisLabel: { fontSize: 11, color: '#6B7280' }
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    fontSize: 11, color: '#6B7280',
                    formatter: isYoy
                        ? v => (v > 0 ? '+' : '') + v + '%'
                        : v => Math.abs(v) >= 1e9 ? '$' + (v / 1e9).toFixed(0) + 'B' : '$' + (v / 1e6).toFixed(0) + 'M'
                },
                splitLine: { lineStyle: { color: '#E5E7EB' } },
                ...(isYoy ? { min: v => Math.floor(v.min / 5) * 5, max: v => Math.ceil(v.max / 5) * 5 } : {})
            },
            series: topAgencies.map((agency, idx) => {
                const name = agency.agency_name;
                const color = getColor(idx);
                const isSel = selectedName === name;
                const active = !hasSel || isSel;
                const data = isYoy ? getYoyData(name) : getDollarData(name);
                return {
                    name,
                    type: 'line',
                    smooth: false,
                    symbol: 'circle',
                    symbolSize: hasSel ? (isSel ? 8 : 4) : 5,
                    showSymbol: true,
                    lineStyle: { color, width: hasSel ? (isSel ? 3 : 1.2) : 2.5, opacity: active ? 1 : 0.08 },
                    itemStyle: { color, opacity: active ? 1 : 0.08 },
                    endLabel: {
                        show: !hasSel || isSel,
                        formatter: () => name.length > 22 ? name.slice(0, 21) + '…' : name,
                        color, fontSize: 10, fontWeight: isSel ? 600 : 400
                    },
                    emphasis: { focus: 'series', lineStyle: { width: 4, opacity: 1 }, itemStyle: { opacity: 1 } },
                    blur: { lineStyle: { opacity: 0.08 }, itemStyle: { opacity: 0.08 } },
                    data
                };
            })
        };
    }

    $: currentConfig = (() => {
        const _view = activeView;
        const _sel = selectedName;
        const _top = topAgencies;
        if (!trendLines?.length || !years?.length) return null;
        return buildConfig();
    })();

    $: if (mainChart && currentConfig) {
        mainChart.setOption(currentConfig, true);
    }

    function toggleName(name) {
        selectedName = selectedName === name ? null : name;
    }

    // Sparkline action — switches between dollar area and YoY bar based on activeView
    function sparkline(el, params) {
        let sc = null;
        let observer = null;
        let lastView = null;

        function render() {
            const { name, view } = typeof params === 'string' ? { name: params, view: activeView } : params;
            const isYoy = view === 'yoy';
            const dollars = getDollarData(name);
            const yoyVals = getYoyData(name);

            const hasData = isYoy
                ? yoyVals.some(v => v !== null)
                : dollars.some(v => v > 0);
            if (!hasData) return;

            const w = el.offsetWidth;
            if (w < 10) return;

            if (!sc) {
                sc = echarts.init(el, null, { width: w, height: 32 });
            } else {
                sc.resize({ width: w, height: 32 });
            }

            if (isYoy) {
                sc.setOption({
                    grid: { top: 2, bottom: 2, left: 2, right: 2 },
                    xAxis: { type: 'category', data: years, show: false },
                    yAxis: { type: 'value', show: false },
                    series: [{
                        type: 'bar',
                        data: yoyVals.map(v => v === null ? 0 : v),
                        itemStyle: {
                            color: (p) => Number(p.value) >= 0 ? 'rgba(46,173,107,0.7)' : 'rgba(200,18,44,0.7)'
                        },
                        barMinHeight: 1
                    }]
                }, true);
            } else {
                sc.setOption({
                    grid: { top: 2, bottom: 2, left: 2, right: 2 },
                    xAxis: { type: 'category', data: years, show: false },
                    yAxis: { type: 'value', show: false },
                    series: [{
                        type: 'line', data: dollars, smooth: false, symbol: 'none',
                        lineStyle: { color: '#5B8FF9', width: 1.5 },
                        areaStyle: { color: 'rgba(91,143,249,0.12)' }
                    }]
                }, true);
            }
            lastView = view;
        }

        if (typeof ResizeObserver !== 'undefined') {
            observer = new ResizeObserver(() => render());
            observer.observe(el);
        } else {
            setTimeout(render, 300);
        }

        return {
            update(newParams) {
                params = newParams;
                render();
            },
            destroy() { observer?.disconnect(); sc?.dispose(); }
        };
    }

    onMount(() => {
        if (chartEl) {
            mainChart = echarts.init(chartEl);
            if (currentConfig) mainChart.setOption(currentConfig, true);
        }
        const onResize = () => mainChart?.resize();
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    });

    onDestroy(() => mainChart?.dispose());

    $: if (mainChart && trendLines?.length > 0) {
        mainChart.setOption(buildConfig(), true);
    }
</script>

<div style="font-family: var(--font-sans, sans-serif);">

    <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
        <p style="font-size:14px; font-weight:500; color:var(--nxt-text,#231F20); margin:0;">{title}</p>
        <div style="display:flex; border:1px solid var(--nxt-border,#E5E7EB); border-radius:8px; overflow:hidden;">
            {#each [['dollars','Dollars ($)'],['yoy','YoY change (%)']] as [v, label]}
                <button
                    on:click={() => { activeView = v; selectedName = null; }}
                    style={'padding:5px 14px; font-size:0.8rem; cursor:pointer; border:none; border-right:1px solid var(--nxt-border,#E5E7EB); background:' + (activeView === v ? '#802cd7' : 'var(--nxt-surface,#fff)') + '; color:' + (activeView === v ? '#fff' : '#231F20') + '; font-weight:' + (activeView === v ? 600 : 400)}
                >{label}</button>
            {/each}
        </div>
    </div>

    <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px;">
        {#each topAgencies as agency, idx}
            {@const color = getColor(idx)}
            {@const isSel = selectedName === agency.agency_name}
            {@const active = !selectedName || isSel}
            <button
                on:click={() => toggleName(agency.agency_name)}
                style={'display:inline-flex; align-items:center; gap:6px; padding:4px 10px; font-size:0.78rem; cursor:pointer; border-radius:20px; border:' + (isSel ? '2px solid ' + color : '1px solid var(--nxt-border,#E5E7EB)') + '; background:' + (isSel ? 'rgba(0,0,0,0.04)' : 'var(--nxt-surface,#fff)') + '; opacity:' + (active ? 1 : 0.35) + '; transition:opacity .15s;'}
            >
                <span style={'width:8px;height:8px;border-radius:50%;background:' + color + ';flex-shrink:0;'}></span>
                <span style={'color:#231F20; font-weight:' + (isSel ? 600 : 500)}>{agency.agency_name}</span>
            </button>
        {/each}
    </div>

    {#if activeView === 'yoy'}
        <p style="font-size:11px; color:var(--color-text-tertiary,#888780); margin:0 0 6px; font-style:italic;">
            Year-over-year % change · green = budget grew · red = budget cut
        </p>
    {/if}

    <div bind:this={chartEl} style="width:100%; height:{height};"></div>

    {#if bottomAgencies.length > 0}
        <p style="font-size:11px; font-weight:500; color:var(--color-text-secondary,#6B7280); margin:16px 0 8px;">
            Remaining {entityLabel}s
            {#if activeView === 'yoy'}— avg annual growth rate{:else}— spend trend{/if}
        </p>
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(160px,1fr)); gap:10px;">
            {#each bottomStats as stat}
                {@const ins = stat.ins}
                {@const isYoy = activeView === 'yoy'}
                <div style="background:var(--color-background-secondary,#F9F9F7); border-radius:8px; padding:10px 12px;">
                    <div style="font-size:10px; color:var(--color-text-secondary,#6B7280); margin-bottom:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title={stat.name}>{stat.name}</div>

                    {#if isYoy}
                        <!-- YoY view: show avg annual growth -->
                        {#if ins.avgYoy !== null}
                            <div style={'font-size:13px; font-weight:600; color:' + (ins.avgYoy >= 0 ? '#231F20' : '#A32D2D')}>
                                {ins.avgYoy >= 0 ? '+' : ''}{ins.avgYoy.toFixed(1)}% avg/yr
                            </div>

                        {:else}
                            <div style="font-size:12px; color:var(--color-text-tertiary,#888780);">No data</div>
                        {/if}
                    {:else}
                        <!-- Dollar view: show latest spend + 3yr momentum -->
                        <div style="font-size:13px; font-weight:600; color:var(--color-text-primary,#231F20);">{usd(stat.latest)}</div>
                        {#if ins.momentum !== null}
                            <div style={'font-size:10px; margin-bottom:4px; color:' + (parseFloat(ins.momentum) >= 0 ? '#3B6D11' : '#A32D2D')}>
                                {parseFloat(ins.momentum) >= 0 ? '↑' : '↓'} {ins.momentum}% 3yr momentum
                            </div>
                        {/if}
                    {/if}

                    <div use:sparkline={{ name: stat.name, view: activeView }} style="width:100%; height:32px;"></div>
                </div>
            {/each}
        </div>
    {/if}

</div>