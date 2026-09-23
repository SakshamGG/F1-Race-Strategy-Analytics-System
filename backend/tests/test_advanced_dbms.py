"""
Unit tests for Advanced DBMS Features:
1. Stored procedure sp_recalculate_standings execution & API endpoint.
2. Stored procedure sp_simulate_strategy execution & API endpoint.
3. Stored procedure sp_validate_race_tyre_rules execution & API endpoint.
4. Strategy notes audit logging & history API endpoints.
5. Trigger logic validation (lap number bounds, pit stop bounds, F1 two-compound dry rule).
6. Guaranteed database connection cleanup and rollback safety on errors.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import mysql.connector

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


class TestAdvancedDBMSEndpoints(unittest.TestCase):
    """API endpoint tests for Stored Procedures and Audit Logging."""

    def setUp(self):
        self.client = app.test_client()

    def test_recalculate_standings_success(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        # Mock stored results from sp_recalculate_standings
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "position": 1,
                "driver_id": 1,
                "driver_name": "Max Verstappen",
                "nationality": "Dutch",
                "points": 58.0,
                "wins": 2,
                "podiums": 3,
                "last_updated": "2024-09-23 20:00:00",
            },
            {
                "position": 2,
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "nationality": "Monegasque",
                "points": 37.0,
                "wins": 1,
                "podiums": 2,
                "last_updated": "2024-09-23 20:00:00",
            },
        ]
        mock_cur.stored_results.return_value = [mock_result]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/standings/recalculate/2024")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("driver_standings", data)
            self.assertEqual(len(data["driver_standings"]), 2)
            self.assertEqual(data["driver_standings"][0]["driver_name"], "Max Verstappen")
            mock_cur.callproc.assert_called_once_with("sp_recalculate_standings", (2024,))
            mock_conn.commit.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_simulate_strategy_success(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "race_id": 1,
                "race_name": "Monaco Grand Prix",
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "total_laps": 78,
                "laps_completed": 20,
                "strategy_option": "1-Stop Strategy",
                "tyre_sequence": "Medium -> Hard",
                "stops_count": 1,
                "pit_window_laps": "Lap 30 - 34",
                "projected_race_time_seconds": 6250.500,
                "is_recommended": True,
                "strategic_rationale": "Minimizes pit lane loss; high track position retention.",
            },
            {
                "race_id": 1,
                "race_name": "Monaco Grand Prix",
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "total_laps": 78,
                "laps_completed": 20,
                "strategy_option": "2-Stop Strategy",
                "tyre_sequence": "Soft -> Medium -> Hard",
                "stops_count": 2,
                "pit_window_laps": "Lap 17 and Lap 45",
                "projected_race_time_seconds": 6265.200,
                "is_recommended": False,
                "strategic_rationale": "Aggressive pace advantage on fresh compounds.",
            },
        ]
        mock_cur.stored_results.return_value = [mock_result]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/analytics/simulate-strategy?race_id=1&driver_id=3")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("simulation_results", data)
            self.assertEqual(len(data["simulation_results"]), 2)
            self.assertEqual(data["simulation_results"][0]["strategy_option"], "1-Stop Strategy")
            self.assertTrue(data["simulation_results"][0]["is_recommended"])
            mock_cur.callproc.assert_called_once_with("sp_simulate_strategy", (1, 3))
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_simulate_strategy_missing_params(self):
        response = self.client.get("/api/analytics/simulate-strategy?race_id=1")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_validate_race_tyre_rules_endpoint(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "race_id": 1,
                "race_name": "Monaco Grand Prix",
                "track_condition": "Dry",
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "team_name": "Ferrari",
                "finishing_position": 1,
                "status": "Finished",
                "dry_compounds_used": 2,
                "compounds_used": "Hard, Medium",
                "rule_compliance_status": "Compliant",
                "recommended_action": "None",
            },
            {
                "race_id": 1,
                "race_name": "Monaco Grand Prix",
                "track_condition": "Dry",
                "driver_id": 99,
                "driver_name": "Test Driver",
                "team_name": "Test Team",
                "finishing_position": 10,
                "status": "Finished",
                "dry_compounds_used": 1,
                "compounds_used": "Medium",
                "rule_compliance_status": "VIOLATION (Two dry compounds required)",
                "recommended_action": "Disqualification (DSQ)",
            },
        ]
        mock_cur.stored_results.return_value = [mock_result]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/races/1/validate-tyre-rules")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["total_drivers_audited"], 2)
            self.assertEqual(data["audit_results"][0]["rule_compliance_status"], "Compliant")
            self.assertEqual(data["audit_results"][1]["recommended_action"], "Disqualification (DSQ)")
            mock_cur.callproc.assert_called_once_with("sp_validate_race_tyre_rules", (1,))
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_strategy_note_audit_history(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchall.return_value = [
            {
                "audit_id": 2,
                "note_id": 1,
                "race_id": 1,
                "analyst_id": 2,
                "driver_id": 3,
                "action_type": "UPDATE",
                "old_note_text": "Strong stint on mediums.",
                "new_note_text": "Strong stint on mediums with low tyre degradation.",
                "old_note_type": "Observation",
                "new_note_type": "Observation",
                "changed_by": "root@localhost",
                "changed_at": "2024-05-26 15:30:00",
            },
            {
                "audit_id": 1,
                "note_id": 1,
                "race_id": 1,
                "analyst_id": 2,
                "driver_id": 3,
                "action_type": "INSERT",
                "old_note_text": None,
                "new_note_text": "Strong stint on mediums.",
                "old_note_type": None,
                "new_note_type": "Observation",
                "changed_by": "root@localhost",
                "changed_at": "2024-05-26 15:00:00",
            },
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/strategy-notes/1/audit")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["note_id"], 1)
            self.assertEqual(data["total_audit_events"], 2)
            self.assertEqual(data["history"][0]["action_type"], "UPDATE")
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_all_strategy_notes_audit(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        mock_cur.fetchall.return_value = [
            {
                "audit_id": 1,
                "note_id": 1,
                "race_id": 1,
                "race_name": "Monaco Grand Prix",
                "analyst_id": 2,
                "analyst_name": "Strategy Analyst",
                "driver_id": 3,
                "driver_name": "Charles Leclerc",
                "action_type": "INSERT",
                "new_note_text": "Strong stint.",
                "new_note_type": "Observation",
                "changed_by": "root@localhost",
                "changed_at": "2024-05-26 15:00:00",
            }
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/strategy-notes/audit?limit=10")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["total_records"], 1)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


class TestTriggerConstraintsAndRollback(unittest.TestCase):
    """Verify trigger-like constraint behavior and error rollback safety."""

    def setUp(self):
        self.client = app.test_client()

    def test_trigger_lap_number_exceeds_error(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        # Simulate MySQL 45000 custom error from trigger
        mock_cur.execute.side_effect = mysql.connector.Error(
            msg="Validation Error: Lap number exceeds race total laps or is less than 1",
            errno=1644,
            sqlstate="45000"
        )

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/lap-times", json={
                "race_id": 1,
                "driver_id": 3,
                "compound_id": 1,
                "lap_number": 999,  # exceeds Monaco total_laps (78)
                "lap_time": "00:01:15.234"
            })
            self.assertEqual(response.status_code, 500)
            data = response.get_json()
            self.assertIn("Lap number exceeds race total laps", data["error"])
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_trigger_f1_dry_tyre_rule_error(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        # Simulate MySQL trigger rejecting single compound finish
        mock_cur.execute.side_effect = mysql.connector.Error(
            msg="F1 Rule Violation: Driver must use at least two distinct dry tyre compounds in a dry race",
            errno=1644,
            sqlstate="45000"
        )

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.put("/api/race-results/1", json={
                "status": "Finished"
            })
            self.assertEqual(response.status_code, 500)
            data = response.get_json()
            self.assertIn("F1 Rule Violation", data["error"])
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_recalculate_standings_error_cleanup(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.callproc.side_effect = Exception("Procedure failed")
        mock_cur.execute.side_effect = Exception("Fallback query failed")

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/standings/recalculate/2024")
            self.assertEqual(response.status_code, 500)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_validate_tyre_rules_error_cleanup(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.callproc.side_effect = Exception("Procedure failed")
        mock_cur.execute.side_effect = Exception("Fallback query failed")

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/races/1/validate-tyre-rules")
            self.assertEqual(response.status_code, 500)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
