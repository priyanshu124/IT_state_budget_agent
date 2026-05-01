/*
    fct_it_spend
    =============
    Fact table for all IT-classified budget line items.
    This is the primary table for TBM analysis.
    
    Contains both IT and non-IT rows so stakeholders can compute
    IT-as-percentage-of-total. Use is_it = true to filter to IT only.
    
    Grain: same as staging — one row per budget line item.
*/

with budget as (
    select * from {{ ref('stg_budget_line_items') }}
),

normalized as (
    select
        *,
        case
            when upper(trim(cast(it_tower as varchar))) = 'NOT_IT' then false
            else coalesce(is_it, false)
        end as is_it_normalized,
        case
            when upper(trim(cast(it_tower as varchar))) = 'NOT_IT' then null
            else it_tower
        end as it_tower_normalized,
        case
            when upper(trim(cast(it_tower as varchar))) = 'NOT_IT' then null
            else it_sub_tower
        end as it_sub_tower_normalized,
        case
            when upper(trim(cast(it_tower as varchar))) = 'NOT_IT' then null
            else tower_confidence
        end as tower_confidence_normalized
    from budget
),

final as (
    select
        -- === SURROGATE KEY ===
        {{ dbt_utils.surrogate_key([
            'fiscal_year', 
            'organization_sub_code', 
            'subobject_code',
            'agency_subobject_code', 
            'fund_type', 
            'budget_type'
        ]) }}                                       as spend_id,

        -- === TIME ===
        fiscal_year,
        
        -- === ORGANIZATIONAL DIMENSIONS ===
        agency_code,
        agency_name,
        unit_code,
        unit_name,
        program_code,
        program_name,
        subprogram_code,
        subprogram_name,
        organization_code,
        organization_sub_code,

        -- === ACCOUNTING DIMENSIONS ===
        object_code,
        object_name,
        subobject_code,
        subobject_name,
        fund_type,
        budget_type,
        category_code,
        category_name,

        -- === TBM CLASSIFICATION ===
        is_it_normalized                            as is_it,
        it_designation,
        
        -- Tower (null for non-IT rows)
        it_tower_normalized                         as it_tower,
        it_sub_tower_normalized                     as it_sub_tower,
        tower_confidence_normalized                 as tower_confidence,
        
        -- Cost Pool (populated for ALL rows)
        cost_pool,
        cost_sub_pool,

        -- === MEASURE ===
        amount,
        
        -- === DERIVED MEASURES ===
        case when is_it_normalized then amount else 0 end      as it_amount,
        case when not is_it_normalized then amount else 0 end  as non_it_amount

    from normalized
)

select * from final
