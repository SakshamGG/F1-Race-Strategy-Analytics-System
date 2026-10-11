"""
Jolpica F1 API Client
=====================
Fetches historical F1 data from the Jolpica API (Ergast successor).
Base URL: https://api.jolpi.ca/ergast/f1/
No API key required — free and open.

Provides: Drivers, Constructors, Circuits, Race schedules, Race results.
"""

import requests
from collections import Counter

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
    parts = str(raw_time).strip().split(":")
    if len(parts) == 2:
        # M:SS.mmm format
        try:
            minutes = int(parts[0])
            sec_parts = parts[1].split(".")
            sec = int(sec_parts[0])
            ms = sec_parts[1] if len(sec_parts) > 1 else "000"
            return f"00:{minutes:02d}:{sec:02d}.{ms[:3]}"
        except Exception:
            return None
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

    drivers = data.get("MRData", {}).get("DriverTable", {}).get("Drivers", [])
    results = []
    for d in drivers:
        first_name = d.get("givenName") or "Unknown"
        last_name = d.get("familyName") or d.get("driverId") or "Driver"
        nationality = d.get("nationality") or "Unknown"
        dob = d.get("dateOfBirth") or "2000-01-01"
        results.append({
            "first_name": first_name,
            "last_name": last_name,
            "nationality": nationality,
            "date_of_birth": dob,
        })
    return results


CONSTRUCTOR_BASE_LOCATIONS = {
    "mercedes": "Brackley, United Kingdom",
    "red bull": "Milton Keynes, United Kingdom",
    "red_bull": "Milton Keynes, United Kingdom",
    "red bull racing": "Milton Keynes, United Kingdom",
    "ferrari": "Maranello, Italy",
    "mclaren": "Woking, United Kingdom",
    "aston martin": "Silverstone, United Kingdom",
    "aston_martin": "Silverstone, United Kingdom",
    "alpine": "Enstone, United Kingdom",
    "alpine f1 team": "Enstone, United Kingdom",
    "williams": "Grove, United Kingdom",
    "rb": "Faenza, Italy",
    "rb f1 team": "Faenza, Italy",
    "racing bulls": "Faenza, Italy",
    "alphatauri": "Faenza, Italy",
    "toro rosso": "Faenza, Italy",
    "toro_rosso": "Faenza, Italy",
    "haas": "Kannapolis, North Carolina, USA",
    "haas f1 team": "Kannapolis, North Carolina, USA",
    "sauber": "Hinwil, Switzerland",
    "kick sauber": "Hinwil, Switzerland",
    "audi": "Hinwil, Switzerland",
    "cadillac": "Fishers, Indiana, USA",
    "cadillac f1 team": "Fishers, Indiana, USA",
    "renault": "Enstone, United Kingdom",
    "force india": "Silverstone, United Kingdom",
    "racing point": "Silverstone, United Kingdom",
    "alfa romeo": "Hinwil, Switzerland",
    "alfa": "Hinwil, Switzerland",
}


def fetch_constructors(season):
    """Fetch all constructors for a given F1 season.

    Returns list of dicts with keys:
        name, nationality, base_location
    """
    url = f"{BASE_URL}/{season}/constructors/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    constructors = data.get("MRData", {}).get("ConstructorTable", {}).get("Constructors", [])
    results = []
    for c in constructors:
        name = c.get("name") or c.get("constructorId") or "Unknown"
        cid = str(c.get("constructorId", "")).lower().strip()
        n_low = name.lower().strip()
        base = CONSTRUCTOR_BASE_LOCATIONS.get(cid) or CONSTRUCTOR_BASE_LOCATIONS.get(n_low) or "N/A"
        results.append({
            "name": name,
            "nationality": c.get("nationality") or "Unknown",
            "base_location": base,
        })
    return results


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

    circuits = data.get("MRData", {}).get("CircuitTable", {}).get("Circuits", [])
    results = []
    for c in circuits:
        loc = c.get("Location") or {}
        results.append({
            "name": c.get("circuitName") or "Unknown Circuit",
            "country": loc.get("country") or "Unknown",
            "city": loc.get("locality") or "Unknown",
            "length_km": 0.000,
            "number_of_turns": 0,
        })
    return results


