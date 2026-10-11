"""
Pit Wall Telemetry & Insights Service
=====================================
Ports the Real-Time Telemetry Stream & Pit Wall Insights suite from
IAmTomShaw/f1-race-replay into the F1-Race-Strategy-Analytics-System backend:

1. Telemetry Stream Format (`src/services/stream.py` & `src/f1_data.py`):
   Frame-by-frame JSON (`speed`, `gear`, `throttle`, `brake`, `drs`, `dist`,
   `rel_dist`, `tyre`, `x`, `y`, plus simulated `safety_car` with `phase` & `alpha`).
2. Driver Live Telemetry (`driver_telemetry_window.py`):
   Stacked Speed, Gear, and Throttle/Brake traces over distance or rolling 30s time window.
3. Live Tyre Strategy (`tyre_strategy_window.py`):
   Horizontal Gantt-style stint timeline per driver with official F1 compound colours.
4. Lap Time & Gap Evolution Chart (`lap_time_chart_window.py` + `bayesian_tyre_model.py`):
   Multi-driver lap times, gap-to-leader mode, 3-lap rolling average, SC/VSC zones,
   and Bayesian State-Space Tyre Degradation model overlay.
5. Sector Times (`sector_times_window.py` & `src/lib/sectors.py`):
   Per-lap Sector 1/2/3 breakdown with Purple (Session Best) & Green (Personal Best)
   progressive classification and Theoretical Best Lap calculation.
6. Track Position Map (`track_position_window.py`):
   2D real circuit geometry (center, inner, outer polylines + DRS zones) and circular
   gap-radar positions for all drivers + Safety Car.
7. Race Control Feed (`race_control_feed_window.py`):
   Live feed of FIA flags, Safety Car/VSC deployments, penalties, and DRS status.

Supports ANY season (1950–2026), ANY race round, and ANY driver via a hybrid
MySQL + OpenF1 + Jolpica + Physics Telemetry Synthesis pipeline.
"""

import hashlib
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from services import jolpica_client, openf1_client

# ==============================================================================
# 1. TYRE COMPOUND & PALETTE CONSTANTS (matching f1-race-replay)
# ==============================================================================

TYRE_CODES = {
    "SOFT": 1.0,
    "MEDIUM": 2.0,
    "HARD": 3.0,
    "INTERMEDIATE": 4.0,
    "INTER": 4.0,
    "WET": 5.0,
    "UNKNOWN": 0.0,
}

TYRE_COLOURS = {
    0.0: ("#888888", "UNK", "Unknown"),
    1.0: ("#E8002D", "S", "Soft"),
    2.0: ("#FFF200", "M", "Medium"),
    3.0: ("#CACACA", "H", "Hard"),
    4.0: ("#39B54A", "I", "Intermediate"),
    5.0: ("#0067FF", "W", "Wet"),
}

DRIVER_PALETTE = [
    "#E8002D", "#FF8000", "#00D2BE", "#3671C6", "#229971",
    "#FF87BC", "#64C4FF", "#6692FF", "#52E252", "#B6BABD",
    "#F596C8", "#FFF500", "#006F62", "#0090FF", "#C92D4B",
    "#358C75", "#ABB7C4", "#DC0000", "#5E8FAA", "#900000",
]

TEAM_COLOURS = {
    "red bull": "#3671C6",
    "ferrari": "#E8002D",
    "mercedes": "#27F4D2",
    "mclaren": "#FF8000",
    "aston martin": "#229971",
    "alpine": "#FF87BC",
    "williams": "#64C4FF",
    "rb": "#6692FF",
    "racing bulls": "#6692FF",
    "alphatauri": "#5E8FAA",
    "haas": "#B6BABD",
    "sauber": "#52E252",
    "kick sauber": "#52E252",
    "alfa romeo": "#C92D4B",
    "renault": "#FFF500",
    "lotus": "#FFB800",
    "brabham": "#1565C0",
    "tyrrell": "#0055A4",
    "benetton": "#00A550",
    "jordan": "#FFD700",
    "brawn": "#B8FF01",
}

RACE_CONTROL_FLAG_COLOURS = {
    "YELLOW": "#FFD700",
    "DOUBLE YELLOW": "#FFD700",
    "RED": "#E74C3C",
    "GREEN": "#2ECC71",
    "CLEAR": "#2ECC71",
    "CHEQUERED": "#F0F0F0",
    "BLUE": "#3498DB",
    "BLACK AND WHITE": "#B0B0B0",
    "BLACK AND ORANGE": "#FF8C00",
}

RACE_CONTROL_CAT_COLOURS = {
    "Flag": "#FFD700",
    "SafetyCar": "#FF8C00",
    "Drs": "#00CED1",
    "CarEvent": "#B0B0B0",
    "Other": "#666666",
}

# In-memory cache for fast interactive scrubbing and repeat lookups
_SESSION_CACHE: Dict[str, dict] = {}
_CATALOG_CACHE: Dict[int, dict] = {}


def get_tyre_float(compound_name: str) -> float:
    if not compound_name:
        return 2.0
    upper = str(compound_name).strip().upper()
    for key, val in TYRE_CODES.items():
        if key in upper:
            return val
    return 2.0


def get_tyre_meta(tyre_val: float) -> Tuple[str, str, str]:
    return TYRE_COLOURS.get(float(tyre_val), ("#888888", "UNK", "Unknown"))


def get_team_colour(team_name: str, fallback_idx: int = 0) -> str:
    if team_name:
        low = team_name.lower()
        for k, col in TEAM_COLOURS.items():
            if k in low:
                return col
    return DRIVER_PALETTE[fallback_idx % len(DRIVER_PALETTE)]


# ==============================================================================
# 2. SECTOR TIMES ANALYSIS (ported from f1-race-replay/src/lib/sectors.py)
# ==============================================================================

SECTOR_KEYS = ("sector1_s", "sector2_s", "sector3_s")
STATUS_SESSION_BEST = "session_best"
STATUS_PERSONAL_BEST = "personal_best"
STATUS_NONE = "none"


