---
title: Maryland Budget & Technology Budget Analysis
sidebar_position: 1
---

<div style="background: linear-gradient(135deg, #802cd7 0%, #211030 100%); padding: 40px 48px; border-radius: 12px; border-bottom: 4px solid #b376f6; margin-bottom: 32px; text-align: center;">
    <h1 style="color: white; font-family: 'DM Sans', sans-serif; font-size: 2rem; font-weight: 700; margin: 0;">MBTSA<br>Budget Analysis</h1>
    <p style="color: #b376f6; font-size: 1rem; margin: 8px 0 0 0;">Transparency in Government Budget · AI-Powered Analysis</p>
    <p style="color: rgba(255,255,255,0.5); font-size: 0.8rem; margin: 4px 0 0 0;">FY2020–FY2027 · 530,000+ Line Items · 80 State Agencies · TBM v5.0.1</p>
</div>

```sql home
select
    case
        when abs(sum(amount)) >= 1000000000 then '$' || printf('%.2f', sum(amount) / 1000000000.0) || 'B'
        when abs(sum(amount)) >= 1000000 then '$' || printf('%.2f', sum(amount) / 1000000.0) || 'M'
        when abs(sum(amount)) >= 1000 then '$' || printf('%.2f', sum(amount) / 1000.0) || 'K'
        else '$' || printf('%.2f', sum(amount))
    end as total_budget_display,
    case
        when abs(sum(it_amount)) >= 1000000000 then '$' || printf('%.2f', sum(it_amount) / 1000000000.0) || 'B'
        when abs(sum(it_amount)) >= 1000000 then '$' || printf('%.2f', sum(it_amount) / 1000000.0) || 'M'
        when abs(sum(it_amount)) >= 1000 then '$' || printf('%.2f', sum(it_amount) / 1000.0) || 'K'
        else '$' || printf('%.2f', sum(it_amount))
    end as it_budget_display,
    sum(it_amount)*1.0/nullif(sum(amount),0) as it_pct,
    count(distinct agency_name) as agencies
from mbtsa.budget
```

<Grid cols=4>
    <BigValue data={home} value=total_budget_display title="Total State Budget"/>
    <BigValue data={home} value=it_budget_display title="IT Budget"/>
    <BigValue data={home} value=it_pct fmt=pct2 title="IT % of Budget"/>
    <BigValue data={home} value=agencies title="State Agencies"/>
</Grid>

---

<Grid cols=3>
<BigLink url="/budget-office">🏛️ Budget Office →</BigLink>
<BigLink url="/technology">💻 Technology →</BigLink>
<BigLink url="/ask-questions">💬 Ask Questions →</BigLink>
</Grid>

> **For analysts:** Variance analysis, anomaly detection, fund breakdown with drill-down. **For executives:** Strategic overview, fiscal health, YoY trends. **For agency heads:** Find your agency's budget and composition. **For the public:** Explore how Maryland budgets your tax dollars.
