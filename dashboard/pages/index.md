---
title: Budget Office
sidebar_link: false
---

<script>
    if (typeof window !== 'undefined' && window.location.pathname === '/') {
        window.location.replace('/budget-office');
    }
</script>

Redirecting to [Budget Office](/budget-office)...

```sql fy_range
select
    min(fiscal_year) as start_year,
    max(fiscal_year) as end_year,
    count(distinct fiscal_year) as total_years
from mbtsa.agency_level
```

```sql full_budget_kpis
with latest_year as (
    select max(fiscal_year) as max_fy from mbtsa.agency_level
),
prior_year as (
    select max(fiscal_year) - 1 as prior_fy from mbtsa.agency_level
),
latest as (
    select
        sum(total_budget_amount) as latest_budget,
        sum(case when lower(fund_type) like '%general%' then total_budget_amount else 0 end) as general_fund,
        sum(case when lower(fund_type) like '%federal%' then total_budget_amount else 0 end) as federal_fund,
        count(distinct agency_code) as agency_count
    from mbtsa.agency_level
    where fiscal_year = (select max_fy from latest_year)
),
prior as (
    select
        sum(total_budget_amount) as prior_budget,
        sum(case when lower(fund_type) like '%general%' then total_budget_amount else 0 end) as prior_general_fund,
        sum(case when lower(fund_type) like '%federal%' then total_budget_amount else 0 end) as prior_federal_fund
    from mbtsa.agency_level
    where fiscal_year = (select prior_fy from prior_year)
)
select
    l.latest_budget,
    l.general_fund,
    l.federal_fund,
    l.agency_count,
    round(l.federal_fund * 100.0 / nullif(l.latest_budget, 0), 1) as federal_pct,
    round(l.general_fund * 100.0 / nullif(l.latest_budget, 0), 1) as general_pct,
    round((l.latest_budget - p.prior_budget) * 100.0 / nullif(p.prior_budget, 0), 1) as yoy_pct,
    round((l.general_fund - p.prior_general_fund) * 100.0 / nullif(p.prior_general_fund, 0), 1) as general_yoy_pct,
    round((l.federal_fund - p.prior_federal_fund) * 100.0 / nullif(p.prior_federal_fund, 0), 1) as federal_yoy_pct,
    (select max_fy from latest_year) as latest_fy,
    (select prior_fy from prior_year) as prior_fy
from latest l cross join prior p
```

```sql it_budget_kpis
with latest_year as (
    select max(fiscal_year) as max_fy from mbtsa.subprogram_level
),
prior_year as (
    select max(fiscal_year) - 1 as prior_fy from mbtsa.subprogram_level
),
latest_it as (
    select
        sum(total_budget_amount) as latest_it_spend,
        count(distinct agency_code) as it_agency_count
    from mbtsa.subprogram_level
    where fiscal_year = (select max_fy from latest_year)
    and is_it = true
),
prior_it as (
    select sum(total_budget_amount) as prior_it_spend
    from mbtsa.subprogram_level
    where fiscal_year = (select prior_fy from prior_year)
    and is_it = true
),
total_budget as (
    select sum(total_budget_amount) as total
    from mbtsa.agency_level
    where fiscal_year = (select max_fy from latest_year)
),
cagr as (
    select
        sum(case when fiscal_year = (select max_fy from latest_year) then total_budget_amount end) as end_val,
        sum(case when fiscal_year = (select max_fy from latest_year) - 5 then total_budget_amount end) as start_val
    from mbtsa.subprogram_level
    where is_it = true
),
top_agency as (
    select agency_name
    from mbtsa.subprogram_level
    where fiscal_year = (select max_fy from latest_year)
    and is_it = true
    group by agency_name
    order by sum(total_budget_amount) desc
    limit 1
)
select
    l.latest_it_spend,
    l.it_agency_count,
    round((l.latest_it_spend - p.prior_it_spend) * 100.0 / nullif(p.prior_it_spend, 0), 1) as yoy_pct,
    round(l.latest_it_spend * 100.0 / nullif(t.total, 0), 2) as it_pct_of_budget,
    round(
        case when c.start_val > 0 and c.end_val > 0
            then (power(c.end_val / c.start_val, 1.0/5.0) - 1.0) * 100.0
        else null end, 1
    ) as cagr_5y,
    ly.max_fy as latest_fy,
    py.prior_fy as prior_fy,
    (select agency_name from top_agency) as top_it_agency
from latest_it l
cross join prior_it p
cross join total_budget t
cross join cagr c
cross join latest_year ly
cross join prior_year py
```

