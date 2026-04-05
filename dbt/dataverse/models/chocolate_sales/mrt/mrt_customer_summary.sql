-- mrt_customer_summary: Customer-level aggregated lifetime value and purchasing behaviour.
-- Business question: "Who are our best customers? How do loyalty members compare to non-members?"

with sales as (
    select * from {{ ref('mrt_sales') }}
)

select
    customer_id,
    customer_age,
    customer_age_band,
    customer_gender,
    loyalty_member,
    customer_join_date,
    customer_tenure_days,
    customer_tenure_band,

    -- Volume metrics
    count(distinct order_id)                            as total_orders,
    sum(quantity)                                       as total_units,

    -- Revenue metrics
    round(sum(revenue), 2)                              as total_revenue,
    round(sum(cost), 2)                                 as total_cost,
    round(sum(profit), 2)                               as total_profit,

    -- Averages per order
    round(avg(revenue), 2)                              as avg_order_revenue,
    round(avg(quantity), 2)                             as avg_order_quantity,

    -- Profitability
    round(sum(profit) / nullif(sum(revenue), 0) * 100, 2) as overall_profit_margin_pct,

    -- Discount behaviour
    round(avg(discount) * 100, 1)                       as avg_discount_pct,
    sum(case when discount > 0 then 1 else 0 end)       as discounted_orders,

    -- Date range
    min(order_date)                                     as first_order_date,
    max(order_date)                                     as last_order_date,
    count(distinct year_month)                          as active_months

from sales
group by
    customer_id,
    customer_age,
    customer_age_band,
    customer_gender,
    loyalty_member,
    customer_join_date,
    customer_tenure_days,
    customer_tenure_band
