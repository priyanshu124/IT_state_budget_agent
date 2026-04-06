/*
    stg_budget_line_items
    =====================
    Clean, typed, and renamed columns from raw budget data.
    This is the single entry point for all budget data in the project.
    
    Grain: one row per fiscal_year × organization_sub_code × comptroller_subobject_code × fund_type × budget_type
*/



    
    


with source as (
        select * from "mbtsa_work"."main"."budget_line_items"
),

staged as (
    select
        -- === KEYS ===
        organization_sub_code                       as line_item_key,
        fiscal_year::int                            as fiscal_year,

        -- === ORGANIZATIONAL HIERARCHY ===
        agency_code,
        agency_name,
        unit_code,
        unit_name,
        program_code,
        program_name,
        subprogram_code,
        subprogram_name,
        organization_code                           as program_key,

        -- === ACCOUNTING CODES ===
        object_code::varchar                        as object_code,
        object_name,
        comptroller_subobject_code::varchar         as subobject_code,
        comptroller_subobject_name                  as subobject_name,
        agency_subobject_code::varchar              as agency_subobject_code,
        agency_subobject_name,

        -- === BUDGET AMOUNTS ===
        budget::bigint                              as amount,
        type                                        as budget_type,
        fund_type_name                              as fund_type,

        -- === BUDGET CATEGORY ===
        category::varchar                           as category_code,
        category_title                              as category_name,

        -- === IT CLASSIFICATION (from pipeline) ===
    
        case
            when upper(trim(cast(tower as varchar))) = 'NOT_IT' then false
            when lower(cast(is_it as varchar)) = 'true' then true
            else false
        end                                         as is_it,
    

    
        coalesce(it_designation, it_designation_right) as it_designation,
    

        -- === TOWER CLASSIFICATION (from Agent 3) ===
        case
            when upper(trim(cast(tower as varchar))) = 'NOT_IT' then null
            else tower
        end                                         as it_tower,
        case
            when upper(trim(cast(tower as varchar))) = 'NOT_IT' then null
            else sub_tower
        end                                         as it_sub_tower,
        case
            when upper(trim(cast(tower as varchar))) = 'NOT_IT' then null
            else confidence::float
        end                                         as tower_confidence,

        -- === COST POOL CLASSIFICATION (from Agent 2) ===
        cost_pool,
        cost_sub_pool

    from source
)

select * from staged