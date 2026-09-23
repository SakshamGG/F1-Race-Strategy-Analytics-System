"""
Unit tests for Strategy Analytics and Telemetry Ingestion endpoints.
Verifies that:
1. /api/analytics/tyre-degradation calculates OLS regression slopes, base pace, and curve samples.
2. /api/analytics/undercut-simulation computes gap deltas, undercut feasibility, and pit window ranges.
3. /api/analytics/stint-comparison calculates stint metrics (median, mean, std dev) and head-to-head deltas.
4. /api/import/laps and /api/import/pit-stops fetch, map, and insert records into database with connection safety.
5. All endpoints guarantee database connection cleanup even on errors.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from services.analytics_service import (
    time_to_seconds,
    seconds_to_time,
    _calculate_ols_regression,
    calculate_tyre_degradation,
    simulate_undercut,
    compare_stints,
)


class TestAnalyticsServiceDirect(unittest.TestCase):
    """Direct unit tests for analytics mathematical logic."""

    def test_time_conversions(self):
        # String conversion
        self.assertAlmostEqual(time_to_seconds("00:01:20.500"), 80.5, places=3)
        self.assertAlmostEqual(time_to_seconds("01:20.500"), 80.5, places=3)
        self.assertAlmostEqual(time_to_seconds("80.5"), 80.5, places=3)
        # Timedelta conversion
        td = timedelta(minutes=1, seconds=24, milliseconds=250)
        self.assertAlmostEqual(time_to_seconds(td), 84.25, places=3)
        # Seconds to time
        self.assertEqual(seconds_to_time(80.5), "00:01:20.500")
        self.assertIsNone(time_to_seconds(None))
        self.assertIsNone(seconds_to_time(None))

    def test_ols_regression(self):
        # Linear: y = 0.05 * x + 75.0
        x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        y = [75.0 + 0.05 * val for val in x]
        slope, intercept, r2 = _calculate_ols_regression(x, y)
        self.assertAlmostEqual(slope, 0.05, places=4)
        self.assertAlmostEqual(intercept, 75.0, places=3)
        self.assertAlmostEqual(r2, 1.0, places=3)

    def test_calculate_tyre_degradation_mock(self):
        mock_cur = MagicMock()
        # Mock 10 laps on Soft tyres with realistic degradation
        mock_cur.fetchall.return_value = [
            {
                "race_id": 1,
                "race_name": "Monaco GP",
                "driver_id": 3,
                "compound_id": 1,
                "compound_name": "Soft",
                "color_code": "#FF0000",
                "expected_lifespan_laps": 25,
                "lap_number": lap,
                "lap_time": f"00:01:{15 + (lap * 0.08):06.3f}",
            }
            for lap in range(1, 11)
        ]

        result = calculate_tyre_degradation(mock_cur, race_id=1)
        self.assertIn("compounds", result)
        self.assertEqual(len(result["compounds"]), 1)
        soft = result["compounds"][0]
        self.assertEqual(soft["compound_name"], "Soft")
        self.assertGreater(soft["degradation_rate_sec_per_lap"], 0.05)
        self.assertEqual(soft["laps_analyzed"], 10)
        self.assertTrue(len(soft["degradation_curve"]) > 0)

    def test_simulate_undercut_viable(self):
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            {"race_id": 1, "race_name": "Monaco GP", "total_laps": 78},  # race
            {"avg_loss": 22.5},  # pit loss
        ]
        mock_cur.fetchall.side_effect = [
            [
                {"driver_id": 1, "name": "Charles Leclerc"},
                {"driver_id": 2, "name": "Max Verstappen"},
            ],  # drivers
            [
                {"driver_id": 2, "lap_number": 19, "lap_time": "00:01:15.000", "compound_id": 2},
                {"driver_id": 1, "lap_number": 19, "lap_time": "00:01:16.200", "compound_id": 2},
            ],  # history laps (chaser is 1.2s behind)
            [],  # calculate_tyre_degradation fetchall
        ]

        # Chaser (id=1, Leclerc) trailing leader (id=2, Verstappen) by 1.2s
        result = simulate_undercut(mock_cur, race_id=1, chaser_driver_id=1, leader_driver_id=2, pit_lap=20)
        self.assertIn("undercut_successful", result)
        self.assertTrue(result["undercut_successful"])  # 1.2s initial gap < ~2.2s out lap advantage
        self.assertIn("pit_window_range", result)

    def test_compare_stints_logic(self):
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"race_id": 1, "race_name": "Monaco GP"}
        mock_cur.fetchall.side_effect = [
            [
                {"driver_id": 1, "name": "Charles Leclerc", "nationality": "Monegasque"},
                {"driver_id": 2, "name": "Carlos Sainz", "nationality": "Spanish"},
            ],  # drivers
            [
                # Driver 1: 5 laps on Medium (id=2), 5 laps on Hard (id=3)
                {"driver_id": 1, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 1, "lap_time": "00:01:16.000"},
                {"driver_id": 1, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 2, "lap_time": "00:01:16.100"},
                {"driver_id": 1, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 3, "lap_time": "00:01:16.200"},
                {"driver_id": 1, "compound_id": 3, "compound_name": "Hard", "color_code": "#FFFFFF", "lap_number": 4, "lap_time": "00:01:15.500"},
                {"driver_id": 1, "compound_id": 3, "compound_name": "Hard", "color_code": "#FFFFFF", "lap_number": 5, "lap_time": "00:01:15.600"},
                # Driver 2: 5 laps on Medium
                {"driver_id": 2, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 1, "lap_time": "00:01:16.500"},
                {"driver_id": 2, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 2, "lap_time": "00:01:16.600"},
                {"driver_id": 2, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 3, "lap_time": "00:01:16.700"},
            ],  # laps
        ]

        result = compare_stints(mock_cur, race_id=1, driver1_id=1, driver2_id=2)
        self.assertIn("stint_comparisons", result)
        self.assertEqual(result["driver1"]["name"], "Charles Leclerc")
        self.assertEqual(result["driver2"]["name"], "Carlos Sainz")
        # Stint 1: Driver 1 median (76.100) vs Driver 2 median (76.600) -> Driver 1 is faster
        stint1 = result["stint_comparisons"][0]
        self.assertEqual(stint1["faster_driver"], "Charles Leclerc")


class TestAnalyticsEndpoints(unittest.TestCase):
    """API endpoint tests for analytics routes."""

    def setUp(self):
        self.client = app.test_client()

    def test_get_tyre_degradation_success(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchall.return_value = [
            {
                "race_id": 1,
                "race_name": "Monaco GP",
                "driver_id": 3,
                "compound_id": 2,
                "compound_name": "Medium",
                "color_code": "#FFFF00",
                "expected_lifespan_laps": 35,
                "lap_number": lap,
                "lap_time": f"00:01:{16 + (lap * 0.05):06.3f}",
            }
            for lap in range(1, 15)
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/analytics/tyre-degradation?race_id=1")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("compounds", data)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_undercut_simulation_endpoint(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchone.side_effect = [
            {"race_id": 1, "race_name": "Monaco GP", "total_laps": 78},
            {"avg_loss": 22.0},
        ]
        mock_cur.fetchall.side_effect = [
            [
                {"driver_id": 1, "name": "Charles Leclerc"},
                {"driver_id": 2, "name": "Max Verstappen"},
            ],
            [
                {"driver_id": 1, "lap_number": 1, "lap_time": "00:01:15.000", "compound_id": 1},
                {"driver_id": 2, "lap_number": 1, "lap_time": "00:01:14.500", "compound_id": 1},
            ],
            [],
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get(
                "/api/analytics/undercut-simulation?race_id=1&chaser_driver_id=1&leader_driver_id=2&pit_lap=18"
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("undercut_successful", data)
            self.assertIn("verdict", data)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_undercut_simulation_missing_args(self):
        response = self.client.get("/api/analytics/undercut-simulation?race_id=1")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_get_stint_comparison_endpoint(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchone.return_value = {"race_id": 1, "race_name": "Monaco GP"}
        mock_cur.fetchall.side_effect = [
            [
                {"driver_id": 1, "name": "Charles Leclerc", "nationality": "Monegasque"},
                {"driver_id": 2, "name": "Carlos Sainz", "nationality": "Spanish"},
            ],
            [
                {"driver_id": 1, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 1, "lap_time": "00:01:16.000"},
                {"driver_id": 2, "compound_id": 2, "compound_name": "Medium", "color_code": "#FFFF00", "lap_number": 1, "lap_time": "00:01:16.500"},
            ],
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get(
                "/api/analytics/stint-comparison?race_id=1&driver1_id=1&driver2_id=2"
            )
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("stint_comparisons", data)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


class TestTelemetryImports(unittest.TestCase):
    """API endpoint tests for automated telemetry ingestion."""

    def setUp(self):
        self.client = app.test_client()

    @patch("services.jolpica_client.fetch_laps")
    @patch("services.openf1_client.fetch_sessions")
    def test_import_laps_openf1_fallback_to_jolpica(self, mock_fetch_sessions, mock_fetch_jolpica_laps):
        # OpenF1 raises exception to trigger Jolpica fallback
        mock_fetch_sessions.side_effect = Exception("OpenF1 down")
        mock_fetch_jolpica_laps.return_value = [
            {"lap_number": 1, "driver_ref": "leclerc", "position": 1, "lap_time": "00:01:15.500"},
            {"lap_number": 2, "driver_ref": "leclerc", "position": 1, "lap_time": "00:01:15.800"},
        ]

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        # 1. Race exists
        mock_cur.fetchone.side_effect = [
            {"race_id": 1, "race_name": "Monaco GP", "circuit_id": 1},  # race lookup
            None,  # lap 1 check existing (not found)
            None,  # lap 2 check existing (not found)
        ]
        # 2. Tyre compounds
        mock_cur.fetchall.side_effect = [
            [{"compound_id": 1, "name": "soft"}, {"compound_id": 2, "name": "medium"}],
            [{"driver_id": 3, "first_name": "charles", "last_name": "leclerc", "car_number": 16}],
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/import/laps/2024/8")
            self.assertEqual(response.status_code, 201)
            data = response.get_json()
            self.assertEqual(data["race_id"], 1)
            self.assertEqual(data["inserted"], 2)
            mock_conn.commit.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    @patch("services.jolpica_client.fetch_pit_stops")
    def test_import_pit_stops_success(self, mock_fetch_pit_stops):
        mock_fetch_pit_stops.return_value = [
            {"driver_ref": "leclerc", "lap_number": 22, "stop_number": 1, "stop_duration": 24.35},
        ]

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchone.side_effect = [
            {"race_id": 1, "race_name": "Monaco GP"},  # race lookup
            None,  # pit stop existing check
        ]
        mock_cur.fetchall.side_effect = [
            [{"compound_id": 2, "name": "medium"}, {"compound_id": 3, "name": "hard"}],
            [{"driver_id": 3, "first_name": "charles", "last_name": "leclerc"}],
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/import/pit-stops/2024/8")
            self.assertEqual(response.status_code, 201)
            data = response.get_json()
            self.assertEqual(data["race_id"], 1)
            self.assertEqual(data["inserted"], 1)
            mock_conn.commit.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_import_laps_race_not_found(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/import/laps/2024/99")
            self.assertEqual(response.status_code, 404)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


class TestAnalyticsConnectionSafety(unittest.TestCase):
    """Verify guaranteed connection cleanup on errors for new routes."""

    def setUp(self):
        self.client = app.test_client()

    def test_tyre_degradation_error_cleanup(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = Exception("DB crash")

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/analytics/tyre-degradation?race_id=1")
            self.assertEqual(response.status_code, 500)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_undercut_simulation_error_cleanup(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = Exception("DB crash")

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get(
                "/api/analytics/undercut-simulation?race_id=1&chaser_driver_id=1&leader_driver_id=2&pit_lap=15"
            )
            self.assertEqual(response.status_code, 500)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_stint_comparison_error_cleanup(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = Exception("DB crash")

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get(
                "/api/analytics/stint-comparison?race_id=1&driver1_id=1&driver2_id=2"
            )
            self.assertEqual(response.status_code, 500)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
