---
title: "{params.agency}"
prerender: false
---

<div style="background: linear-gradient(135deg, #C8122C 0%, #231F20 100%); padding: 24px 36px; border-radius: 12px; border-bottom: 4px solid #FFC838; margin-bottom: 0;">
    <p style="color: rgba(255,255,255,0.7); font-size: 0.8rem; margin: 0;"><a href="/budget-office" style="color: #FFC838; text-decoration: none;">Budget Office</a> -> Agency</p>
    <h1 style="color: white; font-family: Montserrat, sans-serif; font-size: 1.6rem; font-weight: 700; margin: 6px 0 0 0;">{params.agency}</h1>
</div>

```sql g_fy
select distinct fiscal_year as fy
from mbtsa.subprogram_level
order by fiscal_year
```
```sql g_fund
select distinct fund_type
from mbtsa.subprogram_level
where fund_type is not null
  and agency_name = '${params.agency}'
order by fund_type
```
```sql g_agency
select distinct agency_name
from mbtsa.subprogram_level
where agency_name is not null
order by agency_name
```
```sql g_unit
select distinct unit_name
from mbtsa.subprogram_level
where unit_name is not null
  and agency_name = '${params.agency}'
order by unit_name
```
```sql g_program
select distinct program_name
from mbtsa.subprogram_level
where program_name is not null
  and agency_name = '${params.agency}'
order by program_name
```
```sql g_subprogram
select distinct subprogram_name
from mbtsa.subprogram_level
where subprogram_name is not null
  and agency_name = '${params.agency}'
order by subprogram_name
```

<Details title=" Filters  click to expand" open=true>

<Grid cols=3>
    <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue="%"><DropdownOption value="%" valueLabel="All Years"/></Dropdown>
    <Dropdown name=f_fund data={g_fund} value=fund_type title="Fund Type" defaultValue="%"><DropdownOption value="%" valueLabel="All Fund Types"/></Dropdown>
    <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue={params.agency}><DropdownOption value="%" valueLabel="All Agencies"/></Dropdown>
    <Dropdown name=f_unit data={g_unit} value=unit_name title="Unit" defaultValue="%"><DropdownOption value="%" valueLabel="All Units"/></Dropdown>
    <Dropdown name=f_program data={g_program} value=program_name title="Program" defaultValue="%"><DropdownOption value="%" valueLabel="All Programs"/></Dropdown>
    <Dropdown name=f_subprogram data={g_subprogram} value=subprogram_name title="Subprogram" defaultValue="%"><DropdownOption value="%" valueLabel="All Subprograms"/></Dropdown>
</Grid>

</Details>

<Grid cols=1>
    <Dropdown name=f_view title="View" defaultValue="trend">
        <DropdownOption value="trend" valueLabel="Trend Over Years"/>
        <DropdownOption value="latest" valueLabel="Latest Year Snapshot"/>
    </Dropdown>
</Grid>

<Alert status=info>
    Switch between <b>Trend Over Years</b> and <b>Latest Year Snapshot</b> using the View selector above.
</Alert>

