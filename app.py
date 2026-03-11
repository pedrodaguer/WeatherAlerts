import os
from datetime import datetime

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

from alert import format_weather_message, get_cities_by_day, send_weather_alert

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PHONE_NUMBER = os.getenv("PHONE_NUMBER")
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY")
try:
    RAIN_INTENSITY_THRESHOLD_MM = float(os.getenv("RAIN_INTENSITY_THRESHOLD_MM", "0.2"))
except ValueError:
    RAIN_INTENSITY_THRESHOLD_MM = 0.2

if not PHONE_NUMBER or not CALLMEBOT_API_KEY:
    raise ValueError(
        "Set PHONE_NUMBER and CALLMEBOT_API_KEY in .env or environment variables. "
        "See .env.example for reference."
    )

cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

CITIES = {
    "blumenau": {"latitude": -26.9194, "longitude": -49.0661},
    "itajai": {"latitude": -26.9228, "longitude": -48.6606},
}


def get_weather_and_send_alerts():
    """Fetch weather data and send WhatsApp alerts for the configured cities."""
    day_of_week = datetime.now().weekday()
    cities_to_alert = get_cities_by_day(day_of_week)

    print(f"\n{'='*60}")
    print(f"Dia da semana: {get_day_name(day_of_week)}")
    print(f"Cidades para enviar alerta: {', '.join(cities_to_alert)}")
    print(f"{'='*60}\n")

    all_weather_info = []

    for city_name in cities_to_alert:
        if city_name not in CITIES:
            print(f"✗ Cidade '{city_name}' não encontrada")
            continue

        city_coords = CITIES[city_name]
        print(f"\n{'─'*60}")
        print(f"Processando: {city_name.upper()}")
        print(f"{'─'*60}")

        weather_info = fetch_weather_data(city_name, city_coords)
        all_weather_info.append(weather_info)

    if all_weather_info:
        send_weather_alert(PHONE_NUMBER, CALLMEBOT_API_KEY, all_weather_info)


def fetch_weather_data(city_name, city_coords):
    """Fetch weather forecast from Open-Meteo API."""
    weather_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": city_coords["latitude"],
        "longitude": city_coords["longitude"],
        "daily": [
            "weather_code",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
        ],
        # Use total hourly precipitation to match daily precipitation_sum.
        "hourly": "precipitation",
        "timezone": "auto",
        "forecast_days": 1,
    }

    responses = openmeteo.weather_api(weather_url, params=params)
    response = responses[0]

    print(f"Coordinates: {response.Latitude()}°N {response.Longitude()}°E")
    print(f"Elevation: {response.Elevation()} m asl")
    print(f"Timezone: {response.Timezone()}{response.TimezoneAbbreviation()}")

    hourly = response.Hourly()
    hourly_precipitation = hourly.Variables(0).ValuesAsNumpy()

    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time() + response.UtcOffsetSeconds(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd() + response.UtcOffsetSeconds(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        ),
        "precipitation": hourly_precipitation,
    }

    hourly_dataframe = pd.DataFrame(data=hourly_data)
    print("\nHourly data\n", hourly_dataframe)

    rain_hours = []
    for _, row in hourly_dataframe.iterrows():
        rain_mm = float(row["precipitation"])
        if rain_mm >= RAIN_INTENSITY_THRESHOLD_MM:
            hour_str = row["date"].strftime("%H:%M")
            rain_hours.append({"hour": hour_str, "rain": round(rain_mm, 1)})

    daily = response.Daily()
    daily_weather_code = daily.Variables(0).ValuesAsNumpy()
    daily_apparent_temperature_max = daily.Variables(1).ValuesAsNumpy()
    daily_apparent_temperature_min = daily.Variables(2).ValuesAsNumpy()
    daily_temperature_2m_max = daily.Variables(3).ValuesAsNumpy()
    daily_temperature_2m_min = daily.Variables(4).ValuesAsNumpy()
    daily_precipitation_sum = daily.Variables(5).ValuesAsNumpy()

    daily_data = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time() + response.UtcOffsetSeconds(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd() + response.UtcOffsetSeconds(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left",
        ),
        "weather_code": daily_weather_code,
        "apparent_temperature_max": daily_apparent_temperature_max,
        "apparent_temperature_min": daily_apparent_temperature_min,
        "temperature_2m_max": daily_temperature_2m_max,
        "temperature_2m_min": daily_temperature_2m_min,
        "precipitation_sum": daily_precipitation_sum,
    }

    daily_dataframe = pd.DataFrame(data=daily_data)
    print("\nDaily data\n", daily_dataframe)

    weather_info = {
        "city": city_name,
        "coordinates": f"{response.Latitude()}°N {response.Longitude()}°E",
        "elevation": response.Elevation(),
        "daily": {
            "temp_max": round(daily_temperature_2m_max[0], 1),
            "temp_min": round(daily_temperature_2m_min[0], 1),
            "apparent_temp_max": round(daily_apparent_temperature_max[0], 1),
            "apparent_temp_min": round(daily_apparent_temperature_min[0], 1),
            "precipitation": round(daily_precipitation_sum[0], 1),
        },
        "hourly": {"rain_hours": rain_hours},
    }

    return weather_info


def get_day_name(day_of_week):
    """Return weekday name in Portuguese."""
    days = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    return days[day_of_week]


if __name__ == "__main__":
    get_weather_and_send_alerts()
