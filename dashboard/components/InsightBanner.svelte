<script>
    export let insight = '';
    export let icon = '📊';
    export let color = '#C8122C';
    export let bg = 'var(--nxt-pink)';
</script>

{#if insight}
    <div style={'display:inline-flex; align-items:center; gap:8px; background:' + bg + '; border-left:4px solid ' + color + '; border-radius:0 6px 6px 0; padding:8px 14px; margin-bottom:12px;'}>
        <span style="font-size:1.1rem;">{icon}</span>
        <span style={'font-size:0.9rem; font-weight:600; color:' + color + ';'}>{insight}</span>
    </div>
{/if}