<div style="margin-bottom: 20px;">
    <div style="font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #802cd7; letter-spacing: 0.18em; font-weight: 700; text-transform: uppercase; margin-bottom: 8px;">
        Maryland Budget Technology Spend Analysis · MBTSA
    </div>
    <h1 style="font-size: 1.9rem; font-weight: 800; color: #211030; letter-spacing: -0.6px; line-height: 1.1; margin-bottom: 8px;">
        Maryland Budget Intelligence Dashboard
    </h1>
    <p style="font-size: 12px; color: #6B7280; line-height: 1.6; max-width: 580px; margin-bottom: 0;">
        FY{fy_range[0].start_year}–FY{fy_range[0].end_year} · {fy_range[0].total_years} fiscal years · {full_budget_kpis[0].agency_count} state agencies · TBM v5.0.1 · AI-powered analysis
    </p>
</div>

<div style="background:#211030; border-radius:8px; overflow:hidden; margin-bottom:24px; padding:7px 16px;">
    <div id="mbtsa-ticker" style="display:inline-flex; gap:36px; white-space:nowrap; font-size:10px; color:#e0e0e0; font-family:monospace;">
        {#each Array(2) as _}
            <span><span style="color:#b376f6;">◆</span> FY{it_budget_kpis[0].latest_fy ?? ''} IT Spend: {(it_budget_kpis[0].latest_it_spend/1e9).toFixed(2)}B</span>
            <span><span style="color:#b376f6;">◆</span> IT YoY: {it_budget_kpis[0].yoy_pct ?? ''}%</span>
            <span><span style="color:#b376f6;">◆</span> IT as % of Budget: {it_budget_kpis[0].it_pct_of_budget ?? ''}%</span>
            <span><span style="color:#b376f6;">◆</span> Top IT Agency: {it_budget_kpis[0].top_it_agency ?? ''}</span>
            <span><span style="color:#b376f6;">◆</span> State Agencies: {full_budget_kpis[0].agency_count ?? ''}</span>
            <span><span style="color:#b376f6;">◆</span> Federal Funds: {full_budget_kpis[0].federal_pct ?? ''}% of Budget</span>
            <span><span style="color:#b376f6;">◆</span> 5-Year IT CAGR: {it_budget_kpis[0].cagr_5y ?? ''}%</span>
        {/each}
    </div>
</div>

<div style="font-family:'JetBrains Mono',monospace; font-size:8px; color:#211030; text-transform:uppercase; letter-spacing:0.14em; font-weight:700; border-bottom:2px solid #211030; padding-bottom:5px; margin-bottom:12px;">
    Full Budget · FY{full_budget_kpis[0].latest_fy}
    <span style="font-weight:400; color:#6B7280; margin-left:12px;">
        YoY: {full_budget_kpis[0].yoy_pct > 0 ? '+' : ''}{full_budget_kpis[0].yoy_pct}% vs FY{full_budget_kpis[0].prior_fy}
    </span>
</div>

<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:8px; align-items:stretch;">
    <div style="border:0.5px solid #e2d9f3; border-top:3px solid #211030; border-radius:10px; background:#fff; padding:14px 16px;">
        <div style="font-size:8px; color:#6B7280; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:4px; font-family:monospace;">Operating Budget</div>
        <div style="font-size:22px; font-weight:800; color:#211030;">{full_budget_kpis[0].latest_budget >= 1e9 ? '$' + (full_budget_kpis[0].latest_budget/1e9).toFixed(2) + 'B' : '$' + (full_budget_kpis[0].latest_budget/1e6).toFixed(1) + 'M'}</div>
        <div style="font-size:10px; margin-top:4px; color:{full_budget_kpis[0].yoy_pct > 0 ? '#2EAD6B' : '#E24B4A'};">
            {full_budget_kpis[0].yoy_pct > 0 ? '↑' : '↓'} {Math.abs(full_budget_kpis[0].yoy_pct)}% vs FY{full_budget_kpis[0].prior_fy}
        </div>
    </div>
    <div style="border:0.5px solid #e2d9f3; border-top:3px solid #3a1f5a; border-radius:10px; background:#fff; padding:14px 16px;">
        <div style="font-size:8px; color:#6B7280; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:4px; font-family:monospace;">General Fund</div>
        <div style="font-size:22px; font-weight:800; color:#211030;">{full_budget_kpis[0].general_pct}%</div>
        <div style="font-size:10px; margin-top:4px; color:{full_budget_kpis[0].general_yoy_pct > 0 ? '#2EAD6B' : '#E24B4A'};">
            {full_budget_kpis[0].general_yoy_pct > 0 ? '↑' : '↓'} {Math.abs(full_budget_kpis[0].general_yoy_pct)}% vs FY{full_budget_kpis[0].prior_fy}
        </div>
    </div>
    <div style="border:0.5px solid #e2d9f3; border-top:3px solid #551c8e; border-radius:10px; background:#fff; padding:14px 16px;">
        <div style="font-size:8px; color:#6B7280; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:4px; font-family:monospace;">Federal Funds</div>
        <div style="font-size:22px; font-weight:800; color:#211030;">{full_budget_kpis[0].federal_pct}%</div>
        <div style="font-size:10px; margin-top:4px; color:{full_budget_kpis[0].federal_yoy_pct > 0 ? '#2EAD6B' : '#E24B4A'};">
            {full_budget_kpis[0].federal_yoy_pct > 0 ? '↑' : '↓'} {Math.abs(full_budget_kpis[0].federal_yoy_pct)}% vs FY{full_budget_kpis[0].prior_fy}
        </div>
    </div>
    <div style="border:0.5px solid #e2d9f3; border-top:3px solid #6321a5; border-radius:10px; background:#fff; padding:14px 16px;">
        <div style="font-size:8px; color:#6B7280; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:4px; font-family:monospace;">State Agencies</div>
        <div style="font-size:22px; font-weight:800; color:#211030;">{full_budget_kpis[0].agency_count}</div>
        <div style="font-size:10px; margin-top:4px; color:#6B7280;">Active FY{full_budget_kpis[0].latest_fy}</div>
    </div>
</div>

<div style="font-family:'JetBrains Mono',monospace; font-size:8px; color:#802cd7; text-transform:uppercase; letter-spacing:0.14em; font-weight:700; border-bottom:2px solid #802cd7; padding-bottom:5px; margin-bottom:12px; margin-top:20px;">
    IT Budget · FY{it_budget_kpis[0].latest_fy}
    <span style="font-weight:400; color:#6B7280; margin-left:12px;">
        YoY: {it_budget_kpis[0].yoy_pct > 0 ? '+' : ''}{it_budget_kpis[0].yoy_pct}% · 5-Year CAGR: {it_budget_kpis[0].cagr_5y}%
    </span>
</div>

<div style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:8px; align-items:stretch;">
    <div style="border:0.5px solid #e2d9f3; border-top:3px solid #802cd7; border-radius:10px; background:#fff; padding:14px 16px;">
        <div style="font-size:8px; color:#6B7280; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:4px; font-family:monospace;">IT Spend</div>
        <div style="font-size:22px; font-weight:800; color:#211030;">{it_budget_kpis[0].latest_it_spend >= 1e9 ? '$' + (it_budget_kpis[0].latest_it_spend/1e9).toFixed(2) + 'B' : '$' + (it_budget_kpis[0].latest_it_spend/1e6).toFixed(1) + 'M'}</div>
        <div style="font-size:10px; margin-top:4px; color:{it_budget_kpis[0].yoy_pct > 0 ? '#2EAD6B' : '#E24B4A'};">
            {it_budget_kpis[0].yoy_pct > 0 ? '↑' : '↓'} {Math.abs(it_budget_kpis[0].yoy_pct)}% vs prior year
        </div>
    </div>
    <div style="border:0.5px solid #e2d9f3; border-top:3px solid #6321a5; border-radius:10px; background:#fff; padding:14px 16px;">
        <div style="font-size:8px; color:#6B7280; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:4px; font-family:monospace;">IT as % of Budget</div>
        <div style="font-size:22px; font-weight:800; color:#211030;">{it_budget_kpis[0].it_pct_of_budget}%</div>
        <div style="font-size:10px; margin-top:4px; color:{it_budget_kpis[0].cagr_5y > 0 ? '#2EAD6B' : '#E24B4A'};">
            {it_budget_kpis[0].cagr_5y > 0 ? '↑' : '↓'} {Math.abs(it_budget_kpis[0].cagr_5y)}% 5yr CAGR
        </div>
    </div>
    <div style="border:0.5px solid #e2d9f3; border-top:3px solid #551c8e; border-radius:10px; background:#fff; padding:14px 16px; overflow:hidden;">
        <div style="font-size:8px; color:#6B7280; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:4px; font-family:monospace;">Top IT Agency</div>
        <div style="font-size:13px; font-weight:800; color:#211030; line-height:1.2;">{it_budget_kpis[0].top_it_agency}</div>
        <div style="font-size:10px; margin-top:4px; color:#6B7280;">Highest IT spend FY{it_budget_kpis[0].latest_fy}</div>
    </div>
</div>

---

<div style="font-family:'JetBrains Mono',monospace; font-size:8px; color:#802cd7; text-transform:uppercase; letter-spacing:0.14em; font-weight:700; border-bottom:1px solid #e2d9f3; padding-bottom:5px; margin-bottom:12px;">
    Explore the Dashboard
</div>

<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:24px;">
    <a href="/budget-office" style="display:block; background:var(--nxt-surface); border:0.5px solid var(--nxt-border); border-left:4px solid #211030; border-radius:10px; padding:16px 18px; text-decoration:none; box-shadow:0 1px 0 rgba(99,33,165,0.03);">
        <div style="font-size:13px; font-weight:700; color:#211030; margin-bottom:4px;">🏛 Budget Office</div>
        <div style="font-size:10px; color:#6B7280; line-height:1.5;">Agency budgets, fund breakdown, YoY trends and agency drill-down</div>
        <div style="font-size:10px; color:#802cd7; font-weight:700; margin-top:8px;">Open →</div>
    </a>
    <a href="/technology" style="display:block; background:var(--nxt-surface); border:0.5px solid var(--nxt-border); border-left:4px solid #6321a5; border-radius:10px; padding:16px 18px; text-decoration:none; box-shadow:0 1px 0 rgba(99,33,165,0.03);">
        <div style="font-size:13px; font-weight:700; color:#211030; margin-bottom:4px;">💻 Technology</div>
        <div style="font-size:10px; color:#6B7280; line-height:1.5;">IT spend by TBM tower and cost pool. Agency IT benchmarks and trends</div>
        <div style="font-size:10px; color:#802cd7; font-weight:700; margin-top:8px;">Open →</div>
    </a>
    <a href="/variance-analysis" style="display:block; background:var(--nxt-surface); border:0.5px solid var(--nxt-border); border-left:4px solid #b376f6; border-radius:10px; padding:16px 18px; text-decoration:none; box-shadow:0 1px 0 rgba(99,33,165,0.03);">
        <div style="font-size:13px; font-weight:700; color:#211030; margin-bottom:4px;">📊 Variance Analysis</div>
        <div style="font-size:10px; color:#6B7280; line-height:1.5;">Budget vs actual comparison, anomaly detection and threshold flags</div>
        <div style="font-size:10px; color:#802cd7; font-weight:700; margin-top:8px;">Open →</div>
    </a>
    <a href="/anomaly-detection" style="display:block; background:var(--nxt-surface); border:0.5px solid var(--nxt-border); border-left:4px solid #551c8e; border-radius:10px; padding:16px 18px; text-decoration:none; box-shadow:0 1px 0 rgba(99,33,165,0.03);">
        <div style="font-size:13px; font-weight:700; color:#211030; margin-bottom:4px;">🔍 Anomaly Detection</div>
        <div style="font-size:10px; color:#6B7280; line-height:1.5;">Unusual spend patterns, statistical outliers and flagged programs</div>
        <div style="font-size:10px; color:#802cd7; font-weight:700; margin-top:8px;">Open →</div>
    </a>
    <a href="/ask-questions" style="display:block; background:var(--nxt-surface); border:0.5px solid var(--nxt-border); border-left:4px solid #802cd7; border-radius:10px; padding:16px 18px; text-decoration:none; box-shadow:0 1px 0 rgba(99,33,165,0.03);">
        <div style="font-size:13px; font-weight:700; color:#211030; margin-bottom:4px;">💬 Ask Questions</div>
        <div style="font-size:10px; color:#6B7280; line-height:1.5;">AI-powered natural language Q&A over the full budget dataset</div>
        <div style="font-size:10px; color:#802cd7; font-weight:700; margin-top:8px;">Open →</div>
    </a>
</div>

<div style="font-size:9px; color:#9CA3AF; text-align:center; font-family:'JetBrains Mono',monospace; margin-top:32px; padding-top:16px; border-top:1px solid #e2d9f3;">
    State of Maryland · Department of Budget & Management · FY{fy_range[0].start_year}–FY{fy_range[0].end_year} · TBM v5.0.1
</div>
