// ==============================================================================
// F1 Strategy Database - Frontend Script
// ==============================================================================
// All API calls use this single base URL
const API_BASE_URL = 'http://127.0.0.1:5000';

// ==============================================================================
// UTILITIES
// ==============================================================================

async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaults = {
        headers: { 'Content-Type': 'application/json' },
    };
    const config = { ...defaults, ...options };
    if (options.headers) {
        config.headers = { ...defaults.headers, ...options.headers };
    }

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        config.signal = controller.signal;

        const response = await fetch(url, config);
        clearTimeout(timeout);

        let data;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            data = await response.text();
        }

        if (!response.ok) {
            const errorMsg = (typeof data === 'object' && data.error) ? data.error : `HTTP ${response.status}`;
            throw new Error(errorMsg);
        }
        return data;
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new Error('Request timed out. Make sure the Flask backend is running.');
        }
        if (err.message === 'Failed to fetch' || err.message.includes('NetworkError')) {
            throw new Error('Backend connection failed. Make sure Flask is running on port 5000.');
        }
        throw err;
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function showModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function hideModal(id) {
    document.getElementById(id).classList.add('hidden');
    // Reset forms inside
    const form = document.getElementById(id).querySelector('form');
    if (form) form.reset();
    // Reset edit IDs
    const editInput = document.getElementById(id).querySelector('input[type=hidden]');
    if (editInput) editInput.value = '';
}

function hideElement(id) {
    document.getElementById(id).classList.add('hidden');
}

function showElement(id) {
    document.getElementById(id).classList.remove('hidden');
}

function setLoading(btnId, loading) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    if (loading) {
        btn.disabled = true;
        btn._origText = btn.textContent;
        btn.textContent = 'Loading...';
    } else {
        btn.disabled = false;
        btn.textContent = btn._origText || btn.textContent;
    }
}

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
        return dateStr;
    }
}

function truncate(str, len = 60) {
    if (!str) return '—';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

// ==============================================================================
// NAVIGATION
// ==============================================================================

function navigateTo(sectionName) {
    // Update sidebar
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.section === sectionName) {
            item.classList.add('active');
        }
    });
    // Update sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    const target = document.getElementById(`section-${sectionName}`);
    if (target) target.classList.add('active');

    // Load data for the section
    loadSectionData(sectionName);
}

// Sidebar click handlers
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo(item.dataset.section);
    });
});

function loadSectionData(section) {
    switch (section) {
        case 'dashboard': loadDashboard(); break;
        case 'drivers': loadDrivers(); break;
        case 'constructors': loadConstructors(); break;
        case 'races': loadRaces(); break;
        case 'notes': loadNotes(); break;
    }
}

// ==============================================================================
// BACKEND STATUS CHECK
// ==============================================================================

async function checkBackendStatus() {
    const dot = document.getElementById('statusDot');
    const text = document.getElementById('statusText');
    try {
        const response = await apiFetch('/test-db');
        dot.className = 'status-dot connected';
        text.textContent = 'Backend Connected';
    } catch {
        dot.className = 'status-dot disconnected';
        text.textContent = 'Backend Disconnected';
    }
}

// ==============================================================================
// DASHBOARD
// ==============================================================================

async function loadDashboard() {
    const endpoints = [
        { id: 'stat-drivers', endpoint: '/api/drivers' },
        { id: 'stat-constructors', endpoint: '/api/constructors' },
        { id: 'stat-races', endpoint: '/api/races' },
        { id: 'stat-circuits', endpoint: '/api/circuits' },
        { id: 'stat-tyres', endpoint: '/api/tyre-compounds' },
        { id: 'stat-notes', endpoint: '/api/strategy-notes' },
    ];

    for (const item of endpoints) {
        try {
            const data = await apiFetch(item.endpoint);
            document.getElementById(item.id).textContent = Array.isArray(data) ? data.length : '0';
        } catch {
            document.getElementById(item.id).textContent = '—';
        }
    }
}

// ==============================================================================
// DRIVERS CRUD
// ==============================================================================

