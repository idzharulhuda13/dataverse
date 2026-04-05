-- dim_products: Product catalog with derived cocoa and weight tiers.

with src as (
    select * from {{ ref('src_products') }}
)

select
    product_id,
    product_name,
    brand,
    category,
    cocoa_percent,
    weight_g,

    -- Cocoa intensity tier for premium-positioning analysis
    case
        when cocoa_percent < 50  then 'Milk / White'
        when cocoa_percent < 70  then 'Semi-Dark'
        when cocoa_percent < 80  then 'Dark'
        else 'Extra Dark'
    end                         as cocoa_tier,

    -- Package size tier
    case
        when weight_g < 100     then 'Small (< 100g)'
        when weight_g < 150     then 'Medium (100–149g)'
        else 'Large (150g+)'
    end                         as weight_tier

from src
