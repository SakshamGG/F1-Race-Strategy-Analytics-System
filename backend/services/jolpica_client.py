"""
Jolpica F1 API Client
=====================
Fetches historical F1 data from the Jolpica API (Ergast successor).
Base URL: https://api.jolpi.ca/ergast/f1/
No API key required — free and open.

Provides: Drivers, Constructors, Circuits, Race schedules, Race results.
"""

import requests

BASE_URL = "https://api.jolpi.ca/ergast/f1"
TIMEOUT = 30


def _convert_lap_time(raw_time):
    """Convert Jolpica lap time format to MySQL TIME format.

    Examples:
        '1:32.608' → '00:01:32.608'
        '1:02:32.608' → '01:02:32.608'
    """
    if not raw_time:
        return None
    parts = raw_time.split(":")
    if len(parts) == 2:
        # M:SS.mmm format
        minutes = int(parts[0])
        sec_parts = parts[1].split(".")
        sec = int(sec_parts[0])
        ms = sec_parts[1] if len(sec_parts) > 1 else "000"
        return f"00:{minutes:02d}:{sec:02d}.{ms}"
    elif len(parts) == 3:
        return raw_time
    return raw_time


def fetch_drivers(season):
    """Fetch all drivers for a given F1 season.

    Returns list of dicts with keys:
        first_name, last_name, nationality, date_of_birth
    """
    url = f"{BASE_URL}/{season}/drivers/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    drivers = data["MRData"]["DriverTable"]["Drivers"]
    return [
        {
            "first_name": d["givenName"],
            "last_name": d["familyName"],
            "nationality": d["nationality"],
            "date_of_birth": d["dateOfBirth"],
        }
        for d in drivers
    ]


def fetch_constructors(season):
    """Fetch all constructors for a given F1 season.

    Returns list of dicts with keys:
        name, nationality, base_location
    Note: base_location is set to 'N/A' — API does not provide it.
    """
    url = f"{BASE_URL}/{season}/constructors/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    constructors = data["MRData"]["ConstructorTable"]["Constructors"]
    return [
        {
            "name": c["name"],
            "nationality": c["nationality"],
            "base_location": "N/A",
        }
        for c in constructors
    ]


def fetch_circuits(season):
    """Fetch all circuits used in a given F1 season.

    Returns list of dicts with keys:
        name, country, city, length_km, number_of_turns
    Note: length_km and number_of_turns are set to 0 — API does not provide them.
    """
    url = f"{BASE_URL}/{season}/circuits/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    circuits = data["MRData"]["CircuitTable"]["Circuits"]
    return [
        {
            "name": c["circuitName"],
            "country": c["Location"]["country"],
            "city": c["Location"]["locality"],
            "length_km": 0.000,
            "number_of_turns": 0,
        }
        for c in circuits
    ]


def fetch_races(season):
    """Fetch the race schedule for a given F1 season.

    Returns list of dicts with keys:
        circuit_name, season_year, race_name, race_date, total_laps, round_number
    Note: total_laps is set to 0 — only available from results endpoint.
    """
    url = f"{BASE_URL}/{season}/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    races = data["MRData"]["RaceTable"]["Races"]
    return [
        {
            "circuit_name": r["Circuit"]["circuitName"],
            "season_year": int(r["season"]),
            "race_name": r["raceName"],
            "race_date": r["date"],
            "total_laps": 0,
            "round_number": int(r["round"]),
        }
        for r in races
    ]


def fetch_race_results(season, round_number):
    """Fetch race results for a specific round.

    Returns (results_list, total_laps) where results_list contains dicts with:
        driver_first_name, driver_last_name, driver_nationality, driver_dob,
        constructor_name, constructor_nationality,
        grid_position, finishing_position, points_scored, status, fastest_lap_time
    """
    url = f"{BASE_URL}/{season}/{round_number}/results/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    races = data["MRData"]["RaceTable"]["Races"]
    if not races:
        return [], 0

    race = races[0]
    total_laps = int(race["Results"][0]["laps"]) if race["Results"] else 0

    results = []
    for r in race["Results"]:
        fastest_lap = None
        if "FastestLap" in r and "Time" in r["FastestLap"]:
            fastest_lap = _convert_lap_time(r["FastestLap"]["Time"]["time"])

        results.append({
            "driver_first_name": r["Driver"]["givenName"],
            "driver_last_name": r["Driver"]["familyName"],
            "driver_nationality": r["Driver"]["nationality"],
            "driver_dob": r["Driver"]["dateOfBirth"],
            "constructor_name": r["Constructor"]["name"],
            "constructor_nationality": r["Constructor"]["nationality"],
            "grid_position": int(r["grid"]) if r["grid"] != "0" else None,
            "finishing_position": int(r["position"]),
            "points_scored": float(r["points"]),
            "status": r["status"],
            "fastest_lap_time": fastest_lap,
        })

    return results, total_laps
