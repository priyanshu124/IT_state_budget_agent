<script>
    export let targetId = 'page-filters';
    export let title = '⚙ Filters';

    function scrollToFilters() {
        const el = document.getElementById(targetId);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            const details = el.querySelector('details');
            if (details) details.open = true;
        }
    }
</script>

<div style="position:fixed; top:120px; right:0; z-index:999;">
    <button
        on:click={scrollToFilters}
        style="writing-mode:vertical-rl; text-orientation:mixed; padding:16px 10px; background:#C8122C; color:white; border:none; cursor:pointer; font-size:0.8rem; font-weight:700; letter-spacing:0.06em; border-radius:10px 0 0 10px; box-shadow:-3px 0 12px rgba(200,18,44,0.3); white-space:nowrap;"
    >{title}</button>
</div>