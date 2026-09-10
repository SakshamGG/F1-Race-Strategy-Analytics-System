# F1 Strategy Database — Backend

A Flask REST API backend for the F1 Strategy Database project (VIT Sem 3 — Database Systems).

Stores and manages Formula 1 race data including drivers, constructors, circuits, races, lap times, pit stops, weather conditions, and strategy notes. Integrates with two external F1 data APIs to populate the database.

---

## Setup

### 1. Activate the Virtual Environment

```powershell
cd backend
.\venv\Scripts\Activate
```

### 2. Install Dependencies

```powershell
pip install -r requirement.txt
```

**Dependencies:**
| Package | Purpose |
|---------|---------|
| Flask | Web framework |
| mysql-connector-python | MySQL database driver |
| python-dotenv | Load `.env` variables |
| flask-cors | Cross-origin request support |
| requests | External API HTTP calls |

### 3. Configure Environment Variables

Create/edit `backend/.env`:

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=f1_strategy_db
```

> **Note:** No API keys are needed. Both external APIs (Jolpica, OpenF1) are free and open.

### 4. Initialize the Database

```sql
-- Run in MySQL client:
SOURCE database/schema.sql;
SOURCE database/seed.sql;
```

### 5. Start the Server

```powershell
cd backend
.\venv\Scripts\python app.py
```

Server runs at: `http://127.0.0.1:5000`

---

## Database Schema

12 tables in `f1_strategy_db`:

| Table | Description |
|-------|-------------|
| DRIVERS | Driver profiles (name, nationality, DOB) |
| CONSTRUCTORS | F1 teams (name, nationality, base) |
| CIRCUITS | Race tracks (name, country, city, length, turns) |
| TYRE_COMPOUNDS | Tyre types (Soft, Medium, Hard, Inter, Wet) |
| ANALYSTS | System users with role-based access |
| RACES | Race events linked to circuits and seasons |
| DRIVER_CONTRACTS | Driver-team assignments per season |
| RACE_RESULTS | Finishing positions, points, fastest laps |
| LAP_TIMES | Individual lap times with sector splits |
| PIT_STOPS | Pit stop details with tyre changes |
| WEATHER_CONDITIONS | Session weather (temp, humidity, rainfall) |
| STRATEGY_NOTES | Analyst observations and recommendations |

---

## API Endpoints

### Health & Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/test-db` | Test database connection |

### CRUD Endpoints (all 12 entities)

Each entity supports full CRUD operations:

| Method | Pattern | Description |
|--------|---------|-------------|
| GET | `/api/<entity>` | List all records |
| GET | `/api/<entity>/<id>` | Get single record |
| POST | `/api/<entity>` | Create new record |
| PUT | `/api/<entity>/<id>` | Update existing record |
| DELETE | `/api/<entity>/<id>` | Delete record |

**Entity URL paths:**

| Entity | URL Path |
|--------|----------|
| Drivers | `/api/drivers` |
| Constructors | `/api/constructors` |
| Circuits | `/api/circuits` |
| Tyre Compounds | `/api/tyre-compounds` |
| Analysts | `/api/analysts` |
| Races | `/api/races` |
| Driver Contracts | `/api/driver-contracts` |
| Race Results | `/api/race-results` |
| Lap Times | `/api/lap-times` |
| Pit Stops | `/api/pit-stops` |
| Weather Conditions | `/api/weather` |
| Strategy Notes | `/api/strategy-notes` |

### External API Import Endpoints

| Method | Endpoint | Source API | Target Table |
|--------|----------|-----------|--------------|
| POST | `/api/import/drivers/<season>` | Jolpica | DRIVERS |
| POST | `/api/import/constructors/<season>` | Jolpica | CONSTRUCTORS |
| POST | `/api/import/circuits/<season>` | Jolpica | CIRCUITS |
| POST | `/api/import/races/<season>` | Jolpica | RACES + CIRCUITS |
| POST | `/api/import/results/<season>/<round>` | Jolpica | RACE_RESULTS + DRIVERS + CONSTRUCTORS |
| POST | `/api/import/weather` | OpenF1 | WEATHER_CONDITIONS |

---

## Request & Response Examples

### POST /api/drivers — Create a driver

**Request:**
```json
{
    "first_name": "Fernando",
    "last_name": "Alonso",
    "nationality": "Spanish",
    "date_of_birth": "1981-07-29"
}
```

**Response (201):**
```json
{
    "message": "Driver added successfully",
    "driver_id": 8
}
```

### PUT /api/drivers/8 — Update a driver (partial update supported)

**Request:**
```json
{
    "nationality": "Spanish-Basque"
}
```

**Response (200):**
```json
{
    "message": "Driver updated successfully"
}
```

### POST /api/import/drivers/2024 — Import drivers from Jolpica API

**Request:** No body needed — season is in the URL.

**Response (200):**
```json
{
    "message": "Import complete for 2024 season",
    "inserted": 20,
    "skipped": 5,
    "total_from_api": 25
}
```

### POST /api/import/weather — Import weather from OpenF1 API

**Request:**
```json
{
    "race_id": 1,
    "session_type": "Race",
    "session_key": 11361
}
```

**Response (201):**
```json
{
    "message": "Weather data imported successfully from OpenF1",
    "weather_id": 6,
    "data_summary": {
        "temperature_celsius": 32.2,
        "humidity_percent": 37.7,
        "wind_speed_kmh": 1.3,
        "rainfall_mm": 0,
        "track_condition": "Dry"
    }
}
```

---

## External APIs

### Jolpica F1 API (Ergast successor)

- **URL:** `https://api.jolpi.ca/ergast/f1/`
- **Auth:** None (free, open)
- **Used for:** Drivers, Constructors, Circuits, Race schedules, Race results
- **Code:** `backend/services/jolpica_client.py`

### OpenF1 API

- **URL:** `https://api.openf1.org/v1/`
- **Auth:** None (free for historical data)
- **Used for:** Weather data (temperature, humidity, wind, rainfall)
- **Code:** `backend/services/openf1_client.py`

### Data Flow

```
External F1 API (Jolpica / OpenF1)
       ↓
Flask Backend (services/ clients)
       ↓
Validation & Transformation
       ↓
MySQL Database (f1_strategy_db)
       ↓
REST API Endpoints
       ↓
Frontend / Client
```

---

## Project Structure

```
build/
├── .gitignore
├── README.md
├── database/
│   ├── schema.sql          # 12-table schema
│   └── seed.sql            # Sample data
└── backend/
    ├── .env                # DB credentials (not committed)
    ├── requirement.txt     # Python dependencies
    ├── database.py         # MySQL connection logic
    ├── app.py              # Flask app — all routes
    ├── services/
    │   ├── __init__.py
    │   ├── jolpica_client.py   # Jolpica F1 API client
    │   └── openf1_client.py    # OpenF1 API client
    └── venv/               # Python virtual environment
```

---

## Error Handling

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (missing fields, invalid JSON) |
| 404 | Record not found |
| 409 | Conflict (duplicate record, FK violation) |
| 500 | Internal server error |
| 502 | External API failure |

---

## Testing with PowerShell

```powershell
# Health check
Invoke-RestMethod -Uri "http://127.0.0.1:5000/"

# Get all drivers
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/drivers"

# Create a driver
$body = @{
    first_name = "Test"
    last_name = "Driver"
    nationality = "Indian"
    date_of_birth = "2000-01-01"
} | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/drivers" -Method POST -ContentType "application/json" -Body $body

# Import 2024 season drivers from Jolpica API
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/import/drivers/2024" -Method POST
```
