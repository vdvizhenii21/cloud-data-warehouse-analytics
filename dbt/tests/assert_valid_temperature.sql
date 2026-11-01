select * from {{ ref('stg_weather_daily') }}
where max_temp_c < min_temp_c
