<script>
    export let unitData = [];
    export let programData = [];
    export let subprogramData = [];
    export let latestYearLabel = '';

    let searchTerm = '';
    let expandedUnits = {};
    let expandedPrograms = {};

    $: pivotYears = [...new Set([
        ...(unitData ?? []),
        ...(programData ?? []),
        ...(subprogramData ?? [])
    ].flatMap((row) => Object.keys(row).filter((key) => /^FY\d+$/.test(key)).map((key) => key.replace('FY', ''))))]
        .sort((a, b) => Number(a) - Number(b));

    const fmtMoney = (v) => {
        const n = Number(v) || 0;
        const abs = Math.abs(n);
        if (abs >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
        if (abs >= 1e6) return '$' + (n / 1e6).toFixed(2) + 'M';
        if (abs >= 1e3) return '$' + (n / 1e3).toFixed(0) + 'K';
        return '$' + n.toLocaleString();
    };

    const fmtPct = (v) => v == null ? '-' : (Number(v) > 0 ? '+' : '') + v + '%';

    const conditionalStyle = (v) => {
        if (v == null) return 'display:inline-block;padding:4px 8px;border-radius:4px;min-width:54px;text-align:right;color:var(--nxt-muted);';
        const n = Number(v);
        const color = n >= 0 ? '#1A7340' : '#C8122C';
        let bg = 'transparent';
        if      (n >= 15)  bg = 'rgba(46,173,107,0.16)';
        else if (n >= 8)   bg = 'rgba(46,173,107,0.10)';
        else if (n >= 3)   bg = 'rgba(46,173,107,0.05)';
        else if (n >= 0)   bg = 'rgba(46,173,107,0.025)';
        else if (n >= -3)  bg = 'rgba(200,18,44,0.035)';
        else if (n >= -8)  bg = 'rgba(200,18,44,0.065)';
        else if (n >= -15) bg = 'rgba(200,18,44,0.11)';
        else               bg = 'rgba(200,18,44,0.17)';
        return `display:inline-block;padding:4px 8px;border-radius:4px;min-width:54px;text-align:right;font-weight:600;background:${bg};color:${color};`;
    };

    const sparkline = (row, years) => {
        const values = years.map((year) => Number(row['FY' + year]) || 0);
        const max = Math.max(...values);
        if (!years.length || max === 0) return '';
        const width = 48;
        const height = 16;
        const points = values.map((value, index) => {
            const x = years.length === 1 ? width : (index / (years.length - 1)) * width;
            const y = height - (value / max) * height;
            return x + ',' + y;
        }).join(' ');
        const last = values[values.length - 1];
        const previous = values[values.length - 2] ?? last;
        const color = last >= previous ? '#2EAD6B' : '#C8122C';
        return '<svg width="' + width + '" height="' + height + '" style="display:inline-block;vertical-align:middle;margin-left:8px;flex:0 0 auto;"><polyline points="' + points + '" fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linejoin="round"/><circle cx="' + width + '" cy="' + (height - (last / max) * height) + '" r="2" fill="' + color + '"/></svg>';
    };

    $: programByUnit = (programData ?? []).reduce((acc, r) => {
        if (!acc[r.unit_name]) acc[r.unit_name] = [];
        acc[r.unit_name].push(r);
        return acc;
    }, {});

    $: subprogramByUnitProg = (subprogramData ?? []).reduce((acc, r) => {
        const key = r.unit_name + '||' + r.program_name;
        if (!acc[key]) acc[key] = [];
        acc[key].push(r);
        return acc;
    }, {});

    const toggleUnit = (name) => {
        expandedUnits = { ...expandedUnits, [name]: !expandedUnits[name] };
    };

    const toggleProgram = (unit, prog) => {
        const key = unit + '||' + prog;
        expandedPrograms = { ...expandedPrograms, [key]: !expandedPrograms[key] };
    };

    $: searchLower = searchTerm.toLowerCase();

    $: if (searchTerm) {
        const eu = {}, ep = {};
        (unitData ?? []).forEach(u => {
            const progs = programByUnit[u.unit_name] ?? [];
            const unitMatch = u.unit_name.toLowerCase().includes(searchLower);
            const progMatch = progs.some(p => {
                const pm = p.program_name.toLowerCase().includes(searchLower);
                const subs = subprogramByUnitProg[u.unit_name + '||' + p.program_name] ?? [];
                const subMatch = subs.some(s => s.subprogram_name.toLowerCase().includes(searchLower));
                if (pm || subMatch) ep[u.unit_name + '||' + p.program_name] = true;
                return pm || subMatch;
            });
            if (unitMatch || progMatch) eu[u.unit_name] = true;
        });
        expandedUnits = eu;
        expandedPrograms = ep;
    } else {
        expandedUnits = {};
        expandedPrograms = {};
    }

    $: filteredUnits = searchTerm
        ? (unitData ?? []).filter(u => {
            if (u.unit_name.toLowerCase().includes(searchLower)) return true;
            return (programByUnit[u.unit_name] ?? []).some(p => {
                if (p.program_name.toLowerCase().includes(searchLower)) return true;
                return (subprogramByUnitProg[u.unit_name + '||' + p.program_name] ?? [])
                    .some(s => s.subprogram_name.toLowerCase().includes(searchLower));
            });
        })
        : (unitData ?? []);

    const getFilteredPrograms = (unitName) => {
        const progs = programByUnit[unitName] ?? [];
        if (!searchTerm) return progs;
        return progs.filter(p => {
            if (p.program_name.toLowerCase().includes(searchLower)) return true;
            return (subprogramByUnitProg[unitName + '||' + p.program_name] ?? [])
                .some(s => s.subprogram_name.toLowerCase().includes(searchLower));
        });
    };

    const getFilteredSubprograms = (unitName, progName) =>  {
        const subs = subprogramByUnitProg[unitName + '||' + progName] ?? [];
        if (!searchTerm) return subs;
        return subs.filter(s => s.subprogram_name.toLowerCase().includes(searchLower));
    };

    $: latestYearTitle = `Latest Year${latestYearLabel ? ' (' + latestYearLabel + ')' : ''}`;
</script>

<div style="margin-bottom:12px;">
    <input
        bind:value={searchTerm}
        placeholder="Search units, programs, subprograms..."
        style="border:1px solid var(--nxt-border); border-radius:8px; padding:8px 12px; font-size:0.9rem; width:340px; background:var(--nxt-surface); color:var(--nxt-text);"
    />
</div>

<div style="overflow-x:auto; border-radius:8px; border:1px solid var(--nxt-border); background:var(--nxt-surface);">
    <table style="width:100%; border-collapse:collapse; font-size:0.875rem;">
        <thead>
            <tr style="background:var(--nxt-pink); border-bottom:2px solid #C8122C;">
                <th style="text-align:left; padding:10px 14px; font-weight:700; color:#231F20; min-width:280px;">Unit / Program / Subprogram</th>
                <th style="text-align:right; padding:10px 14px; font-weight:700; color:#231F20; white-space:nowrap;">{latestYearTitle}</th>
                <th style="text-align:right; padding:10px 14px; font-weight:700; color:#231F20;">% of Total</th>
                <th style="text-align:right; padding:10px 14px; font-weight:700; color:#231F20;">YoY Change ($)</th>
                <th style="text-align:right; padding:10px 14px; font-weight:700; color:#231F20;">YoY Change (%)</th>
            </tr>
        </thead>
        <tbody>
            {#each filteredUnits as unit, i}
                <tr
                    on:click={() => toggleUnit(unit.unit_name)}
                    style={'border-bottom:1px solid #E5E7EB; cursor:pointer; background:' + (i % 2 === 0 ? 'var(--nxt-surface)' : '#f7f2fc') + ';'}
                    onmouseenter="this.style.background='var(--nxt-pink)'"
                    onmouseleave={'this.style.background=' + (i % 2 === 0 ? "'var(--nxt-surface)'" : "'#f7f2fc'")}
                >
                    <td style="padding:10px 14px; font-weight:600; color:#231F20;">
                        <span style="margin-right:8px; font-size:0.75rem; color:#C8122C;">{expandedUnits[unit.unit_name] ? '▼' : '▶'}</span>
                        {unit.unit_name}
                        {@html sparkline(unit, pivotYears)}
                    </td>
                    <td style="text-align:right; padding:10px 14px; font-weight:600; color:#231F20;">{fmtMoney(unit.latest_budget)}</td>
                    <td style="text-align:right; padding:10px 14px; color:#6B7280;">{unit.latest_year_pct != null ? unit.latest_year_pct + '%' : '-'}</td>
                    <td style="text-align:right; padding:10px 14px;"><span style={conditionalStyle(unit.yoy_change_pct)}>{fmtMoney(unit.dollar_change)}</span></td>
                    <td style="text-align:right; padding:10px 14px;"><span style={conditionalStyle(unit.yoy_change_pct)}>{fmtPct(unit.yoy_change_pct)}</span></td>
                </tr>

                {#if expandedUnits[unit.unit_name]}
                    {#each getFilteredPrograms(unit.unit_name) as prog}
                        <tr
                            on:click={() => toggleProgram(unit.unit_name, prog.program_name)}
                            style="border-bottom:1px solid #F3F4F6; cursor:pointer; background:#F5F5F5;"
                            onmouseenter="this.style.background='#FFF0F0'"
                            onmouseleave="this.style.background='#F5F5F5'"
                        >
                            <td style="padding:8px 14px 8px 36px; color:#374151; font-weight:500;">
                                <span style="margin-right:8px; font-size:0.75rem; color:#6B7280;">{expandedPrograms[unit.unit_name + '||' + prog.program_name] ? '▼' : '▶'}</span>
                                {prog.program_name}
                                {@html sparkline(prog, pivotYears)}
                            </td>
                            <td style="text-align:right; padding:8px 14px; color:#374151;">{fmtMoney(prog.latest_budget)}</td>
                            <td style="text-align:right; padding:8px 14px; color:#6B7280;">{prog.latest_year_pct != null ? prog.latest_year_pct + '%' : '-'}</td>
                            <td style="text-align:right; padding:8px 14px;"><span style={conditionalStyle(prog.yoy_change_pct)}>{fmtMoney(prog.dollar_change)}</span></td>
                            <td style="text-align:right; padding:8px 14px;"><span style={conditionalStyle(prog.yoy_change_pct)}>{fmtPct(prog.yoy_change_pct)}</span></td>
                        </tr>

                        {#if expandedPrograms[unit.unit_name + '||' + prog.program_name]}
                            {#each getFilteredSubprograms(unit.unit_name, prog.program_name) as sub}
                                <tr style="border-bottom:1px solid #F3F4F6; background:#FAFAFA;">
                                    <td style="padding:7px 14px 7px 60px; color:#6B7280; font-style:italic;">{sub.subprogram_name}{@html sparkline(sub, pivotYears)}</td>
                                    <td style="text-align:right; padding:7px 14px; color:#6B7280;">{fmtMoney(sub.latest_budget)}</td>
                                    <td style="text-align:right; padding:7px 14px; color:#6B7280;">{sub.latest_year_pct != null ? sub.latest_year_pct + '%' : '-'}</td>
                                    <td style="text-align:right; padding:7px 14px;"><span style={conditionalStyle(sub.yoy_change_pct)}>{fmtMoney(sub.dollar_change)}</span></td>
                                    <td style="text-align:right; padding:7px 14px;"><span style={conditionalStyle(sub.yoy_change_pct)}>{fmtPct(sub.yoy_change_pct)}</span></td>
                                </tr>
                            {/each}
                        {/if}
                    {/each}
                {/if}
            {/each}
        </tbody>
    </table>
</div>