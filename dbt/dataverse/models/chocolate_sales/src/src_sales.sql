-- src_sales: Minimal casting layer for raw sales transactions.
-- No business logic — only type casting and column rename if needed.

with raw as (
    select * from read_parquet('{{ env_var("DBT_DATA_PATH", "../../data/Chocolate Sales") }}/sales.parquet')
)

select
    order_id,
    cast(order_date as date)     as order_date,
    product_id,
    store_id,
    customer_id,
    cast(quantity as integer)    as quantity,
    cast(unit_price as double)   as unit_price,
    cast(discount as double)     as discount,
    cast(revenue as double)      as revenue,
    cast(cost as double)         as cost,
    cast(profit as double)       as profit
from raw
