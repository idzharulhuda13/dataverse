-- src_stores: Pass-through staging for store locations.

with raw as (
    select * from read_parquet('{{ env_var("DBT_DATA_PATH", "../../data/Chocolate Sales") }}/stores.parquet')
)

select
    store_id,
    store_name,
    city,
    country,
    store_type
from raw
