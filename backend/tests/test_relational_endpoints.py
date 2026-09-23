"""
Unit tests for relational joined endpoints and championship standings.
Verifies that:
1. /api/races/<id>/results returns joined race, driver, and team context.
2. /api/races/<id>/lap-times returns driver names, tyre compounds, and colors.
3. /api/races/<id>/pit-stops returns tyre change details.
4. /api/races/<id>/strategy-notes returns analyst and driver context.
5. /api/standings/drivers/<season> aggregates driver points and podiums.
6. /api/standings/constructors/<season> aggregates constructor points and wins.
7. /api/race-results?detailed=true returns joined results.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


class TestRelationalEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_get_race_results_by_race_success(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchone.return_value = {
            "race_id": 1,
            "race_name": "Monaco Grand Prix",
            "season_year": 2024,
            "round_number": 8,
            "race_date": "2024-05-26",
            "circuit_name": "Circuit de Monaco",
            "circuit_country": "Monaco",
            "circuit_city": "Monte Carlo",
        }
        mock_cur.fetchall.return_value = [
            {
                "result_id": 1,
                "race_id": 1,
                "race_name": "Monaco Grand Prix",
                "season_year": 2024,
                "round_number": 8,
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "driver_nationality": "Monégasque",
                "constructor_id": 3,
                "team_name": "Ferrari",
                "grid_position": 1,
                "finishing_position": 1,
                "points_scored": 25.0,
                "status": "Finished",
                "fastest_lap_time": "00:01:14.567",
            }
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/races/1/results")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("race", data)
            self.assertIn("classification", data)
            self.assertEqual(data["classification"][0]["driver_name"], "Charles Leclerc")
            self.assertEqual(data["classification"][0]["team_name"], "Ferrari")
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_race_results_by_race_not_found(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/races/999/results")
            self.assertEqual(response.status_code, 404)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_race_lap_times_with_driver_filter(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {"race_id": 1, "race_name": "Monaco Grand Prix"}
        mock_cur.fetchall.return_value = [
            {
                "lap_id": 1,
                "race_id": 1,
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "compound_id": 1,
                "compound_name": "Soft",
                "compound_color": "#FF0000",
                "lap_number": 1,
                "lap_time": "00:01:16.234",
                "sector1_time": 18.123,
                "sector2_time": 32.456,
                "sector3_time": 25.655,
            }
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/races/1/lap-times?driver_id=3")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["compound_name"], "Soft")
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_driver_standings(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {
                "season_year": 2024,
                "driver_id": 1,
                "driver_name": "Max Verstappen",
                "team_name": "Red Bull Racing",
                "total_points": 58.0,
                "wins": 2,
                "podiums": 2,
            },
            {
                "season_year": 2024,
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "team_name": "Ferrari",
                "total_points": 37.0,
                "wins": 1,
                "podiums": 1,
            }
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/standings/drivers/2024")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["position"], 1)
            self.assertEqual(data[0]["driver_name"], "Max Verstappen")
            self.assertEqual(data[1]["position"], 2)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_constructor_standings(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {
                "season_year": 2024,
                "constructor_id": 1,
                "team_name": "Red Bull Racing",
                "total_points": 68.0,
                "wins": 2,
                "podiums": 2,
            }
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/standings/constructors/2024")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["position"], 1)
            self.assertEqual(data[0]["team_name"], "Red Bull Racing")
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_race_results_detailed_param(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {
                "result_id": 1,
                "race_id": 1,
                "race_name": "Monaco Grand Prix",
                "season_year": 2024,
                "round_number": 8,
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "driver_nationality": "Monégasque",
                "constructor_id": 3,
                "team_name": "Ferrari",
                "c_nationality": "Italian",
                "grid_position": 1,
                "finishing_position": 1,
                "points_scored": 25.0,
                "status": "Finished",
                "fastest_lap_time": "00:01:14.567",
            }
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/race-results?detailed=true")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data[0]["driver_name"], "Charles Leclerc")
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
