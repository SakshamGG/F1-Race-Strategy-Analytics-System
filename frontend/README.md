# F1 Strategy Database - Frontend

## Overview
A clean F1-themed dashboard frontend that connects to the Flask REST API backend to demonstrate the F1 Strategy Database project.

## Prerequisites
- MySQL Server running with the `f1_strategy_db` database initialized
- Flask backend running on `http://127.0.0.1:5000`
- Python 3.x installed

## Quick Start (Windows PowerShell)

### Step 1: Start MySQL
Ensure your MySQL server is running.

### Step 2: Start the Flask Backend
```powershell
cd c:\Users\gsaks\OneDrive\Documents\VIT\Sem 3\Database\Project\build\backend
.\venv\Scripts\Activate
python app.py
```
The backend will start at `http://127.0.0.1:5000`.

### Step 3: Start the Frontend Server
Open a **new** PowerShell window:
```powershell
cd "c:\Users\gsaks\OneDrive\Documents\VIT\Sem 3\Database\Project\build\frontend"
python -m http.server 5500
```

### Step 4: Open Browser
Navigate to: **http://127.0.0.1:5500**

### Step 5: Verify Connection
Look for the green status indicator in the sidebar:
- 🟢 **Backend Connected** = Everything is working
- 🔴 **Backend Disconnected** = Check that Flask is running

## Project Structure
```
frontend/
├── index.html      # Main dashboard HTML
├── style.css       # F1-themed dark stylesheet
├── script.js       # All frontend logic and API calls
└── README.md       # This file
```

## Features Demonstrated
1. ✅ CRUD Operations (Drivers, Constructors, Circuits, etc.)
2. ✅ Foreign Key Relationships
3. ✅ JOIN Queries (Race Results, Standings)
4. ✅ Database Views
5. ✅ Triggers (Audit Log for Strategy Notes)
6. ✅ Stored Procedures (Recalculate Standings, Strategy Simulation)
7. ✅ External API Integration (Jolpica F1 API, OpenF1 API)

## Demo Flow
1. Dashboard → View summary statistics
2. Drivers → View, Create, Edit, Delete drivers
3. Races → View races, see detailed race results (JOINs)
4. Standings → View driver/constructor championship standings
5. Strategy Analytics → Run tyre degradation and strategy simulations
6. Import Data → Import real F1 data from external APIs
7. Strategy Notes → Create notes, view audit trail (Triggers)
8. Database Features → Demonstrate stored procedures and advanced features

## Technology Stack
- HTML5 / CSS3 / Vanilla JavaScript
- No build tools, frameworks, or npm dependencies required
- Connects to Flask REST API via fetch()

## Backend API Base URL
Configured in `script.js` as:
```javascript
const API_BASE_URL = 'http://127.0.0.1:5000';
```
Modify this if your backend runs on a different port.

## Troubleshooting
| Issue | Solution |
|-------|----------|
| Backend Disconnected | Ensure Flask is running: `python app.py` |
| CORS errors | Flask-CORS is already enabled in the backend |
| Empty tables | Run `seed.sql` to populate sample data |
| Import fails | Check internet connection for API access |
