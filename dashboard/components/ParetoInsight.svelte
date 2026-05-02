<script>
 
    import InsightBanner from './InsightBanner.svelte';
    export let data = [];
    export let entityLabel = 'items';

    $: insight = (() => {
        if (!data || data.length === 0) return '';
        
        const grandTotal = Number(data[0]?.grand_total) || 0;
        if (grandTotal === 0) return '';

        // How much do top 10 represent of ALL items (not just top 10)
        const top10Total = data.reduce(function(sum, d) { return sum + (Number(d.spend) || 0); }, 0);
        const top10Pct = ((top10Total / grandTotal) * 100).toFixed(0);

        // Where does 80% threshold hit within the top 10
        const threshold = data.findIndex(function(d) {
            return ((Number(d.cumulative) / grandTotal) * 100) >= 80;
        });

        if (threshold >= 0) {
            const count = threshold + 1;
            const pct = ((Number(data[threshold].cumulative) / grandTotal) * 100).toFixed(0);
            return pct + '% of total budget is concentrated in the top ' + count + ' ' + (count === 1 ? entityLabel.replace(/s$/, '') : entityLabel);
        } else {
            // 80% threshold not reached within top 10
            return 'Top 10 ' + entityLabel + ' account for ' + top10Pct + '% of total budget';
        }
    })();
</script>

<InsightBanner {insight} icon="📊"/>