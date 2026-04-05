-- dim_customers: Enriched customer dimension with derived segments.

with src as (
    select * from {{ ref('src_customers') }}
)

select
    customer_id,
    age,

    -- Age banding for segmentation analysis
    case
        when age between 18 and 24 then '18–24'
        when age between 25 and 34 then '25–34'
        when age between 35 and 44 then '35–44'
        when age between 45 and 54 then '45–54'
        else '55+'
    end                                         as age_band,

    gender,
    loyalty_member,
    join_date,

    -- Customer tenure in days from join date to end of dataset (2024-12-31)
    cast(date_diff('day', join_date, date '2024-12-31') as integer) as customer_tenure_days,

    -- Tenure bucketing
    case
        when date_diff('day', join_date, date '2024-12-31') < 365 then '< 1 Year'
        when date_diff('day', join_date, date '2024-12-31') < 730 then '1–2 Years'
        else '2+ Years'
    end                                         as tenure_band

from src