# Standard race lap counts for F1 circuits (based on most recent race distances).
# Keyed by circuitId from the Jolpica/Ergast API, with fallback matching by circuit name.
CIRCUIT_LAP_COUNTS = {
    # Current calendar circuits
    "albert_park": 58,          # Australian GP - Albert Park
    "shanghai": 56,             # Chinese GP - Shanghai International Circuit
    "suzuka": 53,               # Japanese GP - Suzuka Circuit
    "miami": 57,                # Miami GP - Miami International Autodrome
    "villeneuve": 70,           # Canadian GP - Circuit Gilles Villeneuve
    "monaco": 78,               # Monaco GP - Circuit de Monaco
    "catalunya": 66,            # Barcelona/Spanish GP - Circuit de Barcelona-Catalunya
    "red_bull_ring": 71,        # Austrian GP - Red Bull Ring
    "silverstone": 52,          # British GP - Silverstone Circuit
    "spa": 44,                  # Belgian GP - Circuit de Spa-Francorchamps
    "hungaroring": 70,          # Hungarian GP - Hungaroring
    "zandvoort": 72,            # Dutch GP - Circuit Park Zandvoort
    "monza": 53,                # Italian GP - Autodromo Nazionale Monza
    "baku": 51,                 # Azerbaijan GP - Baku City Circuit
    "marina_bay": 62,           # Singapore GP - Marina Bay Street Circuit
    "americas": 56,             # United States GP - Circuit of the Americas
    "rodriguez": 71,            # Mexico City GP - Autódromo Hermanos Rodríguez
    "interlagos": 71,           # Brazilian GP - Autódromo José Carlos Pace
    "vegas": 50,                # Las Vegas GP - Las Vegas Strip Street Circuit
    "losail": 57,               # Qatar GP - Lusail International Circuit
    "yas_marina": 58,           # Abu Dhabi GP - Yas Marina Circuit
    "jeddah": 50,               # Saudi Arabian GP - Jeddah Corniche Circuit
    "bahrain": 57,              # Bahrain GP - Bahrain International Circuit
    "imola": 63,                # Emilia Romagna GP - Autodromo Enzo e Dino Ferrari
    "portimao": 66,             # Portuguese GP - Autódromo Internacional do Algarve
    "istanbul": 58,             # Turkish GP - Istanbul Park
    "mugello": 59,              # Tuscan GP - Mugello Circuit
    "nurburgring": 60,          # Eifel GP - Nürburgring
    "sakhir": 87,               # Sakhir GP (outer layout)
    "sepang": 56,               # Malaysian GP - Sepang International Circuit
    "ricard": 53,               # French GP - Paul Ricard
    "sochi": 53,                # Russian GP - Sochi Autodrom
    "yeongam": 55,              # Korean GP - Korea International Circuit
    "buddh": 60,                # Indian GP - Buddh International Circuit
    "valencia": 57,             # European GP - Valencia Street Circuit
    "hockenheimring": 67,       # German GP - Hockenheimring
    "fuji": 67,                 # Japanese GP (Fuji)
    "magny_cours": 70,          # French GP - Magny-Cours
    "indianapolis": 73,         # United States GP - Indianapolis
    "kyalami": 72,              # South African GP - Kyalami
    "jacarepagua": 61,          # Brazilian GP - Jacarepaguá
    "adelaide": 81,             # Australian GP - Adelaide
    "detroit": 63,              # Detroit GP
    "dallas": 67,               # Dallas GP
    "donington": 76,            # European GP - Donington
    "brands_hatch": 75,         # British GP - Brands Hatch
    "long_beach": 80,           # United States GP West
    "dijon": 79,                # French GP - Dijon
    "estoril": 71,              # Portuguese GP - Estoril
    "paul_ricard": 53,          # French GP - Paul Ricard (modern)
    "BAK": 51,                  # Alternative Baku ID
    "madring": 66,              # Madrid GP (new 2026)
}

# Fallback: map circuit names (lowercase) to lap counts
_CIRCUIT_NAME_LAPS = {
    "albert park grand prix circuit": 58,
    "albert park circuit": 58,
    "shanghai international circuit": 56,
    "suzuka circuit": 53,
    "suzuka international racing course": 53,
    "miami international autodrome": 57,
    "circuit gilles villeneuve": 70,
    "circuit de monaco": 78,
    "circuit de barcelona-catalunya": 66,
    "red bull ring": 71,
    "silverstone circuit": 52,
    "circuit de spa-francorchamps": 44,
    "hungaroring": 70,
    "circuit park zandvoort": 72,
    "autodromo nazionale monza": 53,
    "autodromo nazionale di monza": 53,
    "baku city circuit": 51,
    "marina bay street circuit": 62,
    "circuit of the americas": 56,
    "autódromo hermanos rodríguez": 71,
    "autodromo hermanos rodriguez": 71,
    "autódromo josé carlos pace": 71,
    "autodromo jose carlos pace": 71,
    "interlagos": 71,
    "las vegas strip street circuit": 50,
    "las vegas street circuit": 50,
    "lusail international circuit": 57,
    "yas marina circuit": 58,
    "jeddah corniche circuit": 50,
    "bahrain international circuit": 57,
    "autodromo enzo e dino ferrari": 63,
    "autódromo internacional do algarve": 66,
    "istanbul park": 58,
    "mugello circuit": 59,
    "nürburgring": 60,
    "nurburgring": 60,
    "sepang international circuit": 56,
    "circuit paul ricard": 53,
    "paul ricard": 53,
    "sochi autodrom": 53,
    "korea international circuit": 55,
    "buddh international circuit": 60,
    "valencia street circuit": 57,
    "hockenheimring": 67,
    "fuji speedway": 67,
    "circuit de magny-cours": 70,
    "indianapolis motor speedway": 73,
    "kyalami": 72,
    "madring": 66,
}


