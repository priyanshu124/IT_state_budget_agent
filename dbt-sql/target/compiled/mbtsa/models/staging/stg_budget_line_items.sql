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
        TRIM(REGEXP_REPLACE(organization_sub_code, '\s+', ' ')) AS organization_sub_code,
        

        -- === ORGANIZATIONAL HIERARCHY ===
        fiscal_year::int                            as fiscal_year,
        TRIM(REGEXP_REPLACE(organization_sub_code, '\s+', ' ')) AS organization_sub_code,
        TRIM(REGEXP_REPLACE(organization_code, '\s+', ' ')) AS organization_code,
        TRIM(REGEXP_REPLACE(agency_code, '\s+', ' ')) AS agency_code,
        TRIM(REGEXP_REPLACE(agency_name, '\s+', ' ')) AS agency_name,
        TRIM(REGEXP_REPLACE(unit_code, '\s+', ' ')) AS unit_code,
        TRIM(REGEXP_REPLACE(unit_name, '\s+', ' ')) AS unit_name,
        TRIM(REGEXP_REPLACE(program_code::varchar, '\s+', ' ')) AS program_code,
        TRIM(REGEXP_REPLACE(program_name, '\s+', ' ')) AS program_name,
        TRIM(REGEXP_REPLACE(subprogram_code, '\s+', ' ')) AS subprogram_code,
        TRIM(REGEXP_REPLACE(subprogram_name, '\s+', ' ')) AS subprogram_name,
        TRIM(REGEXP_REPLACE(description, '\s+', ' ')) AS description,
        

        -- === ACCOUNTING CODES ===
        TRIM(REGEXP_REPLACE(object_code::varchar, '\s+', ' ')) AS object_code,
        TRIM(REGEXP_REPLACE(object_name, '\s+', ' ')) AS object_name,
        TRIM(REGEXP_REPLACE(comptroller_subobject_code::varchar, '\s+', ' ')) AS subobject_code,
        TRIM(REGEXP_REPLACE(comptroller_subobject_name, '\s+', ' ')) AS subobject_name,
        TRIM(REGEXP_REPLACE(agency_subobject_code::varchar, '\s+', ' ')) AS agency_subobject_code,
        TRIM(REGEXP_REPLACE(agency_subobject_name, '\s+', ' ')) AS agency_subobject_name,

        -- === BUDGET AMOUNTS ===
        budget::bigint                              as amount,
        TRIM(REGEXP_REPLACE(type, '\s+', ' ')) AS budget_type,
        TRIM(REGEXP_REPLACE(fund_type_name, '\s+', ' ')) AS fund_type,

        -- === BUDGET CATEGORY ===
        TRIM(REGEXP_REPLACE(category::varchar, '\s+', ' ')) AS category_code,
        TRIM(REGEXP_REPLACE(category_title, '\s+', ' ')) AS category_name,

        -- === IT CLASSIFICATION (from pipeline) ===
        is_it,
        TRIM(REGEXP_REPLACE(it_designation, '\s+', ' ')) AS it_designation,
        TRIM(REGEXP_REPLACE(tower, '\s+', ' ')) AS it_tower,
        TRIM(REGEXP_REPLACE(sub_tower, '\s+', ' ')) AS it_sub_tower,
        confidence as tower_confidence,
        -- === COST POOL CLASSIFICATION (from Agent 2) ===
        CASE
            WHEN TRIM(REGEXP_REPLACE(object_code::varchar, '\\s+', ' ')) = '12' THEN 'Grants'
            ELSE TRIM(REGEXP_REPLACE(cost_pool, '\\s+', ' '))
        END AS cost_pool,
        TRIM(REGEXP_REPLACE(cost_sub_pool, '\\s+', ' ')) AS cost_sub_pool

    from source
    where agency_code != 'R75'
)

select * from staged