async function loadDrivers() {
    const tbody = document.getElementById('driversBody');
    tbody.innerHTML = '<tr><td colspan="6" class="text-center"><span class="spinner-small"></span> Loading...</td></tr>';
    try {
        const drivers = await apiFetch('/api/drivers');
        if (!drivers.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No drivers found. Add one or import from API.</td></tr>';
            return;
        }
        tbody.innerHTML = drivers.map(d => `
            <tr>
                <td>${d.driver_id}</td>
                <td>${escapeHtml(d.first_name)}</td>
                <td>${escapeHtml(d.last_name)}</td>
                <td>${escapeHtml(d.nationality)}</td>
                <td>${formatDate(d.date_of_birth)}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="editDriver(${d.driver_id})">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteDriver(${d.driver_id}, '${escapeHtml(d.first_name)} ${escapeHtml(d.last_name)}')">Delete</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function submitDriver(e) {
    e.preventDefault();
    const editId = document.getElementById('driverEditId').value;
    const payload = {
        first_name: document.getElementById('driverFirstName').value.trim(),
        last_name: document.getElementById('driverLastName').value.trim(),
        nationality: document.getElementById('driverNationality').value.trim(),
        date_of_birth: document.getElementById('driverDOB').value,
    };

    setLoading('btnSubmitDriver', true);
    try {
        if (editId) {
            await apiFetch(`/api/drivers/${editId}`, { method: 'PUT', body: JSON.stringify(payload) });
            showToast('Driver updated successfully!');
        } else {
            await apiFetch('/api/drivers', { method: 'POST', body: JSON.stringify(payload) });
            showToast('Driver added successfully!');
        }
        hideModal('driverModal');
        loadDrivers();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSubmitDriver', false);
    }
}

async function editDriver(id) {
    try {
        const driver = await apiFetch(`/api/drivers/${id}`);
        document.getElementById('driverEditId').value = id;
        document.getElementById('driverFirstName').value = driver.first_name;
        document.getElementById('driverLastName').value = driver.last_name;
        document.getElementById('driverNationality').value = driver.nationality;
        document.getElementById('driverDOB').value = driver.date_of_birth;
        document.getElementById('driverModalTitle').textContent = 'Edit Driver';
        showModal('driverModal');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteDriver(id, name) {
    if (!confirm(`Delete driver "${name}"? This cannot be undone.`)) return;
    try {
        await apiFetch(`/api/drivers/${id}`, { method: 'DELETE' });
        showToast('Driver deleted successfully!');
        loadDrivers();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ==============================================================================
// CONSTRUCTORS CRUD
// ==============================================================================

async function loadConstructors() {
    const tbody = document.getElementById('constructorsBody');
    tbody.innerHTML = '<tr><td colspan="5" class="text-center"><span class="spinner-small"></span> Loading...</td></tr>';
    try {
        const data = await apiFetch('/api/constructors');
        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No constructors found.</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(c => `
            <tr>
                <td>${c.constructor_id}</td>
                <td>${escapeHtml(c.name)}</td>
                <td>${escapeHtml(c.nationality)}</td>
                <td>${escapeHtml(c.base_location)}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="editConstructor(${c.constructor_id})">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteConstructor(${c.constructor_id}, '${escapeHtml(c.name)}')">Delete</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function submitConstructor(e) {
    e.preventDefault();
    const editId = document.getElementById('constructorEditId').value;
    const payload = {
        name: document.getElementById('constructorName').value.trim(),
        nationality: document.getElementById('constructorNationality').value.trim(),
        base_location: document.getElementById('constructorBase').value.trim(),
    };

    setLoading('btnSubmitConstructor', true);
    try {
        if (editId) {
            await apiFetch(`/api/constructors/${editId}`, { method: 'PUT', body: JSON.stringify(payload) });
            showToast('Constructor updated successfully!');
        } else {
            await apiFetch('/api/constructors', { method: 'POST', body: JSON.stringify(payload) });
            showToast('Constructor added successfully!');
        }
        hideModal('constructorModal');
        loadConstructors();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSubmitConstructor', false);
    }
}

async function editConstructor(id) {
    try {
        const c = await apiFetch(`/api/constructors/${id}`);
        document.getElementById('constructorEditId').value = id;
        document.getElementById('constructorName').value = c.name;
        document.getElementById('constructorNationality').value = c.nationality;
        document.getElementById('constructorBase').value = c.base_location;
        document.getElementById('constructorModalTitle').textContent = 'Edit Constructor';
        showModal('constructorModal');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteConstructor(id, name) {
    if (!confirm(`Delete constructor "${name}"? This cannot be undone.`)) return;
    try {
        await apiFetch(`/api/constructors/${id}`, { method: 'DELETE' });
        showToast('Constructor deleted successfully!');
        loadConstructors();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ==============================================================================
// RACES & RACE RESULTS
// ==============================================================================

async function loadRaces() {
    const tbody = document.getElementById('racesBody');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center"><span class="spinner-small"></span> Loading...</td></tr>';
    try {
        const races = await apiFetch('/api/races');
        if (!races.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No races found. Import from API.</td></tr>';
            return;
        }
        tbody.innerHTML = races.map(r => `
            <tr>
                <td>${r.race_id}</td>
                <td>${escapeHtml(r.race_name)}</td>
                <td>${r.season_year}</td>
                <td>${r.round_number}</td>
                <td>${formatDate(r.race_date)}</td>
                <td>${r.total_laps}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="viewRaceResults(${r.race_id}, '${escapeHtml(r.race_name)}')">View Results</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function viewRaceResults(raceId, raceName) {
    const panel = document.getElementById('raceResultsPanel');
    const title = document.getElementById('raceResultsTitle');
    const tbody = document.getElementById('raceResultsBody');

    title.textContent = `Race Results — ${raceName}`;
    tbody.innerHTML = '<tr><td colspan="7" class="text-center"><span class="spinner-small"></span> Loading...</td></tr>';
    showElement('raceResultsPanel');

    try {
        const data = await apiFetch(`/api/races/${raceId}/results`);
        const results = data.classification || [];
        if (!results.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No results found for this race.</td></tr>';
            return;
        }
        tbody.innerHTML = results.map(r => `
            <tr>
                <td><strong>${r.finishing_position || '—'}</strong></td>
                <td>${escapeHtml(r.driver_name)}</td>
                <td>${escapeHtml(r.team_name)}</td>
                <td>${r.grid_position || '—'}</td>
                <td>${r.points_scored}</td>
                <td><span class="badge ${r.status === 'Finished' ? 'badge-success' : 'badge-warning'}">${escapeHtml(r.status)}</span></td>
                <td>${r.fastest_lap_time || '—'}</td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

// ==============================================================================
// STANDINGS
// ==============================================================================

async function loadStandings() {
    const season = document.getElementById('standingsSeason').value;
    if (!season) { showToast('Please enter a season year', 'error'); return; }

    setLoading('btnLoadStandings', true);
    try {
        // Load driver standings
        const driverData = await apiFetch(`/api/standings/drivers/${season}`);
        const dBody = document.getElementById('driverStandingsBody');
        if (!driverData.length) {
            dBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No standings data for this season.</td></tr>';
        } else {
            dBody.innerHTML = driverData.map(d => `
                <tr>
                    <td><strong>${d.position}</strong></td>
                    <td>${escapeHtml(d.driver_name)}</td>
                    <td>${escapeHtml(d.team_name)}</td>
                    <td><strong>${d.total_points}</strong></td>
                    <td>${d.wins}</td>
                    <td>${d.podiums}</td>
                </tr>
            `).join('');
        }

        // Load constructor standings
        const constData = await apiFetch(`/api/standings/constructors/${season}`);
        const cBody = document.getElementById('constructorStandingsBody');
        if (!constData.length) {
            cBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No standings data for this season.</td></tr>';
        } else {
            cBody.innerHTML = constData.map(c => `
                <tr>
                    <td><strong>${c.position}</strong></td>
                    <td>${escapeHtml(c.team_name)}</td>
                    <td><strong>${c.total_points}</strong></td>
                    <td>${c.wins}</td>
                    <td>${c.podiums}</td>
                </tr>
            `).join('');
        }
        showToast(`Standings loaded for ${season} season`);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnLoadStandings', false);
    }
}

function switchStandingsTab(tab) {
    document.querySelectorAll('.tabs .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));

    if (tab === 'drivers') {
        document.querySelector('.tabs .tab-btn:first-child').classList.add('active');
        document.getElementById('tab-driverStandings').classList.add('active');
    } else {
        document.querySelector('.tabs .tab-btn:last-child').classList.add('active');
        document.getElementById('tab-constructorStandings').classList.add('active');
    }
}

// ==============================================================================
// STRATEGY ANALYTICS
// ==============================================================================

async function runTyreDegradation() {
    setLoading('btnTyreDeg', true);
    const resultBox = document.getElementById('tyreDegResult');
    try {
        const raceId = document.getElementById('tyreDegRaceId').value;
        const endpoint = raceId ? `/api/analytics/tyre-degradation?race_id=${raceId}` : '/api/analytics/tyre-degradation';
        const data = await apiFetch(endpoint);
        resultBox.innerHTML = renderJsonResult(data);
        showElement('tyreDegResult');
        showToast('Tyre degradation analysis complete');
    } catch (err) {
        resultBox.innerHTML = `<p class="text-error">${escapeHtml(err.message)}</p>`;
        showElement('tyreDegResult');
    } finally {
        setLoading('btnTyreDeg', false);
    }
}

async function runStrategySimulation() {
    const raceId = document.getElementById('simRaceId').value;
    const driverId = document.getElementById('simDriverId').value;
    if (!raceId || !driverId) { showToast('Please enter Race ID and Driver ID', 'error'); return; }

    setLoading('btnSimStrategy', true);
    const resultBox = document.getElementById('simStrategyResult');
    try {
        const data = await apiFetch(`/api/analytics/simulate-strategy?race_id=${raceId}&driver_id=${driverId}`);
        let html = '<h4>Strategy Simulation Results</h4>';
        if (data.simulation_results && data.simulation_results.length) {
            html += data.simulation_results.map(s => `
                <div class="result-card ${s.is_recommended ? 'recommended' : ''}">
                    <h4>${escapeHtml(s.strategy_option)} ${s.is_recommended ? '⭐ Recommended' : ''}</h4>
                    <p><strong>Tyre Sequence:</strong> ${escapeHtml(s.tyre_sequence)}</p>
                    <p><strong>Stops:</strong> ${s.stops_count}</p>
                    <p><strong>Pit Window:</strong> ${escapeHtml(s.pit_window_laps)}</p>
                    <p><strong>Projected Time:</strong> ${s.projected_race_time_seconds}s</p>
                    <p><strong>Rationale:</strong> ${escapeHtml(s.strategic_rationale)}</p>
                </div>
            `).join('');
        } else {
            html += '<p class="text-muted">No simulation data returned.</p>';
        }
        resultBox.innerHTML = html;
        showElement('simStrategyResult');
        showToast('Strategy simulation complete');
    } catch (err) {
        resultBox.innerHTML = `<p class="text-error">${escapeHtml(err.message)}</p>`;
        showElement('simStrategyResult');
    } finally {
        setLoading('btnSimStrategy', false);
    }
}

async function runUndercutSimulation() {
    const raceId = document.getElementById('undercutRaceId').value;
    const chaserId = document.getElementById('undercutChaserId').value;
    const leaderId = document.getElementById('undercutLeaderId').value;
    const pitLap = document.getElementById('undercutPitLap').value;
    if (!raceId || !chaserId || !leaderId || !pitLap) {
        showToast('Please fill in all fields', 'error'); return;
    }

    setLoading('btnUndercut', true);
    const resultBox = document.getElementById('undercutResult');
    try {
        const data = await apiFetch(`/api/analytics/undercut-simulation?race_id=${raceId}&chaser_driver_id=${chaserId}&leader_driver_id=${leaderId}&pit_lap=${pitLap}`);
        resultBox.innerHTML = renderJsonResult(data);
        showElement('undercutResult');
        showToast('Undercut simulation complete');
    } catch (err) {
        resultBox.innerHTML = `<p class="text-error">${escapeHtml(err.message)}</p>`;
        showElement('undercutResult');
    } finally {
        setLoading('btnUndercut', false);
    }
}

async function runStintComparison() {
    const raceId = document.getElementById('stintRaceId').value;
    const d1 = document.getElementById('stintDriver1Id').value;
    const d2 = document.getElementById('stintDriver2Id').value;
    if (!raceId || !d1 || !d2) {
        showToast('Please fill in all fields', 'error'); return;
    }

    setLoading('btnStint', true);
    const resultBox = document.getElementById('stintResult');
    try {
        const data = await apiFetch(`/api/analytics/stint-comparison?race_id=${raceId}&driver1_id=${d1}&driver2_id=${d2}`);
        resultBox.innerHTML = renderJsonResult(data);
        showElement('stintResult');
        showToast('Stint comparison complete');
    } catch (err) {
        resultBox.innerHTML = `<p class="text-error">${escapeHtml(err.message)}</p>`;
        showElement('stintResult');
    } finally {
        setLoading('btnStint', false);
    }
}

function renderJsonResult(data) {
    if (typeof data === 'string') return `<pre>${escapeHtml(data)}</pre>`;

    let html = '<div class="json-result">';
    for (const [key, value] of Object.entries(data)) {
        if (Array.isArray(value)) {
            html += `<p><strong>${escapeHtml(key)}:</strong></p>`;
            if (value.length === 0) {
                html += '<p class="text-muted">No data</p>';
            } else if (typeof value[0] === 'object') {
                html += '<div class="table-container"><table class="data-table"><thead><tr>';
                const keys = Object.keys(value[0]);
                keys.forEach(k => html += `<th>${escapeHtml(k)}</th>`);
                html += '</tr></thead><tbody>';
                value.forEach(row => {
                    html += '<tr>';
                    keys.forEach(k => html += `<td>${escapeHtml(String(row[k] ?? '—'))}</td>`);
                    html += '</tr>';
                });
                html += '</tbody></table></div>';
            } else {
                html += `<p>${value.map(v => escapeHtml(String(v))).join(', ')}</p>`;
            }
        } else if (typeof value === 'object' && value !== null) {
            html += `<p><strong>${escapeHtml(key)}:</strong></p>`;
            html += '<div class="nested-result">';
            for (const [k2, v2] of Object.entries(value)) {
                html += `<p><strong>${escapeHtml(k2)}:</strong> ${escapeHtml(String(v2 ?? '—'))}</p>`;
            }
            html += '</div>';
        } else {
            html += `<p><strong>${escapeHtml(key)}:</strong> ${escapeHtml(String(value ?? '—'))}</p>`;
        }
    }
    html += '</div>';
    return html;
}

// ==============================================================================
// IMPORT DATA
// ==============================================================================

async function importData(type) {
    const seasonInput = document.getElementById(`import${capitalize(type)}Season`);
    const season = seasonInput ? seasonInput.value : '2024';
    const btnId = `btnImport${capitalize(type)}`;
    const resultId = `import${capitalize(type)}Result`;

    setLoading(btnId, true);
    try {
        const data = await apiFetch(`/api/import/${type}/${season}`, { method: 'POST' });
        const resultBox = document.getElementById(resultId);
        resultBox.innerHTML = `
            <p class="text-success">✅ ${escapeHtml(data.message)}</p>
            <p><strong>Inserted:</strong> ${data.inserted}</p>
            <p><strong>Skipped:</strong> ${data.skipped}</p>
            <p><strong>Total from API:</strong> ${data.total_from_api}</p>
        `;
        showElement(resultId);
        showToast(`${capitalize(type)} imported successfully!`);
        loadDashboard();
    } catch (err) {
        const resultBox = document.getElementById(resultId);
        resultBox.innerHTML = `<p class="text-error">❌ ${escapeHtml(err.message)}</p>`;
        showElement(resultId);
        showToast(err.message, 'error');
    } finally {
        setLoading(btnId, false);
    }
}

async function importResults() {
    const season = document.getElementById('importResultsSeason').value;
    const round = document.getElementById('importResultsRound').value;
    if (!season || !round) { showToast('Please enter season and round', 'error'); return; }

    setLoading('btnImportResults', true);
    try {
        const data = await apiFetch(`/api/import/results/${season}/${round}`, { method: 'POST' });
        const resultBox = document.getElementById('importResultsResult');
        resultBox.innerHTML = `
            <p class="text-success">✅ ${escapeHtml(data.message)}</p>
            <p><strong>Inserted:</strong> ${data.inserted}</p>
            <p><strong>Skipped:</strong> ${data.skipped}</p>
            <p><strong>Total from API:</strong> ${data.total_from_api}</p>
        `;
        showElement('importResultsResult');
        showToast('Race results imported!');
        loadDashboard();
    } catch (err) {
        const resultBox = document.getElementById('importResultsResult');
        resultBox.innerHTML = `<p class="text-error">❌ ${escapeHtml(err.message)}</p>`;
        showElement('importResultsResult');
        showToast(err.message, 'error');
    } finally {
        setLoading('btnImportResults', false);
    }
}

async function importLaps() {
    const season = document.getElementById('importLapsSeason').value;
    const round = document.getElementById('importLapsRound').value;
    if (!season || !round) { showToast('Please enter season and round', 'error'); return; }

    setLoading('btnImportLaps', true);
    try {
        const data = await apiFetch(`/api/import/laps/${season}/${round}`, { method: 'POST' });
        const resultBox = document.getElementById('importLapsResult');
        resultBox.innerHTML = `
            <p class="text-success">✅ ${escapeHtml(data.message)}</p>
            <p><strong>Inserted:</strong> ${data.inserted}</p>
            <p><strong>Skipped:</strong> ${data.skipped}</p>
            <p><strong>Total from API:</strong> ${data.total_from_api}</p>
        `;
        showElement('importLapsResult');
        showToast('Lap times imported!');
    } catch (err) {
        const resultBox = document.getElementById('importLapsResult');
        resultBox.innerHTML = `<p class="text-error">❌ ${escapeHtml(err.message)}</p>`;
        showElement('importLapsResult');
        showToast(err.message, 'error');
    } finally {
        setLoading('btnImportLaps', false);
    }
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// ==============================================================================
// STRATEGY NOTES
// ==============================================================================

async function loadNotes() {
    const tbody = document.getElementById('notesBody');
    tbody.innerHTML = '<tr><td colspan="8" class="text-center"><span class="spinner-small"></span> Loading...</td></tr>';
    try {
        const notes = await apiFetch('/api/strategy-notes');
        if (!notes.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No strategy notes found.</td></tr>';
            return;
        }
        tbody.innerHTML = notes.map(n => `
            <tr>
                <td>${n.note_id}</td>
                <td>${n.race_id}</td>
                <td>${n.analyst_id}</td>
                <td>${n.driver_id}</td>
                <td title="${escapeHtml(n.note_text)}">${truncate(n.note_text, 40)}</td>
                <td><span class="badge badge-${getNoteTypeClass(n.note_type)}">${escapeHtml(n.note_type)}</span></td>
                <td>${formatDate(n.created_at)}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="editNote(${n.note_id})">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteNote(${n.note_id})">Delete</button>
                    <button class="btn btn-sm btn-secondary" onclick="viewNoteAudit(${n.note_id})">Audit</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

function getNoteTypeClass(type) {
    switch (type) {
        case 'Observation': return 'info';
        case 'Recommendation': return 'success';
        case 'Post-Race Review': return 'warning';
        default: return 'info';
    }
}

async function submitNote(e) {
    e.preventDefault();
    const editId = document.getElementById('noteEditId').value;
    const payload = {
        race_id: parseInt(document.getElementById('noteRaceId').value),
        analyst_id: parseInt(document.getElementById('noteAnalystId').value),
        driver_id: parseInt(document.getElementById('noteDriverId').value),
        note_type: document.getElementById('noteType').value,
        note_text: document.getElementById('noteText').value.trim(),
    };

    setLoading('btnSubmitNote', true);
    try {
        if (editId) {
            await apiFetch(`/api/strategy-notes/${editId}`, { method: 'PUT', body: JSON.stringify(payload) });
            showToast('Strategy note updated successfully!');
        } else {
            await apiFetch('/api/strategy-notes', { method: 'POST', body: JSON.stringify(payload) });
            showToast('Strategy note added successfully!');
        }
        hideModal('noteModal');
        loadNotes();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSubmitNote', false);
    }
}

async function editNote(id) {
    try {
        const n = await apiFetch(`/api/strategy-notes/${id}`);
        document.getElementById('noteEditId').value = id;
        document.getElementById('noteRaceId').value = n.race_id;
        document.getElementById('noteAnalystId').value = n.analyst_id;
        document.getElementById('noteDriverId').value = n.driver_id;
        document.getElementById('noteType').value = n.note_type;
        document.getElementById('noteText').value = n.note_text;
        document.getElementById('noteModalTitle').textContent = 'Edit Strategy Note';
        showModal('noteModal');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteNote(id) {
    if (!confirm('Delete this strategy note?')) return;
    try {
        await apiFetch(`/api/strategy-notes/${id}`, { method: 'DELETE' });
        showToast('Strategy note deleted!');
        loadNotes();
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function viewNoteAudit(noteId) {
    const panel = document.getElementById('auditLogPanel');
    const tbody = document.getElementById('auditLogBody');
    tbody.innerHTML = '<tr><td colspan="9" class="text-center"><span class="spinner-small"></span> Loading...</td></tr>';
    showElement('auditLogPanel');

    try {
        const data = await apiFetch(`/api/strategy-notes/${noteId}/audit`);
        const logs = data.history || [];
        if (!logs.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No audit records found.</td></tr>';
            return;
        }
        tbody.innerHTML = logs.map(l => `
            <tr>
                <td>${l.audit_id}</td>
                <td><span class="badge badge-${l.action_type === 'INSERT' ? 'success' : l.action_type === 'DELETE' ? 'danger' : 'warning'}">${l.action_type}</span></td>
                <td>${l.note_id}</td>
                <td>${l.race_id}</td>
                <td>${l.driver_id}</td>
                <td>${truncate(l.old_note_text, 30)}</td>
                <td>${truncate(l.new_note_text, 30)}</td>
                <td>${escapeHtml(l.changed_by)}</td>
                <td>${formatDate(l.changed_at)}</td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function loadAuditLog() {
    const panel = document.getElementById('auditLogPanel');
    const tbody = document.getElementById('auditLogBody');
    tbody.innerHTML = '<tr><td colspan="9" class="text-center"><span class="spinner-small"></span> Loading...</td></tr>';
    showElement('auditLogPanel');

    try {
        const data = await apiFetch('/api/strategy-notes/audit?limit=50');
        const logs = data.audit_logs || [];
        if (!logs.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No audit records found. Create, edit, or delete a note to generate audit entries.</td></tr>';
            return;
        }
        tbody.innerHTML = logs.map(l => `
            <tr>
                <td>${l.audit_id}</td>
                <td><span class="badge badge-${l.action_type === 'INSERT' ? 'success' : l.action_type === 'DELETE' ? 'danger' : 'warning'}">${l.action_type}</span></td>
                <td>${l.note_id}</td>
                <td>${escapeHtml(l.race_name || l.race_id)}</td>
                <td>${escapeHtml(l.driver_name || l.driver_id)}</td>
                <td>${truncate(l.old_note_text, 30)}</td>
                <td>${truncate(l.new_note_text, 30)}</td>
                <td>${escapeHtml(l.changed_by)}</td>
                <td>${formatDate(l.changed_at)}</td>
            </tr>
        `).join('');
        showToast('Audit log loaded');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

// ==============================================================================
// DATABASE FEATURES (Stored Procedures)
// ==============================================================================

async function runRecalculateStandings() {
    const season = prompt('Enter season year to recalculate:', '2024');
    if (!season) return;

    setLoading('btnRecalculate', true);
    const resultBox = document.getElementById('dbFeatureResult');
    try {
        const data = await apiFetch(`/api/standings/recalculate/${season}`, { method: 'POST' });
        resultBox.innerHTML = renderJsonResult(data);
        showElement('dbFeatureResult');
        showToast(`Standings recalculated for ${season}!`);
    } catch (err) {
        resultBox.innerHTML = `<p class="text-error">${escapeHtml(err.message)}</p>`;
        showElement('dbFeatureResult');
        showToast(err.message, 'error');
    } finally {
        setLoading('btnRecalculate', false);
    }
}

async function runValidateTyreRules() {
    const raceId = prompt('Enter Race ID to validate:', '1');
    if (!raceId) return;

    setLoading('btnValidateTyre', true);
    const resultBox = document.getElementById('dbFeatureResult');
    try {
        const data = await apiFetch(`/api/races/${raceId}/validate-tyre-rules`);
        resultBox.innerHTML = renderJsonResult(data);
        showElement('dbFeatureResult');
        showToast('Tyre rule validation complete!');
    } catch (err) {
        resultBox.innerHTML = `<p class="text-error">${escapeHtml(err.message)}</p>`;
        showElement('dbFeatureResult');
        showToast(err.message, 'error');
    } finally {
        setLoading('btnValidateTyre', false);
    }
}

// ==============================================================================
// INITIALIZATION
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
    checkBackendStatus();
    loadDashboard();
    // Re-check status every 30s
    setInterval(checkBackendStatus, 30000);
});