def _get_circuit_laps(circuit_id, circuit_name):
    """Resolve the standard lap count for a circuit using ID or name fallback."""
    if circuit_id and circuit_id in CIRCUIT_LAP_COUNTS:
        return CIRCUIT_LAP_COUNTS[circuit_id]
    if circuit_name:
        name_lower = circuit_name.lower().strip()
        if name_lower in _CIRCUIT_NAME_LAPS:
            return _CIRCUIT_NAME_LAPS[name_lower]
        # Fuzzy substring match as last resort
        for key, laps in _CIRCUIT_NAME_LAPS.items():
            if key in name_lower or name_lower in key:
                return laps
    return 0


def fetch_races(season):
    """Fetch the race schedule for a given F1 season.

    Returns list of dicts with keys:
        circuit_name, circuit_country, circuit_city, season_year, race_name, race_date, total_laps, round_number
    """
    url = f"{BASE_URL}/{season}/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    results = []
    for r in races:
        circ = r.get("Circuit") or {}
        loc = circ.get("Location") or {}
        circuit_id = circ.get("circuitId") or ""
        circuit_name = circ.get("circuitName") or "Unknown Circuit"
        total_laps = _get_circuit_laps(circuit_id, circuit_name)
        results.append({
            "circuit_name": circuit_name,
            "circuit_country": loc.get("country") or "Unknown",
            "circuit_city": loc.get("locality") or "Unknown",
            "season_year": int(r.get("season") or season),
            "race_name": r.get("raceName") or f"Round {r.get('round', 1)}",
            "race_date": r.get("date") or f"{season}-01-01",
            "total_laps": total_laps,
            "round_number": int(r.get("round") or 1),
        })
    return results


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

    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races or "Results" not in races[0]:
        return [], 0

    race = races[0]
    total_laps = 0
    raw_results = race.get("Results", [])
    if raw_results and raw_results[0].get("laps"):
        try:
            total_laps = int(raw_results[0]["laps"])
        except Exception:
            total_laps = 0

    results = []
    for r in raw_results:
        fastest_lap = None
        if "FastestLap" in r and "Time" in r["FastestLap"]:
            fastest_lap = _convert_lap_time(r["FastestLap"]["Time"].get("time"))

        driver = r.get("Driver") or {}
        constructor = r.get("Constructor") or {}

        grid_raw = str(r.get("grid", "")).strip()
        grid_val = int(grid_raw) if grid_raw.isdigit() and grid_raw != "0" else None

        pos_raw = str(r.get("position", "")).strip()
        pos_val = int(pos_raw) if pos_raw.isdigit() else None

        points_raw = r.get("points")
        try:
            points_val = float(points_raw) if points_raw is not None else 0.0
        except Exception:
            points_val = 0.0

        results.append({
            "driver_first_name": driver.get("givenName") or "Unknown",
            "driver_last_name": driver.get("familyName") or driver.get("driverId") or "Driver",
            "driver_nationality": driver.get("nationality") or "Unknown",
            "driver_dob": driver.get("dateOfBirth") or "2000-01-01",
            "constructor_name": constructor.get("name") or constructor.get("constructorId") or "Unknown",
            "constructor_nationality": constructor.get("nationality") or "Unknown",
            "grid_position": grid_val,
            "finishing_position": pos_val,
            "points_scored": points_val,
            "status": r.get("status") or "Finished",
            "fastest_lap_time": fastest_lap,
        })

    return results, total_laps


