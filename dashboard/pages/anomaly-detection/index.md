---
title: Anomaly Detection
sidebar_position: 5
---

<div style="background: linear-gradient(135deg, #ede5f8 0%, #d4bef0 100%); padding: 28px 36px; border-radius: 12px; border-bottom: 4px solid #802cd7; margin-bottom: 0;">
    <h1 style="color: #211030; font-size: 1.7rem; font-weight: 700; margin: 0;">🔍 Anomaly Detection</h1>
    <p style="color: #6321a5; font-size: 0.95rem; margin: 4px 0 0 0;">Unusual spending patterns — deviations from historical agency averages</p>
</div>

```sql g_agency
select distinct agency_name from mbtsa.subprogram_level where agency_name is not null order by agency_name
```
```sql g_fy
select distinct fiscal_year as fy from mbtsa.subprogram_level order by fiscal_year
```

<Details title=" Filters  click to expand" open=true>
<Grid cols=3>
    <Dropdown name=f_fy data={g_fy} value=fy title="Fiscal Year" defaultValue="%"><DropdownOption value="%" valueLabel="All Years"/></Dropdown>
    <Dropdown name=f_agency data={g_agency} value=agency_name title="Agency" defaultValue="%"><DropdownOption value="%" valueLabel="All Agencies"/></Dropdown>
    <Dropdown name=f_threshold title="Deviation Threshold" defaultValue="25">
        <DropdownOption value="10" valueLabel=">10% deviation"/>
        <DropdownOption value="25" valueLabel=">25% deviation"/>
        <DropdownOption value="50" valueLabel=">50% deviation"/>
        <DropdownOption value="100" valueLabel=">100% deviation"/>
    </Dropdown>
</Grid>
</Details>

```sql anomalies
with agency_yearly as (
    select
        agency_name,
        fiscal_year,
        sum(total_budget_amount) as spend
    from mbtsa.subprogram_level
    where coalesce(agency_name,'') like '${inputs.f_agency.value ?? "%"}'
    group by agency_name, fiscal_year
),
with_stats as (
    select
        agency_name,
        fiscal_year,
        spend,
        avg(spend) over (partition by agency_name)    as avg_spend,
        stddev(spend) over (partition by agency_name) as std_spend,
        round((spend - avg(spend) over (partition by agency_name)) * 100.0
              / nullif(avg(spend) over (partition by agency_name), 0), 1) as deviation_pct
    from agency_yearly
)
select
    agency_name,
    fiscal_year,
    spend,
    avg_spend,
    deviation_pct,
    case when deviation_pct > 0 then 'Spike' else 'Drop' end as anomaly_type
from with_stats
where abs(deviation_pct) > ${inputs.f_threshold.value ?? 25}
  and cast(fiscal_year as varchar) like '${inputs.f_fy.value ?? "%"}'
order by abs(deviation_pct) desc
```

```sql anomaly_summary
select
    count(*) as total_anomalies,
    count(case when anomaly_type = 'Spike' then 1 end) as spikes,
    count(case when anomaly_type = 'Drop' then 1 end) as drops,
    count(distinct agency_name) as affected_agencies
from ${anomalies}
```

<Grid cols=4>
    <BigValue data={anomaly_summary} value=total_anomalies title="Anomalies Detected"/>
    <BigValue data={anomaly_summary} value=spikes title="Spending Spikes"/>
    <BigValue data={anomaly_summary} value=drops title="Spending Drops"/>
    <BigValue data={anomaly_summary} value=affected_agencies title="Affected Agencies"/>
</Grid>

---

## Spending Spikes

```sql positive_anomalies
select * from ${anomalies} where anomaly_type = 'Spike' order by deviation_pct desc
```

{#if positive_anomalies.length > 0}
<DataTable data={positive_anomalies} search=true rows=15>
    <Column id=agency_name title="Agency"/>
    <Column id=fiscal_year title="FY"/>
    <Column id=spend title="Spend" fmt=usd2compactviz/>
    <Column id=avg_spend title="Avg Spend" fmt=usd2compactviz/>
    <Column id=deviation_pct title="Deviation (%)" fmt='0.0"%"' contentType=colorscale colorScale=positive/>
</DataTable>
{:else}
<Alert status=info>No spending spikes detected at this threshold.</Alert>
{/if}

---

## Spending Drops

```sql negative_anomalies
select * from ${anomalies} where anomaly_type = 'Drop' order by deviation_pct asc
```

{#if negative_anomalies.length > 0}
<DataTable data={negative_anomalies} search=true rows=15>
    <Column id=agency_name title="Agency"/>
    <Column id=fiscal_year title="FY"/>
    <Column id=spend title="Spend" fmt=usd2compactviz/>
    <Column id=avg_spend title="Avg Spend" fmt=usd2compactviz/>
    <Column id=deviation_pct title="Deviation (%)" fmt='0.0"%"' contentType=colorscale colorScale=negative/>
</DataTable>
{:else}
<Alert status=info>No spending drops detected at this threshold.</Alert>
{/if}

---

## Program-Level Anomalies

```sql deep_anomalies
with prog_yearly as (
    select agency_name, program_name, fiscal_year, sum(total_budget_amount) as spend
    from mbtsa.subprogram_level
    where coalesce(agency_name,'') like '${inputs.f_agency.value ?? "%"}'
    group by agency_name, program_name, fiscal_year
),
with_dev as (
    select *,
        round((spend - avg(spend) over (partition by agency_name, program_name)) * 100.0
              / nullif(avg(spend) over (partition by agency_name, program_name), 0), 1) as deviation_pct
    from prog_yearly
)
select * from with_dev
where abs(deviation_pct) > ${inputs.f_threshold.value ?? 25}
  and cast(fiscal_year as varchar) like '${inputs.f_fy.value ?? "%"}'
order by abs(deviation_pct) desc
limit 50
```

<DataTable data={deep_anomalies} search=true rows=25>
    <Column id=agency_name title="Agency"/>
    <Column id=program_name title="Program"/>
    <Column id=fiscal_year title="FY"/>
    <Column id=spend title="Spend" fmt=usd2compactviz/>
    <Column id=deviation_pct title="Deviation (%)" fmt='0.0"%"' contentType=colorscale colorScale=diverging/>
</DataTable>
