select
  city,
  date_trunc(observation_date, month) as month,
  count(*) as observed_days,
  round(avg(max_temp_c), 2) as avg_daily_max_temp_c,
  round(avg(min_temp_c), 2) as avg_daily_min_temp_c,
  round(sum(coalesce(precipitation_mm, 0)), 2) as precipitation_total_mm
from {{ ref('stg_weather_daily') }}
group by 1, 2
