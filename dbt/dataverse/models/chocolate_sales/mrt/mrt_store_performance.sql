-- mrt_store_performance: Store-level sales KPIs.
-- Business question: "How do stores compare by region? Which store_type performs best?"

with sales as (
    select * from {{ ref('mrt_sales') }}
)

select
    store_id,
    store_name,
    city,
    country,
    region,
    store_type,

    -- Volume
    count(distinct order_id)                                as total_orders,
    sum(quantity)                                           as total_units_sold,

    -- Revenue & profitability
    round(sum(revenue), 2)                                  as total_revenue,
    round(sum(cost), 2)                                     as total_cost,
    round(sum(profit), 2)                                   as total_profit,

    round(avg(revenue), 2)                                  as avg_order_revenue,
    round(sum(profit) / nullif(sum(revenue), 0) * 100, 2)  as profit_margin_pct,

    -- Discount behaviour
    round(avg(discount) * 100, 1)                           as avg_discount_pct,

    -- Customer metrics
    count(distinct customer_id)                             as unique_customers,
    sum(case when loyalty_member then 1 else 0 end)         as loyalty_member_orders,
    round(
        sum(case when loyalty_member then 1 else 0 end) * 100.0
        / nullif(count(distinct order_id), 0),
        1
    )                                                       as loyalty_member_rate_pct,

    -- Product diversity
    count(distinct product_id)                              as unique_products_sold,

    -- Time range
    min(order_date)                                         as first_sale_date,
    max(order_date)                                         as last_sale_date

from sales
group by
    store_id,
    store_name,
    city,
    country,
    region,
    store_type
