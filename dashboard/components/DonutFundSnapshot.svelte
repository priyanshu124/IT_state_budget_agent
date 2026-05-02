<script>
    import * as echarts from 'echarts';
    import { onMount } from 'svelte';

    export let data = [];
    export let fund_profile = [];
    export let title = '';
    export let height = '420px';
    export let nameField = 'fund_type';
    export let valueField = 'latest_budget';
    export let pctField = 'latest_year_pct';

    let chartContainer;
    let chart;

    function getConfig() {
        const colors = (data || []).map(function(d) { return d.fund_color ?? '#4C4743'; });
        return {
            color: colors,
            title: { text: title, left: 'left', top: 10, textStyle: { fontSize: 14, fontWeight: 600, color: '#231F20' } },
            tooltip: {
                trigger: 'item',
                formatter: function(param) {
                    if (!param || !param.data) return '';
                    const row = data.find(function(d) { return d[nameField] === param.name; });
                    if (!row) return param.name;
                    const budget = Math.abs(row[valueField]) >= 1e9
                        ? '$' + (row[valueField]/1e9).toFixed(2) + 'B'
                        : '$' + (row[valueField]/1e6).toFixed(1) + 'M';
                    const yoy = row.yoy_change_pct != null
                        ? (row.yoy_change_pct > 0 ? '+' : '') + row.yoy_change_pct + '%'
                        : 'N/A';
                    const absChange = Math.abs(row.dollar_change || 0);
                    const dollarChange = (row.dollar_change || 0) >= 0
                        ? '+$' + (absChange >= 1e9 ? (absChange/1e9).toFixed(2) + 'B' : (absChange/1e6).toFixed(1) + 'M')
                        : '-$' + (absChange >= 1e9 ? (absChange/1e9).toFixed(2) + 'B' : (absChange/1e6).toFixed(1) + 'M');
                    const pct = row[pctField] != null ? row[pctField] + '%' : '';
                    return '<b>' + param.name + '</b><br/>'
                        + 'Budget: ' + budget + '<br/>'
                        + 'Share: ' + pct + '<br/>'
                        + 'YoY: ' + yoy + ' (' + dollarChange + ')';
                }
            },
            legend: {
                type: 'scroll',
                orient: 'horizontal',
                left: 'center',
                top: 28,
                textStyle: { fontSize: 11 },
                formatter: function(name) { return name && name.length > 26 ? name.slice(0, 26) + '…' : name; }
            },
            series: [{
                type: 'pie',
                radius: ['38%', '68%'],
                center: ['50%', '60%'],
                avoidLabelOverlap: true,
                minAngle: 2,
                itemStyle: { borderColor: '#FFFFFF', borderWidth: 2 },
                label: { formatter: function(p) { return p.percent >= 4 ? p.percent + '%' : ''; } },
                emphasis: {
                    label: { show: true, fontSize: 13, fontWeight: 700 },
                    itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.2)' }
                },
                data: (data || []).map(function(d) {
                    return { name: d[nameField], value: d[valueField] };
                })
            }]
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