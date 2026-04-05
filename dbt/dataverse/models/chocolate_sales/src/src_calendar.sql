-- src_calendar: Minimal casting for the date spine.

with raw as (
    select * from read_parquet('{{ env_var("DBT_DATA_PATH", "../../data/Chocolate Sales") }}/calendar.parquet')
)

select
    cast(date as date)          as date,
    cast(year as integer)       as year,
    cast(month as integer)      as month,
    cast(day as integer)        as day,
    cast(week as integer)       as week,
    cast(day_of_week as integer) as day_of_week
from raw
