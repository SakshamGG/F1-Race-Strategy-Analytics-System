"""
OpenF1 API Client
=================
Fetches live/historical F1 telemetry and weather data from OpenF1.
Base URL: https://api.openf1.org/v1/
No API key required for historical data — free and open.

Provides: Weather data, Lap times (with sector splits).
"""

import requests

BASE_URL = "https://api.openf1.org/v1"
TIMEOUT = 30


def fetch_weather(session_key):
    """Fetch weather data for a given OpenF1 session.

    Averages all weather readings in the session into a single summary.
    Determines track_condition from rainfall (Dry / Damp / Wet).

    Args:
        session_key: OpenF1 session key (integer or 'latest')

    Returns dict with keys:
        temperature_celsius, humidity_percent, wind_speed_kmh,
        rainfall_mm, track_condition
    Returns None if no data available.
    """
    url = f"{BASE_URL}/weather?session_key={session_key}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    if not data:
        return None

    n = len(data)
    avg_temp = sum(d.get("air_temperature", 0) or 0 for d in data) / n
    avg_humidity = sum(d.get("humidity", 0) or 0 for d in data) / n
    avg_wind = sum(d.get("wind_speed", 0) or 0 for d in data) / n
    max_rainfall = max(d.get("rainfall", 0) or 0 for d in data)

    if max_rainfall > 2:
        track_condition = "Wet"
    elif max_rainfall > 0:
        track_condition = "Damp"
    else:
        track_condition = "Dry"

    return {
        "temperature_celsius": round(avg_temp, 1),
        "humidity_percent": round(avg_humidity, 1),
        "wind_speed_kmh": round(avg_wind, 1),
        "rainfall_mm": round(max_rainfall, 1),
        "track_condition": track_condition,
    }
