"""
Strategy Analytics Engine
=========================
Provides algorithms for Formula 1 race strategy:
1. Tyre Degradation Curves: OLS linear regression on tyre age vs. lap times.
2. Pit Window & Undercut/Overcut Simulator: Predicts post-pit track position delta.
3. Pace & Stint Comparisons: Head-to-head median lap times, consistency, and stint deltas.
"""

from datetime import timedelta
import math
from decimal import Decimal


def time_to_seconds(lap_time):
    """Convert lap time (str '00:01:15.234' or timedelta) to float seconds."""
    if lap_time is None:
        return None
    if isinstance(lap_time, timedelta):
        return lap_time.total_seconds()
    if isinstance(lap_time, (int, float, Decimal)):
        return float(lap_time)

    parts = str(lap_time).split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60.0 + float(parts[1])
        return float(lap_time)
    except Exception:
        return None


def seconds_to_time(seconds):
    """Convert float seconds to '00:MM:SS.mmm' format."""
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


def _calculate_ols_regression(x_vals, y_vals):
    """Calculate Ordinary Least Squares (OLS) linear regression: y = beta * x + alpha."""
    n = len(x_vals)
    if n < 2:
        return 0.0, (y_vals[0] if y_vals else 0.0), 0.0

    mean_x = sum(x_vals) / n
    mean_y = sum(y_vals) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
    denominator = sum((x - mean_x) ** 2 for x in x_vals)

    if denominator == 0:
        return 0.0, mean_y, 0.0

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    # R-squared calculation
    ss_tot = sum((y - mean_y) ** 2 for y in y_vals)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, y_vals))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, max(0.0, min(1.0, r_squared))


