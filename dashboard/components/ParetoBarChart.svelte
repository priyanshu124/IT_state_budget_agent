<script>
    import * as echarts from 'echarts';
    import { onDestroy, onMount } from 'svelte';
    import ParetoInsight from './ParetoInsight.svelte';

    export let data = [];
    export let title = '';
    export let height = '420px';
    export let barField = 'spend';
    export let labelField = 'agency_name';
    export let pctField = 'pct_of_total';
    export let cumulativeField = 'cumulative';
    export let totalField = 'grand_total';
    export let drillable = false;
    export let drillUnitData = [];
    export let drillProgramData = [];
    export let drillSubprogramData = [];
    export let drillUnitField = 'unit_name';
    export let drillProgramField = 'program_name';
    export let drillSubprogramField = 'subprogram_name';

    let chartContainer;
    let chart;
    let chartClickHandler;
    let resizeHandler;
    let drillLevel = 'unit';
    let selectedUnit = '';
    let selectedProgram = '';

    function formatMoney(value) {
        const number = Number(value) || 0;
        if (Math.abs(number) >= 1e9) return '$' + (number / 1e9).toFixed(2) + 'B';
        if (Math.abs(number) >= 1e6) return '$' + (number / 1e6).toFixed(1) + 'M';
        if (Math.abs(number) >= 1e3) return '$' + (number / 1e3).toFixed(1) + 'K';
        return '$' + number.toFixed(0);
    }

    function getLabel(row) {
        return String(row?.label ?? row?.[labelField] ?? '').trim();
    }

    function getSpend(row) {
        return Number(row?.[barField] ?? row?.spend) || 0;
    }

    function getPct(row) {
        return Number(row?.[pctField] ?? row?.pct_of_total) || 0;
    }

    function getCumulativePct(row) {
        const cumulative = Number(row?.[cumulativeField] ?? row?.cumulative) || 0;
        const total = Number(row?.[totalField] ?? row?.grand_total) || 0;
        return total > 0 ? (cumulative * 100.0 / total) : 0;
    }

    function getDisplayRows(sourceRows, labelKey, filters = []) {
        const rows = (sourceRows ?? []).filter(function(row) {
            return filters.every(function(filterFn) {
                return filterFn(row);
            });
        });

        if (!rows.length) return [];

        const latestYear = rows.reduce(function(maxYear, row) {
            const year = Number(row?.fiscal_year);
            return Number.isFinite(year) && year > maxYear ? year : maxYear;
        }, -Infinity);

        if (!Number.isFinite(latestYear)) return [];

        const latestRows = rows.filter(function(row) {
            return Number(row?.fiscal_year) === latestYear;
        });

        const totalsByLabel = latestRows.reduce(function(acc, row) {
            const label = String(row?.[labelKey] ?? '').trim();
            if (!label) return acc;
            acc[label] = (acc[label] || 0) + getSpend(row);
            return acc;
        }, {});

        const ordered = Object.entries(totalsByLabel).sort(function(a, b) {
            return b[1] - a[1];
        });

        const grandTotal = ordered.reduce(function(sum, entry) {
            return sum + entry[1];
        }, 0);

        let cumulative = 0;

        return ordered.slice(0, 10).map(function(entry) {
            const label = entry[0];
            const spend = entry[1];
            cumulative += spend;
            return {
                label,
                spend,
                pct_of_total: grandTotal > 0 ? Number((spend * 100.0 / grandTotal).toFixed(1)) : 0,
                cumulative,
                grand_total: grandTotal,
                fiscal_year: latestYear
            };
        });
    }

    $: drillRows = drillable
        ? (drillLevel === 'program'
            ? getDisplayRows(drillProgramData, drillProgramField, [function(row) { return String(row?.[drillUnitField] ?? '') === selectedUnit; }])
            : drillLevel === 'subprogram'
                ? getDisplayRows(drillSubprogramData, drillSubprogramField, [
                    function(row) { return String(row?.[drillUnitField] ?? '') === selectedUnit; },
                    function(row) { return String(row?.[drillProgramField] ?? '') === selectedProgram; }
                ])
                : getDisplayRows(drillUnitData, drillUnitField))
        : (data ?? []);

    $: displayTitle = title || (!drillable
        ? ''
        : drillLevel === 'program'
            ? `Top 10 programs in ${selectedUnit} by budget — Latest Year`
            : drillLevel === 'subprogram'
                ? `Top 10 subprograms in ${selectedProgram} by budget — Latest Year`
                : 'Top 10 units by budget — Latest Year');

    $: entityLabel = drillLevel === 'program'
        ? 'programs'
        : drillLevel === 'subprogram'
            ? 'subprograms'
            : 'units';

    function goBack() {
        if (!drillable) return;
        if (drillLevel === 'subprogram') {
            drillLevel = 'program';
            selectedProgram = '';
            return;
        }
        if (drillLevel === 'program') {
            drillLevel = 'unit';
            selectedUnit = '';
        }e 
    }

    function getConfig() {
        return {
            title: { text: displayTitle, left: 'left', top: 10, textStyle: { fontSize: 18, fontWeight: 600, color: '#231F20' } },
            tooltip: {
                trigger: 'item',
                formatter: function(param) {
                    if (!param) return '';
                    const idx = param.dataIndex;
                    const row = drillRows[idx] || null;
                    if (!row) return '';
                    return '<b>' + getLabel(row) + '</b><br/>Budget: ' + formatMoney(getSpend(row)) + '<br/>Share: ' + getPct(row) + '%<br/>Cumulative: ' + getCumulativePct(row).toFixed(1) + '%';
                }
            },
            grid: { left: 16, right: 60, top: 70, bottom: 20, containLabel: true },
            xAxis: [{
                type: 'category',
                data: drillRows.map(function(d) {
                    const n = getLabel(d);
                    return n.length > 30 ? n.slice(0, 30) + '…' : n;
                }),
                axisLabel: { rotate: 35, fontSize: 10, color: '#231F20', interval: 0 }
            }],
            yAxis: [
                {
                    type: 'value',
                    name: 'Budget',
                    position: 'left',
                    axisLabel: {
                        formatter: function(v) {
                            return formatMoney(v);
                        }
                    },
                    splitLine: { lineStyle: { color: '#D9DDE3' } }
                },
                {
                    type: 'value',
                    name: 'Cumulative %',
                    min: 0,
                    max: 100,
                    position: 'right',
                    axisLabel: { formatter: function(v) { return v + '%'; } },
                    splitLine: { show: false }
                }
            ],
            series: [
                {
                    type: 'bar',
                    data: drillRows.map(function(d) { return getSpend(d); }),
                    itemStyle: { color: '#C8122C', borderRadius: 2 },
                    label: {
                        show: true, position: 'top', fontSize: 10, color: '#231F20',
                        formatter: function(p) {
                            return formatMoney(p.value);
                        }
                    },
                    yAxisIndex: 0
                },
                {
                    type: 'line',
                    name: 'Cumulative %',
                    yAxisIndex: 1,
                    smooth: false,
                    symbol: 'circle',
                    symbolSize: 6,
                    lineStyle: { color: '#FFC838', width: 2 },
                    itemStyle: { color: '#FFC838' },
                    label: {
                        show: true, position: 'top', fontSize: 10, color: '#B8860B',
                        formatter: function(p) { return (Number(p.value) || 0).toFixed(0) + '%'; }
                    },
                    data: drillRows.map(function(d) {
                        return getCumulativePct(d).toFixed(1);
                    }),
                    markPoint: {
                        symbol: 'circle',
                        symbolSize: 14,
                        data: [{
                            coord: (() => {
                                const idx = drillRows.findIndex(function(d) {
                                    return getCumulativePct(d) >= 80;
                                });
                                return idx >= 0 ? [idx, getCumulativePct(drillRows[idx]).toFixed(1)] : null;
                            })()
                        }].filter(function(d) { return d.coord !== null; }),
                        itemStyle: { color: '#231F20' },
                        label: { show: true, formatter: '80%', position: 'top', fontSize: 11, fontWeight: 700, color: '#231F20' }
                    }
                }
            ]
        };
    }

    function ensureChart() {
        if (!chartContainer || chart) return;
        chart = echarts.init(chartContainer);
        chartClickHandler = function(params) {
            if (!drillable || drillLevel === 'subprogram' || params?.seriesType !== 'bar') return;
            const row = drillRows?.[params.dataIndex];
            if (!row) return;
            if (drillLevel === 'unit') {
                selectedUnit = getLabel(row);
                selectedProgram = '';
                drillLevel = 'program';
                return;
            }
            if (drillLevel === 'program') {
                selectedProgram = getLabel(row);
                drillLevel = 'subprogram';
            }
        };
        chart.on('click', chartClickHandler);
        resizeHandler = function() {
            chart?.resize();
        };
        window.addEventListener('resize', resizeHandler);
    }

    function renderChart() {
        if (!chart || !drillRows?.length) return;
        chart.setOption(getConfig(), true);
    }

    onMount(() => {
        ensureChart();
        renderChart();
    });

    $: if (chartContainer && drillRows?.length > 0) {
        ensureChart();
        renderChart();
    }

    onDestroy(() => {
        if (chart && chartClickHandler) {
            chart.off('click', chartClickHandler);
        }
        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
        }
        chart?.dispose();
    });
</script>

{#if drillRows?.length > 0}
    {#if drillable}
        <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin: 0 0 10px 0; flex-wrap:wrap;">
            <ParetoInsight data={drillRows} {entityLabel} />
            <div>
                {#if drillLevel !== 'unit'}
                    <button
                        type="button"
                        on:click={goBack}
                        style="border:1px solid #d6c1f5; background:linear-gradient(90deg,#f8f2ff,#ede0fc); color:#802cd7; border-radius:999px; padding:7px 14px; font-size:0.85rem; font-weight:700; cursor:pointer;"
                >
                    Back
                </button>
                {/if}
            </div>
        </div>
    {/if}
    <div bind:this={chartContainer} style="width:100%; height:{height};"></div>
{:else}
    <div style="text-align:center; color:#999; padding:20px;">No data available</div>
{/if}
