<script>
    import * as echarts from 'echarts';
    import { onMount } from 'svelte';

    export let data = [];
    export let title = '';
    export let height = '420px';
    export let barField = 'spend';
    export let labelField = 'agency_name';
    export let pctField = 'pct_of_total';
    export let cumulativeField = 'cumulative';
    export let totalField = 'grand_total';

    let chartContainer;
    let chart;

    function getConfig() {
        return {
            title: { text: title, left: 'left', top: 10, textStyle: { fontSize: 18, fontWeight: 600, color: '#231F20' } },
            tooltip: {
                trigger: 'item',
                formatter: function(param) {
                    if (!param) return '';
                    const idx = param.dataIndex;
                    const row = data[idx];
                    if (!row) return '';
                    const spend = Number(row[barField]) || 0;
                    const money = Math.abs(spend) >= 1e9 ? '$' + (spend/1e9).toFixed(2) + 'B' : '$' + (spend/1e6).toFixed(1) + 'M';
                    const cumPct = ((Number(row[cumulativeField]) / Number(row[totalField])) * 100).toFixed(1);
                    return '<b>' + row[labelField] + '</b><br/>Budget: ' + money + '<br/>Share: ' + row[pctField] + '%<br/>Cumulative: ' + cumPct + '%';
                }
            },
            grid: { left: 16, right: 60, top: 70, bottom: 20, containLabel: true },
            xAxis: [{
                type: 'category',
                data: data.map(function(d) {
                    const n = d[labelField] || '';
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
                            const n = Number(v) || 0;
                            return Math.abs(n) >= 1e9 ? '$' + (n/1e9).toFixed(0) + 'B' : '$' + (n/1e6).toFixed(0) + 'M';
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
                    data: data.map(function(d) { return d[barField]; }),
                    itemStyle: { color: '#C8122C', borderRadius: 2 },
                    label: {
                        show: true, position: 'top', fontSize: 10, color: '#231F20',
                        formatter: function(p) {
                            const v = Number(p.value) || 0;
                            return Math.abs(v) >= 1e9 ? '$' + (v/1e9).toFixed(1) + 'B' : '$' + (v/1e6).toFixed(0) + 'M';
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
                    data: data.map(function(d) {
                        return ((Number(d[cumulativeField]) / Number(d[totalField])) * 100).toFixed(1);
                    }),
                    markPoint: {
                        symbol: 'circle',
                        symbolSize: 14,
                        data: [{
                            coord: (() => {
                                const idx = data.findIndex(function(d) {
                                    return ((Number(d[cumulativeField]) / Number(d[totalField])) * 100) >= 80;
                                });
                                return idx >= 0 ? [idx, ((Number(data[idx][cumulativeField]) / Number(data[idx][totalField])) * 100).toFixed(1)] : null;
                            })()
                        }].filter(function(d) { return d.coord !== null; }),
                        itemStyle: { color: '#231F20' },
                        label: { show: true, formatter: '80%', position: 'top', fontSize: 11, fontWeight: 700, color: '#231F20' }
                    }
                }
            ]
        };
    }

    onMount(() => {
        if (chartContainer && data?.length > 0) {
            chart = echarts.init(chartContainer);
            chart.setOption(getConfig());
            window.addEventListener('resize', () => chart?.resize());
            return () => window.removeEventListener('resize', () => chart?.resize());
        }
    });

    $: if (chart && data?.length > 0) {
        chart.setOption(getConfig());
    }
</script>

{#if data?.length > 0}
    <div bind:this={chartContainer} style="width:100%; height:{height};"></div>
{:else}
    <div style="text-align:center; color:#999; padding:20px;">No data available</div>
{/if}