<script>
    // Pull params.agency into a plain JS variable to avoid quote-collision
    // inside Evidence SQL template literals.
    const agencyDefault = (params.agency ?? '').replace(/'/g, "''");

    // Drives the hierarchy drilldown table toggle (trend vs snapshot).
    // Mirrors the f_view dropdown used in the top section.
    $: viewMode = inputs.f_view?.value ?? 'trend';

    $: hierarchyYearColumns = [...new Set((hierarchy_trend_long ?? [])
        .map((row) => Number(row.fiscal_year))
        .filter((year) => !Number.isNaN(year)))].sort((a, b) => a - b);

    // Reshape trend rows with guaranteed key order:
    // unit_name → program_name → subprogram_name → years ascending
    // Evidence DataTable renders columns by JS object key insertion order,
    // not by <Column> declaration order, so we must control it here.
    $: hierarchyTrendShaped = (() => {
        const rows = hierarchyTrendPivot ?? [];
        const level = inputs.f_hierarchy_level?.value ?? 'unit';
        const showProgram    = level === 'program' || level === 'subprogram';
        const showSubprogram = level === 'subprogram';
        return rows.map(row => {
            const shaped = { unit_name: row.unit_name };
            if (showProgram)    shaped.program_name    = row.program_name;
            if (showSubprogram) shaped.subprogram_name = row.subprogram_name;
            for (const y of hierarchyYearColumns) {
                shaped[String(y)] = row[String(y)] ?? null;
            }
            return shaped;
        });
    })();

    $: hierarchyTrendPivot = (() => {
        const rows = hierarchy_trend_long ?? [];
        const grouped = new Map();

        for (const row of rows) {
            const key = `${row.unit_name ?? ''}||${row.program_name ?? ''}||${row.subprogram_name ?? ''}`;
            if (!grouped.has(key)) {
                grouped.set(key, {
                    _unit_name: row.unit_name,
                    _program_name: row.program_name,
                    _subprogram_name: row.subprogram_name,
                    _sort_total: 0
                });
            }

            const entry = grouped.get(key);
            const yearKey = String(row.fiscal_year);
            const amount = Number(row.budget_amount) || 0;

            entry[yearKey] = (entry[yearKey] ?? 0) + amount;
            entry._sort_total += amount;
        }

        // Reconstruct each row with hierarchy fields FIRST, then year columns
        // sorted ascending, so Evidence DataTable always renders them left-to-right.
        const allYears = [...new Set(
            [...grouped.values()].flatMap(e =>
                Object.keys(e).filter(k => !k.startsWith('_'))
            )
        )].sort((a, b) => Number(a) - Number(b));

        return [...grouped.values()]
            .sort((a, b) => (b._sort_total ?? 0) - (a._sort_total ?? 0))
            .map(({ _unit_name, _program_name, _subprogram_name, _sort_total, ...yearCols }) => {
                const row = {
                    unit_name:       _unit_name,
                    program_name:    _program_name,
                    subprogram_name: _subprogram_name,
                };
                // Add year keys in sorted ascending order
                for (const y of allYears) {
                    row[y] = yearCols[y] ?? null;
                }
                return row;
            });
    })();

    let hierarchySearchTerm = '';

    // Reshape hierarchy_table rows so hierarchy fields are always
    // the FIRST keys in the object — Evidence DataTable uses JS key
    // insertion order, not <Column> declaration order.
    $: hierarchyTableShaped = (() => {
        const level = inputs.f_hierarchy_level?.value ?? 'unit';
        const showProgram    = level === 'program' || level === 'subprogram';
        const showSubprogram = level === 'subprogram';
        return (hierarchy_table ?? []).map(row => {
            const shaped = { unit_name: row.unit_name };
            if (showProgram)    shaped.program_name    = row.program_name;
            if (showSubprogram) shaped.subprogram_name = row.subprogram_name;
            shaped.latest_year_budget = row.latest_year_budget;
            shaped.latest_year_pct    = row.latest_year_pct;
            shaped.yoy_change_pct     = row.yoy_change_pct;
            shaped.cagr_5y_pct        = row.cagr_5y_pct;
            shaped.cagr_10y_pct       = row.cagr_10y_pct;
            return shaped;
        });
    })();

    // Client-side search for the latest-year snapshot table
    // (Evidence's built-in search= prop doesn't work on JS-transformed arrays)
    let hierarchyTableSearch = '';
    $: hierarchyTableFiltered = (() => {
        const needle = String(hierarchyTableSearch ?? '').trim().toLowerCase();
        if (!needle) return hierarchyTableShaped;
        return hierarchyTableShaped.filter(row =>
            [row.unit_name, row.program_name, row.subprogram_name]
                .map(v => String(v ?? '').toLowerCase())
                .some(v => v.includes(needle))
        );
    })();
    $: hierarchyTrendFiltered = (() => {
        const needle = String(hierarchySearchTerm ?? '').trim().toLowerCase();
        if (!needle) return hierarchyTrendShaped ?? [];

        return (hierarchyTrendShaped ?? []).filter((row) =>
            [row.unit_name, row.program_name, row.subprogram_name]
                .map((v) => String(v ?? '').toLowerCase())
                .some((v) => v.includes(needle))
        );
    })();
</script>

```sql filter_meta
select
    '${((() => {
        const v = inputs.f_fy?.rawValues?.[0]?.value
            ?? inputs.f_fy?.rawValue?.value
            ?? inputs.f_fy?.value?.value
            ?? inputs.f_fy?.rawValue
            ?? inputs.f_fy?.value
            ?? inputs.f_fy?.rawValues?.[0]?.label
            ?? inputs.f_fy?.label
            ?? inputs.f_fy?.rawValues?.[0]
            ?? "%";
        const s = String(v ?? "%");
        return (s && s.toLowerCase() !== '[object object]') ? s : "%";
    })()).replace(/'/g, "''")}' as selected_fy,
    '${((() => {
        const v = inputs.f_fund?.rawValues?.[0]?.value
            ?? inputs.f_fund?.rawValue?.value
            ?? inputs.f_fund?.value?.value
            ?? inputs.f_fund?.rawValue
            ?? inputs.f_fund?.value
            ?? inputs.f_fund?.rawValues?.[0]?.label
            ?? inputs.f_fund?.label
            ?? inputs.f_fund?.rawValues?.[0]
            ?? "%";
        const s = String(v ?? "%");
        return (s && s.toLowerCase() !== '[object object]') ? s : "%";
    })()).replace(/'/g, "''")}' as selected_fund,
    '${((() => {
        const v = inputs.f_agency?.rawValues?.[0]?.value
            ?? inputs.f_agency?.rawValue?.value
            ?? inputs.f_agency?.value?.value
            ?? inputs.f_agency?.rawValue
            ?? inputs.f_agency?.value
            ?? inputs.f_agency?.rawValues?.[0]?.label
            ?? inputs.f_agency?.label
            ?? inputs.f_agency?.rawValues?.[0]
            ?? agencyDefault;
        const s = String(v ?? "");
        return (s && s.toLowerCase() !== '[object object]') ? s : agencyDefault;
    })()).replace(/'/g, "''")}' as selected_agency,
    '${((() => {
        const v = inputs.f_unit?.rawValues?.[0]?.value
            ?? inputs.f_unit?.rawValue?.value
            ?? inputs.f_unit?.value?.value
            ?? inputs.f_unit?.rawValue
            ?? inputs.f_unit?.value
            ?? inputs.f_unit?.rawValues?.[0]?.label
            ?? inputs.f_unit?.label
            ?? inputs.f_unit?.rawValues?.[0]
            ?? "%";
        const s = String(v ?? "%");
        return (s && s.toLowerCase() !== '[object object]') ? s : "%";
    })()).replace(/'/g, "''")}' as selected_unit,
    '${((() => {
        const v = inputs.f_program?.rawValues?.[0]?.value
            ?? inputs.f_program?.rawValue?.value
            ?? inputs.f_program?.value?.value
            ?? inputs.f_program?.rawValue
            ?? inputs.f_program?.value
            ?? inputs.f_program?.rawValues?.[0]?.label
            ?? inputs.f_program?.label
            ?? inputs.f_program?.rawValues?.[0]
            ?? "%";
        const s = String(v ?? "%");
        return (s && s.toLowerCase() !== '[object object]') ? s : "%";
    })()).replace(/'/g, "''")}' as selected_program,
    '${((() => {
        const v = inputs.f_subprogram?.rawValues?.[0]?.value
            ?? inputs.f_subprogram?.rawValue?.value
            ?? inputs.f_subprogram?.value?.value
            ?? inputs.f_subprogram?.rawValue
            ?? inputs.f_subprogram?.value
            ?? inputs.f_subprogram?.rawValues?.[0]?.label
            ?? inputs.f_subprogram?.label
            ?? inputs.f_subprogram?.rawValues?.[0]
            ?? "%";
        const s = String(v ?? "%");
        return (s && s.toLowerCase() !== '[object object]') ? s : "%";
    })()).replace(/'/g, "''")}' as selected_subprogram
```

```sql filtered
select
    cast(b.fiscal_year as int) as fiscal_year,
    b.fund_type,
    b.agency_name,
    b.unit_name,
    b.program_name,
    b.subprogram_name,
    b.total_budget_amount as amount
from mbtsa.subprogram_level b
cross join ${filter_meta} f
where cast(b.fiscal_year as varchar) like f.selected_fy
    and coalesce(b.fund_type, '') like f.selected_fund
    and coalesce(b.agency_name, '') like f.selected_agency
    and coalesce(b.unit_name, '') like f.selected_unit
    and coalesce(b.program_name, '') like f.selected_program
    and coalesce(b.subprogram_name, '') like f.selected_subprogram
```

```sql yearly_rollup
select fiscal_year, sum(amount) as total_budget
from ${filtered}
group by fiscal_year
```

```sql scope_meta
-- Only consider years with actual non-zero spend to avoid FY2027 $0 estimates
-- skewing latest_budget, prior_budget, and YoY/CAGR calculations.
with rollup_with_data as (
    select fiscal_year, total_budget
    from ${yearly_rollup}
    where total_budget > 0
),
ordered as (
    select
        fiscal_year,
        total_budget,
        row_number() over (order by fiscal_year desc) as year_rank
    from rollup_with_data
),
bounds as (
    select
        min(fiscal_year) as start_year,
        max(fiscal_year) as max_year,
        sum(total_budget) as total_budget
    from rollup_with_data
)
select
    b.start_year,
    b.max_year,
    max(case when o.year_rank = 2 then o.fiscal_year end) as prior_year,
    b.total_budget,
    max(case when o.year_rank = 1 then o.total_budget end) as latest_budget,
    max(case when o.year_rank = 2 then o.total_budget end) as prior_budget
from bounds b
left join ordered o on true
group by b.start_year, b.max_year, b.total_budget
```

```sql filtered_latest
select f.*
from ${filtered} f
cross join ${scope_meta} m
where f.fiscal_year = m.max_year
```

```sql filtered_prior
select f.*
from ${filtered} f
cross join ${scope_meta} m
where f.fiscal_year = m.prior_year
```

```sql overview
with points as (
    select
        m.*,
        y_5.total_budget as budget_5y_ago,
        y_10.total_budget as budget_10y_ago
    from ${scope_meta} m
    left join ${yearly_rollup} y_5 on y_5.fiscal_year = m.max_year - 5
    left join ${yearly_rollup} y_10 on y_10.fiscal_year = m.max_year - 10
)
select
    total_budget,
    latest_budget,
    round((latest_budget - prior_budget) * 100.0 / nullif(prior_budget, 0), 1) as yoy_pct,
    round(
        case
            when budget_5y_ago > 0 and latest_budget > 0
                then (power(latest_budget / budget_5y_ago, 1.0 / 5.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(
        case
            when budget_10y_ago > 0 and latest_budget > 0
                then (power(latest_budget / budget_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_10y_pct,
    coalesce(cast(max_year as varchar), 'N/A') as max_year_label
from points
```

```sql fund_rules
select *
from (
    values
        ('federal funds', 1, '#C8122C', false),
        ('general funds', 2, '#FFC838', false),
        ('special funds', 3, '#2EAD6B', false),
        ('american rescue plan act%', 4, '#9B1C31', true),
        ('coronavirus aid, relief, and economic security act%', 5, '#B08A00', true),
        ('coronavirus response and relief sup act%', 6, '#6A1B2A', true),
        ('federal funds (covid)%', 7, '#1ABC9C', true),
        ('unrestricted', 8, '#F08C46', false),
        ('current%unrest%fund%', 8, '#F08C46', true),
        ('restricted', 9, '#5B8FF9', false),
        ('current%rest%fund%', 9, '#5B8FF9', true)
) as rules(pattern, fund_rank, fund_color, is_like)
```

```sql fund_profile
with distinct_funds as (
    select distinct fund_type
    from ${filtered}
    where fund_type is not null
),
matches as (
    select
        d.fund_type,
        r.fund_rank,
        r.fund_color,
        row_number() over (
            partition by d.fund_type
            order by r.fund_rank
        ) as rank_order
    from distinct_funds d
    join ${fund_rules} r
        on (
            (r.is_like and lower(d.fund_type) like r.pattern)
            or (not r.is_like and lower(d.fund_type) = r.pattern)
        )
)
select
    d.fund_type,
    coalesce(m.fund_rank, 99) as fund_rank,
    coalesce(m.fund_color, '#4C4743') as fund_color
from distinct_funds d
left join matches m
    on m.fund_type = d.fund_type
    and m.rank_order = 1
```

```sql unit_top10
select
    coalesce(nullif(trim(unit_name), ''), '(Unspecified Unit)') as unit_name,
    sum(amount) as latest_year_budget
from ${filtered_latest}
where unit_name is not null
  and trim(unit_name) <> ''
group by coalesce(nullif(trim(unit_name), ''), '(Unspecified Unit)')
order by latest_year_budget desc
limit 10
```

```sql unit_by_fund
with unit_fund as (
    select
        coalesce(nullif(trim(f.unit_name), ''), '(Unspecified Unit)') as unit_name,
        f.fund_type,
        sum(f.amount) as spend,
        coalesce(fp.fund_rank, 99) as fund_rank
    from ${filtered_latest} f
    left join ${fund_profile} fp on fp.fund_type = f.fund_type
    where f.unit_name is not null
      and trim(f.unit_name) <> ''
    group by coalesce(nullif(trim(f.unit_name), ''), '(Unspecified Unit)'), f.fund_type, fp.fund_rank
)
select uf.unit_name, uf.fund_type, uf.spend
from unit_fund uf
join (
    select unit_name, sum(spend) as latest_year_budget
    from unit_fund
    group by unit_name
    order by latest_year_budget desc
    limit 10
) t using (unit_name)
order by t.latest_year_budget desc, uf.fund_rank, uf.spend desc
```

```sql fund_summary
with latest as (
    select
        fund_type,
        sum(amount) as latest_year_budget
    from ${filtered_latest}
    group by fund_type
),
prior as (
    select
        fund_type,
        sum(amount) as prior_year_budget
    from ${filtered_prior}
    group by fund_type
),
hist_5y as (
    select
        f.fund_type,
        sum(f.amount) as budget_5y_ago
    from ${filtered} f
    cross join ${scope_meta} m
    where f.fiscal_year = (m.max_year - 5)
    group by f.fund_type
),
hist_10y as (
    select
        f.fund_type,
        sum(f.amount) as budget_10y_ago
    from ${filtered} f
    cross join ${scope_meta} m
    where f.fiscal_year = (m.max_year - 10)
    group by f.fund_type
)
select
    l.fund_type,
    l.latest_year_budget as total_spend,
    l.latest_year_budget,
    round(
        (l.latest_year_budget - p.prior_year_budget) * 100.0
        / nullif(p.prior_year_budget, 0),
        1
    ) as yoy_change_pct,
    round(
        case
            when h5.budget_5y_ago > 0 and l.latest_year_budget > 0
                then (power(l.latest_year_budget / h5.budget_5y_ago, 1.0 / 5.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_5y_pct,
    round(
        case
            when h10.budget_10y_ago > 0 and l.latest_year_budget > 0
                then (power(l.latest_year_budget / h10.budget_10y_ago, 1.0 / 10.0) - 1.0) * 100.0
            else null
        end,
        1
    ) as cagr_10y_pct,
    round(
        l.latest_year_budget * 100.0
        / nullif(m.latest_budget, 0),
        1
    ) as latest_year_pct,
    coalesce(fp.fund_rank, 99) as fund_rank,
    coalesce(fp.fund_color, '#4C4743') as fund_color
from latest l
left join prior p using (fund_type)
left join hist_5y h5 using (fund_type)
left join hist_10y h10 using (fund_type)
cross join ${scope_meta} m
left join ${fund_profile} fp on fp.fund_type = l.fund_type
order by total_spend desc
```

```sql yearly
select fiscal_year, total_budget
from ${yearly_rollup}
order by fiscal_year
```

```sql yoy_detail
select
    fiscal_year,
    coalesce(
        round(
            (total_budget - lag(total_budget) over (order by fiscal_year)) * 100.0
            / nullif(lag(total_budget) over (order by fiscal_year), 0),
            1
        ),
        0
    ) as change_pct
from ${yearly_rollup}
order by fiscal_year
```

```sql top_units_trend
select
    coalesce(nullif(trim(unit_name), ''), '(Unspecified Unit)') as unit_name,
    sum(amount) as total_budget
from ${filtered}
where unit_name is not null
  and trim(unit_name) <> ''
group by coalesce(nullif(trim(unit_name), ''), '(Unspecified Unit)')
order by total_budget desc
limit 10
```

```sql unit_trend
select
    f.fiscal_year,
    coalesce(nullif(trim(f.unit_name), ''), '(Unspecified Unit)') as unit_name,
    sum(f.amount) as spend
from ${filtered} f
where f.unit_name is not null
  and trim(f.unit_name) <> ''
  and coalesce(nullif(trim(f.unit_name), ''), '(Unspecified Unit)') in (select unit_name from ${top_units_trend})
group by f.fiscal_year, coalesce(nullif(trim(f.unit_name), ''), '(Unspecified Unit)')
order by f.fiscal_year
```

{#if inputs.f_view?.value == 'latest'}
    <Grid cols=4>
        <BigValue data={overview} value=latest_budget fmt=usd2compactviz title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})"/>
        <BigValue data={overview} value=yoy_pct fmt='0.0"%"' title="YoY Change"/>
        <BigValue data={overview} value=cagr_5y_pct fmt='0.0"%"' title="5-Year CAGR"/>
        <BigValue data={overview} value=cagr_10y_pct fmt='0.0"%"' title="10-Year CAGR"/>
    </Grid>

    <Grid cols=2>
        {#if unit_top10?.length > 0}
            <BarChart data={unit_top10} x=unit_name y=latest_year_budget swapXY=true sort=false height=420 yFmt=usd2compactviz xFmt=usd2compactviz labels=true yLabelFmt=usd2compactviz xAxisLabels=true yAxisLabels=false title="Latest year budget by unit" colorPalette={['#C8122C']}/>
        {:else}
            <Alert status=warning>No unit totals available for this filter selection.</Alert>
        {/if}
        {#if unit_by_fund?.length > 0}
            <BarChart data={unit_by_fund} x=unit_name y=spend series=fund_type type=stacked100 swapXY=true sort=false height=420 title="How each unit is funded" colorPalette={['#C8122C','#FFC838','#2EAD6B','#9B1C31','#B08A00','#6A1B2A','#1ABC9C','#F08C46','#5B8FF9','#8A3C4A']} yFmt=pct1 legend=false xAxisLabels=true yAxisLabels=true/>
        {:else}
            <Alert status=warning>No unit-by-fund breakdown is available for this filter selection.</Alert>
        {/if}
    </Grid>

    <Grid cols=1>
        <ECharts
            height="390px"
            config={{
                title: {
                    text: 'Fund type share',
                    left: 'center',
                    top: 0,
                    textStyle: {
                        fontSize: 14,
                        fontWeight: 600,
                        color: '#231F20'
                    }
                },
                tooltip: {
                    trigger: 'item',
                    formatter: (p) => {
                        const v = Number(p.value) || 0;
                        const money = Math.abs(v) >= 1e9
                            ? `$${(v / 1e9).toFixed(2)}B`
                            : Math.abs(v) >= 1e6
                                ? `$${(v / 1e6).toFixed(1)}M`
                                : `$${Math.round(v).toLocaleString()}`;
                        return `${p.name}: ${money} (${p.percent}%)`;
                    }
                },
                legend: {
                    type: 'scroll',
                    orient: 'horizontal',
                    left: 'center',
                    top: 24,
                    textStyle: { fontSize: 11 },
                    formatter: (name) => (name && name.length > 28 ? `${name.slice(0, 28)}...` : name)
                },
                series: [
                    {
                        name: 'Fund Type Share',
                        type: 'pie',
                        radius: ['40%', '66%'],
                        center: ['50%', '56%'],
                        avoidLabelOverlap: true,
                        minAngle: 2,
                        itemStyle: {
                            borderColor: '#FFFFFF',
                            borderWidth: 2
                        },
                        label: {
                            formatter: (p) => (p.percent >= 6 ? `${p.percent}%` : '')
                        },
                        data: fund_summary.map((d) => ({
                            name: d.fund_type,
                            value: d.total_spend,
                            itemStyle: { color: d.fund_color }
                        }))
                    }
                ]
            }}
        />
    </Grid>

    {#if fund_summary?.length > 0}
        <DataTable data={fund_summary} totalRow=true search=true>
            <Column id=fund_type title="Fund Type"/>
            <Column id=latest_year_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
            <Column id=latest_year_pct title="% of Latest Year" fmt='0.0"%"'/>
            <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_5y_pct title="5-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_10y_pct title="10-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
        </DataTable>
    {:else}
        <Alert status=warning>No fund summary data is available for this filter selection.</Alert>
    {/if}
{:else}
    <Grid cols=2>
        {#if yearly?.length > 0}
            <ECharts
                height="300px"
                config={{
                    title: {
                        text: 'Total budget by fiscal year',
                        left: 'left',
                        top: 0,
                        textStyle: { fontSize: 14, fontWeight: 600, color: '#231F20' }
                    },
                    grid: { top: '15%', right: '4%', bottom: '11%', left: '8%', containLabel: true },
                    tooltip: {
                        trigger: 'axis',
                        formatter: (params) => {
                            if (!params || params.length === 0) return '';
                            const p = params[0];
                            const v = Number(p.value) || 0;
                            const money = Math.abs(v) >= 1e9 ? `$${(v/1e9).toFixed(2)}B` : Math.abs(v) >= 1e6 ? `$${(v/1e6).toFixed(2)}M` : `$${Math.round(v).toLocaleString()}`;
                            return `<b>${p.axisValue}</b><br/>Budget: ${money}`;
                        }
                    },
                    xAxis: {
                        type: 'category',
                        data: yearly.map((d) => String(d.fiscal_year))
                    },
                    yAxis: {
                        type: 'value',
                        axisLabel: {
                            formatter: (v) => {
                                const n = Number(v) || 0;
                                return Math.abs(n) >= 1e9 ? `$${(n/1e9).toFixed(0)}B` : `$${(n/1e6).toFixed(0)}M`;
                            }
                        }
                    },
                    series: [{
                        type: 'bar',
                        barMaxWidth: 36,
                        data: yearly.map((d) => Number(d.total_budget) || 0),
                        label: {
                            show: true,
                            position: 'top',
                            distance: 5,
                            color: '#231F20',
                            fontSize: 11,
                            formatter: (p) => {
                                const v = Number(p.value) || 0;
                                return Math.abs(v) >= 1e9 ? `$${(v/1e9).toFixed(2)}B` : Math.abs(v) >= 1e6 ? `$${(v/1e6).toFixed(1)}M` : `$${Math.round(v).toLocaleString()}`;
                            }
                        },
                        labelLayout: { hideOverlap: true },
                        itemStyle: { color: '#C8122C' }
                    }]
                }}
            />
        {:else}
            <Alert status=warning>No fiscal-year totals available for this filter selection.</Alert>
        {/if}
        {#if yoy_detail?.length > 0}
            <ECharts
                height="300px"
                config={{
                    title: {
                        text: 'Year-over-year change (%)',
                        left: 'left',
                        top: 0,
                        textStyle: { fontSize: 14, fontWeight: 600, color: '#231F20' }
                    },
                    grid: { top: '15%', right: '4%', bottom: '11%', left: '8%', containLabel: true },
                    tooltip: {
                        trigger: 'axis',
                        formatter: (params) => {
                            if (!params || params.length === 0) return '';
                            const p = params[0];
                            const v = Number(p.value) || 0;
                            return `<b>${p.axisValue}</b><br/>YoY: ${v.toFixed(1)}%`;
                        }
                    },
                    xAxis: {
                        type: 'category',
                        data: yoy_detail.map((d) => String(d.fiscal_year))
                    },
                    yAxis: {
                        type: 'value',
                        axisLabel: { formatter: (v) => `${Number(v).toFixed(0)}%` }
                    },
                    series: [{
                        type: 'bar',
                        barMaxWidth: 36,
                        data: yoy_detail.map((d) => Number(d.change_pct) || 0),
                        label: {
                            show: true,
                            position: 'top',
                            formatter: (p) => `${(Number(p.value) || 0).toFixed(1)}%`
                        },
                        labelLayout: { hideOverlap: true },
                        itemStyle: { color: (p) => ((Number(p.value) || 0) >= 0 ? '#2EAD6B' : '#C8122C') }
                    }]
                }}
            />
        {:else}
            <Alert status=warning>Year-over-year change is unavailable for this filter selection.</Alert>
        {/if}
    </Grid>

    <ECharts
        height="520px"
        config={{
            color: ['#C8122C','#FFC838','#231F20','#E04B3F','#C99A06','#6F2030','#5B5148','#F26A3D','#A7842A','#8A3C4A'],
            title: {
                text: 'Top 10 units over time',
                left: 'left',
                top: 0,
                textStyle: {
                    fontSize: 14,
                    fontWeight: 600,
                    color: '#231F20'
                }
            },
            tooltip: {
                trigger: 'axis',
                formatter: (params) => {
                    if (!params || params.length === 0) return '';
                    const year = params[0].axisValue;
                    const lines = params.map((p) => {
                        const v = Number(p.value) || 0;
                        const money = Math.abs(v) >= 1e9
                            ? `$${(v / 1e9).toFixed(2)}B`
                            : Math.abs(v) >= 1e6
                                ? `$${(v / 1e6).toFixed(1)}M`
                                : `$${Math.round(v).toLocaleString()}`;
                        return `${p.marker} ${p.seriesName}: ${money}`;
                    });
                    return [`<b>${year}</b>`, ...lines].join('<br/>');
                }
            },
            legend: {
                type: 'plain',
                orient: 'horizontal',
                left: 'center',
                top: 24,
                itemGap: 12,
                textStyle: {
                    fontSize: 11,
                    lineHeight: 14
                },
                formatter: (name) => {
                    const raw = String(name || '');
                    const maxLen = 22;
                    if (raw.length <= maxLen) return raw;
                    const splitAt = raw.lastIndexOf(' ', maxLen);
                    if (splitAt > 8) return `${raw.slice(0, splitAt).trim()}\n${raw.slice(splitAt + 1).trim()}`;
                    return `${raw.slice(0, maxLen)}\n${raw.slice(maxLen)}`;
                }
            },
            grid: {
                left: 64,
                right: 24,
                top: 170,
                bottom: 46
            },
            xAxis: {
                type: 'category',
                data: [...new Set(unit_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b))
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: (v) => {
                        const n = Number(v) || 0;
                        return Math.abs(n) >= 1e9 ? `$${(n / 1e9).toFixed(0)}B` : `$${(n / 1e6).toFixed(0)}M`;
                    }
                },
                splitLine: { lineStyle: { color: '#D9DDE3' } }
            },
            series: top_units_trend.map((unit) => {
                const unitName = unit.unit_name;
                const years = [...new Set(unit_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
                return {
                    name: unitName,
                    type: 'line',
                    smooth: false,
                    symbol: 'circle',
                    symbolSize: 6,
                    data: years.map((y) => unit_trend.find((d) => String(d.fiscal_year) === y && d.unit_name === unitName)?.spend ?? 0)
                };
            })
        }}
    />
{/if}

---

## Fund composition over time

```sql fund_trend
select
    f.fiscal_year,
    f.fund_type,
    sum(f.amount) as spend,
    coalesce(fp.fund_rank, 99) as fund_rank
from ${filtered} f
left join ${fund_profile} fp on fp.fund_type = f.fund_type
group by f.fiscal_year, f.fund_type, fp.fund_rank
order by f.fiscal_year, fund_rank
```

{#if viewMode === 'trend'}
    {#if fund_trend?.length > 0}
        <ECharts
            height="420px"
            config={{
                title: {
                    text: 'Fund composition over time',
                    left: 'left',
                    top: 0,
                    textStyle: {
                        fontSize: 14,
                        fontWeight: 600,
                        color: '#231F20'
                    }
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'shadow' },
                    formatter: (params) => {
                        if (!params || params.length === 0) return '';
                        const year = params[0].axisValue;
                        const lines = params
                            .filter((p) => Number(p.value) !== 0)
                            .map((p) => {
                                const v = Number(p.value) || 0;
                                const money = Math.abs(v) >= 1e9
                                    ? `$${(v / 1e9).toFixed(2)}B`
                                    : Math.abs(v) >= 1e6
                                        ? `$${(v / 1e6).toFixed(1)}M`
                                        : `$${Math.round(v).toLocaleString()}`;
                                return `${p.marker} ${p.seriesName}: ${money}`;
                            });
                        return [`<b>${year}</b>`, ...lines].join('<br/>');
                    }
                },
                legend: {
                    type: 'scroll',
                    orient: 'horizontal',
                    left: 'center',
                    top: 22,
                    textStyle: { fontSize: 11 },
                    formatter: (name) => (name && name.length > 22 ? `${name.slice(0, 22)}...` : name)
                },
                grid: {
                    left: 64,
                    right: 24,
                    top: 70,
                    bottom: 46
                },
                xAxis: {
                    type: 'category',
                    data: [...new Set(fund_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b))
                },
                yAxis: {
                    type: 'value',
                    axisLabel: {
                        formatter: (v) => {
                            const n = Number(v) || 0;
                            return Math.abs(n) >= 1e9 ? `$${(n / 1e9).toFixed(0)}B` : `$${(n / 1e6).toFixed(0)}M`;
                        }
                    },
                    splitLine: { lineStyle: { color: '#D9DDE3' } }
                },
                series: [...new Set(fund_trend.map((d) => d.fund_type))]
                    .sort((a, b) => {
                        const ra = fund_trend.find((d) => d.fund_type === a)?.fund_rank ?? 99;
                        const rb = fund_trend.find((d) => d.fund_type === b)?.fund_rank ?? 99;
                        return ra - rb;
                    })
                    .map((fund) => {
                        const color = fund_summary.find((d) => d.fund_type === fund)?.fund_color ?? '#4C4743';
                        const years = [...new Set(fund_trend.map((d) => String(d.fiscal_year)))].sort((a, b) => Number(a) - Number(b));
                        return {
                            name: fund,
                            type: 'bar',
                            stack: 'total',
                            emphasis: { focus: 'series' },
                            itemStyle: { color },
                            data: years.map((y) => fund_trend.find((d) => String(d.fiscal_year) === y && d.fund_type === fund)?.spend ?? 0)
                        };
                    })
            }}
        />
    {:else}
        <Alert status=warning>No fund trend data available for this filter selection.</Alert>
    {/if}
{/if}

---

## Hierarchy drilldown

{#if viewMode === 'latest'}
    <Grid cols=1>
        <Dropdown name=f_hierarchy_level title="Hierarchy Level" defaultValue="unit">
            <DropdownOption value="unit" valueLabel="Unit"/>
            <DropdownOption value="program" valueLabel="Program"/>
            <DropdownOption value="subprogram" valueLabel="Subprogram"/>
        </Dropdown>
    </Grid>
{:else}
    <Grid cols=2>
        <Dropdown name=f_hierarchy_level title="Hierarchy Level" defaultValue="unit">
            <DropdownOption value="unit" valueLabel="Unit"/>
            <DropdownOption value="program" valueLabel="Program"/>
            <DropdownOption value="subprogram" valueLabel="Subprogram"/>
        </Dropdown>
        <Dropdown name=f_hierarchy_table_view title="Table View" defaultValue="5">
            <DropdownOption value="3" valueLabel="3 Years"/>
            <DropdownOption value="5" valueLabel="5 Years"/>
            <DropdownOption value="all" valueLabel="All Years"/>
        </Dropdown>
    </Grid>
{/if}

```sql hierarchy_base
select
    coalesce(nullif(trim(unit_name), ''), '(Unspecified Unit)') as unit_name,
    case
        when lower(trim('${(inputs.f_hierarchy_level?.value ?? 'unit').toString().replace(/'/g, "''")}')) in ('program', 'subprogram') then
            coalesce(nullif(trim(program_name), ''), '(Unspecified Program)')
        else null
    end as program_name,
    case
        when lower(trim('${(inputs.f_hierarchy_level?.value ?? 'unit').toString().replace(/'/g, "''")}')) = 'subprogram' then
            coalesce(nullif(trim(subprogram_name), ''), '(Unspecified Subprogram)')
        else null
    end as subprogram_name,
    cast(fiscal_year as int) as fiscal_year,
    amount
from ${filtered}
where coalesce(nullif(trim(unit_name), ''), '') <> ''
```

```sql hierarchy_years
with years as (
    select distinct fiscal_year
    from ${hierarchy_base}
),
ranked as (
    select fiscal_year, row_number() over (order by fiscal_year desc) as recent_rank
    from years
)
select fiscal_year
from ranked
where
    lower(trim('${(inputs.f_hierarchy_table_view?.value ?? '5').toString().replace(/'/g, "''")}')) like 'all%'
    or recent_rank <= coalesce(
        try_cast('${(inputs.f_hierarchy_table_view?.value ?? '5').toString().replace(/'/g, "''")}' as int),
        5
    )
order by fiscal_year asc
```

```sql hierarchy_trend_long
with selected_years as (
    select fiscal_year
    from ${hierarchy_years}
)
select
    h.unit_name,
    h.program_name,
    h.subprogram_name,
    h.fiscal_year,
    sum(h.amount) as budget_amount
from ${hierarchy_base} h
where h.fiscal_year in (select fiscal_year from selected_years)
group by h.unit_name, h.program_name, h.subprogram_name, h.fiscal_year
```

```sql hierarchy_table
with
-- all_base: full unwindowed history for accurate lookbacks
all_base as (
    select
        h.unit_name,
        coalesce(h.program_name, '__NULL__')    as program_name,
        coalesce(h.subprogram_name, '__NULL__') as subprogram_name,
        h.fiscal_year,
        sum(h.amount) as budget_amount
    from ${hierarchy_base} h
    group by h.unit_name,
             coalesce(h.program_name, '__NULL__'),
             coalesce(h.subprogram_name, '__NULL__'),
             h.fiscal_year
),
-- base: display window only (3/5/all years)
base as (
    select
        h.unit_name,
        coalesce(h.program_name, '__NULL__')    as program_name,
        coalesce(h.subprogram_name, '__NULL__') as subprogram_name,
        h.fiscal_year,
        sum(h.amount) as budget_amount
    from ${hierarchy_base} h
    where h.fiscal_year in (select fiscal_year from ${hierarchy_years})
    group by h.unit_name,
             coalesce(h.program_name, '__NULL__'),
             coalesce(h.subprogram_name, '__NULL__'),
             h.fiscal_year
),
-- only years with real spend so FY2027 $0 estimates don't hijack "latest"
all_years_with_data as (
    select fiscal_year
    from all_base
    group by fiscal_year
    having sum(budget_amount) > 0
),
latest as (
    select max(fiscal_year) as latest_year from all_years_with_data
),
prior as (
    select max(fiscal_year) as prior_year
    from all_years_with_data
    where fiscal_year < (select latest_year from latest)
),
latest_budget as (
    select unit_name, program_name, subprogram_name,
           sum(budget_amount) as latest_year_budget
    from all_base
    where fiscal_year = (select latest_year from latest)
    group by unit_name, program_name, subprogram_name
),
prior_budget as (
    select unit_name, program_name, subprogram_name,
           sum(budget_amount) as prior_year_budget
    from all_base
    where fiscal_year = (select prior_year from prior)
    group by unit_name, program_name, subprogram_name
),
five_year_ago as (
    select unit_name, program_name, subprogram_name,
           sum(budget_amount) as budget_5y_ago
    from all_base
    where fiscal_year = (select latest_year from latest) - 5
    group by unit_name, program_name, subprogram_name
),
ten_year_ago as (
    select unit_name, program_name, subprogram_name,
           sum(budget_amount) as budget_10y_ago
    from all_base
    where fiscal_year = (select latest_year from latest) - 10
    group by unit_name, program_name, subprogram_name
),
scope as (
    select sum(latest_year_budget) as agency_latest_total from latest_budget
),
-- distinct rows from the display window
dim as (
    select distinct unit_name, program_name, subprogram_name from base
)
select
    d.unit_name,
    -- restore NULL sentinel back to NULL for display
    nullif(d.program_name,    '__NULL__') as program_name,
    nullif(d.subprogram_name, '__NULL__') as subprogram_name,
    coalesce(lb.latest_year_budget, 0) as latest_year_budget,
    round(coalesce(lb.latest_year_budget, 0) * 100.0
          / nullif(s.agency_latest_total, 0), 1)                              as latest_year_pct,
    round((coalesce(lb.latest_year_budget, 0)
           - coalesce(pb.prior_year_budget, 0)) * 100.0
          / nullif(pb.prior_year_budget, 0), 1)                               as yoy_change_pct,
    round(
        case
            when fy5.budget_5y_ago > 0 and lb.latest_year_budget > 0
                then (power(lb.latest_year_budget / fy5.budget_5y_ago,
                            1.0 / 5.0) - 1.0) * 100.0
        end, 1)                                                               as cagr_5y_pct,
    round(
        case
            when fy10.budget_10y_ago > 0 and lb.latest_year_budget > 0
                then (power(lb.latest_year_budget / fy10.budget_10y_ago,
                            1.0 / 10.0) - 1.0) * 100.0
        end, 1)                                                               as cagr_10y_pct
from dim d
cross join scope s
left join latest_budget lb
       on lb.unit_name       = d.unit_name
      and lb.program_name    = d.program_name
      and lb.subprogram_name = d.subprogram_name
left join prior_budget pb
       on pb.unit_name       = d.unit_name
      and pb.program_name    = d.program_name
      and pb.subprogram_name = d.subprogram_name
left join five_year_ago fy5
       on fy5.unit_name       = d.unit_name
      and fy5.program_name    = d.program_name
      and fy5.subprogram_name = d.subprogram_name
left join ten_year_ago fy10
       on fy10.unit_name       = d.unit_name
      and fy10.program_name    = d.program_name
      and fy10.subprogram_name = d.subprogram_name
order by latest_year_budget desc
```

{#if viewMode === 'latest'}
    <div style="margin-bottom: 10px;">
        <input
            type="text"
            bind:value={hierarchyTableSearch}
            placeholder="Search unit, program, or subprogram"
            style="width: 320px; max-width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 8px 10px; font-size: 13px;"
        />
    </div>
    {#if hierarchyTableFiltered?.length > 0}
        <DataTable data={hierarchyTableFiltered} totalRow=true rows=20 search=false>
            <Column id=unit_name title="Unit"/>
            {#if inputs.f_hierarchy_level?.value === 'program' || inputs.f_hierarchy_level?.value === 'subprogram'}
                <Column id=program_name title="Program"/>
            {/if}
            {#if inputs.f_hierarchy_level?.value === 'subprogram'}
                <Column id=subprogram_name title="Subprogram"/>
            {/if}
            <Column id=latest_year_budget title="Latest Year ({overview?.[0]?.max_year_label ?? 'N/A'})" fmt=usd2compactviz/>
            <Column id=latest_year_pct title="% of Latest Year" fmt='0.0"%"'/>
            <Column id=yoy_change_pct title="YoY Change" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_5y_pct title="5-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
            <Column id=cagr_10y_pct title="10-Year CAGR" fmt='0.0"%"' totalAgg="-"/>
        </DataTable>
    {:else}
        <Alert status=warning>No hierarchy data available for this filter selection.</Alert>
    {/if}
{:else}
    <div style="margin-bottom: 10px;">
        <input
            type="text"
            bind:value={hierarchySearchTerm}
            placeholder="Search unit, program, or subprogram"
            style="width: 320px; max-width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 8px 10px; font-size: 13px;"
        />
    </div>
    {#if hierarchyTrendFiltered?.length > 0}
        <DataTable data={hierarchyTrendFiltered} totalRow=true rows=20 search=false>
            <Column id=unit_name title="Unit"/>
            {#if inputs.f_hierarchy_level?.value === 'program' || inputs.f_hierarchy_level?.value === 'subprogram'}
                <Column id=program_name title="Program"/>
            {/if}
            {#if inputs.f_hierarchy_level?.value === 'subprogram'}
                <Column id=subprogram_name title="Subprogram"/>
            {/if}
            {#each hierarchyYearColumns as year}
                <Column id={String(year)} title={String(year)} fmt=usd2compactviz/>
            {/each}
        </DataTable>
    {:else}
        <Alert status=warning>No hierarchy data available for this filter selection.</Alert>
    {/if}
{/if}
