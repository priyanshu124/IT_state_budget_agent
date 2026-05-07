<script>
    import * as echarts from 'echarts';
    import { onMount } from 'svelte';

    export let data = [];
    export let labelField = 'label';
    export let title = 'Budget Changes — Year over Year';
    export let height = '520px';
    export let limit = 10;

    let chartContainer;
    let chart;

    function buildChartData(rows) {
        const gainers = rows
            .filter(function(d) { return (d.dollar_change || 0) > 0; })
            .sort(function(a, b) { return (b.dollar_change || 0) - (a.dollar_change || 0); })
            .slice(0, limit)
            .map(function(d) { return Object.assign({}, d, { type: 'increase' }); });

        const losers = rows
            .filter(function(d) { return (d.dollar_change || 0) < 0; })
            .sort(function(a, b) { return (a.dollar_change || 0) - (b.dollar_change || 0); })
            .slice(0, limit)
            .map(function(d) { return Object.assign({}, d, { type: 'decrease' }); });

        return gainers.concat(losers)
            .sort(function(a, b) { return (b.dollar_change || 0) - (a.dollar_change || 0); });
    }

    function fmtMoney(v) {
        const abs = Math.abs(v);
        return abs >= 1e9 ? '$' + (abs / 1e9).toFixed(1) + 'B' : '$' + (abs / 1e6).toFixed(0) + 'M';
    }

    function getConfig(chartData) {
        return {
            title: {
                text: title,
                left: 'left',
                top: 0,
                textStyle: { fontSize: 14, fontWeight: 600, color: '#231F20' }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function(params) {
                    if (!params || params.length === 0) return '';
                    const idx = params[0].dataIndex;
                    const row = chartData.slice().reverse()[idx];
                    if (!row) return '';
                    const v = Number(row.dollar_change) || 0;
                    const money = fmtMoney(v);
                    const pctStr = row.pct_change != null
                        ? (row.pct_change > 0 ? '+' : '') + row.pct_change + '%'
                        : 'N/A';
                    return '<b>' + row[labelField] + '</b><br/>Change: '
                        + (v >= 0 ? '+' : '-') + money
                        + '<br/>YoY: ' + pctStr;
                }
            },
            grid: { left: 16, right: 120, top: 40, bottom: 20, containLabel: true },
            xAxis: {
                type: 'value',
                axisLine: { show: true, lineStyle: { color: '#231F20', width: 1.5 } },
                axisLabel: {
                    formatter: function(v) {
                        const n = Number(v) || 0;
                        return Math.abs(n) >= 1e9
                            ? '$' + (n / 1e9).toFixed(1) + 'B'
                            : '$' + (n / 1e6).toFixed(0) + 'M';
                    },
                    color: '#6B7280',
                    fontSize: 11
                },
                splitLine: { lineStyle: { color: '#E5E7EB', type: 'dashed' } }
            },
            yAxis: {
                type: 'category',
                data: chartData.map(function(d) { return d[labelField]; }).reverse(),
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    width: 220,
                    overflow: 'truncate',
                    fontSize: 11,
                    color: '#231F20',
                    align: 'right',
                    formatter: function(name) {
                        return name && name.length > 30 ? name.slice(0, 30) + '…' : name;
                    }
                }
            },
            series: [{
                type: 'bar',
                barMaxWidth: 24,
                data: chartData.map(function(d) { return d.dollar_change || 0; }).reverse(),
                label: {
                    show: true,
                    position: function(params) { return Number(params.value) >= 0 ? 'right' : 'left'; },
                    distance: 8,
                    padding: [2, 4],
                    backgroundColor: 'rgba(255,255,255,0.85)',
                    borderRadius: 2,
                    formatter: function(params) {
                        const v = Number(params.value) || 0;
                        const abs = Math.abs(v);
                        const money = (v >= 0 ? '+' : '-') + fmtMoney(v);
                        const idx = params.dataIndex;
                        const row = chartData.slice().reverse()[idx];
                        const pct = row && row.pct_change != null
                            ? ' (' + (row.pct_change > 0 ? '+' : '') + row.pct_change + '%)'
                            : '';
                        return money + pct;
                    },
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#231F20'
                },
                itemStyle: {
                    color: function(params) { return Number(params.value) >= 0 ? '#2EAD6B' : '#C8122C'; },
                    borderRadius: 2
                },
                markLine: {
                    silent: true,
                    symbol: ['none', 'none'],
                    lineStyle: { color: '#231F20', width: 1.5, type: 'solid' },
                    label: { show: false },
                    data: [{ xAxis: 0 }]
                }
            }]
        };
    }

    $: chartData = buildChartData(data || []);

    onMount(() => {
        if (chartContainer) {
            chart = echarts.init(chartContainer);
            if (chartData.length > 0) chart.setOption(getConfig(chartData), true);
        }
        const onResize = () => chart?.resize();
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    });

    // Explicitly read chartData and labelField so Svelte tracks both as dependencies.
    // This fires whenever data changes (filter) or labelField changes (view toggle).
    $: if (chart && (chartData, labelField)) {
        if (chartData.length > 0) {
            chart.setOption(getConfig(chartData), true);
        } else {
            chart.clear();
        }
    }
</script>

{#if chartData.length > 0}
    <div bind:this={chartContainer} style="width:100%; height:{height};"></div>
{:else}
    <div style="text-align:center; color:#9CA3AF; padding:32px; font-size:0.9rem;">No budget change data available.</div>
{/if}