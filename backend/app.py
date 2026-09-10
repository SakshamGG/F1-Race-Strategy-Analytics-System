from flask import Flask, jsonify, request
from flask_cors import CORS
from database import get_db_connection
import mysql.connector
from datetime import date, datetime, timedelta
from decimal import Decimal

app = Flask(__name__)
CORS(app)


# ==============================================================================
# Helper Functions
# ==============================================================================

def serialize_value(val):
    """Convert a single Python/MySQL value to a JSON-serializable type."""
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, timedelta):
        total = int(val.total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        ms = val.microseconds // 1000
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    return val


def serialize_row(row):
    """Convert a dictionary row from MySQL to JSON-serializable format."""
    if row is None:
        return None
    return {k: serialize_value(v) for k, v in row.items()}


def serialize_rows(rows):
    """Convert a list of dictionary rows to JSON-serializable format."""
    return [serialize_row(r) for r in rows]


def validate_required(data, fields):
    """Return the name of the first missing/empty required field, or None."""
    if not data:
        return fields[0] if fields else None
    for f in fields:
        if f not in data or data[f] is None:
            return f
        if isinstance(data[f], str) and data[f].strip() == "":
            return f
    return None


# ==============================================================================
# Health & Database Test Routes (EXISTING — PRESERVED)
# ==============================================================================

@app.route("/")
def home():
    return "F1 Strategy Backend is running!"


@app.route("/test-db")
def test_db():
    try:
        connection = get_db_connection()
        if connection.is_connected():
            connection.close()
            return "Database connection successful!"
        return "Database connection failed!"
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# DRIVERS
# ==============================================================================

@app.route("/api/drivers")
def get_drivers():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVERS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/drivers/<int:driver_id>")
def get_driver(driver_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVERS WHERE driver_id = %s", (driver_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Driver not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/drivers", methods=["POST"])
def add_driver():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["first_name", "last_name", "nationality", "date_of_birth"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO DRIVERS (first_name, last_name, nationality, date_of_birth) VALUES (%s, %s, %s, %s)",
            (data["first_name"], data["last_name"], data["nationality"], data["date_of_birth"])
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Driver added successfully", "driver_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/drivers/<int:driver_id>", methods=["PUT"])
def update_driver(driver_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVERS WHERE driver_id = %s", (driver_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Driver not found"}), 404

        cur.execute(
            "UPDATE DRIVERS SET first_name=%s, last_name=%s, nationality=%s, date_of_birth=%s WHERE driver_id=%s",
            (
                data.get("first_name", existing["first_name"]),
                data.get("last_name", existing["last_name"]),
                data.get("nationality", existing["nationality"]),
                data.get("date_of_birth", existing["date_of_birth"]),
                driver_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Driver updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/drivers/<int:driver_id>", methods=["DELETE"])
def delete_driver(driver_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVERS WHERE driver_id = %s", (driver_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Driver not found"}), 404
        cur.execute("DELETE FROM DRIVERS WHERE driver_id = %s", (driver_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Driver deleted successfully"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Cannot delete driver: referenced by other records"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# CONSTRUCTORS
# ==============================================================================

@app.route("/api/constructors")
def get_constructors():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CONSTRUCTORS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/constructors/<int:constructor_id>")
def get_constructor(constructor_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CONSTRUCTORS WHERE constructor_id = %s", (constructor_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Constructor not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/constructors", methods=["POST"])
def add_constructor():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["name", "nationality", "base_location"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO CONSTRUCTORS (name, nationality, base_location) VALUES (%s, %s, %s)",
            (data["name"], data["nationality"], data["base_location"])
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Constructor added successfully", "constructor_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/constructors/<int:constructor_id>", methods=["PUT"])
def update_constructor(constructor_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CONSTRUCTORS WHERE constructor_id = %s", (constructor_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Constructor not found"}), 404

        cur.execute(
            "UPDATE CONSTRUCTORS SET name=%s, nationality=%s, base_location=%s WHERE constructor_id=%s",
            (
                data.get("name", existing["name"]),
                data.get("nationality", existing["nationality"]),
                data.get("base_location", existing["base_location"]),
                constructor_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Constructor updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/constructors/<int:constructor_id>", methods=["DELETE"])
def delete_constructor(constructor_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CONSTRUCTORS WHERE constructor_id = %s", (constructor_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Constructor not found"}), 404
        cur.execute("DELETE FROM CONSTRUCTORS WHERE constructor_id = %s", (constructor_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Constructor deleted successfully"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Cannot delete constructor: referenced by other records"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# CIRCUITS
# ==============================================================================

@app.route("/api/circuits")
def get_circuits():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CIRCUITS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/circuits/<int:circuit_id>")
def get_circuit(circuit_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CIRCUITS WHERE circuit_id = %s", (circuit_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Circuit not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/circuits", methods=["POST"])
def add_circuit():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["name", "country", "city", "length_km", "number_of_turns"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO CIRCUITS (name, country, city, length_km, number_of_turns) VALUES (%s, %s, %s, %s, %s)",
            (data["name"], data["country"], data["city"], data["length_km"], data["number_of_turns"])
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Circuit added successfully", "circuit_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/circuits/<int:circuit_id>", methods=["PUT"])
def update_circuit(circuit_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CIRCUITS WHERE circuit_id = %s", (circuit_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Circuit not found"}), 404

        cur.execute(
            "UPDATE CIRCUITS SET name=%s, country=%s, city=%s, length_km=%s, number_of_turns=%s WHERE circuit_id=%s",
            (
                data.get("name", existing["name"]),
                data.get("country", existing["country"]),
                data.get("city", existing["city"]),
                data.get("length_km", existing["length_km"]),
                data.get("number_of_turns", existing["number_of_turns"]),
                circuit_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Circuit updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/circuits/<int:circuit_id>", methods=["DELETE"])
def delete_circuit(circuit_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM CIRCUITS WHERE circuit_id = %s", (circuit_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Circuit not found"}), 404
        cur.execute("DELETE FROM CIRCUITS WHERE circuit_id = %s", (circuit_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Circuit deleted successfully"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Cannot delete circuit: referenced by other records"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# TYRE COMPOUNDS
# ==============================================================================

@app.route("/api/tyre-compounds")
def get_tyre_compounds():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM TYRE_COMPOUNDS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tyre-compounds/<int:compound_id>")
def get_tyre_compound(compound_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM TYRE_COMPOUNDS WHERE compound_id = %s", (compound_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Tyre compound not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tyre-compounds", methods=["POST"])
def add_tyre_compound():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["compound_name", "color_code"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO TYRE_COMPOUNDS (compound_name, color_code, expected_lifespan_laps) VALUES (%s, %s, %s)",
            (data["compound_name"], data["color_code"], data.get("expected_lifespan_laps"))
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Tyre compound added successfully", "compound_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tyre-compounds/<int:compound_id>", methods=["PUT"])
def update_tyre_compound(compound_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM TYRE_COMPOUNDS WHERE compound_id = %s", (compound_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Tyre compound not found"}), 404

        cur.execute(
            "UPDATE TYRE_COMPOUNDS SET compound_name=%s, color_code=%s, expected_lifespan_laps=%s WHERE compound_id=%s",
            (
                data.get("compound_name", existing["compound_name"]),
                data.get("color_code", existing["color_code"]),
                data.get("expected_lifespan_laps", existing["expected_lifespan_laps"]),
                compound_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Tyre compound updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tyre-compounds/<int:compound_id>", methods=["DELETE"])
def delete_tyre_compound(compound_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM TYRE_COMPOUNDS WHERE compound_id = %s", (compound_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Tyre compound not found"}), 404
        cur.execute("DELETE FROM TYRE_COMPOUNDS WHERE compound_id = %s", (compound_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Tyre compound deleted successfully"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Cannot delete compound: referenced by other records"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# ANALYSTS
# ==============================================================================

@app.route("/api/analysts")
def get_analysts():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM ANALYSTS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysts/<int:analyst_id>")
def get_analyst(analyst_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM ANALYSTS WHERE analyst_id = %s", (analyst_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Analyst not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysts", methods=["POST"])
def add_analyst():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["name", "email", "role"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ANALYSTS (name, email, role, access_level) VALUES (%s, %s, %s, %s)",
            (data["name"], data["email"], data["role"], data.get("access_level", 1))
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Analyst added successfully", "analyst_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysts/<int:analyst_id>", methods=["PUT"])
def update_analyst(analyst_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM ANALYSTS WHERE analyst_id = %s", (analyst_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Analyst not found"}), 404

        cur.execute(
            "UPDATE ANALYSTS SET name=%s, email=%s, role=%s, access_level=%s WHERE analyst_id=%s",
            (
                data.get("name", existing["name"]),
                data.get("email", existing["email"]),
                data.get("role", existing["role"]),
                data.get("access_level", existing["access_level"]),
                analyst_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Analyst updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysts/<int:analyst_id>", methods=["DELETE"])
def delete_analyst(analyst_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM ANALYSTS WHERE analyst_id = %s", (analyst_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Analyst not found"}), 404
        cur.execute("DELETE FROM ANALYSTS WHERE analyst_id = %s", (analyst_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Analyst deleted successfully"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Cannot delete analyst: referenced by other records"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# RACES
# ==============================================================================

@app.route("/api/races")
def get_races():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACES")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/races/<int:race_id>")
def get_race(race_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACES WHERE race_id = %s", (race_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Race not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/races", methods=["POST"])
def add_race():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["circuit_id", "season_year", "race_name", "race_date", "total_laps", "round_number"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO RACES (circuit_id, season_year, race_name, race_date, total_laps, round_number) VALUES (%s, %s, %s, %s, %s, %s)",
            (data["circuit_id"], data["season_year"], data["race_name"], data["race_date"], data["total_laps"], data["round_number"])
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Race added successfully", "race_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/races/<int:race_id>", methods=["PUT"])
def update_race(race_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACES WHERE race_id = %s", (race_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Race not found"}), 404

        cur.execute(
            "UPDATE RACES SET circuit_id=%s, season_year=%s, race_name=%s, race_date=%s, total_laps=%s, round_number=%s WHERE race_id=%s",
            (
                data.get("circuit_id", existing["circuit_id"]),
                data.get("season_year", existing["season_year"]),
                data.get("race_name", existing["race_name"]),
                data.get("race_date", existing["race_date"]),
                data.get("total_laps", existing["total_laps"]),
                data.get("round_number", existing["round_number"]),
                race_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Race updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/races/<int:race_id>", methods=["DELETE"])
def delete_race(race_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACES WHERE race_id = %s", (race_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Race not found"}), 404
        cur.execute("DELETE FROM RACES WHERE race_id = %s", (race_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Race deleted successfully"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Cannot delete race: referenced by other records"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# DRIVER CONTRACTS
# ==============================================================================

@app.route("/api/driver-contracts")
def get_driver_contracts():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVER_CONTRACTS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/driver-contracts/<int:contract_id>")
def get_driver_contract(contract_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVER_CONTRACTS WHERE contract_id = %s", (contract_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Driver contract not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/driver-contracts", methods=["POST"])
def add_driver_contract():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["driver_id", "constructor_id", "season_year", "car_number", "start_date"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO DRIVER_CONTRACTS (driver_id, constructor_id, season_year, car_number, start_date, end_date) VALUES (%s, %s, %s, %s, %s, %s)",
            (data["driver_id"], data["constructor_id"], data["season_year"], data["car_number"], data["start_date"], data.get("end_date"))
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Driver contract added successfully", "contract_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/driver-contracts/<int:contract_id>", methods=["PUT"])
def update_driver_contract(contract_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVER_CONTRACTS WHERE contract_id = %s", (contract_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Driver contract not found"}), 404

        cur.execute(
            "UPDATE DRIVER_CONTRACTS SET driver_id=%s, constructor_id=%s, season_year=%s, car_number=%s, start_date=%s, end_date=%s WHERE contract_id=%s",
            (
                data.get("driver_id", existing["driver_id"]),
                data.get("constructor_id", existing["constructor_id"]),
                data.get("season_year", existing["season_year"]),
                data.get("car_number", existing["car_number"]),
                data.get("start_date", existing["start_date"]),
                data.get("end_date", existing["end_date"]),
                contract_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Driver contract updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/driver-contracts/<int:contract_id>", methods=["DELETE"])
def delete_driver_contract(contract_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM DRIVER_CONTRACTS WHERE contract_id = %s", (contract_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Driver contract not found"}), 404
        cur.execute("DELETE FROM DRIVER_CONTRACTS WHERE contract_id = %s", (contract_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Driver contract deleted successfully"})
    except mysql.connector.IntegrityError:
        return jsonify({"error": "Cannot delete contract: referenced by other records"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# RACE RESULTS
# ==============================================================================

@app.route("/api/race-results")
def get_race_results():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACE_RESULTS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/race-results/<int:result_id>")
def get_race_result(result_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACE_RESULTS WHERE result_id = %s", (result_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Race result not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/race-results", methods=["POST"])
def add_race_result():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["race_id", "driver_id", "constructor_id", "status"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO RACE_RESULTS
            (race_id, driver_id, constructor_id, grid_position, finishing_position, points_scored, status, fastest_lap_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                data["race_id"], data["driver_id"], data["constructor_id"],
                data.get("grid_position"), data.get("finishing_position"),
                data.get("points_scored", 0), data["status"], data.get("fastest_lap_time"),
            )
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Race result added successfully", "result_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/race-results/<int:result_id>", methods=["PUT"])
def update_race_result(result_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACE_RESULTS WHERE result_id = %s", (result_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Race result not found"}), 404

        cur.execute(
            """UPDATE RACE_RESULTS SET
            race_id=%s, driver_id=%s, constructor_id=%s, grid_position=%s,
            finishing_position=%s, points_scored=%s, status=%s, fastest_lap_time=%s
            WHERE result_id=%s""",
            (
                data.get("race_id", existing["race_id"]),
                data.get("driver_id", existing["driver_id"]),
                data.get("constructor_id", existing["constructor_id"]),
                data.get("grid_position", existing["grid_position"]),
                data.get("finishing_position", existing["finishing_position"]),
                data.get("points_scored", existing["points_scored"]),
                data.get("status", existing["status"]),
                data.get("fastest_lap_time", existing["fastest_lap_time"]),
                result_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Race result updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/race-results/<int:result_id>", methods=["DELETE"])
def delete_race_result(result_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM RACE_RESULTS WHERE result_id = %s", (result_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Race result not found"}), 404
        cur.execute("DELETE FROM RACE_RESULTS WHERE result_id = %s", (result_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Race result deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# LAP TIMES
# ==============================================================================

@app.route("/api/lap-times")
def get_lap_times():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM LAP_TIMES")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lap-times/<int:lap_id>")
def get_lap_time(lap_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM LAP_TIMES WHERE lap_id = %s", (lap_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Lap time not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lap-times", methods=["POST"])
def add_lap_time():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["race_id", "driver_id", "compound_id", "lap_number", "lap_time"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO LAP_TIMES
            (race_id, driver_id, compound_id, lap_number, lap_time, sector1_time, sector2_time, sector3_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                data["race_id"], data["driver_id"], data["compound_id"],
                data["lap_number"], data["lap_time"],
                data.get("sector1_time"), data.get("sector2_time"), data.get("sector3_time"),
            )
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Lap time added successfully", "lap_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lap-times/<int:lap_id>", methods=["PUT"])
def update_lap_time(lap_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM LAP_TIMES WHERE lap_id = %s", (lap_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Lap time not found"}), 404

        cur.execute(
            """UPDATE LAP_TIMES SET
            race_id=%s, driver_id=%s, compound_id=%s, lap_number=%s,
            lap_time=%s, sector1_time=%s, sector2_time=%s, sector3_time=%s
            WHERE lap_id=%s""",
            (
                data.get("race_id", existing["race_id"]),
                data.get("driver_id", existing["driver_id"]),
                data.get("compound_id", existing["compound_id"]),
                data.get("lap_number", existing["lap_number"]),
                data.get("lap_time", existing["lap_time"]),
                data.get("sector1_time", existing["sector1_time"]),
                data.get("sector2_time", existing["sector2_time"]),
                data.get("sector3_time", existing["sector3_time"]),
                lap_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Lap time updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/lap-times/<int:lap_id>", methods=["DELETE"])
def delete_lap_time(lap_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM LAP_TIMES WHERE lap_id = %s", (lap_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Lap time not found"}), 404
        cur.execute("DELETE FROM LAP_TIMES WHERE lap_id = %s", (lap_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Lap time deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# PIT STOPS
# ==============================================================================

@app.route("/api/pit-stops")
def get_pit_stops():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM PIT_STOPS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pit-stops/<int:pit_stop_id>")
def get_pit_stop(pit_stop_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM PIT_STOPS WHERE pit_stop_id = %s", (pit_stop_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Pit stop not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pit-stops", methods=["POST"])
def add_pit_stop():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["race_id", "driver_id", "compound_removed_id", "compound_fitted_id", "lap_number", "stop_duration"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO PIT_STOPS
            (race_id, driver_id, compound_removed_id, compound_fitted_id, lap_number, stop_duration, pit_loss_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                data["race_id"], data["driver_id"],
                data["compound_removed_id"], data["compound_fitted_id"],
                data["lap_number"], data["stop_duration"], data.get("pit_loss_time"),
            )
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Pit stop added successfully", "pit_stop_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pit-stops/<int:pit_stop_id>", methods=["PUT"])
def update_pit_stop(pit_stop_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM PIT_STOPS WHERE pit_stop_id = %s", (pit_stop_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Pit stop not found"}), 404

        cur.execute(
            """UPDATE PIT_STOPS SET
            race_id=%s, driver_id=%s, compound_removed_id=%s, compound_fitted_id=%s,
            lap_number=%s, stop_duration=%s, pit_loss_time=%s
            WHERE pit_stop_id=%s""",
            (
                data.get("race_id", existing["race_id"]),
                data.get("driver_id", existing["driver_id"]),
                data.get("compound_removed_id", existing["compound_removed_id"]),
                data.get("compound_fitted_id", existing["compound_fitted_id"]),
                data.get("lap_number", existing["lap_number"]),
                data.get("stop_duration", existing["stop_duration"]),
                data.get("pit_loss_time", existing["pit_loss_time"]),
                pit_stop_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Pit stop updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pit-stops/<int:pit_stop_id>", methods=["DELETE"])
def delete_pit_stop(pit_stop_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM PIT_STOPS WHERE pit_stop_id = %s", (pit_stop_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Pit stop not found"}), 404
        cur.execute("DELETE FROM PIT_STOPS WHERE pit_stop_id = %s", (pit_stop_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Pit stop deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# WEATHER CONDITIONS
# ==============================================================================

@app.route("/api/weather")
def get_weather_conditions():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM WEATHER_CONDITIONS")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/weather/<int:weather_id>")
def get_weather_condition(weather_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM WEATHER_CONDITIONS WHERE weather_id = %s", (weather_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Weather record not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/weather", methods=["POST"])
def add_weather_condition():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["race_id", "session_type", "track_condition"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO WEATHER_CONDITIONS
            (race_id, session_type, temperature_celsius, humidity_percent, wind_speed_kmh, track_condition, rainfall_mm)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                data["race_id"], data["session_type"],
                data.get("temperature_celsius"), data.get("humidity_percent"),
                data.get("wind_speed_kmh"), data["track_condition"], data.get("rainfall_mm", 0),
            )
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Weather record added successfully", "weather_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/weather/<int:weather_id>", methods=["PUT"])
def update_weather_condition(weather_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM WEATHER_CONDITIONS WHERE weather_id = %s", (weather_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Weather record not found"}), 404

        cur.execute(
            """UPDATE WEATHER_CONDITIONS SET
            race_id=%s, session_type=%s, temperature_celsius=%s, humidity_percent=%s,
            wind_speed_kmh=%s, track_condition=%s, rainfall_mm=%s
            WHERE weather_id=%s""",
            (
                data.get("race_id", existing["race_id"]),
                data.get("session_type", existing["session_type"]),
                data.get("temperature_celsius", existing["temperature_celsius"]),
                data.get("humidity_percent", existing["humidity_percent"]),
                data.get("wind_speed_kmh", existing["wind_speed_kmh"]),
                data.get("track_condition", existing["track_condition"]),
                data.get("rainfall_mm", existing["rainfall_mm"]),
                weather_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Weather record updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/weather/<int:weather_id>", methods=["DELETE"])
def delete_weather_condition(weather_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM WEATHER_CONDITIONS WHERE weather_id = %s", (weather_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Weather record not found"}), 404
        cur.execute("DELETE FROM WEATHER_CONDITIONS WHERE weather_id = %s", (weather_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Weather record deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# STRATEGY NOTES
# ==============================================================================

@app.route("/api/strategy-notes")
def get_strategy_notes():
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM STRATEGY_NOTES")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(serialize_rows(rows))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy-notes/<int:note_id>")
def get_strategy_note(note_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM STRATEGY_NOTES WHERE note_id = %s", (note_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Strategy note not found"}), 404
        return jsonify(serialize_row(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy-notes", methods=["POST"])
def add_strategy_note():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["race_id", "analyst_id", "driver_id", "note_text", "note_type"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO STRATEGY_NOTES
            (race_id, analyst_id, driver_id, note_text, note_type)
            VALUES (%s, %s, %s, %s, %s)""",
            (data["race_id"], data["analyst_id"], data["driver_id"], data["note_text"], data["note_type"])
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()
        return jsonify({"message": "Strategy note added successfully", "note_id": new_id}), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy-notes/<int:note_id>", methods=["PUT"])
def update_strategy_note(note_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM STRATEGY_NOTES WHERE note_id = %s", (note_id,))
        existing = cur.fetchone()
        if not existing:
            cur.close()
            conn.close()
            return jsonify({"error": "Strategy note not found"}), 404

        cur.execute(
            """UPDATE STRATEGY_NOTES SET
            race_id=%s, analyst_id=%s, driver_id=%s, note_text=%s, note_type=%s
            WHERE note_id=%s""",
            (
                data.get("race_id", existing["race_id"]),
                data.get("analyst_id", existing["analyst_id"]),
                data.get("driver_id", existing["driver_id"]),
                data.get("note_text", existing["note_text"]),
                data.get("note_type", existing["note_type"]),
                note_id,
            )
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Strategy note updated successfully"})
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy-notes/<int:note_id>", methods=["DELETE"])
def delete_strategy_note(note_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM STRATEGY_NOTES WHERE note_id = %s", (note_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Strategy note not found"}), 404
        cur.execute("DELETE FROM STRATEGY_NOTES WHERE note_id = %s", (note_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Strategy note deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# EXTERNAL API IMPORT ENDPOINTS
# ==============================================================================

@app.route("/api/import/drivers/<int:season>", methods=["POST"])
def import_drivers(season):
    """Fetch drivers from Jolpica API and insert new ones into the database."""
    try:
        from services.jolpica_client import fetch_drivers
        api_drivers = fetch_drivers(season)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch from Jolpica API: {str(e)}"}), 502

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        inserted = 0
        skipped = 0

        for d in api_drivers:
            cur.execute(
                "SELECT driver_id FROM DRIVERS WHERE first_name = %s AND last_name = %s",
                (d["first_name"], d["last_name"])
            )
            if cur.fetchone():
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO DRIVERS (first_name, last_name, nationality, date_of_birth) VALUES (%s, %s, %s, %s)",
                (d["first_name"], d["last_name"], d["nationality"], d["date_of_birth"])
            )
            inserted += 1

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "message": f"Import complete for {season} season",
            "inserted": inserted,
            "skipped": skipped,
            "total_from_api": len(api_drivers),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/constructors/<int:season>", methods=["POST"])
def import_constructors(season):
    """Fetch constructors from Jolpica API and insert new ones into the database."""
    try:
        from services.jolpica_client import fetch_constructors
        api_constructors = fetch_constructors(season)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch from Jolpica API: {str(e)}"}), 502

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        inserted = 0
        skipped = 0

        for c in api_constructors:
            cur.execute("SELECT constructor_id FROM CONSTRUCTORS WHERE name = %s", (c["name"],))
            if cur.fetchone():
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO CONSTRUCTORS (name, nationality, base_location) VALUES (%s, %s, %s)",
                (c["name"], c["nationality"], c["base_location"])
            )
            inserted += 1

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "message": f"Import complete for {season} season",
            "inserted": inserted,
            "skipped": skipped,
            "total_from_api": len(api_constructors),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/circuits/<int:season>", methods=["POST"])
def import_circuits(season):
    """Fetch circuits from Jolpica API and insert new ones into the database.
    Note: length_km and number_of_turns are set to 0 (API does not provide them).
    """
    try:
        from services.jolpica_client import fetch_circuits
        api_circuits = fetch_circuits(season)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch from Jolpica API: {str(e)}"}), 502

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        inserted = 0
        skipped = 0

        for c in api_circuits:
            cur.execute("SELECT circuit_id FROM CIRCUITS WHERE name = %s", (c["name"],))
            if cur.fetchone():
                skipped += 1
                continue
            cur.execute(
                "INSERT INTO CIRCUITS (name, country, city, length_km, number_of_turns) VALUES (%s, %s, %s, %s, %s)",
                (c["name"], c["country"], c["city"], c["length_km"], c["number_of_turns"])
            )
            inserted += 1

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "message": f"Import complete for {season} season",
            "inserted": inserted,
            "skipped": skipped,
            "total_from_api": len(api_circuits),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/races/<int:season>", methods=["POST"])
def import_races(season):
    """Fetch race schedule from Jolpica API and insert new races.
    Circuits are created automatically if they don't exist.
    Note: total_laps is set to 0 (use /api/import/results to update it).
    """
    try:
        from services.jolpica_client import fetch_races
        api_races = fetch_races(season)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch from Jolpica API: {str(e)}"}), 502

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        inserted = 0
        skipped = 0

        for r in api_races:
            # Find or create circuit
            cur.execute("SELECT circuit_id FROM CIRCUITS WHERE name = %s", (r["circuit_name"],))
            circuit_row = cur.fetchone()
            if circuit_row:
                circuit_id = circuit_row["circuit_id"]
            else:
                cur.execute(
                    "INSERT INTO CIRCUITS (name, country, city, length_km, number_of_turns) VALUES (%s, %s, %s, %s, %s)",
                    (r["circuit_name"], "Unknown", "Unknown", 0.000, 0)
                )
                circuit_id = cur.lastrowid

            # Check if race already exists
            cur.execute(
                "SELECT race_id FROM RACES WHERE race_name = %s AND season_year = %s",
                (r["race_name"], r["season_year"])
            )
            if cur.fetchone():
                skipped += 1
                continue

            cur.execute(
                "INSERT INTO RACES (circuit_id, season_year, race_name, race_date, total_laps, round_number) VALUES (%s, %s, %s, %s, %s, %s)",
                (circuit_id, r["season_year"], r["race_name"], r["race_date"], r["total_laps"], r["round_number"])
            )
            inserted += 1

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "message": f"Import complete for {season} season",
            "inserted": inserted,
            "skipped": skipped,
            "total_from_api": len(api_races),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/results/<int:season>/<int:round_number>", methods=["POST"])
def import_race_results(season, round_number):
    """Fetch race results from Jolpica API and insert into the database.
    Automatically creates missing drivers, constructors, and the race entry.
    Also updates the race's total_laps.
    """
    try:
        from services.jolpica_client import fetch_race_results, fetch_races
        api_results, total_laps = fetch_race_results(season, round_number)
        if not api_results:
            return jsonify({"error": "No results found for this race"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to fetch from Jolpica API: {str(e)}"}), 502

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Find or create the race
        cur.execute(
            "SELECT race_id FROM RACES WHERE season_year = %s AND round_number = %s",
            (season, round_number)
        )
        race_row = cur.fetchone()
        if race_row:
            race_id = race_row["race_id"]
            # Update total_laps if we got it from results
            if total_laps > 0:
                cur.execute("UPDATE RACES SET total_laps = %s WHERE race_id = %s", (total_laps, race_id))
        else:
            # Need to import the race first — fetch race schedule for this round
            try:
                api_races = fetch_races(season)
                race_info = None
                for r in api_races:
                    if r["round_number"] == round_number:
                        race_info = r
                        break
                if not race_info:
                    cur.close()
                    conn.close()
                    return jsonify({"error": f"Race round {round_number} not found in {season} schedule. Import races first."}), 404

                # Find or create circuit
                cur.execute("SELECT circuit_id FROM CIRCUITS WHERE name = %s", (race_info["circuit_name"],))
                circuit_row = cur.fetchone()
                if circuit_row:
                    circuit_id = circuit_row["circuit_id"]
                else:
                    cur.execute(
                        "INSERT INTO CIRCUITS (name, country, city, length_km, number_of_turns) VALUES (%s, %s, %s, %s, %s)",
                        (race_info["circuit_name"], "Unknown", "Unknown", 0.000, 0)
                    )
                    circuit_id = cur.lastrowid

                cur.execute(
                    "INSERT INTO RACES (circuit_id, season_year, race_name, race_date, total_laps, round_number) VALUES (%s, %s, %s, %s, %s, %s)",
                    (circuit_id, season, race_info["race_name"], race_info["race_date"], total_laps, round_number)
                )
                race_id = cur.lastrowid
            except Exception as e:
                cur.close()
                conn.close()
                return jsonify({"error": f"Failed to create race entry: {str(e)}"}), 500

        inserted = 0
        skipped = 0

        for r in api_results:
            # Find or create driver
            cur.execute(
                "SELECT driver_id FROM DRIVERS WHERE first_name = %s AND last_name = %s",
                (r["driver_first_name"], r["driver_last_name"])
            )
            driver_row = cur.fetchone()
            if driver_row:
                driver_id = driver_row["driver_id"]
            else:
                cur.execute(
                    "INSERT INTO DRIVERS (first_name, last_name, nationality, date_of_birth) VALUES (%s, %s, %s, %s)",
                    (r["driver_first_name"], r["driver_last_name"], r["driver_nationality"], r["driver_dob"])
                )
                driver_id = cur.lastrowid

            # Find or create constructor
            cur.execute("SELECT constructor_id FROM CONSTRUCTORS WHERE name = %s", (r["constructor_name"],))
            constructor_row = cur.fetchone()
            if constructor_row:
                constructor_id = constructor_row["constructor_id"]
            else:
                cur.execute(
                    "INSERT INTO CONSTRUCTORS (name, nationality, base_location) VALUES (%s, %s, %s)",
                    (r["constructor_name"], r["constructor_nationality"], "N/A")
                )
                constructor_id = cur.lastrowid

            # Check if result already exists for this race+driver
            cur.execute(
                "SELECT result_id FROM RACE_RESULTS WHERE race_id = %s AND driver_id = %s",
                (race_id, driver_id)
            )
            if cur.fetchone():
                skipped += 1
                continue

            cur.execute(
                """INSERT INTO RACE_RESULTS
                (race_id, driver_id, constructor_id, grid_position, finishing_position, points_scored, status, fastest_lap_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    race_id, driver_id, constructor_id,
                    r["grid_position"], r["finishing_position"],
                    r["points_scored"], r["status"], r["fastest_lap_time"],
                )
            )
            inserted += 1

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "message": f"Import complete for {season} Round {round_number}",
            "race_id": race_id,
            "inserted": inserted,
            "skipped": skipped,
            "total_from_api": len(api_results),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/import/weather", methods=["POST"])
def import_weather():
    """Fetch weather data from OpenF1 API and insert into WEATHER_CONDITIONS.

    Request body:
        race_id (int): The race to associate the weather with
        session_type (str): One of FP1, FP2, FP3, Qualifying, Sprint, Race
        session_key (int): The OpenF1 session key
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        missing = validate_required(data, ["race_id", "session_type", "session_key"])
        if missing:
            return jsonify({"error": f"Missing required field: {missing}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        from services.openf1_client import fetch_weather
        weather = fetch_weather(data["session_key"])
        if not weather:
            return jsonify({"error": "No weather data returned from OpenF1"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to fetch from OpenF1 API: {str(e)}"}), 502

    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        # Verify race exists
        cur.execute("SELECT race_id FROM RACES WHERE race_id = %s", (data["race_id"],))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Race not found"}), 404

        # Check for duplicate
        cur.execute(
            "SELECT weather_id FROM WEATHER_CONDITIONS WHERE race_id = %s AND session_type = %s",
            (data["race_id"], data["session_type"])
        )
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "Weather record already exists for this race and session type"}), 409

        cur.execute(
            """INSERT INTO WEATHER_CONDITIONS
            (race_id, session_type, temperature_celsius, humidity_percent, wind_speed_kmh, track_condition, rainfall_mm)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                data["race_id"], data["session_type"],
                weather["temperature_celsius"], weather["humidity_percent"],
                weather["wind_speed_kmh"], weather["track_condition"], weather["rainfall_mm"],
            )
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        conn.close()

        return jsonify({
            "message": "Weather data imported successfully from OpenF1",
            "weather_id": new_id,
            "data_summary": weather,
        }), 201
    except mysql.connector.IntegrityError as e:
        return jsonify({"error": f"Integrity error: {str(e)}"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    app.run(debug=True)