<script>
    import * as echarts from 'echarts';
    import { onMount } from 'svelte';

    export let data = [];
    export let labelField = 'agency_name';
    export let valueField = 'change_pct';
    export let title = 'Budget Variance (%)';
    export let height = '500px';
    export let limit = 12;
    export let threshold = 10;

    let chartContainer;
    let chart;

    function buildRows(rows, threshold) {
        const valid = (rows || []).filter(function(d) { return d[valueField] != null && isFinite(Number(d[valueField])); });
        const gainers = valid
            .filter(function(d) { return Number(d[valueField]) >= threshold; })
            .sort(function(a, b) { return Number(b[valueField]) - Number(a[valueField]); })
            .slice(0, limit);
        const losers = valid
            .filter(function(d) { return Number(d[valueField]) <= -threshold; })
            .sort(function(a, b) { return Number(a[valueField]) - Number(b[valueField]); })
            .slice(0, limit);
        // interleave: losers (most negative first) then gainers (most positive last)
        return losers.concat(gainers.slice().reverse());
    }

    function truncate(s, n) {
        return s && s.length > n ? s.slice(0, n) + '…' : (s || '');
    }

    function getConfig(rows) {
        const labels = rows.map(function(d) { return d[labelField]; });
        const values = rows.map(function(d) { return Number(d[valueField]); });

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
                    if (!params || !params[0]) return '';
                    const p = params[0];
                    const v = Number(p.value);
                    return '<b>' + p.name + '</b><br/>Change: ' + (v > 0 ? '+' : '') + v.toFixed(1) + '%';
                }
            },
            grid: { left: 16, right: 80, top: 48, bottom: 12, containLabel: true },
            xAxis: {
                type: 'value',
                axisLabel: {
                    formatter: function(v) { return v + '%'; },
                    color: '#6B7280',
                    fontSize: 11
                },
                splitLine: { lineStyle: { color: '#E5E7EB', type: 'dashed' } },
                axisLine: { show: true, lineStyle: { color: '#231F20', width: 1.5 } }
            },
            yAxis: {
                type: 'category',
                data: labels,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    width: 200,
                    overflow: 'truncate',
                    fontSize: 11,
                    color: '#374151',
                    align: 'right',
                    formatter: function(name) { return truncate(name, 32); }
                }
            },
            series: [{
                type: 'bar',
                barMaxWidth: 22,
                data: values,
                itemStyle: {
                    color: function(params) {
                        const v = Number(params.value);
                        if (v >= threshold) return '#2EAD6B';
                        if (v <= -threshold) return '#C8122C';
                        return '#9CA3AF';
                    },
                    borderRadius: 2
                },
                label: {
                    show: true,
                    position: function(params) { return Number(params.value) >= 0 ? 'right' : 'left'; },
                    distance: 6,
                    padding: [2, 4],
                    backgroundColor: 'rgba(255,255,255,0.85)',
                    borderRadius: 2,
                    fontSize: 11,
                    fontWeight: 600,
                    color: '#231F20',
                    formatter: function(params) {
                        const n = Number(params.value);
                        return (n > 0 ? '+' : '') + n.toFixed(1) + '%';
                    }
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

    $: chartRows = buildRows(data, threshold);

    onMount(function() {
        var onResize = function() { if (chart) chart.resize(); };
        window.addEventListener('resize', onResize);
        return function() { window.removeEventListener('resize', onResize); };
    });

    $: if (chartContainer) {
        if (!chart) chart = echarts.init(chartContainer);
        if (chartRows.length > 0) chart.setOption(getConfig(chartRows), true);
    }
</script>

<div bind:this={chartContainer} style="width:100%; height:{height};"></div>
