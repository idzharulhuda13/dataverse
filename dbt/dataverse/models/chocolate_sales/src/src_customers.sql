-- src_customers: Minimal casting for customer profiles.

with raw as (
    select * from read_parquet('{{ env_var("DBT_DATA_PATH", "../../data/Chocolate Sales") }}/customers.parquet')
)

select
    customer_id,
    cast(age as integer)                    as age,
    gender,
    cast(loyalty_member as boolean)         as loyalty_member,
    cast(join_date as date)                 as join_date
from raw
