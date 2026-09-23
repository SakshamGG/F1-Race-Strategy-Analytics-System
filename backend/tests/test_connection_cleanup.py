"""
Unit tests for database connection leak prevention and transaction rollback.
Verifies that:
1. Connections and cursors are closed on success.
2. Connections and cursors are closed on 404 early return.
3. Connections are rolled back and closed on IntegrityError (409).
4. Connections are rolled back and closed on generic Exception (500).
5. Connections are closed in /test-db.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import mysql.connector

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


class TestConnectionCleanup(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_get_drivers_success_cleanup(self):
        """Verify cursor and connection are closed on successful GET request."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {
                "driver_id": 1,
                "first_name": "Max",
                "last_name": "Verstappen",
                "nationality": "Dutch",
                "date_of_birth": "1997-09-30",
            }
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/drivers")
            self.assertEqual(response.status_code, 200)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_get_driver_not_found_cleanup(self):
        """Verify cursor and connection are closed on early return (404 Not Found)."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/api/drivers/999")
            self.assertEqual(response.status_code, 404)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_add_driver_integrity_error_rollback_and_cleanup(self):
        """Verify rollback and cleanup on MySQL IntegrityError (409 Conflict)."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = mysql.connector.IntegrityError("Duplicate entry")

        payload = {
            "first_name": "Max",
            "last_name": "Verstappen",
            "nationality": "Dutch",
            "date_of_birth": "1997-09-30",
        }

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/drivers", json=payload)
            self.assertEqual(response.status_code, 409)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_add_driver_unexpected_exception_rollback_and_cleanup(self):
        """Verify rollback and cleanup on unexpected Exception (500 Internal Server Error)."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.execute.side_effect = RuntimeError("Disk full or unexpected error")

        payload = {
            "first_name": "Max",
            "last_name": "Verstappen",
            "nationality": "Dutch",
            "date_of_birth": "1997-09-30",
        }

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/drivers", json=payload)
            self.assertEqual(response.status_code, 500)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_delete_driver_integrity_error_rollback_and_cleanup(self):
        """Verify rollback and cleanup when deleting a referenced entity (FK constraint)."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {"driver_id": 1}
        mock_cur.execute.side_effect = [
            None,  # SELECT check
            mysql.connector.IntegrityError("Cannot delete: foreign key constraint fails"),
        ]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.delete("/api/drivers/1")
            self.assertEqual(response.status_code, 409)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_update_driver_not_found_cleanup(self):
        """Verify cleanup when updating non-existent driver (404)."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.put("/api/drivers/999", json={"nationality": "British"})
            self.assertEqual(response.status_code, 404)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_update_driver_integrity_error_rollback_and_cleanup(self):
        """Verify rollback and cleanup on update integrity error."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = {
            "driver_id": 1,
            "first_name": "Max",
            "last_name": "Verstappen",
            "nationality": "Dutch",
            "date_of_birth": "1997-09-30",
        }
        mock_cur.execute.side_effect = [None, mysql.connector.IntegrityError("Duplicate key")]

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.put("/api/drivers/1", json={"first_name": "Lando"})
            self.assertEqual(response.status_code, 409)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_import_drivers_db_error_rollback_and_cleanup(self):
        """Verify rollback and cleanup when import encounters a database error."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        mock_cur.execute.side_effect = mysql.connector.IntegrityError("DB Error during batch insert")

        fake_drivers = [
            {"first_name": "Max", "last_name": "Verstappen", "nationality": "Dutch", "date_of_birth": "1997-09-30"}
        ]

        with patch("services.jolpica_client.fetch_drivers", return_value=fake_drivers), \
             patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.post("/api/import/drivers/2024")
            self.assertEqual(response.status_code, 409)
            mock_conn.rollback.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_test_db_cleanup(self):
        """Verify connection is closed in /test-db route."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True

        with patch("app.get_db_connection", return_value=mock_conn):
            response = self.client.get("/test-db")
            self.assertEqual(response.status_code, 200)
            mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
