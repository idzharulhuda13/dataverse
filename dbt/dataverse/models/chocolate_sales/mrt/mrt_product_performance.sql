-- mrt_product_performance: Product-level sales KPIs.
-- Business question: "Which products/brands/categories drive the most profit? What's the margin by cocoa tier?"

with sales as (
    select * from {{ ref('mrt_sales') }}
)

select
    product_id,
    product_name,
    brand,
    category,
    cocoa_percent,
    cocoa_tier,
    weight_g,
    weight_tier,

    -- Volume
    count(distinct order_id)                                as total_orders,
    sum(quantity)                                           as total_units_sold,

    -- Revenue & profitability
    round(sum(revenue), 2)                                  as total_revenue,
    round(sum(cost), 2)                                     as total_cost,
    round(sum(profit), 2)                                   as total_profit,

    round(avg(unit_price), 2)                               as avg_unit_price,
    round(sum(profit) / nullif(sum(revenue), 0) * 100, 2)  as profit_margin_pct,

    -- Revenue per unit (net of discounts)
    round(sum(revenue) / nullif(sum(quantity), 0), 2)       as avg_revenue_per_unit,

    -- Discount stats
    round(avg(discount) * 100, 1)                           as avg_discount_pct,
    sum(case when discount > 0 then 1 else 0 end)           as discounted_orders,
    round(
        sum(case when discount > 0 then 1 else 0 end) * 100.0
        / nullif(count(distinct order_id), 0),
        1
    )                                                       as discount_rate_pct,

    -- Unique customers who bought this product
    count(distinct customer_id)                             as unique_customers

from sales
group by
    product_id,
    product_name,
    brand,
    category,
    cocoa_percent,
    cocoa_tier,
    weight_g,
    weight_tier
