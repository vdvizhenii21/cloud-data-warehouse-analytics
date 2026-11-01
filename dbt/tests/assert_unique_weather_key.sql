select city, observation_date
from {{ ref('stg_weather_daily') }}
group by 1, 2
having count(*) > 1
