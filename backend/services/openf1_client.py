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


def _seconds_to_time_str(seconds):
    """Convert float seconds to MySQL TIME format '00:MM:SS.mmm'."""
    if seconds is None:
        return None
    try:
        sec = float(seconds)
        mins, rem_sec = divmod(sec, 60)
        hours, mins = divmod(mins, 60)
        whole_sec = int(rem_sec)
        millis = int(round((rem_sec - whole_sec) * 1000))
        return f"{int(hours):02d}:{int(mins):02d}:{whole_sec:02d}.{millis:03d}"
    except Exception:
        return None


def fetch_sessions(year, session_name="Race"):
    """Fetch all race sessions for a given year sorted chronologically by date_start."""
    url = f"{BASE_URL}/sessions?year={year}&session_name={session_name}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    sessions = response.json()
    return sorted(sessions, key=lambda s: s.get("date_start", ""))


def fetch_laps(session_key, driver_number=None):
    """Fetch lap timing and sector splits for an OpenF1 session."""
    url = f"{BASE_URL}/laps?session_key={session_key}"
    if driver_number:
        url += f"&driver_number={driver_number}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    laps_data = response.json()

    results = []
    for l in laps_data:
        duration = l.get("lap_duration")
        if duration is None:
            continue
        results.append({
            "lap_number": l.get("lap_number"),
            "driver_number": l.get("driver_number"),
            "lap_duration_seconds": duration,
            "lap_time": _seconds_to_time_str(duration),
            "sector1_time": round(l.get("duration_sector_1"), 3) if l.get("duration_sector_1") is not None else None,
            "sector2_time": round(l.get("duration_sector_2"), 3) if l.get("duration_sector_2") is not None else None,
            "sector3_time": round(l.get("duration_sector_3"), 3) if l.get("duration_sector_3") is not None else None,
            "is_pit_out_lap": l.get("is_pit_out_lap", False),
        })
    return results


def fetch_stints(session_key, driver_number=None):
    """Fetch tyre stints for an OpenF1 session, mapping laps to tyre compounds."""
    url = f"{BASE_URL}/stints?session_key={session_key}"
    if driver_number:
        url += f"&driver_number={driver_number}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    stints_data = response.json()

    results = []
    for s in stints_data:
        compound = s.get("compound", "UNKNOWN").capitalize()
        results.append({
            "driver_number": s.get("driver_number"),
            "stint_number": s.get("stint_number"),
            "lap_start": s.get("lap_start"),
            "lap_end": s.get("lap_end"),
            "compound": compound,
            "tyre_age_at_start": s.get("tyre_age_at_start", 0),
        })
    return results


def fetch_pit(session_key, driver_number=None):
    """Fetch pit stop timing from OpenF1."""
    url = f"{BASE_URL}/pit?session_key={session_key}"
    if driver_number:
        url += f"&driver_number={driver_number}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    pit_data = response.json()

    results = []
    for p in pit_data:
        duration = p.get("pit_duration") or p.get("stop_duration") or p.get("lane_duration") or 0.0
        results.append({
            "driver_number": p.get("driver_number"),
            "lap_number": p.get("lap_number"),
            "stop_duration": round(float(duration), 3),
            "pit_loss_time": round(float(p.get("lane_duration") or duration), 3),
        })
    return results