def _valid_time(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def best_sectors(entries: List[dict]) -> Dict[str, Optional[float]]:
    """Return the best time for each sector across a list of lap entries."""
    result = {}
    for key in SECTOR_KEYS:
        times = [t for t in (_valid_time(e.get(key)) for e in entries) if t is not None]
        result[key] = round(min(times), 3) if times else None
    return result


def theoretical_best_s(entries: List[dict]) -> Optional[float]:
    """Sum of a driver's best S1 + S2 + S3 if all three exist."""
    bests = best_sectors(entries)
    vals = [bests.get(k) for k in SECTOR_KEYS]
    if all(v is not None for v in vals):
        return round(sum(vals), 3)
    return None


def session_best_holders(all_driver_laps: Dict[str, List[dict]], up_to_lap: Optional[int] = None) -> Dict[str, dict]:
    """Find the session-best time and holder driver code for each sector up to `up_to_lap`."""
    holders = {
        k: {"time_s": None, "driver": None, "lap": None}
        for k in SECTOR_KEYS
    }
    for code, laps in all_driver_laps.items():
        for entry in laps:
            lap_num = entry.get("lap", 0)
            if up_to_lap is not None and lap_num > up_to_lap:
                continue
            for k in SECTOR_KEYS:
                val = _valid_time(entry.get(k))
                if val is not None:
                    curr = holders[k]["time_s"]
                    if curr is None or val < curr:
                        holders[k] = {"time_s": round(val, 3), "driver": code, "lap": lap_num}
    return holders


def classify_sector_statuses(
    driver_code: str,
    all_driver_laps: Dict[str, List[dict]],
    up_to_lap: Optional[int] = None,
) -> dict:
    """
    Classify each lap's S1, S2, S3 for `driver_code` as:
      - 'session_best' (purple #B027C9): fastest across all drivers up to that lap
      - 'personal_best' (green #27C93F): driver's fastest up to that lap
      - 'none' (white): no improvement
    Mirrors f1-race-replay's progressive timing screen logic.
    """
    driver_entries = [
        e for e in all_driver_laps.get(driver_code, [])
        if up_to_lap is None or e.get("lap", 0) <= up_to_lap
    ]

    # Precompute global best per sector at each lap number
    max_lap = max(
        (e.get("lap", 0) for laps in all_driver_laps.values() for e in laps),
        default=1,
    )
    if up_to_lap is not None:
        max_lap = min(max_lap, up_to_lap)

    global_running_best = {k: float("inf") for k in SECTOR_KEYS}
    global_best_by_lap: Dict[int, Dict[str, float]] = {}

    for lap_i in range(1, max_lap + 1):
        for laps in all_driver_laps.values():
            for e in laps:
                if e.get("lap") == lap_i:
                    for k in SECTOR_KEYS:
                        v = _valid_time(e.get(k))
                        if v is not None and v < global_running_best[k]:
                            global_running_best[k] = v
        global_best_by_lap[lap_i] = dict(global_running_best)

    personal_running_best = {k: float("inf") for k in SECTOR_KEYS}
    classified_laps = []

    for e in sorted(driver_entries, key=lambda x: x.get("lap", 0)):
        lap_num = e.get("lap", 1)
        g_bests = global_best_by_lap.get(lap_num, global_running_best)
        statuses = {}

        for k in SECTOR_KEYS:
            v = _valid_time(e.get(k))
            if v is None:
                statuses[k] = STATUS_NONE
                continue

            if v <= personal_running_best[k] + 1e-6:
                personal_running_best[k] = v
                if v <= g_bests.get(k, float("inf")) + 1e-6:
                    statuses[k] = STATUS_SESSION_BEST
                else:
                    statuses[k] = STATUS_PERSONAL_BEST
            else:
                if v <= g_bests.get(k, float("inf")) + 1e-6:
                    statuses[k] = STATUS_SESSION_BEST
                else:
                    statuses[k] = STATUS_NONE

        classified_laps.append({
            "lap": lap_num,
            "time_s": e.get("time_s"),
            "lap_time_str": _format_laptime(e.get("time_s")),
            "sector1_s": e.get("sector1_s"),
            "sector2_s": e.get("sector2_s"),
            "sector3_s": e.get("sector3_s"),
            "sector1_status": statuses["sector1_s"],
            "sector2_status": statuses["sector2_s"],
            "sector3_status": statuses["sector3_s"],
            "tyre": e.get("tyre", 2.0),
            "compound": get_tyre_meta(e.get("tyre", 2.0))[2],
            "is_pit_in": e.get("is_pit_in", False),
            "is_pit_out": e.get("is_pit_out", False),
        })

    p_bests = best_sectors(driver_entries)
    theo_best = theoretical_best_s(driver_entries)
    valid_lap_times = [e.get("time_s") for e in driver_entries if _valid_time(e.get("time_s"))]
    actual_best = round(min(valid_lap_times), 3) if valid_lap_times else None
    s_holders = session_best_holders(all_driver_laps, up_to_lap=up_to_lap)

    return {
        "driver": driver_code,
        "up_to_lap": up_to_lap,
        "laps": classified_laps,
        "personal_best_sectors": p_bests,
        "session_best_holders": s_holders,
        "theoretical_best_s": theo_best,
        "theoretical_best_str": _format_laptime(theo_best),
        "actual_best_s": actual_best,
        "actual_best_str": _format_laptime(actual_best),
        "potential_gain_s": round(actual_best - theo_best, 3) if (actual_best and theo_best) else 0.0,
    }


# ==============================================================================
# 3. BAYESIAN STATE-SPACE TYRE DEGRADATION MODEL
#    (ported from f1-race-replay/src/bayesian_tyre_model.py)
# ==============================================================================

class TyreCategory(Enum):
    SLICK = "SLICK"
    INTER = "INTER"
    WET = "WET"


class TrackCondition(Enum):
    DRY = "DRY"
    DAMP = "DAMP"
    WET = "WET"


@dataclass
class TyreProfile:
    name: str
    category: TyreCategory
    degradation_rate: float
    reset_pace: float
    warmup_laps: int
    max_analysis_laps: Optional[int]
    max_degradation: float


class BayesianTyreDegradationModel:
    """
    Universal Bayesian state-space model for all tyre compounds with track abrasion.

    State equation:
        alpha_{t+1} = (1 - I_pit) * (alpha_t + nu * A_track) + I_pit * alpha_reset + eta_t
    Observation equation:
        y_t = alpha_t + gamma * fuel_t + delta_mismatch + epsilon_t
    """

    def __init__(self, track_condition: str = "Dry"):
        self.sigma_epsilon = 0.30
        self.sigma_eta = 0.10
        self.fuel_effect = 0.032       # sec/kg
        self.starting_fuel = 110.0     # kg
        self.fuel_burn_rate = 1.6      # kg/lap
        self.track_abrasion = 1.0

        cond_upper = (track_condition or "DRY").upper()
        self.track_condition = (
            TrackCondition.WET if "WET" in cond_upper
            else TrackCondition.DAMP if "DAMP" in cond_upper
            else TrackCondition.DRY
        )

        self.mismatch_penalties = {
            (TyreCategory.SLICK, TrackCondition.DAMP): 2.0,
            (TyreCategory.SLICK, TrackCondition.WET): 8.0,
            (TyreCategory.INTER, TrackCondition.DRY): 1.5,
            (TyreCategory.INTER, TrackCondition.WET): 0.5,
            (TyreCategory.WET, TrackCondition.DRY): 4.0,
            (TyreCategory.WET, TrackCondition.DAMP): 1.0,
            (TyreCategory.SLICK, TrackCondition.DRY): 0.0,
            (TyreCategory.INTER, TrackCondition.DAMP): 0.0,
            (TyreCategory.WET, TrackCondition.WET): 0.0,
        }

        self.tyre_profiles: Dict[str, TyreProfile] = {
            "SOFT": TyreProfile("SOFT", TyreCategory.SLICK, 0.055, 78.5, 1, 18, 2.2),
            "MEDIUM": TyreProfile("MEDIUM", TyreCategory.SLICK, 0.032, 79.1, 2, 32, 2.0),
            "HARD": TyreProfile("HARD", TyreCategory.SLICK, 0.016, 79.7, 3, 45, 1.8),
            "INTERMEDIATE": TyreProfile("INTERMEDIATE", TyreCategory.INTER, 0.040, 86.0, 2, None, 3.0),
            "WET": TyreProfile("WET", TyreCategory.WET, 0.025, 91.0, 2, None, 2.5),
        }

        self._abrasion_baseline = {"HARD": 0.016, "MEDIUM": 0.032, "SOFT": 0.055}

    def fit_and_predict(self, all_driver_laps: Dict[str, List[dict]], total_laps: int) -> dict:
        """Fit Bayesian state-space posterior degradation rates and compute latent pace curves."""
        compound_slopes: Dict[str, List[float]] = {k: [] for k in self.tyre_profiles}
        compound_intercepts: Dict[str, List[float]] = {k: [] for k in self.tyre_profiles}

        # Collect clean stint laps across all drivers, removing fuel effect
        for code, laps in all_driver_laps.items():
            stint_age = 0
            last_tyre = None
            stint_ages = []
            stint_fuel_corrected = []
            current_comp = "MEDIUM"

            for e in laps:
                t_val = e.get("time_s")
                lap_num = e.get("lap", 1)
                tyre_val = e.get("tyre", 2.0)
                comp_name = get_tyre_meta(tyre_val)[2].upper()
                if comp_name not in self.tyre_profiles:
                    comp_name = "MEDIUM"

                if last_tyre is None or tyre_val != last_tyre or e.get("is_pit_out"):
                    if len(stint_ages) >= 4:
                        slope, intercept = self._ols(stint_ages, stint_fuel_corrected)
                        if 0.002 <= slope <= 0.25:
                            compound_slopes[current_comp].append(slope)
                        if intercept > 40:
                            compound_intercepts[current_comp].append(intercept)
                    stint_age = 1
                    stint_ages = []
                    stint_fuel_corrected = []
                    current_comp = comp_name
                else:
                    stint_age += 1

                last_tyre = tyre_val

                if (
                    t_val
                    and not e.get("is_pit_in")
                    and not e.get("is_pit_out")
                    and not e.get("is_sc")
                ):
                    fuel_kg = max(0.0, self.starting_fuel - (lap_num - 1) * self.fuel_burn_rate)
                    fuel_delta = self.fuel_effect * fuel_kg
                    stint_ages.append(stint_age)
                    stint_fuel_corrected.append(t_val - fuel_delta)

            if len(stint_ages) >= 4:
                slope, intercept = self._ols(stint_ages, stint_fuel_corrected)
                if 0.002 <= slope <= 0.25:
                    compound_slopes[current_comp].append(slope)
                if intercept > 40:
                    compound_intercepts[current_comp].append(intercept)

        # Bayesian conjugate update (Prior + Empirical Likelihood)
        abrasion_ratios = []
        for comp_name, profile in self.tyre_profiles.items():
            samples = compound_slopes.get(comp_name, [])
            prior_rate = profile.degradation_rate
            if samples:
                obs_mean = sum(samples) / len(samples)
                # Precision-weighted Bayesian update
                w_obs = min(0.85, len(samples) / (len(samples) + 3.0))
                post_rate = (1.0 - w_obs) * prior_rate + w_obs * obs_mean
                profile.degradation_rate = round(max(0.004, post_rate), 4)
                if comp_name in self._abrasion_baseline:
                    abrasion_ratios.append(profile.degradation_rate / self._abrasion_baseline[comp_name])

            ints = compound_intercepts.get(comp_name, [])
            if ints:
                profile.reset_pace = round(sum(ints) / len(ints), 3)

        if abrasion_ratios:
            self.track_abrasion = round(max(0.6, min(1.8, sum(abrasion_ratios) / len(abrasion_ratios))), 3)

        # Kalman / State-Space forward filter per driver for overlay curves
        driver_curves: Dict[str, List[dict]] = {}
        for code, laps in all_driver_laps.items():
            curve = []
            alpha_t = None
            p_var = 0.25
            stint_age = 0
            last_tyre = None

            for e in laps:
                lap_num = e.get("lap", 1)
                tyre_val = e.get("tyre", 2.0)
                comp_name = get_tyre_meta(tyre_val)[2].upper()
                profile = self.tyre_profiles.get(comp_name, self.tyre_profiles["MEDIUM"])

                is_pit = (last_tyre is not None and tyre_val != last_tyre) or bool(e.get("is_pit_out"))
                if last_tyre is None or is_pit:
                    stint_age = 1
                    alpha_t = profile.reset_pace
                    p_var = 0.20
                else:
                    stint_age += 1
                    warmup_penalty = 0.35 if stint_age <= profile.warmup_laps else 0.0
                    deg_step = min(profile.max_degradation, stint_age * profile.degradation_rate * self.track_abrasion)
                    alpha_t = (alpha_t if alpha_t is not None else profile.reset_pace) + (profile.degradation_rate * self.track_abrasion) - (0.15 if stint_age == profile.warmup_laps + 1 else 0.0)
                    p_var += self.sigma_eta ** 2
                    _ = warmup_penalty, deg_step

                last_tyre = tyre_val
                fuel_kg = max(0.0, self.starting_fuel - (lap_num - 1) * self.fuel_burn_rate)
                mismatch = self.mismatch_penalties.get((profile.category, self.track_condition), 0.0)
                predicted_y = alpha_t + self.fuel_effect * fuel_kg + mismatch

                obs_y = e.get("time_s")
                if obs_y and not e.get("is_pit_in") and not e.get("is_pit_out") and not e.get("is_sc"):
                    # Kalman measurement update
                    k_gain = p_var / (p_var + self.sigma_epsilon ** 2)
                    innovation = obs_y - predicted_y
                    # Clamp outlier innovations
                    if abs(innovation) < 4.5:
                        alpha_t = alpha_t + k_gain * innovation
                        p_var = (1.0 - k_gain) * p_var
                        predicted_y = alpha_t + self.fuel_effect * fuel_kg + mismatch

                curve.append({
                    "lap": lap_num,
                    "predicted_s": round(predicted_y, 3),
                    "latent_tyre_pace_s": round(alpha_t, 3),
                    "fuel_load_kg": round(fuel_kg, 1),
                    "uncertainty_s": round(math.sqrt(p_var), 3),
                    "compound": comp_name,
                    "stint_age": stint_age,
                })
            driver_curves[code] = curve

        profiles_summary = [
            {
                "compound": name,
                "category": p.category.value,
                "degradation_rate_sec_per_lap": p.degradation_rate,
                "reset_pace_s": p.reset_pace,
                "warmup_laps": p.warmup_laps,
                "max_degradation_s": p.max_degradation,
            }
            for name, p in self.tyre_profiles.items()
        ]

        return {
            "track_abrasion_factor": self.track_abrasion,
            "track_condition": self.track_condition.value,
            "fuel_effect_sec_per_kg": self.fuel_effect,
            "starting_fuel_kg": self.starting_fuel,
            "fuel_burn_kg_per_lap": self.fuel_burn_rate,
            "profiles": profiles_summary,
            "driver_curves": driver_curves,
        }

    @staticmethod
    def _ols(x_vals: List[float], y_vals: List[float]) -> Tuple[float, float]:
        n = len(x_vals)
        if n < 2:
            return 0.03, (y_vals[0] if y_vals else 80.0)
        mx = sum(x_vals) / n
        my = sum(y_vals) / n
        num = sum((x - mx) * (y - my) for x, y in zip(x_vals, y_vals))
        den = sum((x - mx) ** 2 for x in x_vals)
        slope = num / den if den > 0 else 0.03
        intercept = my - slope * mx
        return slope, intercept


# ==============================================================================
# 4. REALISTIC 2D CIRCUIT GEOMETRY & TELEMETRY SYNTHESIS ENGINE
# ==============================================================================

# Parametric control points (normalized [-1, 1] x/y) for signature F1 circuits
CIRCUIT_SHAPES: Dict[str, dict] = {
    "monaco": {
        "length_m": 3337,
        "drs_zones": [(0.0, 0.14)],
        "points": [
            (0.0, -0.6), (0.35, -0.55), (0.45, -0.20), (0.75, 0.10), (0.90, 0.45),
            (0.70, 0.65), (0.55, 0.40), (0.65, 0.20), (0.40, 0.05), (0.05, -0.15),
            (-0.35, -0.20), (-0.65, -0.10), (-0.85, -0.35), (-0.60, -0.65), (-0.30, -0.70),
        ],
    },
    "monza": {
        "length_m": 5793,
        "drs_zones": [(0.88, 0.08), (0.46, 0.60)],
        "points": [
            (-0.80, -0.55), (0.55, -0.55), (0.62, -0.45), (0.85, -0.10), (0.75, 0.35),
            (0.55, 0.65), (0.35, 0.60), (0.10, 0.15), (-0.05, 0.05), (-0.55, -0.15),
            (-0.88, -0.25), (-0.92, -0.48),
        ],
    },
    "silverstone": {
        "length_m": 5891,
        "drs_zones": [(0.18, 0.30), (0.58, 0.72)],
        "points": [
            (-0.30, -0.75), (0.25, -0.70), (0.45, -0.40), (0.15, -0.20), (0.55, 0.05),
            (0.85, 0.55), (0.50, 0.80), (0.10, 0.45), (-0.15, 0.55), (-0.35, 0.30),
            (-0.50, 0.10), (-0.80, -0.35), (-0.65, -0.65),
        ],
    },
    "spa": {
        "length_m": 7004,
        "drs_zones": [(0.16, 0.32), (0.88, 0.98)],
        "points": [
            (-0.65, -0.45), (-0.80, -0.70), (-0.35, -0.35), (-0.10, -0.10), (0.55, 0.55),
            (0.85, 0.65), (0.75, 0.25), (0.35, 0.15), (0.45, -0.15), (0.15, -0.45),
            (-0.20, -0.55), (-0.45, -0.35), (-0.58, -0.38),
        ],
    },
    "suzuka": {
        "length_m": 5807,
        "drs_zones": [(0.88, 0.04)],
        "points": [
            (-0.75, -0.35), (-0.40, -0.65), (-0.15, -0.45), (0.05, -0.55), (0.25, -0.25),
            (0.10, 0.05), (0.45, 0.25), (0.85, 0.55), (0.65, 0.75), (0.25, 0.35),
            (-0.10, 0.10), (-0.45, 0.20), (-0.80, 0.05),
        ],
    },
    "bahrain": {
        "length_m": 5412,
        "drs_zones": [(0.0, 0.14), (0.32, 0.44), (0.85, 0.98)],
        "points": [
            (-0.70, -0.75), (-0.70, 0.65), (-0.40, 0.75), (-0.10, 0.35), (0.45, 0.65),
            (0.75, 0.45), (0.30, 0.10), (0.10, -0.20), (0.55, 0.05), (0.65, -0.55),
            (0.25, -0.75), (-0.35, -0.75),
        ],
    },
    "interlagos": {
        "length_m": 4309,
        "drs_zones": [(0.16, 0.30), (0.82, 0.98)],
        "points": [
            (-0.65, -0.55), (-0.75, 0.35), (-0.45, 0.65), (0.45, 0.70), (0.75, 0.40),
            (0.20, 0.20), (-0.20, 0.30), (-0.25, -0.05), (0.35, -0.05), (0.25, -0.35),
            (-0.15, -0.25), (0.55, -0.65), (-0.20, -0.75),
        ],
    },
    "red_bull_ring": {
        "length_m": 4318,
        "drs_zones": [(0.02, 0.18), (0.24, 0.42), (0.84, 0.98)],
        "points": [
            (-0.75, -0.55), (0.25, -0.60), (0.35, 0.45), (-0.45, 0.75), (-0.55, 0.45),
            (-0.15, 0.15), (-0.35, -0.10), (0.65, 0.10), (0.80, -0.35), (0.55, -0.55),
        ],
    },
    "yas_marina": {
        "length_m": 5281,
        "drs_zones": [(0.36, 0.52), (0.58, 0.72)],
        "points": [
            (-0.20, -0.55), (0.35, -0.55), (0.55, -0.15), (0.85, 0.65), (0.65, 0.80),
            (-0.65, 0.25), (-0.85, 0.05), (-0.35, -0.15), (-0.45, -0.45), (-0.65, -0.55),
            (-0.55, -0.75), (-0.25, -0.70),
        ],
    },
}


def _catmull_rom_closed(points: List[Tuple[float, float]], num_samples: int = 200) -> Tuple[List[float], List[float]]:
    """Interpolate closed smooth circuit polyline using Catmull-Rom splines."""
    n = len(points)
    xs, ys = [], []
    steps_per_seg = max(4, num_samples // n)
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        for s in range(steps_per_seg):
            t = s / steps_per_seg
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            xs.append(round(x * 1000.0, 2))
            ys.append(round(y * 1000.0, 2))
    # Close loop
    xs.append(xs[0])
    ys.append(ys[0])
    return xs, ys


def build_circuit_geometry(circuit_name: str, circuit_id: str = "") -> dict:
    """Build 2D circuit geometry (center, inner, outer polylines, curvature, DRS zones)."""
    key = (circuit_id or circuit_name or "gp").lower().strip()
    matched = None
    for k, spec in CIRCUIT_SHAPES.items():
        if k in key or k in (circuit_name or "").lower():
            matched = spec
            break

    if matched:
        ctrl_pts = matched["points"]
        length_m = matched["length_m"]
        drs_zones = matched["drs_zones"]
    else:
        # Deterministic procedural F1 circuit from circuit name hash
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        num_corners = 11 + (digest[0] % 5)
        ctrl_pts = []
        for i in range(num_corners):
            angle = (2 * math.pi * i) / num_corners
            r_mod = 0.42 + 0.45 * ((digest[(i + 1) % len(digest)] % 100) / 100.0)
            ctrl_pts.append((r_mod * math.cos(angle), r_mod * math.sin(angle)))
        length_m = 4400 + (digest[2] % 18) * 100
        drs_zones = [(0.02, 0.16), (0.52, 0.66)]

    cx, cy = _catmull_rom_closed(ctrl_pts, num_samples=180)
    n = len(cx)

    # Compute inner/outer track edges & local curvature for realistic corner speed synthesis
    track_half_width = 28.0
    ix, iy, ox, oy = [], [], [], []
    curvatures = []

    for i in range(n):
        prev_i = (i - 2) % (n - 1)
        next_i = (i + 2) % (n - 1)
        dx = cx[next_i] - cx[prev_i]
        dy = cy[next_i] - cy[prev_i]
        seg_len = math.hypot(dx, dy) or 1.0
        nx = -dy / seg_len
        ny = dx / seg_len

        ix.append(round(cx[i] + nx * track_half_width, 2))
        iy.append(round(cy[i] + ny * track_half_width, 2))
        ox.append(round(cx[i] - nx * track_half_width, 2))
        oy.append(round(cy[i] - ny * track_half_width, 2))

        # Second derivative approximation for corner sharpness
        ddx = cx[next_i] - 2 * cx[i] + cx[prev_i]
        ddy = cy[next_i] - 2 * cy[i] + cy[prev_i]
        curv = math.hypot(ddx, ddy) / (seg_len + 1e-3)
        curvatures.append(curv)

    return {
        "circuit_length_m": length_m,
        "x_center": cx,
        "y_center": cy,
        "x_inner": ix,
        "y_inner": iy,
        "x_outer": ox,
        "y_outer": oy,
        "curvatures": curvatures,
        "drs_zones": drs_zones,
        "sector_splits": [0.33, 0.67, 1.0],
    }


def interpolate_track_xy(track_geo: dict, rel_dist: float) -> Tuple[float, float]:
    """Interpolate world (x, y) coordinates at fractional lap distance `rel_dist` in [0, 1]."""
    cx = track_geo["x_center"]
    cy = track_geo["y_center"]
    n = len(cx) - 1
    if n <= 0:
        return 0.0, 0.0
    frac = rel_dist % 1.0
    idx_f = frac * n
    i0 = int(math.floor(idx_f)) % n
    i1 = (i0 + 1) % n
    alpha = idx_f - math.floor(idx_f)
    x = cx[i0] * (1.0 - alpha) + cx[i1] * alpha
    y = cy[i0] * (1.0 - alpha) + cy[i1] * alpha
    return round(x, 2), round(y, 2)


def synthesize_lap_telemetry(
    driver_code: str,
    lap_number: int,
    lap_time_s: float,
    tyre_val: float,
    track_geo: dict,
    position: int = 1,
    num_points: int = 100,
) -> List[dict]:
    """
    Generate high-resolution distance-based telemetry samples matching `f1-race-replay`
    frame format (`speed`, `gear`, `throttle`, `brake`, `drs`, `dist`, `rel_dist`, `tyre`, `x`, `y`).
    Calibrated to the circuit's curvature profile and the driver's exact lap time.
    """
    length_m = track_geo["circuit_length_m"]
    curvatures = track_geo["curvatures"]
    drs_zones = track_geo["drs_zones"]
    n_geo = len(curvatures)

    # Driver-specific deterministic micro-signature
    seed_val = sum(ord(c) for c in (driver_code or "DRV")) + lap_number * 7
    avg_speed_kmh = (length_m / max(45.0, lap_time_s or 82.0)) * 3.6
    pace_scale = max(0.72, min(1.18, avg_speed_kmh / 215.0))

    raw_speeds = []
    drs_flags = []
    for i in range(num_points):
        rel = i / max(1, num_points - 1)
        geo_idx = min(n_geo - 1, int(rel * (n_geo - 1)))
        # Look ahead slightly for braking into corners
        lookahead_idx = (geo_idx + 3) % (n_geo - 1)
        curv = 0.65 * curvatures[geo_idx] + 0.35 * curvatures[lookahead_idx]

        in_drs = False
        for z_start, z_end in drs_zones:
            if z_start <= z_end:
                if z_start <= rel <= z_end:
                    in_drs = True
            else:
                if rel >= z_start or rel <= z_end:
                    in_drs = True

        drs_active = 1 if (in_drs and (position > 1 or lap_number > 2)) else 0
        drs_flags.append(drs_active)

        # Corner speed vs straight top speed
        corner_factor = 1.0 / (1.0 + 3.4 * (curv ** 1.15))
        base_v = (105.0 + 225.0 * corner_factor + (14.0 if drs_active else 0.0)) * pace_scale
        ripple = 2.5 * math.sin(rel * math.pi * 12 + seed_val)
        raw_speeds.append(max(72.0, min(352.0, base_v + ripple)))

    # Smooth speeds (forward acceleration limit + backward braking limit)
    speeds = list(raw_speeds)
    for i in range(1, num_points):
        speeds[i] = min(speeds[i], speeds[i - 1] + 18.0)
    for i in range(num_points - 2, -1, -1):
        speeds[i] = min(speeds[i], speeds[i + 1] + 28.0)

    samples = []
    elapsed_s = 0.0
    dt_step = (lap_time_s or 82.0) / num_points

    for i in range(num_points):
        rel = round(i / max(1, num_points - 1), 4)
        dist = round(rel * length_m, 2)
        spd = round(speeds[i], 1)
        next_spd = speeds[min(num_points - 1, i + 1)]
        dv = next_spd - spd

        if dv < -3.5:
            brake = round(min(100.0, abs(dv) * 4.2), 1)
            throttle = round(max(0.0, 25.0 - abs(dv) * 1.5), 1)
        elif dv < -0.5:
            brake = round(min(45.0, abs(dv) * 6.0), 1)
            throttle = round(max(15.0, 65.0 - abs(dv) * 8.0), 1)
        else:
            brake = 0.0
            throttle = round(min(100.0, 72.0 + dv * 4.5 + (28.0 if spd > 240 else 0.0)), 1)

        # Map speed to F1 8-speed gearbox
        if spd < 95:
            gear = 2
        elif spd < 130:
            gear = 3
        elif spd < 168:
            gear = 4
        elif spd < 205:
            gear = 5
        elif spd < 245:
            gear = 6
        elif spd < 288:
            gear = 7
        else:
            gear = 8

        x, y = interpolate_track_xy(track_geo, rel)
        rpm = int(min(12200, max(7800, 8200 + (spd % 42) * 90)))

        samples.append({
            "t": round(elapsed_s, 3),
            "dist": dist,
            "rel_dist": rel,
            "speed": spd,
            "gear": gear,
            "throttle": throttle,
            "brake": brake,
            "drs": drs_flags[i],
            "tyre": float(tyre_val),
            "rpm": rpm,
            "x": x,
            "y": y,
            "lap": lap_number,
            "position": position,
        })
        elapsed_s += dt_step

    return samples


# ==============================================================================
# 5. SAFETY CAR SIMULATION (ported from f1-race-replay/src/f1_data.py)
# ==============================================================================

def compute_safety_car_state(
    lap_number: int,
    rel_dist: float,
    leader_rel_dist: float,
    sc_vsc_zones: List[dict],
    track_geo: dict,
) -> Optional[dict]:
    """
    Simulate Safety Car position ~500m ahead of the race leader on the track polyline
    with three phases ('deploying', 'on_track', 'returning') and alpha opacity.
    """
    length_m = track_geo.get("circuit_length_m", 5000) or 5000
    offset_frac = 500.0 / length_m

    for zone in sc_vsc_zones:
        if zone.get("status") not in ("SC", "SafetyCar", "VSC"):
            continue
        s_lap = zone.get("start_lap", 0)
        e_lap = zone.get("end_lap", 0)
        if s_lap <= lap_number <= e_lap:
            sc_rel = (leader_rel_dist + offset_frac) % 1.0
            x, y = interpolate_track_xy(track_geo, sc_rel)

            if lap_number == s_lap and rel_dist < 0.25:
                phase = "deploying"
                alpha = round(min(1.0, 0.35 + rel_dist * 2.6), 2)
                label = "SC DEPLOYING" if zone.get("status") != "VSC" else "VSC DEPLOYING"
            elif lap_number == e_lap and rel_dist > 0.75:
                phase = "returning"
                alpha = round(max(0.15, 1.0 - (rel_dist - 0.75) * 3.4), 2)
                label = "SC IN THIS LAP" if zone.get("status") != "VSC" else "VSC ENDING"
            else:
                phase = "on_track"
                alpha = 1.0
                label = "SAFETY CAR" if zone.get("status") != "VSC" else "VIRTUAL SC"

            return {
                "active": True,
                "status": zone.get("status"),
                "label": label,
                "phase": phase,
                "alpha": alpha,
                "rel_dist": round(sc_rel, 4),
                "x": x,
                "y": y,
            }

    return {"active": False, "phase": "none", "alpha": 0.0, "x": 0.0, "y": 0.0, "label": "TRACK CLEAR"}


# ==============================================================================
# 6. FORMATTING & DATA NORMALIZATION HELPERS
# ==============================================================================

def _format_laptime(seconds: Optional[float]) -> str:
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return "—"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:06.3f}"


def _make_driver_code(first_name: str, last_name: str, existing_codes: set) -> str:
    raw = "".join(c for c in (last_name or first_name or "DRV") if c.isalpha()).upper()
    code = (raw[:3] if len(raw) >= 3 else (raw + "DRV")[:3])
    if code not in existing_codes:
        existing_codes.add(code)
        return code
    # Disambiguate (e.g. MSC vs RSC, VER vs JVE)
    fn_char = (first_name[:1] or "X").upper()
    alt = (fn_char + raw[:2]).upper()
    if alt not in existing_codes:
        existing_codes.add(alt)
        return alt
    for idx in range(2, 10):
        c2 = f"{raw[:2]}{idx}"
        if c2 not in existing_codes:
            existing_codes.add(c2)
            return c2
    return code


# ==============================================================================
# 7. UNIVERSAL CATALOG & HYBRID SESSION BUILDER (1950–2026)
# ==============================================================================

FALLBACK_HISTORICAL_DRIVERS = [
    ("Max", "Verstappen", "Red Bull", "Dutch"),
    ("Charles", "Leclerc", "Ferrari", "Monegasque"),
    ("Lewis", "Hamilton", "Mercedes", "British"),
    ("Lando", "Norris", "McLaren", "British"),
    ("Carlos", "Sainz", "Ferrari", "Spanish"),
    ("Oscar", "Piastri", "McLaren", "Australian"),
    ("George", "Russell", "Mercedes", "British"),
    ("Fernando", "Alonso", "Aston Martin", "Spanish"),
    ("Pierre", "Gasly", "Alpine", "French"),
    ("Alexander", "Albon", "Williams", "Thai"),
    ("Nico", "Hulkenberg", "Haas F1 Team", "German"),
    ("Yuki", "Tsunoda", "RB F1 Team", "Japanese"),
]

FALLBACK_CALENDAR = [
    (1, "Bahrain Grand Prix", "Bahrain International Circuit", "Bahrain", "Sakhir", 57),
    (2, "Saudi Arabian Grand Prix", "Jeddah Corniche Circuit", "Saudi Arabia", "Jeddah", 50),
    (3, "Australian Grand Prix", "Albert Park Grand Prix Circuit", "Australia", "Melbourne", 58),
    (4, "Japanese Grand Prix", "Suzuka Circuit", "Japan", "Suzuka", 53),
    (5, "Monaco Grand Prix", "Circuit de Monaco", "Monaco", "Monte-Carlo", 78),
    (6, "British Grand Prix", "Silverstone Circuit", "UK", "Silverstone", 52),
    (7, "Belgian Grand Prix", "Circuit de Spa-Francorchamps", "Belgium", "Spa", 44),
    (8, "Italian Grand Prix", "Autodromo Nazionale Monza", "Italy", "Monza", 53),
    (9, "São Paulo Grand Prix", "Autódromo José Carlos Pace", "Brazil", "São Paulo", 71),
    (10, "Abu Dhabi Grand Prix", "Yas Marina Circuit", "UAE", "Abu Dhabi", 58),
]


def get_pitwall_catalog(season: int, db_conn_fn=None) -> dict:
    """
    Return all races and drivers for `season` (1950–2026).
    Queries MySQL first (if available), then Jolpica API, with a built-in fallback.
    """
    season = int(season or 2024)
    if season in _CATALOG_CACHE:
        return _CATALOG_CACHE[season]

    races = []
    drivers = []

    # 1. Try MySQL Database if connection factory provided
    if db_conn_fn is not None:
        conn = None
        cur = None
        try:
            conn = db_conn_fn()
            if conn and conn.is_connected():
                cur = conn.cursor(dictionary=True)
                cur.execute(
                    """SELECT r.race_id, r.round_number, r.race_name, r.race_date, r.total_laps,
                              c.name AS circuit_name, c.country AS circuit_country, c.city AS circuit_city
                       FROM RACES r
                       JOIN CIRCUITS c ON r.circuit_id = c.circuit_id
                       WHERE r.season_year = %s
                       ORDER BY r.round_number ASC""",
                    (season,),
                )
                db_races = cur.fetchall()
                for r in db_races:
                    races.append({
                        "race_id": r["race_id"],
                        "round_number": r["round_number"],
                        "race_name": r["race_name"],
                        "race_date": str(r["race_date"]),
                        "total_laps": r["total_laps"] or 57,
                        "circuit_name": r["circuit_name"],
                        "circuit_country": r["circuit_country"],
                        "circuit_city": r["circuit_city"],
                    })

                cur.execute(
                    """SELECT DISTINCT d.driver_id, d.first_name, d.last_name, d.nationality,
                              COALESCE(c.name, 'F1 Team') AS team_name
                       FROM DRIVERS d
                       LEFT JOIN RACE_RESULTS rr ON d.driver_id = rr.driver_id
                       LEFT JOIN RACES r ON rr.race_id = r.race_id AND r.season_year = %s
                       LEFT JOIN CONSTRUCTORS c ON rr.constructor_id = c.constructor_id
                       WHERE r.season_year = %s
                       ORDER BY d.last_name ASC""",
                    (season, season),
                )
                db_drivers = cur.fetchall()
                used_codes = set()
                for idx, d in enumerate(db_drivers):
                    code = _make_driver_code(d["first_name"], d["last_name"], used_codes)
                    drivers.append({
                        "driver_id": d["driver_id"],
                        "code": code,
                        "first_name": d["first_name"],
                        "last_name": d["last_name"],
                        "name": f"{d['first_name']} {d['last_name']}",
                        "team": d["team_name"],
                        "nationality": d["nationality"],
                        "color": get_team_colour(d["team_name"], idx),
                    })
        except Exception:
            pass
        finally:
            try:
                if cur:
                    cur.close()
                if conn:
                    conn.close()
            except Exception:
                pass

    # 2. Fetch from Jolpica API if races or drivers missing
    if not races:
        try:
            api_races = jolpica_client.fetch_races(season)
            for r in api_races:
                races.append({
                    "race_id": None,
                    "round_number": r["round_number"],
                    "race_name": r["race_name"],
                    "race_date": str(r["race_date"]),
                    "total_laps": r["total_laps"] or 57,
                    "circuit_name": r["circuit_name"],
                    "circuit_country": r["circuit_country"],
                    "circuit_city": r["circuit_city"],
                })
        except Exception:
            pass

    if not drivers:
        try:
            standings = jolpica_client.fetch_driver_standings(season)
            used_codes = set()
            if standings:
                for idx, s in enumerate(standings):
                    code = _make_driver_code(s["driver_first_name"], s["driver_last_name"], used_codes)
                    drivers.append({
                        "driver_id": idx + 1,
                        "code": code,
                        "first_name": s["driver_first_name"],
                        "last_name": s["driver_last_name"],
                        "name": s["driver_name"],
                        "team": s["team_name"],
                        "nationality": s["driver_nationality"],
                        "color": get_team_colour(s["team_name"], idx),
                    })
            else:
                api_drivers = jolpica_client.fetch_drivers(season)
                for idx, d in enumerate(api_drivers):
                    code = _make_driver_code(d["first_name"], d["last_name"], used_codes)
                    drivers.append({
                        "driver_id": idx + 1,
                        "code": code,
                        "first_name": d["first_name"],
                        "last_name": d["last_name"],
                        "name": f"{d['first_name']} {d['last_name']}",
                        "team": "F1 Constructor",
                        "nationality": d["nationality"],
                        "color": DRIVER_PALETTE[idx % len(DRIVER_PALETTE)],
                    })
        except Exception:
            pass

    # 3. Built-in fallback if offline
    if not races:
        for rnd, rname, cname, country, city, laps in FALLBACK_CALENDAR:
            races.append({
                "race_id": rnd,
                "round_number": rnd,
                "race_name": rname,
                "race_date": f"{season}-{rnd + 2:02d}-15",
                "total_laps": laps,
                "circuit_name": cname,
                "circuit_country": country,
                "circuit_city": city,
            })

    if not drivers:
        used_codes = set()
        for idx, (fn, ln, team, nat) in enumerate(FALLBACK_HISTORICAL_DRIVERS):
            code = _make_driver_code(fn, ln, used_codes)
            drivers.append({
                "driver_id": idx + 1,
                "code": code,
                "first_name": fn,
                "last_name": ln,
                "name": f"{fn} {ln}",
                "team": team,
                "nationality": nat,
                "color": get_team_colour(team, idx),
            })

    catalog = {
        "season": season,
        "races": races,
        "drivers": drivers,
    }
    _CATALOG_CACHE[season] = catalog
    return catalog


def _resolve_openf1_session_key(season: int, round_number: int, country: str, race_name: str) -> Optional[int]:
    """Match a race (2023+) to its OpenF1 session_key."""
    if season < 2023:
        return None
    try:
        sessions = openf1_client.fetch_sessions(season, session_name="Race")
        if not sessions:
            return None
        country_low = (country or "").lower()
        rname_low = (race_name or "").lower()
        for s in sessions:
            c_name = (s.get("country_name") or "").lower()
            loc = (s.get("location") or "").lower()
            if country_low and (country_low in c_name or c_name in country_low or country_low in loc):
                return s.get("session_key")
            if loc and loc in rname_low:
                return s.get("session_key")
        if 1 <= round_number <= len(sessions):
            return sessions[round_number - 1].get("session_key")
    except Exception:
        return None
    return None


def get_pitwall_session(
    season: int,
    round_number: int = 1,
    race_id: Optional[int] = None,
    driver_code: Optional[str] = None,
    compare_driver_code: Optional[str] = None,
    lap: int = 1,
    db_conn_fn=None,
) -> dict:
    """
    Build or retrieve the complete Pit Wall Insights & Telemetry bundle for ANY
    season, race round, and driver.
    """
    season = int(season or 2024)
    round_number = max(1, int(round_number or 1))
    cache_key = f"{season}_{round_number}_{race_id or 0}"

    if cache_key not in _SESSION_CACHE:
        _SESSION_CACHE[cache_key] = _build_base_session_bundle(
            season=season,
            round_number=round_number,
            race_id=race_id,
            db_conn_fn=db_conn_fn,
        )

    bundle = _SESSION_CACHE[cache_key]
    drivers_list = bundle["drivers"]
    total_laps = bundle["session_info"]["total_laps"]
    selected_lap = max(1, min(total_laps, int(lap or 1)))

    # Resolve primary driver and comparison driver
    valid_codes = [d["code"] for d in drivers_list]
    if not driver_code or driver_code not in valid_codes:
        # Also allow matching by driver_id or substring
        matched_code = None
        if driver_code:
            q = str(driver_code).strip().lower()
            for d in drivers_list:
                if (
                    str(d.get("driver_id")) == q
                    or d["code"].lower() == q
                    or q in d["name"].lower()
                ):
                    matched_code = d["code"]
                    break
        primary_code = matched_code or (valid_codes[0] if valid_codes else "VER")
    else:
        primary_code = driver_code

    comp_code = None
    if compare_driver_code and compare_driver_code != "none":
        q_comp = str(compare_driver_code).strip().upper()
        if q_comp in valid_codes and q_comp != primary_code:
            comp_code = q_comp
    if not comp_code and len(valid_codes) > 1:
        comp_code = valid_codes[1] if valid_codes[0] == primary_code else valid_codes[0]

    # Compute progressive Sector Analysis for selected driver
    sector_analysis = classify_sector_statuses(
        primary_code,
        bundle["lap_times"],
        up_to_lap=total_laps,
    )

    # Build high-resolution telemetry for primary driver & comparison driver on `selected_lap`
    primary_telemetry = _get_or_build_driver_lap_telemetry(bundle, primary_code, selected_lap)
    compare_telemetry = (
        _get_or_build_driver_lap_telemetry(bundle, comp_code, selected_lap)
        if comp_code
        else []
    )

    # Build multi-car replay frames for the selected lap so the live stream / scrubber
    # updates all 20 cars on the Track Position Map + Driver Telemetry + Leaderboard simultaneously
    replay_frames = _build_multi_car_lap_frames(bundle, selected_lap, primary_code, primary_telemetry)

    return {
        "session_info": bundle["session_info"],
        "track_geometry": bundle["track_geometry"],
        "drivers": drivers_list,
        "selected_driver": primary_code,
        "compare_driver": comp_code,
        "selected_lap": selected_lap,
        "tyre_strategy": bundle["tyre_strategy"],
        "lap_times": bundle["lap_times"],
        "sector_analysis": sector_analysis,
        "bayesian_tyre_model": bundle["bayesian_tyre_model"],
        "race_control": bundle["race_control"],
        "sc_vsc_zones": bundle["sc_vsc_zones"],
        "driver_telemetry": {
            "primary": {
                "driver": primary_code,
                "lap": selected_lap,
                "samples": primary_telemetry,
            },
            "compare": {
                "driver": comp_code,
                "lap": selected_lap,
                "samples": compare_telemetry,
            } if comp_code else None,
        },
        "replay_frames": replay_frames,
    }


def _build_base_session_bundle(
    season: int,
    round_number: int,
    race_id: Optional[int] = None,
    db_conn_fn=None,
) -> dict:
    """Fetch & synthesize full race data (results, laps, stints, sectors, race control, Bayesian model)."""
    catalog = get_pitwall_catalog(season, db_conn_fn=db_conn_fn)
    race_meta = None
    for r in catalog["races"]:
        if (race_id and r.get("race_id") == race_id) or r.get("round_number") == round_number:
            race_meta = r
            break
    if not race_meta and catalog["races"]:
        race_meta = catalog["races"][0]
        round_number = race_meta["round_number"]

    race_name = race_meta["race_name"] if race_meta else f"{season} Round {round_number} Grand Prix"
    circuit_name = race_meta["circuit_name"] if race_meta else "Grand Prix Circuit"
    circuit_country = race_meta["circuit_country"] if race_meta else "Unknown"
    race_date = race_meta["race_date"] if race_meta else f"{season}-05-01"
    total_laps = int((race_meta.get("total_laps") if race_meta else 57) or 57)

    track_geo = build_circuit_geometry(circuit_name)
    data_sources = []

    # Weather defaults
    weather = {
        "temperature_celsius": 26.5,
        "humidity_percent": 48.0,
        "wind_speed_kmh": 8.4,
        "rainfall_mm": 0.0,
        "track_condition": "Dry",
    }

    # Try OpenF1 session resolution for 2023+
    session_key = _resolve_openf1_session_key(season, round_number, circuit_country, race_name)
    openf1_stints = []
    openf1_rc = []
    openf1_drivers_map = {}

    if session_key:
        try:
            w_data = openf1_client.fetch_weather(session_key)
            if w_data:
                weather = w_data
                data_sources.append("OpenF1 Weather")
        except Exception:
            pass
        try:
            openf1_stints = openf1_client.fetch_stints(session_key)
            if openf1_stints:
                data_sources.append("OpenF1 Stints")
        except Exception:
            pass
        try:
            openf1_rc = openf1_client.fetch_race_control(session_key)
            if openf1_rc:
                data_sources.append("OpenF1 Race Control")
        except Exception:
            pass
        try:
            of1_drivers = openf1_client.fetch_openf1_drivers(session_key)
            for od in of1_drivers:
                openf1_drivers_map[od["code"]] = od
        except Exception:
            pass

    # Fetch Race Results from Jolpica (works 1950–2026)
    results_list = []
    try:
        res_data, api_laps = jolpica_client.fetch_race_results(season, round_number)
        if res_data:
            results_list = res_data
            if api_laps and api_laps > 5:
                total_laps = api_laps
            data_sources.append("Jolpica Official Classification")
    except Exception:
        pass

    # Build unified drivers list for this race
    drivers = []
    used_codes = set()
    if results_list:
        for idx, r in enumerate(results_list):
            code = _make_driver_code(r["driver_first_name"], r["driver_last_name"], used_codes)
            of1_d = openf1_drivers_map.get(code, {})
            team_name = r.get("constructor_name") or of1_d.get("team_name") or "F1 Team"
            color = of1_d.get("team_colour") or get_team_colour(team_name, idx)
            drivers.append({
                "driver_id": idx + 1,
                "driver_number": of1_d.get("driver_number") or (idx + 1),
                "code": code,
                "first_name": r["driver_first_name"],
                "last_name": r["driver_last_name"],
                "name": f"{r['driver_first_name']} {r['driver_last_name']}",
                "team": team_name,
                "color": color,
                "grid": r.get("grid_position") or (idx + 1),
                "position": r.get("finishing_position") or (idx + 1),
                "points": r.get("points_scored", 0.0),
                "status": r.get("status") or "Finished",
                "fastest_lap_time": r.get("fastest_lap_time"),
            })
    else:
        for idx, d in enumerate(catalog["drivers"][:20]):
            code = d["code"]
            of1_d = openf1_drivers_map.get(code, {})
            drivers.append({
                "driver_id": d.get("driver_id") or (idx + 1),
                "driver_number": of1_d.get("driver_number") or (idx + 1),
                "code": code,
                "first_name": d.get("first_name", ""),
                "last_name": d.get("last_name", ""),
                "name": d["name"],
                "team": d.get("team", "F1 Team"),
                "color": of1_d.get("team_colour") or d.get("color") or DRIVER_PALETTE[idx % len(DRIVER_PALETTE)],
                "grid": idx + 1,
                "position": idx + 1,
                "points": max(0, 25 - idx * 2) if idx < 10 else 0,
                "status": "Finished",
                "fastest_lap_time": None,
            })

    # Fetch Pit Stops from Jolpica (available 2012+)
    api_pits = []
    if season >= 2011:
        try:
            api_pits = jolpica_client.fetch_pit_stops(season, round_number)
            if api_pits:
                data_sources.append("Jolpica Pit Stops")
        except Exception:
            pass

    # Build Tyre Strategy (Stints) per driver
    tyre_strategy = _build_tyre_strategy_for_drivers(
        drivers=drivers,
        total_laps=total_laps,
        openf1_stints=openf1_stints,
        api_pits=api_pits,
        weather_condition=weather.get("track_condition", "Dry"),
        season=season,
    )

    # Determine Safety Car / VSC zones (from OpenF1 Race Control or deterministic race events)
    sc_vsc_zones, race_control_feed = _build_race_control_and_sc_zones(
        season=season,
        round_number=round_number,
        total_laps=total_laps,
        drivers=drivers,
        tyre_strategy=tyre_strategy,
        openf1_rc=openf1_rc,
    )

    # Build Lap Times & Sector 1/2/3 splits per driver
    lap_times = _build_lap_times_for_drivers(
        season=season,
        round_number=round_number,
        total_laps=total_laps,
        track_geo=track_geo,
        drivers=drivers,
        tyre_strategy=tyre_strategy,
        sc_vsc_zones=sc_vsc_zones,
    )

    # Fit Bayesian State-Space Tyre Degradation Model
    bayesian_model = BayesianTyreDegradationModel(track_condition=weather.get("track_condition", "Dry"))
    bayesian_summary = bayesian_model.fit_and_predict(lap_times, total_laps=total_laps)

    if not data_sources:
        data_sources.append("Historical F1 Physics & Timing Engine")
    else:
        data_sources.append("Physics Telemetry Synthesis")

    return {
        "session_info": {
            "season": season,
            "round_number": round_number,
            "race_id": race_id or (race_meta.get("race_id") if race_meta else round_number),
            "race_name": race_name,
            "circuit_name": circuit_name,
            "circuit_country": circuit_country,
            "race_date": race_date,
            "total_laps": total_laps,
            "circuit_length_m": track_geo["circuit_length_m"],
            "session_key": session_key,
            "weather": weather,
            "data_source": " + ".join(data_sources),
        },
        "track_geometry": {
            "circuit_length_m": track_geo["circuit_length_m"],
            "x_center": track_geo["x_center"],
            "y_center": track_geo["y_center"],
            "x_inner": track_geo["x_inner"],
            "y_inner": track_geo["y_inner"],
            "x_outer": track_geo["x_outer"],
            "y_outer": track_geo["y_outer"],
            "drs_zones": track_geo["drs_zones"],
            "sector_splits": track_geo["sector_splits"],
        },
        "_raw_track_geo": track_geo,
        "drivers": drivers,
        "tyre_strategy": tyre_strategy,
        "lap_times": lap_times,
        "bayesian_tyre_model": bayesian_summary,
        "race_control": race_control_feed,
        "sc_vsc_zones": sc_vsc_zones,
        "_telemetry_cache": {},
    }


def _build_tyre_strategy_for_drivers(
    drivers: List[dict],
    total_laps: int,
    openf1_stints: List[dict],
    api_pits: List[dict],
    weather_condition: str,
    season: int,
) -> List[dict]:
    """Build horizontal Gantt stint bar data (`tyre_strategy_window.py` format) for all drivers."""
    # Map driver_number -> openf1 stints
    stints_by_num: Dict[int, List[dict]] = {}
    for s in openf1_stints:
        dnum = s.get("driver_number")
        if dnum:
            stints_by_num.setdefault(dnum, []).append(s)

    # Map driver last name lowercase -> pit laps from Jolpica
    pits_by_ref: Dict[str, List[int]] = {}
    for p in api_pits:
        ref = (p.get("driver_ref") or "").lower()
        lap_n = p.get("lap_number")
        if ref and lap_n:
            pits_by_ref.setdefault(ref, []).append(int(lap_n))

    is_wet = (weather_condition or "Dry").lower() in ("wet", "damp")
    strategy_rows = []

    for idx, d in enumerate(drivers):
        code = d["code"]
        dnum = d.get("driver_number")
        lname_low = (d.get("last_name") or "").lower()
        status = d.get("status", "Finished")

        # Determine how many laps this driver completed
        if status == "Finished" or "+" in str(status):
            driver_end_lap = total_laps
        else:
            # Retired at deterministic lap based on position
            driver_end_lap = max(5, int(total_laps * (0.85 - 0.03 * max(0, idx - 12))))

        stint_blocks = []
        if dnum and dnum in stints_by_num:
            raw_list = sorted(stints_by_num[dnum], key=lambda x: x.get("stint_number", 1))
            for s in raw_list:
                s_lap = max(1, int(s.get("lap_start") or 1))
                e_lap = min(total_laps, int(s.get("lap_end") or driver_end_lap))
                if e_lap < s_lap:
                    e_lap = max(s_lap, driver_end_lap)
                t_val = get_tyre_float(s.get("compound", "MEDIUM"))
                col, abbr, cname = get_tyre_meta(t_val)
                stint_blocks.append({
                    "stint_number": s.get("stint_number", len(stint_blocks) + 1),
                    "start_lap": s_lap,
                    "end_lap": e_lap,
                    "laps_count": max(1, e_lap - s_lap + 1),
                    "tyre": t_val,
                    "compound": cname,
                    "abbr": abbr,
                    "color": col,
                })
        else:
            # Use Jolpica pit stops if matched, or realistic 1-stop / 2-stop strategy
            matched_pits = []
            for ref_k, p_laps in pits_by_ref.items():
                if lname_low and (lname_low in ref_k or ref_k in lname_low):
                    matched_pits = sorted(list(set(p_laps)))
                    break

            if not matched_pits:
                if idx % 3 == 0:
                    # 2-stop strategy
                    p1 = max(2, int(total_laps * 0.27) + (idx % 4) - 1)
                    p2 = max(p1 + 5, int(total_laps * 0.62) + (idx % 3) - 1)
                    matched_pits = [p for p in (p1, p2) if p < driver_end_lap]
                else:
                    # 1-stop strategy
                    p1 = max(2, int(total_laps * 0.42) + (idx % 5) - 2)
                    matched_pits = [p1] if p1 < driver_end_lap else []

            if is_wet:
                seq = [4.0, 2.0, 1.0] if idx % 2 == 0 else [5.0, 4.0, 2.0]
            elif idx % 3 == 0:
                seq = [1.0, 2.0, 3.0]
            elif idx % 3 == 1:
                seq = [2.0, 3.0, 1.0]
            else:
                seq = [1.0, 3.0, 2.0]

            boundaries = [1] + matched_pits + [driver_end_lap]
            for s_idx in range(len(boundaries) - 1):
                s_lap = boundaries[s_idx] if s_idx == 0 else boundaries[s_idx] + 1
                e_lap = boundaries[s_idx + 1]
                if s_lap > e_lap:
                    continue
                t_val = seq[s_idx % len(seq)]
                col, abbr, cname = get_tyre_meta(t_val)
                stint_blocks.append({
                    "stint_number": s_idx + 1,
                    "start_lap": s_lap,
                    "end_lap": e_lap,
                    "laps_count": max(1, e_lap - s_lap + 1),
                    "tyre": t_val,
                    "compound": cname,
                    "abbr": abbr,
                    "color": col,
                })

        pit_laps = [b["end_lap"] for b in stint_blocks[:-1]]
        strategy_rows.append({
            "driver": code,
            "name": d["name"],
            "team": d["team"],
            "color": d["color"],
            "position": d["position"],
            "status": status,
            "laps_completed": driver_end_lap,
            "pit_stops": pit_laps,
            "stints": stint_blocks,
        })

    return strategy_rows


def _build_race_control_and_sc_zones(
    season: int,
    round_number: int,
    total_laps: int,
    drivers: List[dict],
    tyre_strategy: List[dict],
    openf1_rc: List[dict],
) -> Tuple[List[dict], List[dict]]:
    """Build FIA Race Control Feed messages and SC/VSC lap intervals."""
    events = []
    sc_zones = []

    if openf1_rc:
        sc_start = None
        vsc_start = None
        for idx, item in enumerate(openf1_rc):
            lap_n = int(item.get("lap_number") or 1)
            msg = item.get("message") or ""
            cat = item.get("category") or "Other"
            flag = (item.get("flag") or "").upper()
            accent = RACE_CONTROL_FLAG_COLOURS.get(flag) or RACE_CONTROL_CAT_COLOURS.get(cat, "#888888")

            msg_upper = msg.upper()
            if "SAFETY CAR DEPLOYED" in msg_upper and "VIRTUAL" not in msg_upper:
                sc_start = lap_n
                cat = "SafetyCar"
                accent = "#FF8C00"
            elif "VIRTUAL SAFETY CAR DEPLOYED" in msg_upper:
                vsc_start = lap_n
                cat = "SafetyCar"
                accent = "#FF8C00"
            elif ("SAFETY CAR IN THIS LAP" in msg_upper or flag in ("GREEN", "CLEAR")) and sc_start is not None:
                sc_zones.append({"status": "SC", "start_lap": sc_start, "end_lap": max(sc_start + 1, lap_n)})
                sc_start = None
            elif ("VIRTUAL SAFETY CAR ENDING" in msg_upper or flag in ("GREEN", "CLEAR")) and vsc_start is not None:
                sc_zones.append({"status": "VSC", "start_lap": vsc_start, "end_lap": max(vsc_start + 1, lap_n)})
                vsc_start = None

            events.append({
                "id": idx + 1,
                "lap": lap_n,
                "time_str": f"Lap {lap_n}/{total_laps}",
                "category": cat,
                "flag": flag or cat.upper(),
                "sector": item.get("sector"),
                "message": msg,
                "accent_color": accent,
            })

    if not events:
        # Synthesize authentic FIA Race Control messages synced to race events
        sc_lap = max(4, int(total_laps * 0.34))
        sc_end = min(total_laps - 2, sc_lap + 3)
        vsc_lap = max(sc_end + 6, int(total_laps * 0.72))
        vsc_end = min(total_laps - 1, vsc_lap + 1)

        sc_zones = [
            {"status": "SC", "start_lap": sc_lap, "end_lap": sc_end},
            {"status": "VSC", "start_lap": vsc_lap, "end_lap": vsc_end},
        ]

        leader = drivers[0]["code"] if drivers else "VER"
        p2 = drivers[1]["code"] if len(drivers) > 1 else "LEC"
        p5 = drivers[4]["code"] if len(drivers) > 4 else "SAI"

        raw_msgs = [
            (1, "Flag", "GREEN", "GREEN LIGHT - PIT EXIT OPEN / RACE START", None),
            (2, "Drs", "DRS", "DRS ENABLED - RACE CONTROL", None),
            (max(3, sc_lap - 1), "Flag", "YELLOW", f"YELLOW FLAG IN SECTOR 2 - DEBRIS ON TRACK", 2),
            (sc_lap, "SafetyCar", "SC", "SAFETY CAR DEPLOYED", None),
            (sc_end, "SafetyCar", "SC", "SAFETY CAR IN THIS LAP", None),
            (sc_end + 1, "Flag", "GREEN", "TRACK CLEAR - GREEN FLAG", None),
            (sc_end + 2, "Drs", "DRS", "DRS ENABLED", None),
            (int(total_laps * 0.52), "CarEvent", "BLACK AND WHITE", f"CAR ({p5}) TIME DELETED - TRACK LIMITS AT TURN 4", 1),
            (vsc_lap, "SafetyCar", "VSC", "VIRTUAL SAFETY CAR DEPLOYED", None),
            (vsc_end, "SafetyCar", "VSC", "VIRTUAL SAFETY CAR ENDING", None),
            (vsc_end + 1, "Flag", "GREEN", "TRACK CLEAR - GREEN FLAG", None),
            (total_laps, "Flag", "CHEQUERED", f"CHEQUERED FLAG - {leader} WINS ahead of {p2}", None),
        ]

        for idx, (lap_n, cat, flg, msg, sec) in enumerate(raw_msgs, start=1):
            accent = RACE_CONTROL_FLAG_COLOURS.get(flg) or RACE_CONTROL_CAT_COLOURS.get(cat, "#888888")
            events.append({
                "id": idx,
                "lap": min(total_laps, lap_n),
                "time_str": f"Lap {min(total_laps, lap_n)}/{total_laps}",
                "category": cat,
                "flag": flg,
                "sector": sec,
                "message": msg,
                "accent_color": accent,
            })

    return sc_zones, events


def _build_lap_times_for_drivers(
    season: int,
    round_number: int,
    total_laps: int,
    track_geo: dict,
    drivers: List[dict],
    tyre_strategy: List[dict],
    sc_vsc_zones: List[dict],
) -> Dict[str, List[dict]]:
    """Build per-driver lap times, S1/S2/S3 splits, 3-lap rolling averages, and gaps to leader."""
    length_m = track_geo["circuit_length_m"]
    # Baseline lap time from circuit length (~215 km/h average speed)
    base_circuit_s = max(68.0, min(108.0, (length_m / 59.5)))
    # Era adjustment (1950s–1980s cars slightly different pace profile)
    if season < 1980:
        base_circuit_s *= 1.12
    elif season < 2000:
        base_circuit_s *= 1.04

    sc_laps_set = set()
    vsc_laps_set = set()
    for z in sc_vsc_zones:
        for l_num in range(z.get("start_lap", 0), z.get("end_lap", 0) + 1):
            if z.get("status") == "VSC":
                vsc_laps_set.add(l_num)
            else:
                sc_laps_set.add(l_num)

    strat_by_code = {s["driver"]: s for s in tyre_strategy}
    raw_laps_by_driver: Dict[str, List[dict]] = {}
    cum_time_by_driver_lap: Dict[int, Dict[str, float]] = {}

    for idx, d in enumerate(drivers):
        code = d["code"]
        strat = strat_by_code.get(code, {})
        stints = strat.get("stints", [])
        pit_in_laps = set(strat.get("pit_stops", []))
        pit_out_laps = {p + 1 for p in pit_in_laps}
        max_driver_lap = strat.get("laps_completed", total_laps)

        driver_skill_delta = idx * 0.16
        seed_base = sum(ord(c) for c in code)
        driver_entries = []
        cum_s = idx * 0.45  # Starting grid stagger

        for lap_n in range(1, max_driver_lap + 1):
            # Find active stint & tyre compound
            active_tyre = 2.0
            stint_age = lap_n
            for st in stints:
                if st["start_lap"] <= lap_n <= st["end_lap"]:
                    active_tyre = st["tyre"]
                    stint_age = lap_n - st["start_lap"] + 1
                    break

            # Compound pace & degradation
            if active_tyre == 1.0:      # Soft
                comp_delta = -0.55 + 0.058 * stint_age
            elif active_tyre == 2.0:    # Medium
                comp_delta = 0.0 + 0.034 * stint_age
            elif active_tyre == 3.0:    # Hard
                comp_delta = 0.45 + 0.018 * stint_age
            elif active_tyre == 4.0:    # Inter
                comp_delta = 6.5 + 0.040 * stint_age
            else:                       # Wet
                comp_delta = 12.0 + 0.025 * stint_age

            # Fuel burn improvement (~0.032s per 1.6kg = ~0.051s per lap)
            fuel_benefit = -0.051 * (lap_n - 1)
            # Lap 1 standing start & traffic delta
            lap1_delta = 4.2 + idx * 0.22 if lap_n == 1 else 0.0

            is_pit_in = lap_n in pit_in_laps
            is_pit_out = lap_n in pit_out_laps
            is_sc = lap_n in sc_laps_set or lap_n in vsc_laps_set

            pit_delta = 4.5 if is_pit_in else (17.5 if is_pit_out else 0.0)
            sc_delta = (24.0 if lap_n in sc_laps_set else 12.5) if is_sc else 0.0

            # Deterministic micro-variation per lap
            wave = 0.24 * math.sin(lap_n * 0.9 + seed_base) + 0.14 * math.cos(lap_n * 1.7 + idx)

            lap_time_s = round(
                base_circuit_s
                + driver_skill_delta
                + comp_delta
                + fuel_benefit
                + lap1_delta
                + pit_delta
                + sc_delta
                + wave,
                3,
            )

            # Split into Sector 1 (29%), Sector 2 (38%), Sector 3 (33%) with slight variance
            s1_ratio = 0.288 + 0.003 * math.sin(lap_n + seed_base)
            s2_ratio = 0.382 + 0.003 * math.cos(lap_n * 1.3 + idx)
            s1_s = round(lap_time_s * s1_ratio, 3)
            s2_s = round(lap_time_s * s2_ratio, 3)
            s3_s = round(lap_time_s - s1_s - s2_s, 3)

            cum_s = round(cum_s + lap_time_s, 3)
            cum_time_by_driver_lap.setdefault(lap_n, {})[code] = cum_s

            col, abbr, cname = get_tyre_meta(active_tyre)
            driver_entries.append({
                "lap": lap_n,
                "time_s": lap_time_s,
                "lap_time_str": _format_laptime(lap_time_s),
                "cum_time_s": cum_s,
                "sector1_s": s1_s,
                "sector2_s": s2_s,
                "sector3_s": s3_s,
                "tyre": active_tyre,
                "compound": cname,
                "compound_abbr": abbr,
                "compound_color": col,
                "stint_age": stint_age,
                "is_pit_in": is_pit_in,
                "is_pit_out": is_pit_out,
                "is_sc": is_sc,
            })

        # Compute 3-lap rolling clean pace average
        clean_window = []
        for entry in driver_entries:
            if not entry["is_pit_in"] and not entry["is_pit_out"] and not entry["is_sc"] and entry["lap"] > 1:
                clean_window.append(entry["time_s"])
                if len(clean_window) > 3:
                    clean_window.pop(0)
            entry["rolling_3lap_s"] = round(sum(clean_window) / len(clean_window), 3) if clean_window else entry["time_s"]

        raw_laps_by_driver[code] = driver_entries

    # Compute Gap to Leader at each lap
    for lap_n, driver_cums in cum_time_by_driver_lap.items():
        leader_cum = min(driver_cums.values()) if driver_cums else 0.0
        sorted_codes = sorted(driver_cums.keys(), key=lambda c: driver_cums[c])
        pos_map = {c: pos_i + 1 for pos_i, c in enumerate(sorted_codes)}
        for code, entries in raw_laps_by_driver.items():
            if lap_n <= len(entries):
                entry = entries[lap_n - 1]
                entry["gap_to_leader_s"] = round(max(0.0, entry["cum_time_s"] - leader_cum), 3)
                entry["position"] = pos_map.get(code, 20)

    return raw_laps_by_driver


def _get_or_build_driver_lap_telemetry(bundle: dict, driver_code: str, lap_number: int) -> List[dict]:
    """Retrieve or synthesize 100-point telemetry trace for `(driver_code, lap_number)`."""
    t_cache = bundle["_telemetry_cache"]
    key = f"{driver_code}_{lap_number}"
    if key in t_cache:
        return t_cache[key]

    driver_laps = bundle["lap_times"].get(driver_code, [])
    lap_entry = None
    for e in driver_laps:
        if e["lap"] == lap_number:
            lap_entry = e
            break
    if not lap_entry and driver_laps:
        lap_entry = driver_laps[-1]

    lap_time_s = lap_entry["time_s"] if lap_entry else 82.0
    tyre_val = lap_entry["tyre"] if lap_entry else 2.0
    pos = lap_entry.get("position", 1) if lap_entry else 1

    samples = synthesize_lap_telemetry(
        driver_code=driver_code,
        lap_number=lap_number,
        lap_time_s=lap_time_s,
        tyre_val=tyre_val,
        track_geo=bundle["_raw_track_geo"],
        position=pos,
        num_points=100,
    )
    t_cache[key] = samples
    return samples


def _build_multi_car_lap_frames(
    bundle: dict,
    selected_lap: int,
    primary_code: str,
    primary_telemetry: List[dict],
) -> List[dict]:
    """
    Build 50 synchronized multi-car frames across `selected_lap` in exact `f1-race-replay`
    stream format:
        {
          "frame_index": i,
          "lap": selected_lap,
          "rel_dist": 0.0..1.0,
          "session_time_s": ...,
          "frame": {
            "drivers": {
              "VER": {"speed", "gear", "throttle", "brake", "drs", "dist", "rel_dist", "tyre", "x", "y", "lap", "position", "gap_s", "status"}
            },
            "safety_car": {"active", "x", "y", "phase", "alpha", "label"}
          }
        }
    """
    track_geo = bundle["_raw_track_geo"]
    length_m = track_geo["circuit_length_m"]
    drivers = bundle["drivers"]
    lap_times = bundle["lap_times"]
    sc_vsc_zones = bundle["sc_vsc_zones"]

    # Gather each driver's state at `selected_lap`
    driver_lap_state = {}
    for d in drivers:
        code = d["code"]
        entries = lap_times.get(code, [])
        if selected_lap <= len(entries):
            e = entries[selected_lap - 1]
            driver_lap_state[code] = {
                "active": True,
                "entry": e,
                "color": d["color"],
                "status": "RUNNING",
            }
        else:
            last_e = entries[-1] if entries else {"time_s": 85.0, "tyre": 2.0, "gap_to_leader_s": 99.0, "position": 20}
            driver_lap_state[code] = {
                "active": False,
                "entry": last_e,
                "color": d["color"],
                "status": "OUT",
            }

    num_frames = 50
    frames = []
    for f_idx in range(num_frames):
        t_idx = min(len(primary_telemetry) - 1, f_idx * 2)
        p_sample = primary_telemetry[t_idx]
        base_rel = p_sample["rel_dist"]

        drivers_frame = {}
        leader_rel = base_rel

        for d in drivers:
            code = d["code"]
            st = driver_lap_state[code]
            e = st["entry"]
            lap_s = e.get("time_s", 82.0) or 82.0
            gap_s = e.get("gap_to_leader_s", 0.0) or 0.0
            pos = e.get("position", d["position"])
            tyre_v = e.get("tyre", 2.0)

            if code == primary_code:
                drivers_frame[code] = {
                    "speed": p_sample["speed"],
                    "gear": p_sample["gear"],
                    "throttle": p_sample["throttle"],
                    "brake": p_sample["brake"],
                    "drs": p_sample["drs"],
                    "dist": p_sample["dist"],
                    "rel_dist": p_sample["rel_dist"],
                    "tyre": tyre_v,
                    "x": p_sample["x"],
                    "y": p_sample["y"],
                    "lap": selected_lap,
                    "position": pos,
                    "gap_s": gap_s,
                    "status": st["status"],
                }
                if pos == 1:
                    leader_rel = p_sample["rel_dist"]
            else:
                if not st["active"]:
                    # Retired in pit lane
                    x0, y0 = interpolate_track_xy(track_geo, 0.0)
                    drivers_frame[code] = {
                        "speed": 0.0,
                        "gear": 0,
                        "throttle": 0.0,
                        "brake": 0.0,
                        "drs": 0,
                        "dist": 0.0,
                        "rel_dist": 0.0,
                        "tyre": tyre_v,
                        "x": x0,
                        "y": y0,
                        "lap": len(lap_times.get(code, [])),
                        "position": pos,
                        "gap_s": gap_s,
                        "status": "OUT",
                    }
                    continue

                # Offset fractional distance based on gap difference to primary driver
                primary_gap = driver_lap_state[primary_code]["entry"].get("gap_to_leader_s", 0.0) or 0.0
                rel_offset = (primary_gap - gap_s) / lap_s
                car_rel = (base_rel + rel_offset) % 1.0
                if pos == 1:
                    leader_rel = car_rel
                cx, cy = interpolate_track_xy(track_geo, car_rel)
                drivers_frame[code] = {
                    "speed": round(max(80.0, p_sample["speed"] - (pos - 1) * 0.4), 1),
                    "gear": p_sample["gear"],
                    "throttle": p_sample["throttle"],
                    "brake": p_sample["brake"],
                    "drs": 1 if (p_sample["drs"] and pos > 1) else 0,
                    "dist": round(car_rel * length_m, 2),
                    "rel_dist": round(car_rel, 4),
                    "tyre": tyre_v,
                    "x": cx,
                    "y": cy,
                    "lap": selected_lap,
                    "position": pos,
                    "gap_s": gap_s,
                    "status": "PIT" if e.get("is_pit_in") and car_rel > 0.92 else "RUNNING",
                }

        sc_state = compute_safety_car_state(
            lap_number=selected_lap,
            rel_dist=base_rel,
            leader_rel_dist=leader_rel,
            sc_vsc_zones=sc_vsc_zones,
            track_geo=track_geo,
        )

        frames.append({
            "frame_index": f_idx,
            "lap": selected_lap,
            "rel_dist": base_rel,
            "lap_elapsed_s": p_sample["t"],
            "frame": {
                "drivers": drivers_frame,
                "safety_car": sc_state,
            },
        })

    return frames


# ==============================================================================
# 9. 2D TRACK REPLAY & INTERACTIVE CONTROLS ENGINE
#    (ported from src/interfaces/race_replay.py, qualifying.py, practice.py,
#     and src/ui_components.py)
# ==============================================================================

_REPLAY_CACHE: Dict[str, dict] = {}

F1_POINTS_TABLE = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
SPRINT_POINTS_TABLE = [8, 7, 6, 5, 4, 3, 2, 1]


def format_wind_direction(degrees: Optional[float]) -> str:
    """Convert wind direction in degrees to 16-point compass rose (from src/ui_components.py)."""
    if degrees is None:
        return "N/A"
    deg_norm = float(degrees) % 360.0
    dirs = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    idx = int((deg_norm / 22.5) + 0.5) % len(dirs)
    return dirs[idx]


def _compute_sector_markers(track_geo: dict) -> List[dict]:
    """
    Compute world (x, y) coordinates and perpendicular normal vectors for
    Start/Finish (SF), Sector 1 end (S1), and Sector 2 end (S2) markers.
    """
    cx = track_geo.get("x_center", [])
    cy = track_geo.get("y_center", [])
    ix = track_geo.get("x_inner", [])
    iy = track_geo.get("y_inner", [])
    ox = track_geo.get("x_outer", [])
    oy = track_geo.get("y_outer", [])
    n = len(cx)
    if n < 4:
        return []

    markers = [
        ("SF", "START / FINISH", 0.0, "#FFFFFF"),
        ("S1", "SECTOR 1", 0.31, "#E10600"),
        ("S2", "SECTOR 2", 0.67, "#00D2BE"),
    ]
    out = []
    for code, label, frac, col in markers:
        idx = int(round(frac * (n - 1))) % (n - 1)
        out.append({
            "code": code,
            "label": label,
            "rel_dist": frac,
            "color": col,
            "x": cx[idx],
            "y": cy[idx],
            "x_inner": ix[idx] if idx < len(ix) else cx[idx],
            "y_inner": iy[idx] if idx < len(iy) else cy[idx],
            "x_outer": ox[idx] if idx < len(ox) else cx[idx],
            "y_outer": oy[idx] if idx < len(oy) else cy[idx],
        })
    return out


def _build_weather_state(base_weather: dict, progress_ratio: float, seed: int) -> dict:
    """Build dynamic frame weather HUD state (Track Temp, Air Temp, Humidity, Wind + Cardinal, Rain)."""
    air_base = float(base_weather.get("temperature_celsius") or 25.5)
    hum_base = float(base_weather.get("humidity_percent") or 50.0)
    wind_base = float(base_weather.get("wind_speed_kmh") or 9.2)
    rain_base = float(base_weather.get("rainfall_mm") or 0.0)
    cond_base = str(base_weather.get("track_condition") or "Dry")

    air_t = round(air_base + 0.6 * math.sin(progress_ratio * math.pi), 1)
    # Track temp is typically +9°C to +14°C above ambient in dry conditions
    track_offset = 4.2 if rain_base > 0 or "wet" in cond_base.lower() else 11.8
    track_t = round(air_t + track_offset + 1.1 * math.sin(progress_ratio * math.pi * 1.5), 1)
    hum = round(max(20.0, min(98.0, hum_base - 1.5 * math.sin(progress_ratio * math.pi))), 0)
    wind_spd = round(max(1.0, wind_base + 1.8 * math.cos(progress_ratio * math.pi * 2 + seed)), 1)
    wind_deg = round((seed * 37 + progress_ratio * 28.0) % 360.0, 0)
    wind_dir = format_wind_direction(wind_deg)

    if rain_base > 0.5 or "wet" in cond_base.lower():
        rain_state = f"WET ({max(0.6, rain_base):.1f} mm)"
    elif "damp" in cond_base.lower():
        rain_state = "DAMP"
    else:
        rain_state = "DRY (0%)"

    return {
        "track_temp": track_t,
        "air_temp": air_t,
        "humidity": int(hum),
        "wind_speed": wind_spd,
        "wind_direction": wind_deg,
        "wind_cardinal": wind_dir,
        "rain_state": rain_state,
        "rainfall_mm": rain_base,
    }


def _compute_tyre_health(tyre_code: float, tyre_life: int) -> float:
    """
    Compute remaining tyre health percentage (0–100%) matching `ui_components.py`
    `LeaderboardComponent` & `TyreDegradationIntegrator`.
    """
    max_life_by_code = {
        1.0: 24,  # Soft
        2.0: 36,  # Medium
        3.0: 48,  # Hard
        4.0: 32,  # Inter
        5.0: 40,  # Wet
    }
    max_life = max_life_by_code.get(float(tyre_code), 34)
    ratio = max(0.08, min(1.0, 1.0 - (max(0, tyre_life - 1) / float(max_life))))
    return round(ratio * 100.0, 1)


def _build_full_race_replay(
    bundle: dict,
    session_type: str = "Race",
) -> Tuple[List[dict], List[dict], dict]:
    """
    Build continuous multi-car frames across the entire Race or Sprint session
    (ported from `F1RaceReplayWindow` in `src/interfaces/race_replay.py`),
    plus `race_events` for `RaceProgressBarComponent` and live Championship overlays.
    """
    info = bundle["session_info"]
    track_geo = bundle["_raw_track_geo"]
    length_m = track_geo["circuit_length_m"]
    drivers = bundle["drivers"]
    lap_times = bundle["lap_times"]
    tyre_strategy = bundle["tyre_strategy"]
    sc_vsc_zones = bundle["sc_vsc_zones"]

    total_laps = info["total_laps"]
    if session_type.lower() == "sprint":
        total_laps = max(15, min(24, int(round(total_laps * 0.33))))

    # Sub-lap steps per lap so the full race scrub bar has ~220–300 smooth frames
    steps_per_lap = 6 if total_laps <= 35 else 4
    frames = []
    race_events = []

    strat_by_code = {s["driver"]: s for s in tyre_strategy}
    sc_map = {}
    for z in sc_vsc_zones:
        for l_num in range(z.get("start_lap", 0), z.get("end_lap", 0) + 1):
            sc_map[l_num] = z.get("status", "SC")
        race_events.append({
            "lap": z.get("start_lap", 1),
            "end_lap": z.get("end_lap", 1),
            "progress_pct": round(((z.get("start_lap", 1) - 1) / max(1, total_laps)) * 100.0, 2),
            "width_pct": round(((z.get("end_lap", 1) - z.get("start_lap", 1) + 1) / max(1, total_laps)) * 100.0, 2),
            "type": z.get("status", "SC"),
            "label": f"{z.get('status', 'SC')} (L{z.get('start_lap')}–L{z.get('end_lap')})",
            "color": "#FF9100" if z.get("status") == "SC" else "#FFD600",
        })

    # Record Pit Stop & Retirement markers for RaceProgressBarComponent
    for d in drivers:
        code = d["code"]
        st = strat_by_code.get(code, {})
        for p_lap in st.get("pit_stops", []):
            if p_lap <= total_laps:
                race_events.append({
                    "lap": p_lap,
                    "progress_pct": round(((p_lap - 0.5) / max(1, total_laps)) * 100.0, 2),
                    "width_pct": 0.6,
                    "type": "PIT",
                    "label": f"{code} Pit Stop (Lap {p_lap})",
                    "color": "#3B82F6",
                })
        laps_done = st.get("laps_completed", total_laps)
        if laps_done < total_laps and str(d.get("status", "")).lower() not in ("finished", ""):
            race_events.append({
                "lap": max(1, laps_done),
                "progress_pct": round((laps_done / max(1, total_laps)) * 100.0, 2),
                "width_pct": 0.8,
                "type": "OUT",
                "label": f"{code} Retired ({d.get('status', 'OUT')}) L{laps_done}",
                "color": "#FF1744",
            })

    elapsed_race_s = 0.0
    prev_order: Dict[str, int] = {d["code"]: idx + 1 for idx, d in enumerate(drivers)}
    seed_val = int(info.get("season", 2024)) + int(info.get("round_number", 1))
    frame_idx = 0

    for lap_n in range(1, total_laps + 1):
        # Determine leader lap duration
        leader_code = drivers[0]["code"] if drivers else "VER"
        leader_laps = lap_times.get(leader_code, [])
        leader_lap_entry = leader_laps[min(len(leader_laps) - 1, lap_n - 1)] if leader_laps else {"time_s": 82.0}
        lap_dur_s = leader_lap_entry.get("time_s", 82.0) or 82.0

        # Pre-fetch primary telemetry profile for realistic corner speeds
        ref_samples = _get_or_build_driver_lap_telemetry(bundle, leader_code, min(lap_n, len(leader_laps) or 1))
        n_ref = len(ref_samples)

        for step_i in range(steps_per_lap):
            sub_frac = round(step_i / float(steps_per_lap), 4)
            step_dt = lap_dur_s / float(steps_per_lap)
            progress_ratio = ((lap_n - 1) + sub_frac) / float(max(1, total_laps))

            # Determine track status
            if lap_n == total_laps and step_i == steps_per_lap - 1:
                track_status = "CHEQUERED"
            elif lap_n in sc_map:
                track_status = sc_map[lap_n]
            else:
                track_status = "GREEN"

            drivers_state = {}
            raw_progress_list = []

            for d_idx, d in enumerate(drivers):
                code = d["code"]
                d_laps = lap_times.get(code, [])
                st = strat_by_code.get(code, {})
                laps_completed = st.get("laps_completed", total_laps)
                is_retired = (lap_n > laps_completed) and (str(d.get("status", "")).lower() not in ("finished", ""))

                if is_retired or not d_laps:
                    x0, y0 = interpolate_track_xy(track_geo, 0.0)
                    last_e = d_laps[-1] if d_laps else {}
                    t_val = last_e.get("tyre", 2.0)
                    t_col, t_abbr, t_name = get_tyre_meta(t_val)
                    drivers_state[code] = {
                        "x": x0,
                        "y": y0,
                        "dist": 0.0,
                        "rel_dist": 1.0,  # ui_components.py uses rel_dist == 1 or is_out for OUT
                        "lap": len(d_laps),
                        "position": 20,
                        "pos_change": 0,
                        "gap_to_leader": None,
                        "interval": None,
                        "speed": 0.0,
                        "gear": 0,
                        "throttle": 0.0,
                        "brake": 0.0,
                        "drs": 0,
                        "tyre": t_val,
                        "compound": t_name,
                        "compound_abbr": t_abbr,
                        "compound_color": t_col,
                        "tyre_life": last_e.get("stint_age", 1),
                        "tyre_health": 0.0,
                        "in_pit": False,
                        "is_out": True,
                        "status": "OUT",
                    }
                    raw_progress_list.append((code, -1000.0 - d_idx))
                    continue

                e_curr = d_laps[min(len(d_laps) - 1, lap_n - 1)]
                e_prev = d_laps[min(len(d_laps) - 1, max(0, lap_n - 2))] if lap_n > 1 else None
                gap_curr = e_curr.get("gap_to_leader_s", 0.0) or 0.0
                gap_prev = (e_prev.get("gap_to_leader_s", 0.0) if e_prev else d_idx * 0.35) or 0.0
                interp_gap_s = round(gap_prev + (gap_curr - gap_prev) * sub_frac, 3)

                # Car fractional track position offset behind leader by gap
                car_total_laps = (lap_n - 1) + sub_frac - (interp_gap_s / max(60.0, lap_dur_s))
                car_lap = max(1, int(math.floor(car_total_laps)) + 1)
                car_rel = car_total_laps % 1.0
                cx, cy = interpolate_track_xy(track_geo, car_rel)

                s_idx = min(n_ref - 1, int(car_rel * (n_ref - 1)))
                ref_pt = ref_samples[s_idx] if ref_samples else {"speed": 210.0, "gear": 6, "throttle": 80.0, "brake": 0.0, "drs": 0}

                in_pit = bool((e_curr.get("is_pit_in") and car_rel > 0.88) or (e_curr.get("is_pit_out") and car_rel < 0.12))
                spd = 80.0 if in_pit else round(max(75.0, ref_pt["speed"] - d_idx * 0.35), 1)
                t_val = e_curr.get("tyre", 2.0)
                t_col, t_abbr, t_name = get_tyre_meta(t_val)
                t_life = int(e_curr.get("stint_age", 1))
                t_health = _compute_tyre_health(t_val, t_life)

                progress_m = round(car_total_laps * length_m, 2)
                raw_progress_list.append((code, progress_m))

                drivers_state[code] = {
                    "x": cx,
                    "y": cy,
                    "dist": round(car_rel * length_m, 2),
                    "rel_dist": round(car_rel, 4),
                    "progress_m": progress_m,
                    "lap": car_lap,
                    "position": e_curr.get("position", d_idx + 1),
                    "pos_change": 0,
                    "gap_to_leader": max(0.0, interp_gap_s),
                    "interval": 0.0,
                    "speed": spd,
                    "gear": 2 if in_pit else ref_pt["gear"],
                    "throttle": 35.0 if in_pit else ref_pt["throttle"],
                    "brake": 0.0 if in_pit else ref_pt["brake"],
                    "drs": 1 if (not in_pit and ref_pt["drs"] and interp_gap_s > 0.15 and interp_gap_s <= 1.2 and track_status == "GREEN") else 0,
                    "tyre": t_val,
                    "compound": t_name,
                    "compound_abbr": t_abbr,
                    "compound_color": t_col,
                    "tyre_life": t_life,
                    "tyre_health": t_health,
                    "in_pit": in_pit,
                    "is_out": False,
                    "status": "PIT" if in_pit else "RUNNING",
                }

            # Sort drivers by progress_m to assign exact live positions & neighbor intervals
            raw_progress_list.sort(key=lambda item: item[1], reverse=True)
            leader_prog = raw_progress_list[0][1] if raw_progress_list else 0.0
            leader_rel_dist = drivers_state[raw_progress_list[0][0]]["rel_dist"] if raw_progress_list else sub_frac

            for rank_i, (code, prog_m) in enumerate(raw_progress_list):
                pos_num = rank_i + 1
                st_obj = drivers_state[code]
                old_pos = prev_order.get(code, pos_num)
                st_obj["position"] = pos_num
                st_obj["pos_change"] = old_pos - pos_num
                if st_obj["is_out"]:
                    st_obj["gap_to_leader"] = None
                    st_obj["interval"] = None
                elif rank_i == 0:
                    st_obj["gap_to_leader"] = 0.0
                    st_obj["interval"] = 0.0
                else:
                    prev_code, prev_prog = raw_progress_list[rank_i - 1]
                    gap_l = max(0.0, (leader_prog - prog_m) / 58.5)
                    gap_i = max(0.0, (prev_prog - prog_m) / 58.5)
                    st_obj["gap_to_leader"] = round(gap_l, 2)
                    st_obj["interval"] = round(gap_i, 2)
                    _ = prev_code

            if step_i == steps_per_lap - 1:
                for code, st_obj in drivers_state.items():
                    prev_order[code] = st_obj["position"]

            sc_state = compute_safety_car_state(
                lap_number=lap_n,
                rel_dist=sub_frac,
                leader_rel_dist=leader_rel_dist,
                sc_vsc_zones=sc_vsc_zones,
                track_geo=track_geo,
            )

            hrs = int(elapsed_race_s // 3600)
            mins = int((elapsed_race_s % 3600) // 60)
            secs = int(elapsed_race_s % 60)
            time_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"

            frames.append({
                "frame_index": frame_idx,
                "t": round(elapsed_race_s, 2),
                "time_str": time_str,
                "lap": lap_n,
                "total_laps": total_laps,
                "progress_pct": round(progress_ratio * 100.0, 2),
                "track_status": track_status,
                "weather": _build_weather_state(info.get("weather", {}), progress_ratio, seed_val),
                "safety_car": sc_state,
                "drivers": drivers_state,
            })

            elapsed_race_s += step_dt
            frame_idx += 1

    # Championship overlay data (Drivers & Constructors live points)
    pts_table = SPRINT_POINTS_TABLE if session_type.lower() == "sprint" else F1_POINTS_TABLE
    drv_champ = []
    team_totals: Dict[str, dict] = {}
    round_num = int(info.get("round_number", 1))

    for idx, d in enumerate(drivers):
        code = d["code"]
        base_pts = max(0, int((20 - idx) * 1.4 * max(0, round_num - 1)))
        live_gain = pts_table[idx] if idx < len(pts_table) else 0
        drv_champ.append({
            "position": idx + 1,
            "code": code,
            "name": d["name"],
            "team": d["team"],
            "color": d["color"],
            "base_points": base_pts,
            "live_gain": live_gain,
            "live_points": base_pts + live_gain,
        })
        t_name = d["team"]
        if t_name not in team_totals:
            team_totals[t_name] = {
                "team": t_name,
                "color": d["color"],
                "base_points": 0,
                "live_gain": 0,
                "live_points": 0,
            }
        team_totals[t_name]["base_points"] += base_pts
        team_totals[t_name]["live_gain"] += live_gain
        team_totals[t_name]["live_points"] += (base_pts + live_gain)

    drv_champ.sort(key=lambda x: x["live_points"], reverse=True)
    for i, row in enumerate(drv_champ):
        row["position"] = i + 1

    con_champ = sorted(team_totals.values(), key=lambda x: x["live_points"], reverse=True)
    for i, row in enumerate(con_champ):
        row["position"] = i + 1

    championship_overlay = {
        "drivers": drv_champ[:12],
        "constructors": con_champ[:10],
    }

    return frames, race_events, championship_overlay


def _build_qualifying_and_practice_data(bundle: dict) -> Tuple[dict, dict]:
    """
    Build Qualifying (`Q1`, `Q2`, `Q3`) and Practice (`FP1`, `FP2`, `FP3`)
    session data, leaderboards, and flying-lap telemetry traces matching
    `src/interfaces/qualifying.py` and `src/interfaces/practice.py`.
    """
    drivers = bundle["drivers"]
    lap_times = bundle["lap_times"]
    track_geo = bundle["_raw_track_geo"]

    # Base pole time derived from fastest race lap minus ~2.8s low-fuel qualifying delta
    fastest_race_s = 80.5
    for laps in lap_times.values():
        for e in laps:
            if e.get("time_s") and e["time_s"] < fastest_race_s:
                fastest_race_s = e["time_s"]
    pole_base_s = max(64.5, round(fastest_race_s - 2.85, 3))

    quali_results = []
    quali_telemetry = {}

    for idx, d in enumerate(drivers):
        code = d["code"]
        seed_d = sum(ord(c) for c in code)
        q1_s = round(pole_base_s + 0.65 + idx * 0.14 + 0.04 * math.sin(seed_d), 3)
        q2_s = round(pole_base_s + 0.28 + idx * 0.12 + 0.03 * math.cos(seed_d), 3) if idx < 15 else None
        q3_s = round(pole_base_s + idx * 0.095 + 0.02 * math.sin(seed_d * 2), 3) if idx < 10 else None

        best_s = q3_s or q2_s or q1_s
        gap_s = round(best_s - pole_base_s, 3) if idx > 0 else 0.0
        eliminated = "Q3" if idx < 10 else ("Q2" if idx < 15 else "Q1")

        quali_results.append({
            "pos": idx + 1,
            "position": idx + 1,
            "code": code,
            "driver_name": d["name"],
            "full_name": d["name"],
            "team": d["team"],
            "color": d["color"],
            "Q1_s": q1_s,
            "Q1": _format_laptime(q1_s),
            "Q2_s": q2_s,
            "Q2": _format_laptime(q2_s) if q2_s else "—",
            "Q3_s": q3_s,
            "Q3": _format_laptime(q3_s) if q3_s else "—",
            "best_s": best_s,
            "time": _format_laptime(best_s),
            "gap_s": gap_s,
            "gap_str": "POLE" if idx == 0 else f"+{gap_s:.3f}s",
            "tyre": 1.0,  # Qualifying flying laps on Soft
            "compound": "Soft",
            "compound_abbr": "S",
            "compound_color": "#E8002D",
            "eliminated_in": eliminated,
            "s1_s": round(best_s * 0.288, 3),
            "s2_s": round(best_s * 0.382, 3),
            "s3_s": round(best_s - round(best_s * 0.288, 3) - round(best_s * 0.382, 3), 3),
        })

        # Synthesize flying-lap telemetry for Q1, Q2, Q3
        quali_telemetry[code] = {}
        for seg_name, seg_time in (("Q1", q1_s), ("Q2", q2_s), ("Q3", q3_s)):
            if seg_time is not None:
                quali_telemetry[code][seg_name] = synthesize_lap_telemetry(
                    driver_code=code,
                    lap_number=1,
                    lap_time_s=seg_time,
                    tyre_val=1.0,
                    track_geo=track_geo,
                    position=idx + 1,
                    num_points=80,
                )

    # Practice sessions (FP1, FP2, FP3)
    practice_sessions = {}
    for fp_idx, fp_name in enumerate(("FP1", "FP2", "FP3"), start=1):
        fp_offset = 1.45 - fp_idx * 0.35
        fp_rows = []
        for idx, d in enumerate(drivers):
            code = d["code"]
            seed_fp = sum(ord(c) for c in code) + fp_idx * 13
            # Shuffle order slightly in practice sessions
            perf_rank = (idx + ((seed_fp % 5) - 2)) % max(1, len(drivers))
            best_s = round(pole_base_s + fp_offset + max(0, perf_rank) * 0.13 + (seed_fp % 7) * 0.02, 3)
            tyre_choice = 1.0 if (idx + fp_idx) % 2 == 0 else (2.0 if (idx + fp_idx) % 3 == 0 else 3.0)
            t_col, t_abbr, t_name = get_tyre_meta(tyre_choice)
            laps_run = 18 + (seed_fp % 14)
            fp_rows.append({
                "code": code,
                "driver_name": d["name"],
                "full_name": d["name"],
                "team": d["team"],
                "color": d["color"],
                "best_s": best_s,
                "time": _format_laptime(best_s),
                "tyre": tyre_choice,
                "compound": t_name,
                "compound_abbr": t_abbr,
                "compound_color": t_col,
                "tyre_life": 4 + (seed_fp % 9),
                "laps_run": laps_run,
            })

        fp_rows.sort(key=lambda r: r["best_s"])
        p1_s = fp_rows[0]["best_s"] if fp_rows else pole_base_s
        for rank_i, r in enumerate(fp_rows):
            r["pos"] = rank_i + 1
            r["position"] = rank_i + 1
            r["gap_s"] = round(r["best_s"] - p1_s, 3)
            r["gap_str"] = "FASTEST" if rank_i == 0 else f"+{r['gap_s']:.3f}s"

        practice_sessions[fp_name] = {
            "session_type": fp_name,
            "results": fp_rows,
        }

    qualifying_data = {
        "pole_driver": quali_results[0]["code"] if quali_results else "VER",
        "pole_time": quali_results[0]["time"] if quali_results else "1:18.000",
        "results": quali_results,
        "telemetry": quali_telemetry,
    }

    return qualifying_data, practice_sessions


def get_track_replay_session(
    season: int,
    round_number: int = 1,
    session_type: str = "Race",
    segment: str = "Q3",
    db_conn_fn=None,
) -> dict:
    """
    Build or retrieve the complete 2D Track Replay & Interactive Controls bundle
    for `Race`, `Sprint`, `Qualifying (Q1/Q2/Q3)`, or `Practice (FP1/FP2/FP3)`
    for any season (1950–2026) and round.
    """
    season = int(season or 2024)
    round_number = max(1, int(round_number or 1))
    session_type_clean = (session_type or "Race").strip()

    base_key = f"{season}_{round_number}_0"
    if base_key not in _SESSION_CACHE:
        _SESSION_CACHE[base_key] = _build_base_session_bundle(
            season=season,
            round_number=round_number,
            race_id=None,
            db_conn_fn=db_conn_fn,
        )
    bundle = _SESSION_CACHE[base_key]

    replay_key = f"{season}_{round_number}_{session_type_clean.lower()}"
    if replay_key not in _REPLAY_CACHE:
        race_frames, race_events, champ_overlay = _build_full_race_replay(
            bundle=bundle,
            session_type=session_type_clean,
        )
        quali_data, practice_data = _build_qualifying_and_practice_data(bundle)
        sector_markers = _compute_sector_markers(bundle["track_geometry"])

        _REPLAY_CACHE[replay_key] = {
            "session_info": {
                **bundle["session_info"],
                "session_type": session_type_clean,
                "segment": segment,
                "circuit_rotation_deg": 0.0,
            },
            "track_geometry": {
                **bundle["track_geometry"],
                "sector_markers": sector_markers,
            },
            "drivers": bundle["drivers"],
            "race_frames": race_frames,
            "race_events": race_events,
            "championship_overlay": champ_overlay,
            "qualifying": quali_data,
            "practice": practice_data,
            "race_control": bundle["race_control"],
        }

    cached = _REPLAY_CACHE[replay_key]
    cached["session_info"]["segment"] = segment
    return cached

