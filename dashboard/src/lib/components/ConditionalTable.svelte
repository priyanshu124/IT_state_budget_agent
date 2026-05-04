<script>
    export let data = [];
    export let columns = [];
    export let linkField = null;
    export let totalRow = null;
    export let search = true;
    export let rows = 0;
    export let defaultSort = null;
    export let defaultDir = -1;

    let tableSearch = '';
    let sortCol = defaultSort;
    let sortDir = defaultDir;

    const setSort = (col) => {
        if (sortCol === col) sortDir = sortDir * -1;
        else { sortCol = col; sortDir = defaultDir ?? -1; }
    };

    const fmtMoney = (v) => {
        const n = Number(v) || 0;
        const abs = Math.abs(n);
        if (abs >= 1e9) return '$' + (n/1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return '$' + (n/1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return '$' + (n/1e3).toFixed(0) + 'K';
        return '$' + n.toLocaleString();
    };

    const fmtPct = (v) => (v == null ? '-' : (Number(v) > 0 ? '+' : '') + String(v) + '%');

    const conditionalStyle = (val) => {
        if (val == null) return { background: 'transparent', color: 'var(--nxt-muted)' };
        const n = Number(val);
        const color = n >= 0 ? '#1A7340' : '#C8122C';
        let bg = 'transparent';
        if (n >= 15) bg = 'rgba(46,173,107,0.16)';
        else if (n >= 8) bg = 'rgba(46,173,107,0.10)';
        else if (n >= 3) bg = 'rgba(46,173,107,0.05)';
        else if (n >= 0) bg = 'rgba(46,173,107,0.025)';
        else if (n >= -3) bg = 'rgba(200,18,44,0.035)';
        else if (n >= -8) bg = 'rgba(200,18,44,0.065)';
        else if (n >= -15) bg = 'rgba(200,18,44,0.11)';
        else bg = 'rgba(200,18,44,0.17)';
        return { background: bg, color };
    };

    $: filtered = tableSearch
        ? (data ?? []).filter(r => String(r[columns[0]?.id] ?? '').toLowerCase().includes(tableSearch.toLowerCase()))
        : (data ?? []);

    $: sorted = sortCol
        ? filtered.slice().sort((a,b) => {
            const aVal = a[sortCol] ?? (sortDir === -1 ? -Infinity : Infinity);
            const bVal = b[sortCol] ?? (sortDir === -1 ? -Infinity : Infinity);
            if (sortCol === columns[0]?.id) return sortDir * String(aVal).localeCompare(String(bVal));
            return sortDir * (Number(bVal) - Number(aVal));
        })
        : filtered;

    $: displayed = rows && rows > 0 ? sorted.slice(0, rows) : sorted;
</script>

{#if search}
    <div style="margin-bottom:12px;">
        <input bind:value={tableSearch} placeholder="Search..." style="border:1px solid var(--nxt-border); border-radius:8px; padding:8px 12px; width:320px; background:var(--nxt-surface); color:var(--nxt-text);" />
    </div>
{/if}

<div style="overflow-x:auto; border-radius:8px; border:1px solid var(--nxt-border); background:var(--nxt-surface);">
    <table style="width:100%; border-collapse:collapse; font-size:0.875rem;">
        <thead>
            <tr style="background:var(--nxt-pink); border-bottom:2px solid #C8122C;">
                {#each columns as col}
                    <th
                        on:click={() => col.sortable !== false && setSort(col.id)}
                        style="padding:10px 14px; font-weight:700; color:#231F20; cursor:pointer; text-align:{col.align ?? 'right'}; user-select:none;"
                    >
                        {@html col.title}
                        {#if sortCol === col.id}{sortDir === -1 ? '↓' : '↑'}{/if}
                    </th>
                {/each}
                {#if !columns.length}<th></th>{/if}
            </tr>
        </thead>
        <tbody>
            {#if totalRow}
                <tr style="background:var(--nxt-pink); border-bottom:1px solid var(--nxt-border);">
                    {#each columns as col}
                        <td style="padding:10px 14px; font-weight:700; color:#C8122C; text-align:{col.align ?? 'right'};">
                            {#if col.id === columns[0].id}{totalRow.label ?? 'Total'}{:else if col.fmt === 'money'}{fmtMoney(totalRow[col.id])}{:else if col.fmt === 'pct'}{fmtPct(totalRow[col.id])}{/if}
                        </td>
                    {/each}
                </tr>
            {/if}

            {#each displayed as row, i}
                <tr
                    on:click={() => linkField ? window.location.href = row[linkField] : null}
                    style={'border-bottom:1px solid #F3F4F6; cursor:pointer; background:' + (i % 2 === 0 ? 'var(--nxt-surface)' : '#f7f2fc') + ';'}
                    onmouseenter="this.style.background='var(--nxt-pink)'"
                    onmouseleave={'this.style.background=' + (i % 2 === 0 ? "'var(--nxt-surface)'" : "'#f7f2fc'") + ''}
                >
                    {#each columns as col}
                        <td style={'padding:9px 14px; text-align:' + (col.align ?? 'right') + '; ' + (col.bold ? 'font-weight:600;' : '') + ' color:#231F20'}>
                            {#if col.id === columns[0].id}
                                <span style="color:#231F20; font-weight:500; text-align:left; display:inline-block;">{row[col.id]}</span>
                            {:else}
                                {#if col.conditional}
                                    {#key row[col.id]}
                                        {#let st = conditionalStyle(row[col.id])}
                                            <span style={'display:inline-block; padding:6px 8px; border-radius:4px; background:' + st.background + '; color:' + st.color + '; font-weight:600; min-width:54px; text-align:right;'}>
                                                {col.fmt === 'money' ? fmtMoney(row[col.id]) : col.fmt === 'pct' ? fmtPct(row[col.id]) : (row[col.id] == null ? '-' : row[col.id])}
                                            </span>
                                        {/let}
                                    {/key}
                                {:else}
                                    {col.fmt === 'money' ? fmtMoney(row[col.id]) : col.fmt === 'pct' ? fmtPct(row[col.id]) : (row[col.id] == null ? '-' : row[col.id])}
                                {/if}
                            {/if}
                        </td>
                    {/each}
                    <td style="padding:9px 8px; color:#C8122C; font-size:0.8rem;">›</td>
                </tr>
            {/each}
        </tbody>
    </table>
</div>

<style>
    th { text-align: right; }
    th:first-child { text-align: left; }
</style>
