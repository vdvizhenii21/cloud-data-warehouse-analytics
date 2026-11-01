select
  city,
  observation_date,
  temperature_2m_max as max_temp_c,
  temperature_2m_min as min_temp_c,
  precipitation_sum as precipitation_mm
from {{ source('raw', 'raw_weather_daily') }}
