-- src_products: Minimal casting for product catalog.

with raw as (
    select * from read_parquet('{{ env_var("DBT_DATA_PATH", "../../data/Chocolate Sales") }}/products.parquet')
)

select
    product_id,
    product_name,
    brand,
    category,
    cast(cocoa_percent as integer)  as cocoa_percent,
    cast(weight_g as integer)       as weight_g
from raw
