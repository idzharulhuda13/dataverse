-- dim_stores: Store directory with derived region field.

with src as (
    select * from {{ ref('src_stores') }}
)

select
    store_id,
    store_name,
    city,
    country,
    store_type,

    -- High-level region grouping from country
    case
        when country in ('Canada', 'USA', 'United States') then 'North America'
        when country in ('UK', 'United Kingdom', 'France', 'Germany',
                         'Italy', 'Spain', 'Netherlands', 'Belgium',
                         'Sweden', 'Switzerland', 'Austria', 'Poland') then 'Europe'
        when country in ('Australia', 'New Zealand') then 'Oceania'
        when country in ('Japan', 'China', 'India', 'South Korea',
                         'Singapore', 'Thailand', 'Vietnam', 'Indonesia',
                         'Malaysia', 'Philippines') then 'Asia'
        when country in ('Brazil', 'Argentina', 'Colombia', 'Chile',
                         'Peru', 'Mexico') then 'Latin America'
        when country in ('South Africa', 'Nigeria', 'Kenya', 'Egypt',
                         'Morocco', 'Ghana') then 'Africa'
        when country in ('UAE', 'Saudi Arabia', 'Qatar', 'Kuwait',
                         'Bahrain', 'Jordan') then 'Middle East'
        else 'Other'
    end                 as region

from src
