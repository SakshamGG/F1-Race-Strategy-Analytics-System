import unittest

import app as flask_app
from services.pitwall_service import (
    BayesianTyreDegradationModel,
    build_circuit_geometry,
    classify_sector_statuses,
    compute_safety_car_state,
    format_wind_direction,
    interpolate_track_xy,
    synthesize_lap_telemetry,
)


class PitWallServiceAndEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.app.test_client()

    def test_sector_classification_purple_and_green(self):
        all_laps = {
            "VER": [
                {"lap": 1, "time_s": 92.0, "sector1_s": 29.5, "sector2_s": 39.5, "sector3_s": 23.0, "tyre": 1.0},
                {"lap": 2, "time_s": 90.5, "sector1_s": 29.0, "sector2_s": 39.0, "sector3_s": 22.5, "tyre": 1.0},
            ],
            "LEC": [
                {"lap": 1, "time_s": 91.2, "sector1_s": 28.8, "sector2_s": 39.4, "sector3_s": 23.0, "tyre": 1.0},
                {"lap": 2, "time_s": 90.8, "sector1_s": 29.1, "sector2_s": 38.9, "sector3_s": 22.8, "tyre": 1.0},
            ],
        }
        res = classify_sector_statuses("VER", all_laps, up_to_lap=2)
        self.assertEqual(res["driver"], "VER")
        self.assertEqual(len(res["laps"]), 2)
        # On Lap 2, VER's S1 (29.0) is personal best because LEC holds session best (28.8),
        # while VER's S3 (22.5) is session best
        lap2 = res["laps"][1]
        self.assertEqual(lap2["sector1_status"], "personal_best")
        self.assertEqual(lap2["sector3_status"], "session_best")
        self.assertAlmostEqual(res["theoretical_best_s"], 90.5, places=3)

    def test_bayesian_tyre_degradation_model(self):
        model = BayesianTyreDegradationModel(track_condition="Dry")
        all_laps = {
            "VER": [
                {"lap": i, "time_s": 90.0 + i * 0.06, "tyre": 1.0, "is_pit_in": False, "is_pit_out": False, "is_sc": False}
                for i in range(1, 11)
            ]
        }
        out = model.fit_and_predict(all_laps, total_laps=20)
        self.assertIn("VER", out["driver_curves"])
        curve = out["driver_curves"]["VER"]
        self.assertEqual(len(curve), 10)
        self.assertTrue(len(out["profiles"]) >= 3)

    def test_circuit_geometry_and_telemetry_synthesis(self):
        geo = build_circuit_geometry("Circuit de Monaco")
        self.assertEqual(geo["circuit_length_m"], 3337)
        x, y = interpolate_track_xy(geo, 0.5)
        self.assertIsInstance(x, float)
        self.assertIsInstance(y, float)

        samples = synthesize_lap_telemetry("VER", 5, 74.5, 1.0, geo, position=1, num_points=40)
        self.assertEqual(len(samples), 40)
        for key in ("speed", "gear", "throttle", "brake", "drs", "dist", "rel_dist", "tyre", "x", "y"):
            self.assertIn(key, samples[0])

        sc = compute_safety_car_state(
            lap_number=14,
            rel_dist=0.5,
            leader_rel_dist=0.4,
            sc_vsc_zones=[{"start_lap": 14, "end_lap": 16, "status": "SC"}],
            track_geo=geo,
        )
        self.assertTrue(sc["active"])
        self.assertEqual(sc["phase"], "on_track")

    def test_pitwall_endpoints_universal_seasons(self):
        # Catalog endpoint (1950 historical season)
        r_cat = self.client.get("/api/pitwall/catalog?season=1950")
        self.assertEqual(r_cat.status_code, 200)
        cat_data = r_cat.get_json()
        self.assertEqual(cat_data["season"], 1950)
        self.assertTrue(len(cat_data["races"]) > 0)
        self.assertTrue(len(cat_data["drivers"]) > 0)

        # Full Pit Wall Session endpoint (2024 modern season)
        r_sess = self.client.get("/api/pitwall/session?season=2024&round=1&lap=5")
        self.assertEqual(r_sess.status_code, 200)
        s_data = r_sess.get_json()
        for key in (
            "session_info",
            "track_geometry",
            "drivers",
            "selected_driver",
            "tyre_strategy",
            "lap_times",
            "sector_analysis",
            "bayesian_tyre_model",
            "race_control",
            "driver_telemetry",
            "replay_frames",
        ):
            self.assertIn(key, s_data)

        # Fast Telemetry endpoint
        r_tel = self.client.get(f"/api/pitwall/telemetry?season=2024&round=1&driver={s_data['selected_driver']}&lap=3")
        self.assertEqual(r_tel.status_code, 200)
        t_data = r_tel.get_json()
        self.assertEqual(t_data["selected_lap"], 3)
        self.assertTrue(len(t_data["replay_frames"]) > 0)

    def test_track_replay_session_race_quali_practice(self):
        self.assertEqual(format_wind_direction(0), "N")
        self.assertEqual(format_wind_direction(90), "E")
        self.assertEqual(format_wind_direction(225), "SW")

        # 1. Full 2D Race Replay
        r_race = self.client.get("/api/replay/session?season=2024&round=1&session_type=Race")
        self.assertEqual(r_race.status_code, 200)
        race_data = r_race.get_json()
        self.assertEqual(race_data["session_info"]["session_type"], "Race")
        self.assertIn("track_geometry", race_data)
        self.assertIn("sector_markers", race_data["track_geometry"])
        self.assertTrue(len(race_data["drivers"]) >= 15)
        self.assertIn("race_frames", race_data)
        self.assertIn("race_events", race_data)
        self.assertIn("championship_overlay", race_data)
        frames = race_data["race_frames"]
        self.assertTrue(len(frames) > 100)
        sample_frame = frames[10]
        self.assertIn("weather", sample_frame)
        self.assertIn("track_temp", sample_frame["weather"])
        self.assertIn("wind_direction", sample_frame["weather"])
        self.assertIn("wind_cardinal", sample_frame["weather"])
        self.assertTrue(len(sample_frame["drivers"]) >= 15)
        first_car = next(iter(sample_frame["drivers"].values()))
        for k in ("position", "x", "y", "tyre", "tyre_life", "tyre_health", "status", "gap_to_leader", "interval"):
            self.assertIn(k, first_car)

        # 2. Qualifying (Q1/Q2/Q3) Replay
        r_quali = self.client.get("/api/replay/session?season=2024&round=1&session_type=Qualifying&segment=Q3")
        self.assertEqual(r_quali.status_code, 200)
        quali_data = r_quali.get_json()
        self.assertEqual(quali_data["session_info"]["session_type"], "Qualifying")
        self.assertIn("qualifying", quali_data)
        self.assertIn("results", quali_data["qualifying"])
        self.assertIn("telemetry", quali_data["qualifying"])
        self.assertTrue(len(quali_data["qualifying"]["results"]) >= 15)
        pole_row = quali_data["qualifying"]["results"][0]
        for seg in ("Q1", "Q2", "Q3"):
            self.assertIn(seg, pole_row)

        # 3. Practice (FP1/FP2/FP3) Replay
        r_fp1 = self.client.get("/api/replay/session?season=2024&round=1&session_type=FP1")
        self.assertEqual(r_fp1.status_code, 200)
        fp1_data = r_fp1.get_json()
        self.assertEqual(fp1_data["session_info"]["session_type"], "FP1")
        for seg in ("FP1", "FP2", "FP3"):
            self.assertIn(seg, fp1_data["practice"])
        self.assertTrue(len(fp1_data["practice"]["FP1"]["results"]) >= 15)


if __name__ == "__main__":
    unittest.main()