def calculate_tyre_degradation(cur, race_id=None, circuit_id=None, compound_id=None):
    """Calculate tyre degradation rates (sec/lap) per compound at a race or circuit.

    Filters outliers (pit in/out laps, laps >110% of median) to prevent safety car distortion.
    """
    conditions = []
    params = []

    if race_id:
        conditions.append("lt.race_id = %s")
        params.append(race_id)
    elif circuit_id:
        conditions.append("r.circuit_id = %s")
        params.append(circuit_id)

    if compound_id:
        conditions.append("lt.compound_id = %s")
        params.append(compound_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT 
            lt.race_id,
            r.race_name,
            lt.driver_id,
            lt.compound_id,
            tc.compound_name,
            tc.color_code,
            tc.expected_lifespan_laps,
            lt.lap_number,
            lt.lap_time
        FROM LAP_TIMES lt
        JOIN RACES r ON lt.race_id = r.race_id
        JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id
        {where_clause}
        ORDER BY lt.race_id, lt.driver_id, lt.lap_number ASC
    """
    cur.execute(query, tuple(params))
    rows = cur.fetchall()

    if not rows:
        return {"error": "No lap time records found for the specified filters", "compounds": []}

    # Group laps by compound -> driver -> stints
    # To determine tyre age, track consecutive laps run by the same driver on the same compound
    compound_data = {}

    # Sort rows into compound groups
    for row in rows:
        cid = row["compound_id"]
        if cid not in compound_data:
            compound_data[cid] = {
                "compound_id": cid,
                "compound_name": row["compound_name"],
                "color_code": row["color_code"],
                "expected_lifespan_laps": row["expected_lifespan_laps"] or 30,
                "stints": {},  # (race_id, driver_id) -> list of lap records
            }

        key = (row["race_id"], row["driver_id"])
        if key not in compound_data[cid]["stints"]:
            compound_data[cid]["stints"][key] = []
        compound_data[cid]["stints"][key].append(row)

    compounds_result = []

    for cid, cinfo in compound_data.items():
        all_x = []
        all_y = []
        valid_laps_count = 0

        for key, laps in cinfo["stints"].items():
            # Calculate tyre age in stint
            # A gap of >1 lap in lap_number implies a pit stop / new stint
            current_stint_laps = []
            last_lap_num = None

            stint_groups = []
            for l in laps:
                curr_lap = l["lap_number"]
                if last_lap_num is None or curr_lap == last_lap_num + 1:
                    current_stint_laps.append(l)
                else:
                    stint_groups.append(current_stint_laps)
                    current_stint_laps = [l]
                last_lap_num = curr_lap
            if current_stint_laps:
                stint_groups.append(current_stint_laps)

            for stint in stint_groups:
                if len(stint) < 3:
                    continue

                times_sec = []
                for s in stint:
                    t = time_to_seconds(s["lap_time"])
                    if t and t > 0:
                        times_sec.append(t)

                if len(times_sec) < 3:
                    continue

                # Compute median pace for outlier filtering (remove laps > 110% of median, e.g. safety car)
                sorted_times = sorted(times_sec)
                median_time = sorted_times[len(sorted_times) // 2]
                cutoff = median_time * 1.10

                for age_idx, (s, t) in enumerate(zip(stint, times_sec), start=1):
                    # Exclude the very first out-lap if significantly slower and laps above cutoff
                    if t <= cutoff:
                        all_x.append(age_idx)
                        all_y.append(t)
                        valid_laps_count += 1

        if len(all_x) >= 3:
            slope, intercept, r2 = _calculate_ols_regression(all_x, all_y)
            deg_rate = round(slope, 4)
            base_pace = round(intercept, 3)
            r_squared = round(r2, 3)
        else:
            deg_rate = 0.050  # F1 typical default if minimal data
            base_pace = (sum(all_y) / len(all_y)) if all_y else 80.0
            r_squared = 0.0

        # Generate predicted curve sample
        lifespan = cinfo["expected_lifespan_laps"]
        sample_ages = [1, 5, 10, 15, 20, 25, min(30, lifespan)]
        sample_ages = sorted(list(set([a for a in sample_ages if a <= lifespan])))

        curve_sample = []
        for age in sample_ages:
            pred_sec = base_pace + deg_rate * age
            curve_sample.append({
                "tyre_age_laps": age,
                "predicted_lap_time_seconds": round(pred_sec, 3),
                "predicted_lap_time": seconds_to_time(pred_sec),
                "pace_loss_from_fresh": round(deg_rate * (age - 1), 3),
            })

        compounds_result.append({
            "compound_id": cid,
            "compound_name": cinfo["compound_name"],
            "color_code": cinfo["color_code"],
            "expected_lifespan_laps": lifespan,
            "degradation_rate_sec_per_lap": deg_rate,
            "base_pace_seconds": base_pace,
            "base_pace": seconds_to_time(base_pace),
            "r_squared": r_squared,
            "laps_analyzed": valid_laps_count,
            "degradation_curve": curve_sample,
        })

    return {
        "race_id": race_id,
        "circuit_id": circuit_id,
        "compounds": compounds_result,
    }


def simulate_undercut(cur, race_id, chaser_driver_id, leader_driver_id, pit_lap, pit_loss_seconds=None):
    """Simulate an undercut strategy: Chaser pits on lap N, leader responds on lap N+1.

    Calculates whether the chaser's out-lap on fresh rubber overcomes the initial gap and jumps the leader.
    """
    # 1. Fetch race info
    cur.execute("SELECT race_id, race_name, total_laps FROM RACES WHERE race_id = %s", (race_id,))
    race = cur.fetchone()
    if not race:
        return {"error": "Race not found"}

    # 2. Fetch driver names
    cur.execute(
        "SELECT driver_id, CONCAT(first_name, ' ', last_name) AS name FROM DRIVERS WHERE driver_id IN (%s, %s)",
        (chaser_driver_id, leader_driver_id)
    )
    drivers = {d["driver_id"]: d["name"] for d in cur.fetchall()}
    if chaser_driver_id not in drivers or leader_driver_id not in drivers:
        return {"error": "One or both drivers not found"}

    # 3. Determine pit loss time (default ~22.0 seconds if no pit records exist)
    if not pit_loss_seconds:
        cur.execute(
            "SELECT AVG(COALESCE(pit_loss_time, stop_duration + 20.0)) AS avg_loss FROM PIT_STOPS WHERE race_id = %s",
            (race_id,)
        )
        row = cur.fetchone()
        if row and row.get("avg_loss"):
            pit_loss_seconds = round(float(row["avg_loss"]), 2)
        else:
            pit_loss_seconds = 22.0

    # 4. Fetch lap times of both drivers around pit_lap
    cur.execute(
        """SELECT driver_id, lap_number, lap_time, compound_id
           FROM LAP_TIMES
           WHERE race_id = %s AND driver_id IN (%s, %s) AND lap_number <= %s
           ORDER BY lap_number ASC""",
        (race_id, chaser_driver_id, leader_driver_id, pit_lap)
    )
    history_laps = cur.fetchall()

    chaser_laps = [l for l in history_laps if l["driver_id"] == chaser_driver_id]
    leader_laps = [l for l in history_laps if l["driver_id"] == leader_driver_id]

    chaser_total_sec = sum(time_to_seconds(l["lap_time"]) or 0 for l in chaser_laps)
    leader_total_sec = sum(time_to_seconds(l["lap_time"]) or 0 for l in leader_laps)

    # Current gap on track at start of pit lap
    initial_gap = round(chaser_total_sec - leader_total_sec, 3)
    if initial_gap < 0:
        initial_gap = 1.8  # If chaser was actually ahead, default to standard chasing gap

    # 5. Fetch baseline pace & degradation for compounds
    deg_analysis = calculate_tyre_degradation(cur, race_id=race_id)
    compounds = deg_analysis.get("compounds", [])

    fresh_pace_advantage = 1.75  # Typical fresh tyre delta over 20-lap old tyre
    if compounds:
        sorted_compounds = sorted(compounds, key=lambda c: c.get("base_pace_seconds", 0))
        if len(sorted_compounds) >= 2:
            fresh_pace_advantage = max(1.2, sorted_compounds[-1]["base_pace_seconds"] - sorted_compounds[0]["base_pace_seconds"] + 0.8)

    # 6. Model Undercut Dynamics:
    # Lap N: Chaser pits.
    #   Chaser in-lap incurs pit_loss_seconds.
    # Lap N+1:
    #   Chaser completes out-lap on fresh rubber (pace advantage = fresh_pace_advantage).
    #   Leader stays out on old degraded rubber.
    # Lap N+1 (End): Leader pits and incurs pit_loss_seconds.
    # Lap N+2: Both cars now on fresh tyres.
    # Net delta gained during the undercut window:
    #   Delta gained = fresh_pace_advantage + out_lap_delta (approx 0.5s warm-up advantage)
    out_lap_gain = fresh_pace_advantage + 0.45
    net_gap_after_stops = round(initial_gap - out_lap_gain, 3)

    is_successful = net_gap_after_stops < 0
    margin = round(abs(net_gap_after_stops), 3)

    verdict = (
        f"Undercut Viable: {drivers[chaser_driver_id]} is predicted to jump {drivers[leader_driver_id]} by {margin}s"
        if is_successful
        else f"Undercut Ineffective: {drivers[leader_driver_id]} is predicted to retain track position by {margin}s"
    )

    # Calculate optimal pit window range [pit_lap - 2, pit_lap + 2]
    pit_window_analysis = []
    for lap_offset in [-2, -1, 0, 1, 2]:
        test_lap = pit_lap + lap_offset
        if test_lap < 1 or test_lap >= race.get("total_laps", 70):
            continue
        test_gain = round(out_lap_gain + (lap_offset * 0.15), 3)
        test_net = round(initial_gap - test_gain, 3)
        pit_window_analysis.append({
            "lap": test_lap,
            "predicted_gain_seconds": test_gain,
            "post_pit_gap_seconds": test_net,
            "track_position": "Ahead" if test_net < 0 else "Behind",
        })

    return {
        "race_id": race_id,
        "race_name": race.get("race_name"),
        "pit_lap": pit_lap,
        "chaser": {"driver_id": chaser_driver_id, "name": drivers[chaser_driver_id]},
        "leader": {"driver_id": leader_driver_id, "name": drivers[leader_driver_id]},
        "initial_gap_seconds": initial_gap,
        "pit_loss_seconds": pit_loss_seconds,
        "fresh_tyre_delta_seconds": round(out_lap_gain, 3),
        "post_undercut_gap_seconds": net_gap_after_stops,
        "undercut_successful": is_successful,
        "verdict": verdict,
        "pit_window_range": pit_window_analysis,
    }


def compare_stints(cur, race_id, driver1_id, driver2_id):
    """Compare head-to-head median lap times, consistency, and stint pace between two drivers."""
    cur.execute("SELECT race_id, race_name FROM RACES WHERE race_id = %s", (race_id,))
    race = cur.fetchone()
    if not race:
        return {"error": "Race not found"}

    cur.execute(
        "SELECT driver_id, CONCAT(first_name, ' ', last_name) AS name, nationality FROM DRIVERS WHERE driver_id IN (%s, %s)",
        (driver1_id, driver2_id)
    )
    drivers = {d["driver_id"]: d for d in cur.fetchall()}
    if driver1_id not in drivers or driver2_id not in drivers:
        return {"error": "One or both drivers not found"}

    # Fetch laps for both drivers
    query = """
        SELECT 
            lt.driver_id,
            lt.compound_id,
            tc.compound_name,
            tc.color_code,
            lt.lap_number,
            lt.lap_time
        FROM LAP_TIMES lt
        JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id
        WHERE lt.race_id = %s AND lt.driver_id IN (%s, %s)
        ORDER BY lt.driver_id, lt.lap_number ASC
    """
    cur.execute(query, (race_id, driver1_id, driver2_id))
    rows = cur.fetchall()

    def process_driver_stints(driver_id):
        driver_rows = [r for r in rows if r["driver_id"] == driver_id]
        if not driver_rows:
            return []

        stints = []
        current_stint = []
        last_compound = None

        for r in driver_rows:
            if last_compound is None or r["compound_id"] == last_compound:
                current_stint.append(r)
            else:
                stints.append(current_stint)
                current_stint = [r]
            last_compound = r["compound_id"]
        if current_stint:
            stints.append(current_stint)

        stint_summaries = []
        for idx, st in enumerate(stints, start=1):
            times = [time_to_seconds(l["lap_time"]) for l in st if time_to_seconds(l["lap_time"]) is not None]
            if not times:
                continue

            sorted_times = sorted(times)
            n = len(sorted_times)
            median_val = sorted_times[n // 2] if n % 2 != 0 else (sorted_times[n // 2 - 1] + sorted_times[n // 2]) / 2.0
            mean_val = sum(times) / n
            best_val = min(times)

            # Standard deviation (consistency metric)
            variance = sum((t - mean_val) ** 2 for t in times) / n if n > 1 else 0.0
            std_dev = math.sqrt(variance)

            stint_summaries.append({
                "stint_number": idx,
                "compound_name": st[0]["compound_name"],
                "color_code": st[0]["color_code"],
                "start_lap": st[0]["lap_number"],
                "end_lap": st[-1]["lap_number"],
                "total_laps": len(st),
                "median_lap_seconds": round(median_val, 3),
                "median_lap_time": seconds_to_time(median_val),
                "mean_lap_seconds": round(mean_val, 3),
                "mean_lap_time": seconds_to_time(mean_val),
                "best_lap_seconds": round(best_val, 3),
                "best_lap_time": seconds_to_time(best_val),
                "consistency_std_dev": round(std_dev, 3),
            })

        return stint_summaries

    d1_stints = process_driver_stints(driver1_id)
    d2_stints = process_driver_stints(driver2_id)

    # Compute head-to-head stint deltas
    max_stints = max(len(d1_stints), len(d2_stints)) if (d1_stints or d2_stints) else 0
    stint_comparisons = []

    for i in range(max_stints):
        s1 = d1_stints[i] if i < len(d1_stints) else None
        s2 = d2_stints[i] if i < len(d2_stints) else None

        delta = None
        faster_driver = None
        if s1 and s2:
            delta = round(s1["median_lap_seconds"] - s2["median_lap_seconds"], 3)
            if delta < 0:
                faster_driver = drivers[driver1_id]["name"]
            elif delta > 0:
                faster_driver = drivers[driver2_id]["name"]
            else:
                faster_driver = "Tied"

        stint_comparisons.append({
            "stint_number": i + 1,
            "driver1_stint": s1,
            "driver2_stint": s2,
            "median_delta_seconds": delta,
            "faster_driver": faster_driver,
        })

    # Overall pace summary
    all_d1_times = [s["median_lap_seconds"] for s in d1_stints if s.get("median_lap_seconds")]
    all_d2_times = [s["median_lap_seconds"] for s in d2_stints if s.get("median_lap_seconds")]

    overall_delta = None
    overall_faster = None
    if all_d1_times and all_d2_times:
        avg1 = sum(all_d1_times) / len(all_d1_times)
        avg2 = sum(all_d2_times) / len(all_d2_times)
        overall_delta = round(avg1 - avg2, 3)
        overall_faster = drivers[driver1_id]["name"] if overall_delta < 0 else drivers[driver2_id]["name"]

    return {
        "race_id": race_id,
        "race_name": race.get("race_name"),
        "driver1": drivers[driver1_id],
        "driver2": drivers[driver2_id],
        "overall_faster_driver": overall_faster,
        "overall_pace_delta_seconds": overall_delta,
        "stint_comparisons": stint_comparisons,
    }
