-- mrt_daily_sales: Date-grain time-series for forecasting and trend analysis.
-- Business question: "Show me the revenue trend. Forecast the next 30 days."

with sales as (
    select * from {{ ref('mrt_sales') }}
)

select
    order_date                                              as date,
    year,
    month,
    month_name,
    month_short,
    quarter,
    week,
    day_of_week,
    day_name,
    is_weekend,
    year_month,

    -- Daily volume
    count(distinct order_id)                                as daily_orders,
    sum(quantity)                                           as daily_units,

    -- Daily financials
    round(sum(revenue), 2)                                  as daily_revenue,
    round(sum(cost), 2)                                     as daily_cost,
    round(sum(profit), 2)                                   as daily_profit,

    round(sum(profit) / nullif(sum(revenue), 0) * 100, 2)  as daily_profit_margin_pct,
    round(avg(discount) * 100, 1)                           as avg_discount_pct,

    -- Customer activity
    count(distinct customer_id)                             as unique_customers,
    sum(case when loyalty_member then 1 else 0 end)         as loyalty_member_orders

from sales
group by
    order_date,
    year,
    month,
    month_name,
    month_short,
    quarter,
    week,
    day_of_week,
    day_name,
    is_weekend,
    year_month
order by
    order_date
