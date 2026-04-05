-- dim_date: Full date dimension with human-readable labels.

with src as (
    select * from {{ ref('src_calendar') }}
)

select
    date,
    year,
    month,
    day,
    week,
    day_of_week,

    -- Human-readable month name
    case month
        when 1  then 'January'
        when 2  then 'February'
        when 3  then 'March'
        when 4  then 'April'
        when 5  then 'May'
        when 6  then 'June'
        when 7  then 'July'
        when 8  then 'August'
        when 9  then 'September'
        when 10 then 'October'
        when 11 then 'November'
        when 12 then 'December'
    end                                     as month_name,

    -- Short month label (for charts)
    case month
        when 1  then 'Jan' when 2  then 'Feb' when 3  then 'Mar'
        when 4  then 'Apr' when 5  then 'May' when 6  then 'Jun'
        when 7  then 'Jul' when 8  then 'Aug' when 9  then 'Sep'
        when 10 then 'Oct' when 11 then 'Nov' when 12 then 'Dec'
    end                                     as month_short,

    -- Quarter label
    case
        when month between 1 and 3  then 'Q1'
        when month between 4 and 6  then 'Q2'
        when month between 7 and 9  then 'Q3'
        else 'Q4'
    end                                     as quarter,

    -- Day of week name (DuckDB: 0=Sunday, 6=Saturday)
    case day_of_week
        when 0 then 'Sunday'
        when 1 then 'Monday'
        when 2 then 'Tuesday'
        when 3 then 'Wednesday'
        when 4 then 'Thursday'
        when 5 then 'Friday'
        when 6 then 'Saturday'
    end                                     as day_name,

    -- Weekend flag
    case
        when day_of_week in (0, 6) then true
        else false
    end                                     as is_weekend,

    -- Year-Month label for time-series charts (e.g. "2023-01")
    cast(year as varchar) || '-' || lpad(cast(month as varchar), 2, '0')  as year_month

from src