def _parse_duration_seconds(raw_duration):
    """Parse pit duration string into float seconds. Handles both '24.123' and '1:24.123'."""
    if not raw_duration:
        return 0.0
    try:
        parts = str(raw_duration).strip().split(":")
        if len(parts) == 2:
            return float(parts[0]) * 60.0 + float(parts[1])
        elif len(parts) == 3:
            return float(parts[0]) * 3600.0 + float(parts[1]) * 60.0 + float(parts[2])
        return float(raw_duration)
    except Exception:
        return 0.0


def fetch_pit_stops(season, round_number):
    """Fetch pit stop data for a specific race round from Jolpica API.

    Returns list of dicts with keys:
        driver_ref, lap_number, stop_number, stop_duration
    """
    url = f"{BASE_URL}/{season}/{round_number}/pitstops/?format=json&limit=100"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races or "PitStops" not in races[0]:
        return []

    pit_stops = races[0].get("PitStops", [])
    results = []
    for p in pit_stops:
        driver_ref = p.get("driverId")
        lap_raw = str(p.get("lap", "")).strip()
        stop_raw = str(p.get("stop", "")).strip()
        if not driver_ref or not lap_raw.isdigit():
            continue

        results.append({
            "driver_ref": driver_ref,
            "lap_number": int(lap_raw),
            "stop_number": int(stop_raw) if stop_raw.isdigit() else 1,
            "stop_duration": round(_parse_duration_seconds(p.get("duration", "0")), 3),
        })
    return results


def fetch_laps(season, round_number, limit=2000):
    """Fetch lap timing records for a specific race round from Jolpica API.

    Returns list of dicts with keys:
        lap_number, driver_ref, position, lap_time
    """
    url = f"{BASE_URL}/{season}/{round_number}/laps/?format=json&limit={limit}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races or "Laps" not in races[0]:
        return []

    laps_list = []
    for lap in races[0].get("Laps", []):
        lap_raw = str(lap.get("number", "")).strip()
        if not lap_raw.isdigit():
            continue
        lap_num = int(lap_raw)
        for timing in lap.get("Timings", []):
            driver_ref = timing.get("driverId")
            if not driver_ref:
                continue
            pos_raw = str(timing.get("position", "")).strip()
            pos = int(pos_raw) if pos_raw.isdigit() else None
            laps_list.append({
                "lap_number": lap_num,
                "driver_ref": driver_ref,
                "position": pos,
                "lap_time": _convert_lap_time(timing.get("time")),
            })

    return laps_list


