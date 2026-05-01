*
    dim_fiscal_year
    ===============
    Time spine at fiscal year grain.
    Maryland fiscal years run July 1 - June 30.
*/

with years as (
    select
        cast(d as date) as fiscal_year_start
    from generate_series(
        date '2017-01-01',
        date '2027-01-01',
        interval 1 year
    ) as t(d)
),

final as (
    select
        date_part('year', fiscal_year_start)::int as fiscal_year,
        fiscal_year_start,
        fiscal_year_start + interval '1 year' - interval '1 day' as fiscal_year_end
    from years
)

select * from final