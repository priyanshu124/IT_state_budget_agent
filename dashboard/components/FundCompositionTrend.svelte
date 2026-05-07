<script>
    import * as echarts from 'echarts';
    import { onMount, onDestroy } from 'svelte';

    export let fundTrend = [];
    export let fundTrendYears = [];
    export let fundSeriesNames = [];
    export let fundSeriesTotals = {};

    let chartEl;
    let chart;
    let activeView = 'composition';
    let selectedFund = null;

    const covidYears = ['2020', '2021', '2022'];

    const isCovid = (name) => {
        const n = (name || '').toLowerCase();
        return n.includes('covid') || n.includes('american rescue') || n.includes('coronavirus') || n.includes('cares') || n.includes('crrsa') || n.includes('arra');
    };

    function getFundColor(name) {
        return fundTrend.find(d => d.fund_type === name)?.fund_color ?? '#4C4743';
    }

    function getSeriesData(name) {
        return fundTrendYears.map(y => {
            const row = fundTrend.find(d => String(d.fiscal_year) === y && d.fund_type === name);
            return row ? row.spend : 0;
        });
    }

    function getYearTotal(y) {
        return fundTrend
            .filter(d => String(d.fiscal_year) === y)
            .reduce((s, d) => s + (Number(d.spend) || 0), 0);
    }

    function calcCAGR(name) {
        const data = getSeriesData(name);
        const valid = data.filter(v => v > 0);
        if (valid.length < 2) return null;
        const first = data.find(v => v > 0);
        const last = [...data].reverse().find(v => v > 0);
        const years = data.length - 1;
        if (!first || !last || years <= 0) return null;
        return ((Math.pow(last / first, 1 / years) - 1) * 100).toFixed(1);
    }

    function usd(v) {
        const n = Number(v) || 0;
        if (Math.abs(n) >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
        if (Math.abs(n) >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
        return '$' + Math.round(n).toLocaleString();
    }

    // Insight cards computed from data
    $: coreNames = fundSeriesNames.filter(n => !isCovid(n));
    $: covidNames = fundSeriesNames.filter(n => isCovid(n));

    $: largestFund = (() => {
        if (!coreNames.length) return null;
        return coreNames.reduce((best, n) => {
            const tot = fundSeriesTotals[n] || 0;
            return tot > (fundSeriesTotals[best] || 0) ? n : best;
        }, coreNames[0]);
    })();

    $: fastestFund = (() => {
        if (!coreNames.length) return null;
        return coreNames.reduce((best, n) => {
            const cagr = parseFloat(calcCAGR(n) || '-999');
            const bestCagr = parseFloat(calcCAGR(best) || '-999');
            return cagr > bestCagr ? n : best;
        }, coreNames[0]);
    })();

    $: covidPeak = (() => {
        let peak = 0;
        covidNames.forEach(n => {
            getSeriesData(n).forEach(v => { if (v > peak) peak = v; });
        });
        return peak;
    })();

    $: largestShareLatest = (() => {
        const lastY = fundTrendYears[fundTrendYears.length - 1];
        if (!lastY) return null;
        const total = getYearTotal(lastY);
        if (!total) return null;
        const data = getSeriesData(largestFund);
        const val = data[data.length - 1] || 0;
        return total > 0 ? ((val / total) * 100).toFixed(1) : null;
    })();

    $: fastestCAGR = fastestFund ? calcCAGR(fastestFund) : null;

    function buildCompositionConfig() {
        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function(params) {
                    if (!params || !params.length) return '';
                    const ay = params[0].axisValue;
                    const yearTotal = getYearTotal(ay);
                    const rows = params.slice()
                        .sort((a, b) => (fundSeriesTotals[b.seriesName] || 0) - (fundSeriesTotals[a.seriesName] || 0))
                        .map(p => {
                            const v = Number(p.value) || 0;
                            const pct = yearTotal > 0 ? ((v / yearTotal) * 100).toFixed(1) : '0.0';
                            return p.marker + ' ' + p.seriesName + ': ' + usd(v) + ' (' + pct + '%)';
                        });
                    return '<b>FY' + ay + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 64, right: 24, top: 20, bottom: 36 },
            xAxis: { type: 'category', boundaryGap: false, data: fundTrendYears, axisLabel: { fontSize: 11 } },
            yAxis: {
                type: 'value',
                axisLabel: { formatter: v => Math.abs(v) >= 1e9 ? '$' + (v/1e9).toFixed(0) + 'B' : '$' + (v/1e6).toFixed(0) + 'M', fontSize: 11 },
                splitLine: { lineStyle: { color: '#E5E7EB' } }
            },
            series: fundSeriesNames.map(name => {
                const color = getFundColor(name);
                const hasSelection = Boolean(selectedFund);
                const isSelected = !hasSelection || selectedFund === name;
                return {
                    name,
                    type: 'line',
                    stack: 'total',
                    smooth: false,
                    symbol: 'none',
                    lineStyle: { width: 0 },
                    itemStyle: { color, opacity: 0 },
                    areaStyle: { color, opacity: isSelected ? 0.85 : 0.06 },
                    emphasis: { focus: 'series' },
                    data: getSeriesData(name)
                };
            })
        };
    }

    function buildGrowthConfig() {
        return {
            tooltip: {
                trigger: 'axis',
                formatter: function(params) {
                    if (!params || !params.length) return '';
                    const ay = params[0].axisValue;
                    const rows = params
                        .filter(p => Number(p.value) > 0)
                        .sort((a, b) => (Number(b.value) || 0) - (Number(a.value) || 0))
                        .map(p => p.marker + ' ' + p.seriesName + ': ' + usd(p.value));
                    return '<b>FY' + ay + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 64, right: 120, top: 20, bottom: 36 },
            xAxis: {
                type: 'category', boundaryGap: false, data: fundTrendYears,
                axisLabel: { fontSize: 11 },
                markArea: covidYears.length >= 2 ? {} : undefined
            },
            yAxis: {
                type: 'value',
                axisLabel: { formatter: v => Math.abs(v) >= 1e9 ? '$' + (v/1e9).toFixed(1) + 'B' : '$' + (v/1e6).toFixed(0) + 'M', fontSize: 11 },
                splitLine: { lineStyle: { color: '#E5E7EB' } }
            },
            series: [
                // COVID shading as markArea on first series
                ...fundSeriesNames.map((name, i) => {
                    const color = getFundColor(name);
                    const hasSelection = Boolean(selectedFund);
                    const isSelected = !hasSelection || selectedFund === name;
                    const isCovidFund = isCovid(name);
                    const cagr = calcCAGR(name);
                    const data = getSeriesData(name);
                    const lastVal = data[data.length - 1] || 0;
                    return {
                        name,
                        type: 'line',
                        smooth: true,
                        symbol: 'circle',
                        symbolSize: 4,
                        lineStyle: {
                            color,
                            width: isCovidFund ? 1.5 : 2,
                            type: isCovidFund ? 'dashed' : 'solid',
                            opacity: isSelected ? 1 : 0.08
                        },
                        itemStyle: { color, opacity: isSelected ? 1 : 0.08 },
                        endLabel: {
                            show: isSelected || !selectedFund,
                            formatter: p => {
                                const short = name.length > 14 ? name.slice(0, 13) + '…' : name;
                                return short + (cagr ? '\n' + (cagr > 0 ? '+' : '') + cagr + '%' : '');
                            },
                            color,
                            fontSize: 10,
                            lineHeight: 14
                        },
                        markArea: i === 0 ? {
                            silent: true,
                            itemStyle: { color: 'rgba(245,158,11,0.07)' },
                            label: { show: false },
                            data: [[
                                { xAxis: '2020' },
                                { xAxis: '2022' }
                            ]]
                        } : undefined,
                        data
                    };
                })
            ]
        };
    }

    function buildShareConfig() {
        return {
            tooltip: {
                trigger: 'axis',
                formatter: function(params) {
                    if (!params || !params.length) return '';
                    const ay = params[0].axisValue;
                    const rows = params
                        .filter(p => Number(p.value) > 0)
                        .sort((a, b) => (Number(b.value) || 0) - (Number(a.value) || 0))
                        .map(p => p.marker + ' ' + p.seriesName + ': ' + Number(p.value).toFixed(1) + '%');
                    return '<b>FY' + ay + '</b><br/>' + rows.join('<br/>');
                }
            },
            grid: { left: 48, right: 24, top: 20, bottom: 36 },
            xAxis: { type: 'category', boundaryGap: false, data: fundTrendYears, axisLabel: { fontSize: 11 } },
            yAxis: {
                type: 'value', min: 0, max: 100,
                axisLabel: { formatter: v => v + '%', fontSize: 11 },
                splitLine: { lineStyle: { color: '#E5E7EB' } }
            },
            series: [
                ...fundSeriesNames.map((name, i) => {
                    const color = getFundColor(name);
                    const hasSelection = Boolean(selectedFund);
                    const isSelected = !hasSelection || selectedFund === name;
                    const shareData = fundTrendYears.map(y => {
                        const total = getYearTotal(y);
                        const row = fundTrend.find(d => String(d.fiscal_year) === y && d.fund_type === name);
                        const val = row ? row.spend : 0;
                        return total > 0 ? parseFloat(((val / total) * 100).toFixed(2)) : 0;
                    });
                    return {
                        name,
                        type: 'line',
                        stack: 'pct',
                        smooth: false,
                        symbol: 'none',
                        lineStyle: { width: 0 },
                        itemStyle: { color, opacity: 0 },
                        areaStyle: { color, opacity: isSelected ? 0.85 : 0.06 },
                        emphasis: { focus: 'series' },
                        markArea: i === 0 ? {
                            silent: true,
                            itemStyle: { color: 'rgba(245,158,11,0.09)', borderColor: '#F59E0B', borderWidth: 0.5 },
                            label: { show: true, position: 'top', formatter: 'COVID era', fontSize: 9, color: '#92400E' },
                            data: [[{ xAxis: '2020' }, { xAxis: '2022' }]]
                        } : undefined,
                        data: shareData
                    };
                })
            ]
        };
    }

    // Svelte tracks variables read at the TOP LEVEL of a $: block.
    // By reading activeView and selectedFund directly here (not inside a function),
    // any change to either will recompute currentConfig and re-render the chart.
    $: currentConfig = (() => {
        const _view = activeView;   // explicit read → Svelte tracks activeView
        const _sel = selectedFund;  // explicit read → Svelte tracks selectedFund
        if (!fundTrend?.length) return null;
        if (_view === 'growth') return buildGrowthConfig();
        if (_view === 'share') return buildShareConfig();
        return buildCompositionConfig();
    })();

    $: if (chart && currentConfig) {
        chart.setOption(currentConfig, true);
    }

    onMount(() => {
        if (chartEl) {
            chart = echarts.init(chartEl);
            if (currentConfig) chart.setOption(currentConfig, true);
        }
        const onResize = () => chart?.resize();
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    });

    onDestroy(() => chart?.dispose());

    function toggleFund(name) {
        selectedFund = selectedFund === name ? null : name;
    }
</script>

<div style="font-family: var(--font-sans, sans-serif);">

    <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
        <div style="display:flex; border:1px solid var(--nxt-border, #E5E7EB); border-radius:8px; overflow:hidden;">
            {#each [['composition','Composition ($)'],['growth','Growth lines'],['share','Share (%)']] as [v, label]}
                <button
                    on:click={() => { activeView = v; selectedFund = null; }}
                    style={'padding:6px 14px; font-size:0.82rem; cursor:pointer; border:none; border-right:1px solid var(--nxt-border,#E5E7EB); background:' + (activeView === v ? '#802cd7' : 'var(--nxt-surface,#fff)') + '; color:' + (activeView === v ? '#fff' : '#231F20') + '; font-weight:' + (activeView === v ? 600 : 400)}
                >{label}</button>
            {/each}
        </div>
        
    </div>

    <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px;">
        {#each fundSeriesNames as name}
            {@const color = getFundColor(name)}
            {@const cagr = calcCAGR(name)}
            {@const cagrNum = cagr ? parseFloat(cagr) : 0}
            {@const isSelected = !selectedFund || selectedFund === name}
            <button
                on:click={() => toggleFund(name)}
                style={'display:inline-flex; align-items:center; gap:6px; padding:4px 10px; font-size:0.78rem; cursor:pointer; border-radius:20px; border:' + (selectedFund === name ? '2px solid ' + color : '1px solid var(--nxt-border,#E5E7EB)') + '; background:' + (selectedFund === name ? 'rgba(0,0,0,0.04)' : 'var(--nxt-surface,#fff)') + '; opacity:' + (isSelected ? 1 : 0.4) + '; transition:opacity .15s;'}
            >
                <span style={'width:8px;height:8px;border-radius:50%;background:' + color + ';flex-shrink:0;' + (isCovid(name) ? 'opacity:0.6;' : '')}></span>
                <span style={'color:#231F20;font-weight:' + (selectedFund === name ? 600 : 400)}>{name}</span>
                {#if cagr && activeView !== 'composition'}
                    <span style={'font-size:0.7rem;padding:1px 4px;border-radius:3px;font-weight:500;background:' + (cagrNum > 3 ? '#EAF3DE' : cagrNum < 0 ? '#FCEBEB' : '#F1EFE8') + ';color:' + (cagrNum > 3 ? '#3B6D11' : cagrNum < 0 ? '#A32D2D' : '#5F5E5A')}>{cagrNum > 0 ? '+' : ''}{cagr}%</span>
                {/if}
            </button>
        {/each}
    </div>

    <div bind:this={chartEl} style="width:100%; height:420px;"></div>

    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:12px;">
        {#if largestFund}
            <div style="background:var(--nxt-surface,#fff); border:0.5px solid var(--nxt-border,#E5E7EB); border-radius:8px; padding:10px 12px;">
                <div style="font-size:10px; color:#6B7280; margin-bottom:3px;">Largest fund source</div>
                <div style="font-size:13px; font-weight:600; color:#231F20; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{largestFund}</div>
                <div style="font-size:10px; color:#3B6D11; margin-top:2px;">{largestShareLatest ? largestShareLatest + '% of total · ' : ''}{calcCAGR(largestFund) ? '+' + calcCAGR(largestFund) + '% CAGR' : ''}</div>
            </div>
        {/if}
        {#if fastestFund}
            <div style="background:var(--nxt-surface,#fff); border:0.5px solid var(--nxt-border,#E5E7EB); border-radius:8px; padding:10px 12px;">
                <div style="font-size:10px; color:#6B7280; margin-bottom:3px;">Fastest growing</div>
                <div style="font-size:13px; font-weight:600; color:#231F20; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{fastestFund}</div>
                <div style="font-size:10px; color:#3B6D11; margin-top:2px;">{fastestCAGR ? '+' + fastestCAGR + '% CAGR over period' : ''}</div>
            </div>
        {/if}
        {#if covidPeak > 0}
            <div style="background:#FFF8E1; border:0.5px solid #F59E0B; border-radius:8px; padding:10px 12px;">
                <div style="font-size:10px; color:#92400E; margin-bottom:3px;">COVID peak injection</div>
                <div style="font-size:13px; font-weight:600; color:#231F20;">{usd(covidPeak)}</div>
                <div style="font-size:10px; color:#92400E; margin-top:2px;">FY2020–2022 · temporary</div>
            </div>
        {:else}
            <div style="background:var(--nxt-surface,#fff); border:0.5px solid var(--nxt-border,#E5E7EB); border-radius:8px; padding:10px 12px;">
                <div style="font-size:10px; color:#6B7280; margin-bottom:3px;">Fund sources</div>
                <div style="font-size:13px; font-weight:600; color:#231F20;">{fundSeriesNames.length}</div>
                <div style="font-size:10px; color:#6B7280; margin-top:2px;">across {fundTrendYears.length} fiscal years</div>
            </div>
        {/if}
    </div>
</div>