def fetch_podium_counts(season):
    """Fetch total podium finishes (positions 1, 2, 3) for drivers and constructors in a season.
    
    Returns:
        (driver_podiums_dict, constructor_podiums_dict)
    """
    driver_podiums = Counter()
    constructor_podiums = Counter()
    for pos in [1, 2, 3]:
        try:
            url = f"{BASE_URL}/{season}/results/{pos}/?format=json&limit=100"
            resp = requests.get(url, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
                for r in races:
                    for res in r.get("Results", []):
                        driver = res.get("Driver", {})
                        d_id = (driver.get("driverId") or "").strip().lower()
                        given = (driver.get("givenName") or "").strip().lower()
                        family = (driver.get("familyName") or "").strip().lower()
                        if d_id:
                            driver_podiums[d_id] += 1
                        if given or family:
                            driver_podiums[(given, family)] += 1

                        constructor = res.get("Constructor", {})
                        c_name = (constructor.get("name") or "").strip().lower()
                        c_id = (constructor.get("constructorId") or "").strip().lower()
                        if c_name:
                            constructor_podiums[c_name] += 1
                        elif c_id:
                            constructor_podiums[c_id] += 1
        except Exception:
            pass
    return driver_podiums, constructor_podiums


def fetch_driver_standings(season):
    """Fetch official FIA/Ergast driver championship standings for a season with podiums."""
    url = f"{BASE_URL}/{season}/driverstandings/?format=json&limit=100"
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    lists = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
    if not lists:
        return []

    driver_podiums, _ = fetch_podium_counts(season)

    standings = []
    for s in lists[0].get("DriverStandings", []):
        driver = s.get("Driver", {})
        first_name = driver.get("givenName") or "Unknown"
        last_name = driver.get("familyName") or driver.get("driverId") or "Driver"
        d_id = (driver.get("driverId") or "").strip().lower()
        d_key = (first_name.strip().lower(), last_name.strip().lower())

        podiums = driver_podiums.get(d_id) or driver_podiums.get(d_key) or 0

        constructors = s.get("Constructors", [])
        team_name = constructors[0].get("name", "Unknown") if constructors else "Unknown"

        try:
            points_val = float(s.get("points", 0))
        except Exception:
            points_val = 0.0

        try:
            wins_val = int(s.get("wins", 0))
        except Exception:
            wins_val = 0

        try:
            pos_val = int(s.get("position", len(standings) + 1))
        except Exception:
            pos_val = len(standings) + 1

        standings.append({
            "position": pos_val,
            "driver_first_name": first_name,
            "driver_last_name": last_name,
            "driver_name": f"{first_name} {last_name}",
            "driver_nationality": driver.get("nationality") or "Unknown",
            "driver_dob": driver.get("dateOfBirth") or "2000-01-01",
            "team_name": team_name,
            "total_points": points_val,
            "wins": wins_val,
            "podiums": podiums,
        })

    return standings


def fetch_constructor_standings(season):
    """Fetch official FIA/Ergast constructor championship standings for a season with podiums."""
    url = f"{BASE_URL}/{season}/constructorstandings/?format=json&limit=100"
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    lists = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
    if not lists:
        return []

    _, constructor_podiums = fetch_podium_counts(season)

    standings = []
    for s in lists[0].get("ConstructorStandings", []):
        constructor = s.get("Constructor", {})
        team_name = constructor.get("name") or constructor.get("constructorId") or "Unknown"
        c_name_lower = team_name.strip().lower()
        c_id_lower = (constructor.get("constructorId") or "").strip().lower()

        podiums = constructor_podiums.get(c_name_lower) or constructor_podiums.get(c_id_lower) or 0

        try:
            points_val = float(s.get("points", 0))
        except Exception:
            points_val = 0.0

        try:
            wins_val = int(s.get("wins", 0))
        except Exception:
            wins_val = 0

        try:
            pos_val = int(s.get("position", len(standings) + 1))
        except Exception:
            pos_val = len(standings) + 1

        standings.append({
            "position": pos_val,
            "team_name": team_name,
            "team_nationality": constructor.get("nationality") or "Unknown",
            "total_points": points_val,
            "wins": wins_val,
            "podiums": podiums,
        })

    return standings


def fetch_all_season_race_results(season):
    """Fetch all race results for an entire season using Jolpica pagination.
    
    Returns a dict mapping round_number -> race info with list of results.
    """
    offset = 0
    all_races = {}
    while True:
        url = f"{BASE_URL}/{season}/results/?format=json&limit=100&offset={offset}"
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        total = int(data.get("MRData", {}).get("total", 0))

        for r in races:
            rnd = int(r.get("round", 0))
            if rnd not in all_races:
                circ = r.get("Circuit", {})
                loc = circ.get("Location", {})
                circuit_name = circ.get("circuitName") or "Unknown Circuit"
                circuit_id = circ.get("circuitId") or ""
                all_races[rnd] = {
                    "round_number": rnd,
                    "race_name": r.get("raceName") or f"Round {rnd}",
                    "race_date": r.get("date") or f"{season}-01-01",
                    "circuit_name": circuit_name,
                    "circuit_country": loc.get("country") or "Unknown",
                    "circuit_city": loc.get("locality") or "Unknown",
                    "total_laps": _get_circuit_laps(circuit_id, circuit_name),
                    "results": []
                }
            for res in r.get("Results", []):
                fastest_lap = None
                if "FastestLap" in res and "Time" in res["FastestLap"]:
                    fastest_lap = _convert_lap_time(res["FastestLap"]["Time"].get("time"))

                driver = res.get("Driver", {})
                constructor = res.get("Constructor", {})

                grid_raw = str(res.get("grid", "")).strip()
                grid_val = int(grid_raw) if grid_raw.isdigit() and grid_raw != "0" else None

                pos_raw = str(res.get("position", "")).strip()
                pos_val = int(pos_raw) if pos_raw.isdigit() else None

                try:
                    points_val = float(res.get("points", 0))
                except Exception:
                    points_val = 0.0

                all_races[rnd]["results"].append({
                    "driver_first_name": driver.get("givenName") or "Unknown",
                    "driver_last_name": driver.get("familyName") or driver.get("driverId") or "Driver",
                    "driver_nationality": driver.get("nationality") or "Unknown",
                    "driver_dob": driver.get("dateOfBirth") or "2000-01-01",
                    "constructor_name": constructor.get("name") or constructor.get("constructorId") or "Unknown",
                    "constructor_nationality": constructor.get("nationality") or "Unknown",
                    "grid_position": grid_val,
                    "finishing_position": pos_val,
                    "points_scored": points_val,
                    "status": res.get("status") or "Finished",
                    "fastest_lap_time": fastest_lap,
                })

        offset += 100
        if offset >= total or not races:
            break

    return all_races

