<script>
    import * as echarts from 'echarts';
    import { onMount, onDestroy } from 'svelte';

    export let yearly = [];
    export let yoyDetail = [];
    export let fiscalOverviewCagr = [];
    export let cagrPct = null;
    export let chartHeight = '320px';

    function usdCompact(value) {
        const num = Number(value) || 0;
        const abs = Math.abs(num);
        if (abs >= 1e9) return '$' + (num / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return '$' + (num / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return '$' + (num / 1e3).toFixed(2) + 'K';
        return '$' + num.toFixed(2);
    }

    let overviewEl;
    let yoyEl;
    let overviewChart;
    let yoyChart;

    function buildTrendConfig() {
        return {
            title: [{
                text: '{sq|■} {spend|Spend}    {line|——} {cagr|CAGR' + (cagrPct ? ` ${cagrPct}%` : '') + '}    {dash|╌ ╌} {inf|Infl. base}',
                left: 'left', top: 4,
                textStyle: {
                    fontSize: 11, fontWeight: 400, color: '#231F20',
                    rich: {
                        sq:    { color: '#FFC838', fontSize: 14, fontWeight: 900, lineHeight: 16 },
                        spend: { color: '#BA7517', fontSize: 11, fontWeight: 600 },
                        line:  { color: '#C8122C', fontSize: 12, fontWeight: 900 },
                        cagr:  { color: '#C8122C', fontSize: 11, fontWeight: 600 },
                        dash:  { color: '#6B7280', fontSize: 11 },
                        inf:   { color: '#6B7280', fontSize: 11 }
                    }
                }
            }],
            grid: { top: '18%', right: '4%', bottom: '11%', left: '8%', containLabel: true },
            legend: { show: false },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255,255,255,0.97)',
                borderColor: '#E5E7EB', borderWidth: 1,
                textStyle: { color: '#231F20', fontSize: 12 },
                formatter: (params) => {
                    if (!params || params.length === 0) return '';
                    const fy = params[0].axisValue;
                    const rows = params.map((p) => {
                        const v = Number(p.value) || 0;
                        if (p.seriesName === 'Nominal Budget') return `${p.marker} <b>Nominal:</b> ${usdCompact(v)}`;
                        if (p.seriesName && p.seriesName.startsWith('CAGR')) return `${p.marker} <b>CAGR trend:</b> ${usdCompact(v)}`;
                        return `${p.marker} <b>Inflation baseline:</b> ${usdCompact(v)}`;
                    });
                    const nomRow = params.find((p) => p.seriesName === 'Nominal Budget');
                    const infRow = params.find((p) => p.seriesName && p.seriesName.includes('Inflation'));
                    let gap = '';
                    if (nomRow && infRow) {
                        const diff = (Number(nomRow.value) || 0) - (Number(infRow.value) || 0);
                        gap = `<br/><span style="color:#6321a5;font-size:11px;">▲ Real expansion above inflation: ${usdCompact(diff)}</span>`;
                    }
                    return `<b>FY${fy}</b><br/>${rows.join('<br/>')}${gap}`;
                }
            },
            xAxis: {
                type: 'category',
                data: fiscalOverviewCagr.map((d) => String(d.fiscal_year)),
                axisLine: { lineStyle: { color: '#E5E7EB' } },
                axisTick: { show: false }
            },
            yAxis: {
                type: 'value',
                axisLabel: { formatter: (v) => usdCompact(v), fontSize: 11 },
                splitLine: { show: false }
            },
            series: [
                {
                    name: 'Nominal Budget',
                    type: 'bar', barMaxWidth: 36,
                    data: fiscalOverviewCagr.map((d) => Number(d.total_budget) || 0),
                    label: {
                        show: true, position: 'top', distance: 4,
                        fontSize: 9.5, fontWeight: 600,
                        color: (p) => p.dataIndex === fiscalOverviewCagr.length - 1 ? '#BA7517' : '#B08A00',
                        formatter: (p) => usdCompact(p.value)
                    },
                    labelLayout: { hideOverlap: true },
                    itemStyle: { color: (p) => p.dataIndex === fiscalOverviewCagr.length - 1 ? '#BA7517' : '#FFC838' },
                    z: 1
                },
                {
                    name: 'CAGR Trend' + (cagrPct ? ` (${cagrPct}%)` : ''),
                    type: 'line', smooth: false,
                    data: fiscalOverviewCagr.map((d) => Number(d.cagr_trend) || 0),
                    lineStyle: { color: '#C8122C', width: 2.5 },
                    symbol: 'none', itemStyle: { color: '#C8122C' }, z: 3
                },
                {
                    name: 'Inflation-Only Baseline',
                    type: 'line', smooth: false,
                    data: fiscalOverviewCagr.map((d) => Number(d.inflation_baseline) || 0),
                    lineStyle: { color: '#6B7280', width: 1.8, type: 'dashed' },
                    symbol: (val, params) => params.dataIndex === fiscalOverviewCagr.length - 1 ? 'circle' : 'none',
                    symbolSize: 5, itemStyle: { color: '#6B7280' },
                    label: {
                        show: true,
                        formatter: (p) => p.dataIndex === fiscalOverviewCagr.length - 1 ? 'Infl. base' : '',
                        position: 'bottom', color: '#6B7280', fontSize: 10,
                        backgroundColor: 'rgba(255,255,255,0.88)', padding: [2, 5], borderRadius: 3
                    },
                    z: 2
                }
            ]
        };
    }

    function buildYoyConfig() {
        return {
            title: [{
                text: '{base|─} {bl|Base}    {sq0|■} {l0|< 0% Decline}    {sq1|■} {l1|0–4% Steady}    {sq2|■} {l2|5–9% Expansion}    {sq3|■} {l3|10%+ High growth}',
                left: 'left', top: 4,
                textStyle: {
                    fontSize: 11, fontWeight: 400, color: '#231F20',
                    rich: {
                        base: { color: '#B4B2A9', fontSize: 12, fontWeight: 700 },
                        bl:   { color: '#888780', fontSize: 11 },
                        sq0:  { color: '#E24B4A', fontSize: 14, fontWeight: 900 },
                        l0:   { color: '#A32D2D', fontSize: 11, fontWeight: 600 },
                        sq1:  { color: '#9FE1CB', fontSize: 14, fontWeight: 900 },
                        l1:   { color: '#0F6E56', fontSize: 11, fontWeight: 600 },
                        sq2:  { color: '#1D9E75', fontSize: 14, fontWeight: 900 },
                        l2:   { color: '#085041', fontSize: 11, fontWeight: 600 },
                        sq3:  { color: '#EF9F27', fontSize: 14, fontWeight: 900 },
                        l3:   { color: '#BA7517', fontSize: 11, fontWeight: 600 }
                    }
                }
            }],
            grid: { top: '22%', right: '4%', bottom: '11%', left: '8%', containLabel: true },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255,255,255,0.97)',
                borderColor: '#E5E7EB', borderWidth: 1,
                textStyle: { color: '#231F20', fontSize: 12 },
                formatter: (params) => {
                    if (!params || params.length === 0) return '';
                    const p = params[0];
                    const v = Number(p.value) || 0;
                    const fy = p.axisValue;
                    if (v === 0) return `<b>FY${fy}</b><br/>Base year`;
                    const tier = v < 0
                        ? `<span style="color:#A32D2D">Budget contraction (${v.toFixed(1)}%)</span>`
                        : v >= 10
                            ? `<span style="color:#BA7517">High growth (10%+)</span>`
                            : v >= 5
                                ? `<span style="color:#1D9E75">Significant expansion (5–9%)</span>`
                                : `<span style="color:#0F6E56">Steady growth (0–4%)</span>`;
                    const covidNote = (fy === '2021' || fy === '2022')
                        ? '<br/><span style="color:#6321a5;font-size:11px;">Federal COVID relief injection</span>'
                        : '';
                    return `<b>FY${fy}</b><br/>${p.marker} YoY change: <b>${v.toFixed(1)}%</b><br/>${tier}${covidNote}`;
                }
            },
            xAxis: {
                type: 'category',
                data: yoyDetail.map((d) => String(d.fiscal_year)),
                axisLine: { lineStyle: { color: '#E5E7EB' } },
                axisTick: { show: false }
            },
            yAxis: {
                type: 'value',
                axisLabel: { formatter: (v) => `${Number(v).toFixed(0)}%`, fontSize: 11 },
                splitLine: { lineStyle: { color: '#F3F4F6' } }
            },
            series: [
                {
                    type: 'bar', barMaxWidth: 36,
                    data: yoyDetail.map((d) => Number(d.change_pct) || 0),
                    label: {
                        show: true, fontSize: 10, fontWeight: 600,
                        color: '#4B5563', position: 'outside',
                        formatter: (p) => {
                            const v = Number(p.value) || 0;
                            return v === 0 ? 'Base' : `${v.toFixed(1)}%`;
                        }
                    },
                    itemStyle: {
                        color: (p) => {
                            const v = Number(p.value) || 0;
                            if (v === 0) return '#B4B2A9';
                            if (v < 0) return '#E24B4A';
                            if (v >= 10) return '#EF9F27';
                            if (v >= 5) return '#1D9E75';
                            return '#9FE1CB';
                        }
                    }
                },
                {
                    name: 'covid_annotation', type: 'line', data: [],
                    markLine: {
                        silent: true, symbol: 'none',
                        data: [[
                            {
                                coord: ['2021', 14.5],
                                lineStyle: { color: 'rgba(99,33,165,0.5)', width: 1, type: 'dotted' },
                                label: { show: true, position: 'middle', formatter: 'Federal COVID relief', fontSize: 9, color: 'rgba(99,33,165,0.75)', fontStyle: 'italic' }
                            },
                            { coord: ['2022', 14.5] }
                        ]]
                    }
                }
            ]
        };
    }

    // Mirror the exact pattern from the working BudgetChangesChart:
    // divs are ALWAYS rendered, reactive block fires when container + data both exist
    onMount(() => {
        // Init charts on mount — same pattern as ParetoBarChart
        if (overviewEl) {
            overviewChart = echarts.init(overviewEl);
            if (fiscalOverviewCagr?.length > 0) overviewChart.setOption(buildTrendConfig(), true);
        }
        if (yoyEl) {
            yoyChart = echarts.init(yoyEl);
            if (yoyDetail?.length > 0) yoyChart.setOption(buildYoyConfig(), true);
        }
        const onResize = () => {
            overviewChart?.resize();
            yoyChart?.resize();
        };
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    });

    onDestroy(() => {
        overviewChart?.dispose();
        yoyChart?.dispose();
    });

    // Fires when data arrives after mount — same as ParetoBarChart
    $: if (overviewChart && fiscalOverviewCagr?.length > 0) {
        overviewChart.setOption(buildTrendConfig(), true);
    }
    $: if (yoyChart && yoyDetail?.length > 0) {
        yoyChart.setOption(buildYoyConfig(), true);
    }
</script>

<!-- Divs are ALWAYS in the DOM — no {#if} wrapper — so bind:this assigns immediately -->
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; width: 100%;">
    <div bind:this={overviewEl} style="width: 100%; height: {chartHeight};"></div>
    <div bind:this={yoyEl} style="width: 100%; height: {chartHeight};"></div>
</div>