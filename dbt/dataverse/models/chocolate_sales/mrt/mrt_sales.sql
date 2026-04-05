{{
    config(materialized='table')
}}

-- mrt_sales: Main One Big Table (OBT) — the ONLY stored table.
-- All other mrt_ models are views computed from this.
-- Joins all dimensions onto the fact sales table.

with sales as (
    select * from {{ ref('src_sales') }}
),

customers as (
    select * from {{ ref('dim_customers') }}
),

products as (
    select * from {{ ref('dim_products') }}
),

stores as (
    select * from {{ ref('dim_stores') }}
),

dates as (
    select * from {{ ref('dim_date') }}
)

select
    -- ── Order identifiers ──────────────────────────────────────────────
    s.order_id,
    s.order_date,

    -- ── Time dimensions ────────────────────────────────────────────────
    d.year,
    d.month,
    d.month_name,
    d.month_short,
    d.quarter,
    d.week,
    d.day_of_week,
    d.day_name,
    d.is_weekend,
    d.year_month,

    -- ── Customer dimensions ────────────────────────────────────────────
    s.customer_id,
    c.age                       as customer_age,
    c.age_band                  as customer_age_band,
    c.gender                    as customer_gender,
    c.loyalty_member,
    c.join_date                 as customer_join_date,
    c.customer_tenure_days,
    c.tenure_band               as customer_tenure_band,

    -- ── Product dimensions ─────────────────────────────────────────────
    s.product_id,
    p.product_name,
    p.brand,
    p.category,
    p.cocoa_percent,
    p.cocoa_tier,
    p.weight_g,
    p.weight_tier,

    -- ── Store dimensions ───────────────────────────────────────────────
    s.store_id,
    st.store_name,
    st.city,
    st.country,
    st.store_type,
    st.region,

    -- ── Sales metrics ──────────────────────────────────────────────────
    s.quantity,
    s.unit_price,
    s.discount,

    -- Discount label for readable segmentation
    case
        when s.discount = 0    then 'No Discount'
        when s.discount = 0.10 then '10% Off'
        when s.discount = 0.15 then '15% Off'
        when s.discount = 0.20 then '20% Off'
        else cast(round(s.discount * 100) as varchar) || '% Off'
    end                         as discount_label,

    s.revenue,
    s.cost,
    s.profit,

    -- Derived KPIs
    round(s.profit / nullif(s.revenue, 0) * 100, 2)    as profit_margin_pct,
    round(s.revenue / nullif(s.quantity, 0), 2)         as revenue_per_unit,
    round(s.cost / nullif(s.quantity, 0), 2)            as cost_per_unit

from sales s
left join customers c   on s.customer_id = c.customer_id
left join products p    on s.product_id  = p.product_id
left join stores st     on s.store_id    = st.store_id
left join dates d       on s.order_date  = d.date