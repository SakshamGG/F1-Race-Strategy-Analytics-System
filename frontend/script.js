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
    if (id === 'noteModal') {
        populateAllStrategyDropdowns();
    }
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

function parseSeasonInput(raw, defaultYear = '2026') {
    if (!raw) return defaultYear;
    const trimmed = String(raw).trim();
    if (!trimmed) return defaultYear;
    const lower = trimmed.toLowerCase();
    if (lower === 'all' || lower.includes('historical')) return 'all';
    const match = trimmed.match(/\b(19\d\d|20\d\d)\b/);
    if (match) return match[1];
    const num = parseInt(trimmed, 10);
    if (!isNaN(num) && num >= 1950 && num <= 2030) return String(num);
    return trimmed;
}

// ==============================================================================
// NAVIGATION & SIDEBAR
// ==============================================================================

function toggleSidebar(forceCollapse) {
    const isCurrentlyCollapsed = document.body.classList.contains('sidebar-collapsed');
    let shouldCollapse;
    if (typeof forceCollapse === 'boolean') {
        shouldCollapse = forceCollapse;
    } else {
        shouldCollapse = !isCurrentlyCollapsed;
    }

    if (shouldCollapse) {
        document.body.classList.add('sidebar-collapsed');
        localStorage.setItem('f1_sidebar_collapsed', 'true');
    } else {
        document.body.classList.remove('sidebar-collapsed');
        localStorage.setItem('f1_sidebar_collapsed', 'false');
    }
    updateSidebarToggleUI();
}

function updateSidebarToggleUI() {
    const isCollapsed = document.body.classList.contains('sidebar-collapsed');
    const menuBtn = document.getElementById('floatingNavBtn');
    if (menuBtn) {
        menuBtn.setAttribute('aria-expanded', String(!isCollapsed));
        const icon = menuBtn.querySelector('.glass-menu-icon');
        const text = menuBtn.querySelector('.glass-menu-text');
        if (icon) {
            icon.textContent = isCollapsed ? '☰' : '✕';
        }
        if (text) {
            text.textContent = isCollapsed ? 'Menu' : 'Close';
        }
    }
}

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

    // On mobile / small screens, auto-collapse sidebar upon navigation
    if (window.innerWidth <= 1024) {
        toggleSidebar(true);
    }

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
        case 'standings': loadStandings(); break;
        case 'replay': loadTrackReplay(); break;
        case 'pitwall': loadPitWall(); break;
        case 'analytics': populateAllStrategyDropdowns(); break;
        case 'notes': loadNotes(); populateAllStrategyDropdowns(); break;
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

async function loadDrivers(season) {
    if (season === undefined) {
        const filterElem = document.getElementById('driversSeasonFilter');
        season = filterElem ? filterElem.value : '2026';
    }
    season = parseSeasonInput(season, '2026');
    const isSeason = season && season !== 'all';
    const tbody = document.getElementById('driversBody');
    const subtitle = document.getElementById('driversSubtitle');
    const thRank = document.getElementById('thDriverRank');
    if (thRank) {
        thRank.textContent = isSeason ? 'Pos' : 'ID';
    }
    tbody.innerHTML = '<tr><td colspan="6" class="text-center"><span class="spinner-small"></span> Loading drivers...</td></tr>';
    try {
        const endpoint = isSeason ? `/api/drivers?season=${encodeURIComponent(season)}` : '/api/drivers';
        const drivers = await apiFetch(endpoint);
        if (subtitle) {
            subtitle.textContent = isSeason
                ? `Showing ${drivers.length} driver(s) active in the ${season} Formula 1 season (arranged by championship standings)`
                : `Showing all ${drivers.length} historical Formula 1 drivers`;
        }
        if (!drivers.length) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No drivers found for season ${escapeHtml(season)}.</td></tr>`;
            return;
        }

        // Ensure standings order in frontend if standing position is present
        if (isSeason) {
            drivers.sort((a, b) => {
                const posA = a.standing_position && a.standing_position > 0 ? a.standing_position : 9999;
                const posB = b.standing_position && b.standing_position > 0 ? b.standing_position : 9999;
                if (posA !== posB) return posA - posB;
                const ptsA = Number(a.standing_points) || 0;
                const ptsB = Number(b.standing_points) || 0;
                if (ptsA !== ptsB) return ptsB - ptsA;
                return (a.last_name || '').localeCompare(b.last_name || '');
            });
        }

        const targetYear = isSeason ? parseInt(season, 10) || 2024 : 2024;
        tbody.innerHTML = drivers.map(d => {
            const posBadge = (d.standing_position && isSeason)
                ? `<span class="badge ${d.standing_position === 1 ? 'badge-champion' : 'badge-rank'}" title="${season} Championship Rank: P${d.standing_position}">P${d.standing_position}${d.standing_position === 1 ? ' 🏆' : ''}</span>`
                : (isSeason ? `<span class="badge badge-rank-unranked" title="Unranked / 0 pts">—</span>` : `#${d.driver_id}`);

            const ptsInfo = (isSeason && d.standing_points !== null && d.standing_points !== undefined)
                ? `<br><small class="text-muted" style="font-size:11px;">${d.standing_points} pts${d.standing_wins ? ` • ${d.standing_wins}W` : ''}</small>`
                : '';

            const teamInfo = d.team_name ? `<br><small class="text-muted">🏎️ ${escapeHtml(d.team_name)}</small>` : '';

            return `
            <tr>
                <td><strong>${posBadge}</strong>${ptsInfo}</td>
                <td>${escapeHtml(d.first_name)}</td>
                <td><strong>${escapeHtml(d.last_name)}</strong>${teamInfo}</td>
                <td>${escapeHtml(d.nationality)}</td>
                <td>${formatDate(d.date_of_birth)}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="openPitwallFor(${targetYear}, 1, '${escapeHtml(d.last_name)}')">📡 Telemetry</button>
                    <button class="btn btn-sm btn-secondary" onclick="editDriver(${d.driver_id})">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteDriver(${d.driver_id}, '${escapeHtml(d.first_name)} ${escapeHtml(d.last_name)}')">Delete</button>
                </td>
            </tr>
            `;
        }).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

function onDriverSeasonChange() {
    const sel = document.getElementById('driversSeasonFilter');
    const season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    loadDrivers(season);
}

function loadCustomDriverYear() {
    onDriverSeasonChange();
}

async function syncDriversFromApi() {
    const sel = document.getElementById('driversSeasonFilter');
    let season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    if (season === 'all') season = '2026';

    setLoading('btnSyncDrivers', true);
    try {
        const data = await apiFetch(`/api/import/drivers/${season}`, { method: 'POST' });
        showToast(data.message || `Drivers synced for ${season} season!`);
        loadDrivers(season);
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSyncDrivers', false);
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

async function loadConstructors(season) {
    if (season === undefined) {
        const filterElem = document.getElementById('constructorsSeasonFilter');
        season = filterElem ? filterElem.value : '2026';
    }
    season = parseSeasonInput(season, '2026');
    const isSeason = season && season !== 'all';
    const tbody = document.getElementById('constructorsBody');
    const subtitle = document.getElementById('constructorsSubtitle');
    const thRank = document.getElementById('thConstructorRank');
    if (thRank) {
        thRank.textContent = isSeason ? 'Pos' : 'ID';
    }
    tbody.innerHTML = '<tr><td colspan="5" class="text-center"><span class="spinner-small"></span> Loading constructors...</td></tr>';
    try {
        const endpoint = isSeason ? `/api/constructors?season=${encodeURIComponent(season)}` : '/api/constructors';
        const data = await apiFetch(endpoint);
        if (subtitle) {
            subtitle.textContent = isSeason
                ? `Showing ${data.length} team(s) active in the ${season} Formula 1 season (arranged by constructors' standings)`
                : `Showing all ${data.length} historical Formula 1 constructors`;
        }
        if (!data.length) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No constructors found for season ${escapeHtml(season)}.</td></tr>`;
            return;
        }

        // Ensure standings order in frontend if standing position is present
        if (isSeason) {
            data.sort((a, b) => {
                const posA = a.standing_position && a.standing_position > 0 ? a.standing_position : 9999;
                const posB = b.standing_position && b.standing_position > 0 ? b.standing_position : 9999;
                if (posA !== posB) return posA - posB;
                const ptsA = Number(a.standing_points) || 0;
                const ptsB = Number(b.standing_points) || 0;
                if (ptsA !== ptsB) return ptsB - ptsA;
                return (a.name || '').localeCompare(b.name || '');
            });
        }

        tbody.innerHTML = data.map(c => {
            const posBadge = (c.standing_position && isSeason)
                ? `<span class="badge ${c.standing_position === 1 ? 'badge-champion' : 'badge-rank'}" title="${season} Constructors' Championship: P${c.standing_position}">P${c.standing_position}${c.standing_position === 1 ? ' 🏆' : ''}</span>`
                : (isSeason ? `<span class="badge badge-rank-unranked" title="Unranked / 0 pts">—</span>` : `#${c.constructor_id}`);

            const ptsInfo = (isSeason && c.standing_points !== null && c.standing_points !== undefined)
                ? `<br><small class="text-muted" style="font-size:11px;">${c.standing_points} pts${c.standing_wins ? ` • ${c.standing_wins}W` : ''}</small>`
                : '';

            return `
            <tr>
                <td><strong>${posBadge}</strong>${ptsInfo}</td>
                <td><strong>${escapeHtml(c.name)}</strong></td>
                <td>${escapeHtml(c.nationality)}</td>
                <td>📍 ${escapeHtml(c.base_location)}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="editConstructor(${c.constructor_id})">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteConstructor(${c.constructor_id}, '${escapeHtml(c.name)}')">Delete</button>
                </td>
            </tr>
            `;
        }).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

function onConstructorSeasonChange() {
    const sel = document.getElementById('constructorsSeasonFilter');
    const season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    loadConstructors(season);
}

function loadCustomConstructorYear() {
    onConstructorSeasonChange();
}

async function syncConstructorsFromApi() {
    const sel = document.getElementById('constructorsSeasonFilter');
    let season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    if (season === 'all') season = '2026';

    setLoading('btnSyncConstructors', true);
    try {
        const data = await apiFetch(`/api/import/constructors/${season}`, { method: 'POST' });
        showToast(data.message || `Constructors synced for ${season} season!`);
        loadConstructors(season);
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSyncConstructors', false);
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

let currentViewedRace = null;
let currentRacesMap = {};

async function loadRaces(season) {
    if (season === undefined) {
        const filterElem = document.getElementById('racesSeasonFilter');
        season = filterElem ? filterElem.value : '2026';
    }
    season = parseSeasonInput(season, '2026');
    const tbody = document.getElementById('racesBody');
    const subtitle = document.getElementById('racesSubtitle');
    currentViewedRace = null;
    currentRacesMap = {};
    tbody.innerHTML = '<tr><td colspan="7" class="text-center"><span class="spinner-small"></span> Loading races...</td></tr>';
    try {
        const endpoint = (season && season !== 'all') ? `/api/races?season=${encodeURIComponent(season)}` : '/api/races';
        const races = await apiFetch(endpoint);
        if (subtitle) {
            subtitle.textContent = (season && season !== 'all')
                ? `Showing ${races.length} race(s) in the ${season} Formula 1 season`
                : `Showing all ${races.length} historical Formula 1 races`;
        }
        if (!races.length) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No races found for season ${escapeHtml(season)}.</td></tr>`;
            return;
        }
        races.forEach(r => { currentRacesMap[r.race_id] = r; });
        tbody.innerHTML = races.map(r => `
            <tr id="race-row-${r.race_id}" data-race-id="${r.race_id}">
                <td>${r.race_id}</td>
                <td><strong>${escapeHtml(r.race_name)}</strong><br><small class="text-muted">📍 ${escapeHtml(r.circuit_name || 'Circuit')}${r.circuit_country ? ', ' + escapeHtml(r.circuit_country) : ''}</small></td>
                <td>${r.season_year}</td>
                <td>Round ${r.round_number}</td>
                <td>${formatDate(r.race_date)}</td>
                <td>${r.total_laps}</td>
                <td>
                    <button class="btn btn-sm btn-primary" id="btn-race-${r.race_id}" onclick="viewRaceResults(${r.race_id}, '${escapeHtml(r.race_name)}', ${r.season_year}, ${r.round_number})">View Results</button>
                    <button class="btn btn-sm btn-secondary" onclick="openTrackReplayFor(${r.season_year}, ${r.round_number}, 'Race')">🏎️ 2D Replay</button>
                    <button class="btn btn-sm btn-secondary" onclick="openPitwallFor(${r.season_year}, ${r.round_number}, '', ${r.race_id || 'null'})">📡 Pit Wall</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

function onRaceSeasonChange() {
    const sel = document.getElementById('racesSeasonFilter');
    const season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    loadRaces(season);
}

function loadCustomRaceYear() {
    onRaceSeasonChange();
}

async function syncRacesFromApi() {
    const sel = document.getElementById('racesSeasonFilter');
    let season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    if (season === 'all') season = '2026';

    setLoading('btnSyncRaces', true);
    try {
        const data = await apiFetch(`/api/import/races/${season}`, { method: 'POST' });
        showToast(data.message || `Races synced for ${season} season!`);
        loadRaces(season);
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSyncRaces', false);
    }
}

async function syncAllRaceResultsForSeason() {
    const sel = document.getElementById('racesSeasonFilter');
    let season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    if (season === 'all') season = '2026';

    setLoading('btnSyncAllResults', true);
    try {
        const data = await apiFetch(`/api/import/results-season/${season}`, { method: 'POST' });
        showToast(data.message || `All race results synced for ${season}!`);
        loadRaces(season);
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSyncAllResults', false);
    }
}

function closeRaceResults(raceId) {
    const detailRow = document.getElementById(`race-results-row-${raceId}`);
    if (detailRow) {
        detailRow.remove();
    }
    const parentRow = document.getElementById(`race-row-${raceId}`) || (window.event && window.event.target ? window.event.target.closest('tr') : null);
    if (parentRow) {
        parentRow.classList.remove('race-row-active');
        const btn = document.getElementById(`btn-race-${raceId}`) || parentRow.querySelector('button');
        if (btn) {
            btn.textContent = 'View Results';
            btn.className = 'btn btn-sm btn-primary';
        }
    }
    if (currentViewedRace && currentViewedRace.raceId === raceId) {
        currentViewedRace = null;
    }
}

async function viewRaceResults(raceId, fallbackName, fallbackYear, fallbackRound) {
    try {
        // Toggle closed if already open
        const existingRow = document.getElementById(`race-results-row-${raceId}`);
        if (existingRow) {
            closeRaceResults(raceId);
            return;
        }

        // Close any other currently open race results row
        if (currentViewedRace && currentViewedRace.raceId !== raceId) {
            closeRaceResults(currentViewedRace.raceId);
        }

        // Retrieve race metadata from cached map or fallback arguments
        const rData = currentRacesMap[raceId] || {};
        const raceName = rData.race_name || fallbackName || ('Race #' + raceId);
        const seasonYear = rData.season_year || fallbackYear || '';
        const roundNumber = rData.round_number || fallbackRound || '';

        // Locate parent row with multiple robust fallbacks
        let parentRow = document.getElementById(`race-row-${raceId}`);
        if (!parentRow && window.event && window.event.target) {
            parentRow = window.event.target.closest('tr');
        }
        if (!parentRow) {
            const allRows = document.querySelectorAll('#racesBody tr');
            for (const row of allRows) {
                if (row.dataset && row.dataset.raceId == raceId) {
                    parentRow = row;
                    break;
                }
                const firstTd = row.querySelector('td');
                if (firstTd && firstTd.textContent.trim() == String(raceId)) {
                    parentRow = row;
                    break;
                }
            }
        }

        if (!parentRow) {
            console.warn('Could not locate table row for race ID:', raceId);
            showToast('Unable to locate race row in table', 'error');
            return;
        }

        currentViewedRace = { raceId, raceName, seasonYear, roundNumber };

        // Highlight parent row and change button text
        parentRow.classList.add('race-row-active');
        const btn = document.getElementById(`btn-race-${raceId}`) || parentRow.querySelector('button');
        if (btn) {
            btn.textContent = '✕ Hide Results';
            btn.className = 'btn btn-sm btn-secondary';
        }

        // Insert inline detail row immediately below the selected race row
        const detailRow = document.createElement('tr');
        detailRow.id = `race-results-row-${raceId}`;
        detailRow.className = 'race-results-expand-row';
        detailRow.innerHTML = `
            <td colspan="7" class="race-results-cell">
                <div class="race-inline-results-panel">
                    <div class="section-header" style="flex-wrap:wrap; gap:10px; margin-bottom:12px;">
                        <div>
                            <h4 style="margin:0; font-size:15px; color:var(--text-white);">
                                🏁 Results: ${escapeHtml(raceName)} <span class="text-muted" style="font-weight:normal; font-size:13px;">(${seasonYear} Round ${roundNumber})</span>
                            </h4>
                        </div>
                        <div style="display:flex; gap:8px; align-items:center;">
                            <button class="btn btn-sm btn-primary" onclick="syncCurrentRaceResults()" id="btnSyncResults">🔄 Sync Results from API</button>
                            <button class="btn btn-sm btn-secondary" onclick="syncCurrentRaceLaps()" id="btnSyncLaps">⏱️ Sync Laps</button>
                            <button class="btn btn-sm btn-secondary" onclick="closeRaceResults(${raceId})">✕ Close</button>
                        </div>
                    </div>
                    <div class="table-container" style="margin-bottom:0;">
                        <table class="data-table race-results-subtable">
                            <thead>
                                <tr>
                                    <th>Pos</th>
                                    <th>Driver</th>
                                    <th>Team</th>
                                    <th>Grid</th>
                                    <th>Points</th>
                                    <th>Status</th>
                                    <th>Fastest Lap</th>
                                </tr>
                            </thead>
                            <tbody id="raceResultsBody-${raceId}">
                                <tr><td colspan="7" class="text-center" style="padding:18px;"><span class="spinner-small"></span> Loading results...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </td>
        `;
        parentRow.insertAdjacentElement('afterend', detailRow);

        await loadRaceResultsData(raceId);
    } catch (err) {
        console.error('viewRaceResults error:', err);
        showToast('Error opening race results: ' + err.message, 'error');
    }
}

async function loadRaceResultsData(raceId) {
    const tbody = document.getElementById(`raceResultsBody-${raceId}`);
    if (!tbody) return;

    try {
        const data = await apiFetch(`/api/races/${raceId}/results`);
        const results = data.classification || [];
        if (!results.length) {
            tbody.innerHTML = `
                <tr><td colspan="7" class="text-center text-muted" style="padding: 24px;">
                    No results recorded yet for this race.<br>
                    <button class="btn btn-sm btn-primary mt-1" onclick="syncCurrentRaceResults()">🔄 Fetch Results from Jolpica API</button>
                </td></tr>
            `;
            return;
        }
        tbody.innerHTML = results.map(r => `
            <tr>
                <td><strong>${r.finishing_position || '—'}</strong></td>
                <td>${escapeHtml(r.driver_name)}</td>
                <td>${escapeHtml(r.team_name)}</td>
                <td>${r.grid_position || '—'}</td>
                <td><strong>${r.points_scored}</strong></td>
                <td><span class="badge ${r.status === 'Finished' ? 'badge-success' : 'badge-warning'}">${escapeHtml(r.status)}</span></td>
                <td>${r.fastest_lap_time || '—'}</td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function syncCurrentRaceResults() {
    if (!currentViewedRace || !currentViewedRace.seasonYear || !currentViewedRace.roundNumber) {
        showToast('No race currently selected', 'error');
        return;
    }
    setLoading('btnSyncResults', true);
    try {
        const data = await apiFetch(`/api/import/results/${currentViewedRace.seasonYear}/${currentViewedRace.roundNumber}`, { method: 'POST' });
        showToast(data.message || 'Results fetched successfully!');
        await loadRaceResultsData(currentViewedRace.raceId);
        loadDashboard();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSyncResults', false);
    }
}

async function syncCurrentRaceLaps() {
    if (!currentViewedRace || !currentViewedRace.seasonYear || !currentViewedRace.roundNumber) {
        showToast('No race currently selected', 'error');
        return;
    }
    setLoading('btnSyncLaps', true);
    try {
        const data = await apiFetch(`/api/import/laps/${currentViewedRace.seasonYear}/${currentViewedRace.roundNumber}`, { method: 'POST' });
        showToast(data.message || 'Laps telemetry fetched successfully!');
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSyncLaps', false);
    }
}

// ==============================================================================
// STANDINGS
// ==============================================================================

async function loadStandings(season) {
    if (season === undefined) {
        const filterElem = document.getElementById('standingsSeasonFilter');
        season = filterElem ? filterElem.value : '2026';
    }
    season = parseSeasonInput(season, '2026');
    if (!season || season === 'all') season = '2026';

    const subtitle = document.getElementById('standingsSubtitle');
    if (subtitle) subtitle.textContent = `Driver and constructor championship standings for the ${season} season`;

    const dBody = document.getElementById('driverStandingsBody');
    const cBody = document.getElementById('constructorStandingsBody');
    if (dBody) dBody.innerHTML = '<tr><td colspan="6" class="text-center"><span class="spinner-small"></span> Loading driver standings...</td></tr>';
    if (cBody) cBody.innerHTML = '<tr><td colspan="5" class="text-center"><span class="spinner-small"></span> Loading constructor standings...</td></tr>';

    setLoading('btnLoadStandings', true);
    try {
        // Load driver standings
        const driverData = await apiFetch(`/api/standings/drivers/${season}`);
        if (!driverData.length) {
            if (dBody) dBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding: 20px;">No driver standings recorded for the ${season} season yet.</td></tr>`;
        } else {
            if (dBody) dBody.innerHTML = driverData.map(d => `
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
        if (!constData.length) {
            if (cBody) cBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted" style="padding: 20px;">No constructor standings recorded for the ${season} season yet.</td></tr>`;
        } else {
            if (cBody) cBody.innerHTML = constData.map(c => `
                <tr>
                    <td><strong>${c.position}</strong></td>
                    <td>${escapeHtml(c.team_name)}</td>
                    <td><strong>${c.total_points}</strong></td>
                    <td>${c.wins}</td>
                    <td>${c.podiums}</td>
                </tr>
            `).join('');
        }
    } catch (err) {
        if (dBody) dBody.innerHTML = `<tr><td colspan="6" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
        if (cBody) cBody.innerHTML = `<tr><td colspan="5" class="text-center text-error">${escapeHtml(err.message)}</td></tr>`;
        showToast(err.message, 'error');
    } finally {
        setLoading('btnLoadStandings', false);
    }
}

function onStandingsSeasonChange() {
    const sel = document.getElementById('standingsSeasonFilter');
    const season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    loadStandings(season);
}

function loadCustomStandingsYear() {
    onStandingsSeasonChange();
}

async function recalculateStandingsForSeason() {
    const sel = document.getElementById('standingsSeasonFilter');
    let season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    if (season === 'all') season = '2026';

    setLoading('btnRecalcStandings', true);
    try {
        const data = await apiFetch(`/api/standings/recalculate/${season}`, { method: 'POST' });
        showToast(data.message || `Standings recalculated via stored procedure for ${season}!`);
        loadStandings(season);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnRecalcStandings', false);
    }
}

async function syncStandingsFromApi() {
    const sel = document.getElementById('standingsSeasonFilter');
    let season = parseSeasonInput(sel ? sel.value : '2026', '2026');
    if (season === 'all') season = '2026';

    setLoading('btnSyncStandings', true);
    try {
        const data = await apiFetch(`/api/standings/sync/${season}`, { method: 'POST' });
        showToast(data.message || `Standings synced from official F1 API for ${season}!`);
        loadStandings(season);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        setLoading('btnSyncStandings', false);
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
// DYNAMIC DROPDOWNS (RACES, DRIVERS, ANALYSTS)
// ==============================================================================

let cachedDropdownRaces = null;
let cachedDropdownDrivers = null;
let cachedDropdownAnalysts = null;

async function fetchDropdownData(forceReload = false) {
    if (!forceReload && cachedDropdownRaces && cachedDropdownDrivers && cachedDropdownAnalysts) {
        return { races: cachedDropdownRaces, drivers: cachedDropdownDrivers, analysts: cachedDropdownAnalysts };
    }

    try {
        const [racesRes, driversRes, analystsRes] = await Promise.allSettled([
            apiFetch('/api/races'),
            apiFetch('/api/drivers'),
            apiFetch('/api/analysts')
        ]);

        if (racesRes.status === 'fulfilled' && Array.isArray(racesRes.value)) {
            // Sort races: season descending, round ascending
            cachedDropdownRaces = [...racesRes.value].sort((a, b) => {
                if (b.season_year !== a.season_year) return b.season_year - a.season_year;
                return (a.round_number || 0) - (b.round_number || 0);
            });
        } else {
            cachedDropdownRaces = cachedDropdownRaces || [];
        }

        if (driversRes.status === 'fulfilled' && Array.isArray(driversRes.value)) {
            // Sort drivers: last name ASC, first name ASC
            cachedDropdownDrivers = [...driversRes.value].sort((a, b) => {
                const nameA = `${a.last_name || ''} ${a.first_name || ''}`.trim().toLowerCase();
                const nameB = `${b.last_name || ''} ${b.first_name || ''}`.trim().toLowerCase();
                return nameA.localeCompare(nameB);
            });
        } else {
            cachedDropdownDrivers = cachedDropdownDrivers || [];
        }

        if (analystsRes.status === 'fulfilled' && Array.isArray(analystsRes.value)) {
            cachedDropdownAnalysts = [...analystsRes.value].sort((a, b) => a.analyst_id - b.analyst_id);
        } else {
            cachedDropdownAnalysts = cachedDropdownAnalysts || [];
        }
    } catch (err) {
        console.warn('Failed to fetch dropdown datasets:', err);
    }

    return {
        races: cachedDropdownRaces || [],
        drivers: cachedDropdownDrivers || [],
        analysts: cachedDropdownAnalysts || []
    };
}

function populateRaceSelect(selectId, races, placeholder = '-- Select Grand Prix --', isOptional = false) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const currentVal = sel.value;

    let html = isOptional 
        ? `<option value="">-- Latest Race (Default) --</option>`
        : `<option value="" disabled ${!currentVal ? 'selected' : ''}>${placeholder}</option>`;

    // Group races by season
    const seasons = {};
    races.forEach(r => {
        const season = r.season_year || 'Historical';
        if (!seasons[season]) seasons[season] = [];
        seasons[season].push(r);
    });

    for (const season of Object.keys(seasons)) {
        html += `<optgroup label="🏁 ${season} Season">`;
        seasons[season].forEach(r => {
            const loc = r.circuit_city ? ` (${r.circuit_city})` : '';
            const round = r.round_number ? `R${r.round_number}: ` : '';
            html += `<option value="${r.race_id}">${r.season_year} ${round}${escapeHtml(r.race_name)}${loc}</option>`;
        });
        html += `</optgroup>`;
    }

    sel.innerHTML = html;
    if (currentVal) {
        sel.value = currentVal;
    } else if (!isOptional && races.length > 0) {
        sel.value = races[0].race_id;
    }
}

function populateDriverSelect(selectId, drivers, placeholder = '-- Select Driver --', defaultDriverName = null) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const currentVal = sel.value;

    let html = `<option value="" disabled ${!currentVal ? 'selected' : ''}>${placeholder}</option>`;

    const withTeam = [];
    const withoutTeam = [];

    drivers.forEach(d => {
        if (d.team_name && d.team_name !== 'Unknown') {
            withTeam.push(d);
        } else {
            withoutTeam.push(d);
        }
    });

    if (withTeam.length > 0) {
        html += `<optgroup label="🏎️ Formula 1 Constructors Grid">`;
        withTeam.forEach(d => {
            const team = d.team_name ? ` (${d.team_name})` : (d.nationality ? ` (${d.nationality})` : '');
            html += `<option value="${d.driver_id}">${escapeHtml(d.first_name)} ${escapeHtml(d.last_name)}${team}</option>`;
        });
        html += `</optgroup>`;
    }

    if (withoutTeam.length > 0) {
        html += `<optgroup label="🌐 Historical & Reserve Drivers">`;
        withoutTeam.forEach(d => {
            const nat = d.nationality && d.nationality !== 'Unknown' ? ` (${d.nationality})` : '';
            html += `<option value="${d.driver_id}">${escapeHtml(d.first_name)} ${escapeHtml(d.last_name)}${nat}</option>`;
        });
        html += `</optgroup>`;
    }

    sel.innerHTML = html;
    if (currentVal) {
        sel.value = currentVal;
    } else if (defaultDriverName) {
        const found = drivers.find(d => `${d.first_name} ${d.last_name}`.toLowerCase().includes(defaultDriverName.toLowerCase()));
        if (found) sel.value = found.driver_id;
        else if (drivers.length > 0) sel.value = drivers[0].driver_id;
    } else if (drivers.length > 0) {
        sel.value = drivers[0].driver_id;
    }
}

function populateAnalystSelect(selectId, analysts, placeholder = '-- Select Analyst --') {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const currentVal = sel.value;

    let html = `<option value="" disabled ${!currentVal ? 'selected' : ''}>${placeholder}</option>`;
    analysts.forEach(a => {
        html += `<option value="${a.analyst_id}">${escapeHtml(a.name)} (${escapeHtml(a.role || 'Analyst')})</option>`;
    });

    sel.innerHTML = html;
    if (currentVal) {
        sel.value = currentVal;
    } else if (analysts.length > 0) {
        sel.value = analysts[0].analyst_id;
    }
}

async function populateAllStrategyDropdowns(forceReload = false) {
    const { races, drivers, analysts } = await fetchDropdownData(forceReload);

    // 1. Tyre Degradation
    populateRaceSelect('tyreDegRaceId', races, '-- Latest Race (Default) --', true);

    // 2. Strategy Simulation
    populateRaceSelect('simRaceId', races, '-- Select Grand Prix --', false);
    populateDriverSelect('simDriverId', drivers, '-- Select Driver --', 'Verstappen');

    // 3. Undercut Simulation
    populateRaceSelect('undercutRaceId', races, '-- Select Grand Prix --', false);
    populateDriverSelect('undercutChaserId', drivers, '-- Select Chaser Driver --', 'Norris');
    populateDriverSelect('undercutLeaderId', drivers, '-- Select Leader Driver --', 'Verstappen');

    // 4. Stint Comparison
    populateRaceSelect('stintRaceId', races, '-- Select Grand Prix --', false);
    populateDriverSelect('stintDriver1Id', drivers, '-- Select Driver 1 --', 'Hamilton');
    populateDriverSelect('stintDriver2Id', drivers, '-- Select Driver 2 --', 'Leclerc');

    // 5. Strategy Notes Modal
    populateRaceSelect('noteRaceId', races, '-- Select Grand Prix --', false);
    populateDriverSelect('noteDriverId', drivers, '-- Select Driver --', 'Verstappen');
    populateAnalystSelect('noteAnalystId', analysts, '-- Select Analyst --');
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
    if (!raceId || !driverId) { showToast('Please select Grand Prix and Driver from dropdowns', 'error'); return; }

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
        showToast('Please select Grand Prix, Chaser, Leader, and Pit Lap', 'error'); return;
    }
    if (chaserId === leaderId) {
        showToast('Chaser and Leader must be different drivers!', 'warning'); return;
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
        showToast('Please select Grand Prix and both Drivers to compare', 'error'); return;
    }
    if (d1 === d2) {
        showToast('Please select two different drivers for stint comparison!', 'warning'); return;
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
        const skippedNote = data.skipped > 0 ? `<p class="text-muted" style="margin-top:6px;font-size:0.85rem;">ℹ️ ${escapeHtml(data.skipped_reason || 'Skipped items already exist in database to avoid duplicate entries.')}</p>` : '';
        resultBox.innerHTML = `
            <p class="text-success">✅ ${escapeHtml(data.message)}</p>
            <p><strong>Inserted:</strong> ${data.inserted}</p>
            <p><strong>Skipped:</strong> ${data.skipped}</p>
            <p><strong>Total from API:</strong> ${data.total_from_api}</p>
            ${skippedNote}
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
        const skippedNote = data.skipped > 0 ? `<p class="text-muted" style="margin-top:6px;font-size:0.85rem;">ℹ️ ${escapeHtml(data.skipped_reason || 'Skipped items already exist in database to avoid duplicate entries.')}</p>` : '';
        resultBox.innerHTML = `
            <p class="text-success">✅ ${escapeHtml(data.message)}</p>
            <p><strong>Inserted:</strong> ${data.inserted}</p>
            <p><strong>Skipped:</strong> ${data.skipped}</p>
            <p><strong>Total from API:</strong> ${data.total_from_api}</p>
            ${skippedNote}
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
        const skippedNote = data.skipped > 0 ? `<p class="text-muted" style="margin-top:6px;font-size:0.85rem;">ℹ️ ${escapeHtml(data.skipped_reason || 'Skipped items already exist in database to avoid duplicate entries.')}</p>` : '';
        resultBox.innerHTML = `
            <p class="text-success">✅ ${escapeHtml(data.message)}</p>
            <p><strong>Inserted:</strong> ${data.inserted}</p>
            <p><strong>Skipped:</strong> ${data.skipped}</p>
            <p><strong>Total from API:</strong> ${data.total_from_api}</p>
            ${skippedNote}
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
    const raceIdVal = document.getElementById('noteRaceId').value;
    const analystIdVal = document.getElementById('noteAnalystId').value;
    const driverIdVal = document.getElementById('noteDriverId').value;

    if (!raceIdVal || !analystIdVal || !driverIdVal) {
        showToast('Please select Grand Prix, Analyst, and Driver from the dropdowns', 'error');
        return;
    }

    const payload = {
        race_id: parseInt(raceIdVal),
        analyst_id: parseInt(analystIdVal),
        driver_id: parseInt(driverIdVal),
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
        await populateAllStrategyDropdowns();
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
// PIT WALL & LIVE TELEMETRY STREAM (f1-race-replay Integration)
// ==============================================================================

const PITWALL_TYRE_META = {
    0: { hex: '#888888', abbr: 'U', name: 'Unknown' },
    1: { hex: '#E8002D', abbr: 'S', name: 'Soft' },
    2: { hex: '#FFF200', abbr: 'M', name: 'Medium' },
    3: { hex: '#CACACA', abbr: 'H', name: 'Hard' },
    4: { hex: '#39B54A', abbr: 'I', name: 'Intermediate' },
    5: { hex: '#0067FF', abbr: 'W', name: 'Wet' },
};

const pitwallState = {
    initialized: false,
    season: 2024,
    round: 1,
    raceId: null,
    driverCode: null,
    compareCode: null,
    lap: 1,
    catalogRaces: [],
    catalogDrivers: [],
    session: null,
    frameIndex: 0,
    playing: false,
    speed: 1.0,
    timerId: null,
    hoverTelemetryRatio: null,
    windowFilter: 'all',
};

function getTyreMeta(codeOrName) {
    if (typeof codeOrName === 'number') {
        return PITWALL_TYRE_META[Math.round(codeOrName)] || PITWALL_TYRE_META[2];
    }
    const s = String(codeOrName || '').toUpperCase();
    if (s.includes('SOFT') || s === 'S') return PITWALL_TYRE_META[1];
    if (s.includes('HARD') || s === 'H') return PITWALL_TYRE_META[3];
    if (s.includes('INTER') || s === 'I') return PITWALL_TYRE_META[4];
    if (s.includes('WET') || s === 'W') return PITWALL_TYRE_META[5];
    return PITWALL_TYRE_META[2];
}

function formatLapTimeSec(sec) {
    if (typeof sec !== 'number' || !isFinite(sec) || sec <= 0) return '—';
    const mins = Math.floor(sec / 60);
    const rem = (sec % 60).toFixed(3).padStart(6, '0');
    return `${mins}:${rem}`;
}

async function openPitwallFor(season, roundNumber = 1, driverQuery = '', raceId = null) {
    pitwallState.season = parseInt(season, 10) || 2024;
    pitwallState.round = parseInt(roundNumber, 10) || 1;
    pitwallState.raceId = raceId || null;
    pitwallState.driverCode = driverQuery || null;
    pitwallState.lap = 1;
    pitwallState.initialized = false;
    navigateTo('pitwall');
}

async function loadPitWall() {
    const seasonSel = document.getElementById('pitwallSeasonSelect');
    if (seasonSel) {
        seasonSel.value = String(pitwallState.season || 2024);
    }

    setupPitwallCanvasInteractions();
    await loadPitwallCatalog(pitwallState.season, pitwallState.round, pitwallState.driverCode);
    pitwallState.initialized = true;
}

async function loadPitwallCatalog(season, preferredRound = 1, preferredDriver = null) {
    try {
        setLoading('btnPitwallLoad', true);
        const cat = await apiFetch(`/api/pitwall/catalog?season=${encodeURIComponent(season)}`);
        pitwallState.season = cat.season || season;
        pitwallState.catalogRaces = cat.races || [];
        pitwallState.catalogDrivers = cat.drivers || [];

        const raceSel = document.getElementById('pitwallRaceSelect');
        if (raceSel) {
            raceSel.innerHTML = pitwallState.catalogRaces.map(r =>
                `<option value="${r.round_number}" data-race-id="${r.race_id || ''}">R${r.round_number}: ${escapeHtml(r.race_name)} (${escapeHtml(r.circuit_name || '')})</option>`
            ).join('');
            const matchRound = pitwallState.catalogRaces.find(r => r.round_number === Number(preferredRound));
            raceSel.value = matchRound ? String(matchRound.round_number) : (pitwallState.catalogRaces[0] ? String(pitwallState.catalogRaces[0].round_number) : '1');
            pitwallState.round = parseInt(raceSel.value, 10) || 1;
        }

        populatePitwallDriverSelects(pitwallState.catalogDrivers, preferredDriver, pitwallState.compareCode);
        await reloadPitwallSession();
    } catch (err) {
        showToast(`Pit Wall catalog error: ${err.message}`, 'error');
    } finally {
        setLoading('btnPitwallLoad', false);
    }
}

function populatePitwallDriverSelects(drivers, preferredPrimary = null, preferredCompare = null) {
    const drvSel = document.getElementById('pitwallDriverSelect');
    const cmpSel = document.getElementById('pitwallCompareSelect');
    if (!drvSel || !cmpSel) return;

    drvSel.innerHTML = drivers.map(d =>
        `<option value="${escapeHtml(d.code)}">${escapeHtml(d.code)} — ${escapeHtml(d.name)} (${escapeHtml(d.team)})</option>`
    ).join('');

    cmpSel.innerHTML = `<option value="none">None (Single Driver)</option>` + drivers.map(d =>
        `<option value="${escapeHtml(d.code)}">${escapeHtml(d.code)} — ${escapeHtml(d.name)} (${escapeHtml(d.team)})</option>`
    ).join('');

    if (preferredPrimary) {
        const q = String(preferredPrimary).toLowerCase();
        const found = drivers.find(d => d.code.toLowerCase() === q || d.name.toLowerCase().includes(q));
        if (found) drvSel.value = found.code;
    }
    pitwallState.driverCode = drvSel.value || (drivers[0] ? drivers[0].code : 'VER');

    if (preferredCompare && preferredCompare !== 'none' && drivers.some(d => d.code === preferredCompare)) {
        cmpSel.value = preferredCompare;
    } else if (drivers.length > 1) {
        const second = drivers.find(d => d.code !== pitwallState.driverCode);
        cmpSel.value = second ? second.code : 'none';
    }
    pitwallState.compareCode = cmpSel.value;
}

function filterPitwallDriverDropdown(query) {
    const drvSel = document.getElementById('pitwallDriverSelect');
    if (!drvSel || !pitwallState.session) return;
    const allDrivers = pitwallState.session.drivers || pitwallState.catalogDrivers || [];
    const q = (query || '').trim().toLowerCase();
    const filtered = q
        ? allDrivers.filter(d =>
            d.code.toLowerCase().includes(q) ||
            d.name.toLowerCase().includes(q) ||
            (d.team && d.team.toLowerCase().includes(q))
        )
        : allDrivers;

    if (!filtered.length) return;
    const prevVal = drvSel.value;
    drvSel.innerHTML = filtered.map(d =>
        `<option value="${escapeHtml(d.code)}">${escapeHtml(d.code)} — ${escapeHtml(d.name)} (${escapeHtml(d.team)})</option>`
    ).join('');

    if (filtered.some(d => d.code === prevVal)) {
        drvSel.value = prevVal;
    } else {
        drvSel.value = filtered[0].code;
        onPitwallDriverChange();
    }
}

function onPitwallSeasonChange() {
    const sel = document.getElementById('pitwallSeasonSelect');
    if (!sel) return;
    const yearParsed = parseInt(parseSeasonInput(sel.value, '2024'), 10);
    const year = (isNaN(yearParsed) || yearParsed < 1950 || yearParsed > 2030) ? 2024 : yearParsed;
    pitwallState.season = year;
    pitwallState.round = 1;
    pitwallState.lap = 1;
    loadPitwallCatalog(year, 1, null);
}

function loadPitwallCustomYear() {
    onPitwallSeasonChange();
}

function onPitwallRaceChange() {
    const raceSel = document.getElementById('pitwallRaceSelect');
    if (!raceSel) return;
    pitwallState.round = parseInt(raceSel.value, 10) || 1;
    pitwallState.lap = 1;
    reloadPitwallSession();
}

function onPitwallDriverChange() {
    const drvSel = document.getElementById('pitwallDriverSelect');
    const cmpSel = document.getElementById('pitwallCompareSelect');
    if (drvSel) pitwallState.driverCode = drvSel.value;
    if (cmpSel) pitwallState.compareCode = cmpSel.value;
    reloadPitwallSession();
}

function onPitwallLapChange() {
    const lapSel = document.getElementById('pitwallLapSelect');
    if (!lapSel) return;
    pitwallState.lap = parseInt(lapSel.value, 10) || 1;
    reloadPitwallSession(true);
}

async function reloadPitwallSession(preservePlayState = false) {
    const wasPlaying = pitwallState.playing;
    if (!preservePlayState) stopPitwallPlayback();

    const season = pitwallState.season;
    const round = pitwallState.round;
    const drv = pitwallState.driverCode || '';
    const cmp = pitwallState.compareCode || 'none';
    const lap = pitwallState.lap || 1;

    setLoading('btnPitwallLoad', true);
    try {
        const qs = new URLSearchParams({
            season: String(season),
            round: String(round),
            driver: drv,
            compare_driver: cmp,
            lap: String(lap),
        });
        const data = await apiFetch(`/api/pitwall/session?${qs.toString()}`);
        pitwallState.session = data;
        pitwallState.driverCode = data.selected_driver;
        pitwallState.compareCode = data.compare_driver || 'none';
        pitwallState.lap = data.selected_lap || 1;

        // Sync dropdowns with session's resolved driver list
        if (Array.isArray(data.drivers) && data.drivers.length) {
            populatePitwallDriverSelects(data.drivers, data.selected_driver, data.compare_driver || 'none');
        }

        // Populate Lap dropdown (1 .. total_laps)
        const totalLaps = (data.session_info && data.session_info.total_laps) ? data.session_info.total_laps : 57;
        const lapSel = document.getElementById('pitwallLapSelect');
        if (lapSel) {
            lapSel.innerHTML = Array.from({ length: totalLaps }, (_, i) =>
                `<option value="${i + 1}">Lap ${i + 1} / ${totalLaps}</option>`
            ).join('');
            lapSel.value = String(pitwallState.lap);
        }

        // Update header badges & SSE link
        const info = data.session_info || {};
        const sub = document.getElementById('pitwallSubtitle');
        if (sub) {
            sub.textContent = `${info.season || season} ${info.race_name || ''} • ${info.circuit_name || ''} (${info.circuit_country || ''}) • ${totalLaps} Laps`;
        }
        const srcBadge = document.getElementById('pitwallSourceBadge');
        if (srcBadge) {
            const srcs = Array.isArray(info.data_sources) ? info.data_sources.join(' + ') : 'Hybrid Telemetry';
            srcBadge.textContent = `Pipeline: ${srcs}`;
        }
        const wBadge = document.getElementById('pitwallWeatherBadge');
        if (wBadge && info.weather) {
            const w = info.weather;
            wBadge.textContent = `🌡️ ${w.temperature_celsius ?? 26}°C • 💧 ${w.humidity_percent ?? 48}% • ${w.track_condition || 'Dry'}`;
        }
        const sseLink = document.getElementById('pitwallSseLink');
        if (sseLink) {
            sseLink.href = `${API_BASE_URL}/api/pitwall/stream?season=${season}&round=${round}&driver=${encodeURIComponent(pitwallState.driverCode)}&lap=${pitwallState.lap}`;
        }

        // Reset scrubber range
        const frames = data.replay_frames || [];
        const scrubber = document.getElementById('pitwallFrameScrubber');
        if (scrubber) {
            scrubber.max = String(Math.max(0, frames.length - 1));
            scrubber.value = '0';
        }
        pitwallState.frameIndex = 0;

        // Render all 6 Pit Wall Insights
        renderAllPitwallInsights();

        if (preservePlayState && wasPlaying) {
            startPitwallPlayback();
        }
    } catch (err) {
        showToast(`Pit Wall session error: ${err.message}`, 'error');
    } finally {
        setLoading('btnPitwallLoad', false);
    }
}

function setPitwallWindowFilter(winKey) {
    pitwallState.windowFilter = winKey;
    document.querySelectorAll('.pitwall-window-pill').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.window === winKey);
    });
    const grid = document.getElementById('pitwallPanelsGrid');
    document.querySelectorAll('[data-pitwall-panel]').forEach(panel => {
        const key = panel.getAttribute('data-pitwall-panel');
        if (winKey === 'all' || key === winKey) {
            panel.classList.remove('hidden');
            if (winKey !== 'all') {
                panel.classList.add('pitwall-panel-wide');
            } else {
                const defaultWide = (key === 'tyres' || key === 'racecontrol' || key === 'stream');
                panel.classList.toggle('pitwall-panel-wide', defaultWide);
            }
        } else {
            panel.classList.add('hidden');
        }
    });
    if (grid) {
        renderAllPitwallInsights();
    }
}

// ==============================================================================
// INTERACTIVE REPLAY STREAM CONTROLLER & HUD
// ==============================================================================

function togglePitwallPlayback() {
    if (pitwallState.playing) {
        stopPitwallPlayback();
    } else {
        startPitwallPlayback();
    }
}

function startPitwallPlayback() {
    if (!pitwallState.session) return;
    stopPitwallPlayback();
    pitwallState.playing = true;
    const btn = document.getElementById('btnPitwallPlay');
    if (btn) btn.textContent = '⏸ Pause Stream';

    const intervalMs = Math.max(30, Math.round(110 / pitwallState.speed));
    pitwallState.timerId = setInterval(() => {
        const frames = (pitwallState.session && pitwallState.session.replay_frames) || [];
        if (!frames.length) return;
        if (pitwallState.frameIndex < frames.length - 1) {
            pitwallState.frameIndex++;
            updatePitwallFrameUI(pitwallState.frameIndex);
        } else {
            const autoAdv = document.getElementById('pitwallAutoAdvanceLap');
            const totalLaps = (pitwallState.session.session_info && pitwallState.session.session_info.total_laps) || 57;
            if (autoAdv && autoAdv.checked && pitwallState.lap < totalLaps) {
                stepPitwallLap(1, true);
            } else {
                stopPitwallPlayback();
            }
        }
    }, intervalMs);
}

function stopPitwallPlayback() {
    pitwallState.playing = false;
    if (pitwallState.timerId) {
        clearInterval(pitwallState.timerId);
        pitwallState.timerId = null;
    }
    const btn = document.getElementById('btnPitwallPlay');
    if (btn) btn.textContent = '▶ Play Stream';
}

function setPitwallSpeed(mult) {
    pitwallState.speed = Number(mult) || 1.0;
    document.querySelectorAll('.pitwall-speed-btn').forEach(b => {
        b.classList.toggle('active', Number(b.dataset.speed) === pitwallState.speed);
    });
    if (pitwallState.playing) {
        startPitwallPlayback();
    }
}

function stepPitwallFrame(delta) {
    if (!pitwallState.session) return;
    const frames = pitwallState.session.replay_frames || [];
    if (!frames.length) return;
    pitwallState.frameIndex = Math.max(0, Math.min(frames.length - 1, pitwallState.frameIndex + delta));
    updatePitwallFrameUI(pitwallState.frameIndex);
}

function restartPitwallLap() {
    pitwallState.frameIndex = 0;
    updatePitwallFrameUI(0);
}

function stepPitwallLap(delta, keepPlaying = false) {
    if (!pitwallState.session) return;
    const totalLaps = (pitwallState.session.session_info && pitwallState.session.session_info.total_laps) || 57;
    const nextLap = Math.max(1, Math.min(totalLaps, pitwallState.lap + delta));
    if (nextLap === pitwallState.lap) return;
    pitwallState.lap = nextLap;
    const lapSel = document.getElementById('pitwallLapSelect');
    if (lapSel) lapSel.value = String(nextLap);
    reloadPitwallSession(keepPlaying);
}

function onPitwallScrubberInput(val) {
    pitwallState.frameIndex = parseInt(val, 10) || 0;
    updatePitwallFrameUI(pitwallState.frameIndex);
}

function renderAllPitwallInsights() {
    if (!pitwallState.session) return;
    updatePitwallFrameUI(pitwallState.frameIndex);
    renderPitwallTyreGantt();
    renderPitwallLapChartCanvas();
    renderPitwallSectorTable();
    renderPitwallRaceControl();
}

function updatePitwallFrameUI(frameIdx) {
    const s = pitwallState.session;
    if (!s) return;
    const frames = s.replay_frames || [];
    const frameObj = frames[frameIdx] || frames[0];
    if (!frameObj) return;

    const scrubber = document.getElementById('pitwallFrameScrubber');
    if (scrubber) scrubber.value = String(frameIdx);

    const totalLaps = (s.session_info && s.session_info.total_laps) || 57;
    const drvCode = s.selected_driver;
    const drvFrame = (frameObj.frame && frameObj.frame.drivers && frameObj.frame.drivers[drvCode]) || {};
    const scState = (frameObj.frame && frameObj.frame.safety_car) || { active: false, label: 'TRACK CLEAR', phase: 'none' };

    const lapLbl = document.getElementById('pitwallScrubberLapLabel');
    if (lapLbl) lapLbl.textContent = `Lap ${s.selected_lap} / ${totalLaps}`;
    const distLbl = document.getElementById('pitwallScrubberDistLabel');
    if (distLbl) {
        const pct = ((frameObj.rel_dist || 0) * 100).toFixed(1);
        distLbl.textContent = `Dist: ${Math.round(drvFrame.dist || 0)} m (${pct}%)`;
    }
    const timeLbl = document.getElementById('pitwallScrubberTimeLabel');
    if (timeLbl) timeLbl.textContent = `t = ${(frameObj.lap_elapsed_s || 0).toFixed(3)}s`;

    // Update HUD boxes
    const primarySamples = (s.driver_telemetry && s.driver_telemetry.primary && s.driver_telemetry.primary.samples) || [];
    const sampleIdx = Math.min(primarySamples.length - 1, Math.round((frameIdx / Math.max(1, frames.length - 1)) * (primarySamples.length - 1)));
    const pSample = primarySamples[sampleIdx] || {};

    const speed = drvFrame.speed ?? pSample.speed ?? 0;
    const gear = drvFrame.gear ?? pSample.gear ?? 0;
    const throttle = drvFrame.throttle ?? pSample.throttle ?? 0;
    const brake = drvFrame.brake ?? pSample.brake ?? 0;
    const drs = drvFrame.drs ?? pSample.drs ?? 0;
    const rpm = pSample.rpm ?? Math.round(7500 + speed * 14);
    const tyreMeta = getTyreMeta(drvFrame.tyre ?? pSample.tyre ?? 2);

    const elCode = document.getElementById('hudDriverCode');
    if (elCode) elCode.textContent = drvCode;
    const elPos = document.getElementById('hudDriverPos');
    if (elPos) {
        const gapStr = drvFrame.position === 1 ? 'LEADER' : `+${(drvFrame.gap_s || 0).toFixed(3)}s`;
        elPos.textContent = `P${drvFrame.position || 1} • ${gapStr}`;
    }
    const elSpd = document.getElementById('hudSpeed');
    if (elSpd) elSpd.textContent = Math.round(speed);
    const elSpdBar = document.getElementById('hudSpeedBar');
    if (elSpdBar) elSpdBar.style.width = `${Math.min(100, (speed / 355) * 100)}%`;

    const elGear = document.getElementById('hudGear');
    if (elGear) elGear.textContent = gear > 0 ? String(gear) : 'N';
    const elRpm = document.getElementById('hudRpm');
    if (elRpm) elRpm.textContent = `${rpm.toLocaleString()} RPM`;

    const elThr = document.getElementById('hudThrottle');
    if (elThr) elThr.textContent = Math.round(throttle);
    const elThrBar = document.getElementById('hudThrottleBar');
    if (elThrBar) elThrBar.style.width = `${Math.min(100, throttle)}%`;

    const elBrk = document.getElementById('hudBrake');
    if (elBrk) elBrk.textContent = Math.round(brake);
    const elBrkBar = document.getElementById('hudBrakeBar');
    if (elBrkBar) elBrkBar.style.width = `${Math.min(100, brake)}%`;

    const elDrs = document.getElementById('hudDrsBadge');
    if (elDrs) {
        const isOn = Number(drs) > 0;
        elDrs.className = `hud-drs-pill ${isOn ? 'on' : 'off'}`;
        elDrs.textContent = isOn ? 'DRS ACTIVE' : 'DRS OFF';
    }

    const elTyre = document.getElementById('hudTyreBadge');
    if (elTyre) {
        elTyre.style.borderColor = tyreMeta.hex;
        elTyre.style.color = tyreMeta.hex;
        elTyre.textContent = `${tyreMeta.abbr} • ${tyreMeta.name}`;
    }

    const elCoords = document.getElementById('hudCoords');
    if (elCoords) {
        elCoords.textContent = `x: ${(drvFrame.x || 0).toFixed(1)}, y: ${(drvFrame.y || 0).toFixed(1)}`;
    }

    const elSc = document.getElementById('hudSafetyCarBadge');
    const elScPhase = document.getElementById('hudSafetyCarPhase');
    if (elSc) {
        if (scState && scState.active) {
            elSc.className = 'hud-sc-pill active';
            elSc.textContent = `🟠 ${scState.label || 'SAFETY CAR'}`;
            if (elScPhase) elScPhase.textContent = `Phase: ${scState.phase} (α=${scState.alpha})`;
        } else {
            elSc.className = 'hud-sc-pill clear';
            elSc.textContent = '🟢 TRACK CLEAR';
            if (elScPhase) elScPhase.textContent = 'Phase: Nominal Racing';
        }
    }

    // Update Raw Telemetry Stream Inspector packet
    const rawPre = document.getElementById('pitwallRawStreamPre');
    if (rawPre) {
        const streamPreview = {
            frame_index: frameObj.frame_index,
            lap: frameObj.lap,
            rel_dist: frameObj.rel_dist,
            lap_elapsed_s: frameObj.lap_elapsed_s,
            focus_driver: {
                code: drvCode,
                ...drvFrame,
            },
            safety_car: scState,
            active_drivers_in_frame: Object.keys((frameObj.frame && frameObj.frame.drivers) || {}).length,
        };
        rawPre.textContent = JSON.stringify(streamPreview, null, 2);
    }

    // Re-render frame-reactive canvases
    renderPitwallTelemetryCanvas();
    renderPitwallTrackMapCanvas();
    renderPitwallTimingTower(frameObj);
}

// ==============================================================================
// INSIGHT 1: DRIVER LIVE TELEMETRY (driver_telemetry_window.py)
// ==============================================================================

function renderPitwallTelemetryCanvas() {
    const canvas = document.getElementById('pitwallTelemetryCanvas');
    if (!canvas || !pitwallState.session) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const s = pitwallState.session;
    const primaryObj = (s.driver_telemetry && s.driver_telemetry.primary) || {};
    const compareObj = (s.driver_telemetry && s.driver_telemetry.compare) || null;
    const showCompare = document.getElementById('pitwallTelShowCompare')?.checked && compareObj && Array.isArray(compareObj.samples) && compareObj.samples.length > 0;
    const xMode = document.getElementById('pitwallTelXMode')?.value || 'distance';

    let pSamples = primaryObj.samples || [];
    let cSamples = showCompare ? compareObj.samples : [];
    if (!pSamples.length) return;

    const drvMap = {};
    (s.drivers || []).forEach(d => { drvMap[d.code] = d; });
    const pColor = (drvMap[s.selected_driver] && drvMap[s.selected_driver].color) || '#E10600';
    const cColor = (compareObj && drvMap[compareObj.driver] && drvMap[compareObj.driver].color) || '#00D2BE';

    const frames = s.replay_frames || [];
    const playRatio = frames.length > 1 ? pitwallState.frameIndex / (frames.length - 1) : 0;

    // Filter samples if Rolling 30s Window mode is active
    let xMin = 0;
    let xMax = (s.track_geometry && s.track_geometry.circuit_length_m) || 5000;
    let xKey = 'dist';
    let xUnit = 'm';

    if (xMode === 'window30s') {
        xKey = 't';
        xUnit = 's';
        const curIdx = Math.min(pSamples.length - 1, Math.round(playRatio * (pSamples.length - 1)));
        const curT = pSamples[curIdx]?.t || 30;
        xMax = Math.max(30, curT);
        xMin = Math.max(0, xMax - 30);
    }

    const padL = 54, padR = 18, padT = 16, padB = 26, gapY = 12;
    const plotW = W - padL - padR;
    const availH = H - padT - padB - gapY * 2;
    const hSpeed = Math.round(availH * 0.50);
    const hGear = Math.round(availH * 0.24);
    const hPedals = availH - hSpeed - hGear;

    const ySpeedTop = padT;
    const yGearTop = ySpeedTop + hSpeed + gapY;
    const yPedalsTop = yGearTop + hGear + gapY;

    const mapX = (val) => padL + Math.max(0, Math.min(1, (val - xMin) / Math.max(1e-3, xMax - xMin))) * plotW;

    // Background panels
    const drawPanelBox = (yTop, h, title, yLabels) => {
        ctx.fillStyle = 'rgba(13, 18, 32, 0.92)';
        ctx.fillRect(padL, yTop, plotW, h);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.strokeRect(padL, yTop, plotW, h);

        ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.font = 'bold 10px Inter, sans-serif';
        ctx.fillText(title, padL + 8, yTop + 13);

        yLabels.forEach(({ v, frac }) => {
            const py = yTop + h - frac * h;
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
            ctx.beginPath();
            ctx.moveTo(padL, py);
            ctx.lineTo(padL + plotW, py);
            ctx.stroke();
            ctx.fillStyle = '#8b95a5';
            ctx.font = '10px Rajdhani, monospace';
            ctx.fillText(String(v), 8, py + 3);
        });
    };

    drawPanelBox(ySpeedTop, hSpeed, 'SPEED (km/h) & DRS ZONES', [
        { v: '100', frac: 100 / 360 },
        { v: '200', frac: 200 / 360 },
        { v: '300', frac: 300 / 360 },
    ]);
    drawPanelBox(yGearTop, hGear, 'GEAR (1-8)', [
        { v: 'G2', frac: 2 / 8.5 },
        { v: 'G5', frac: 5 / 8.5 },
        { v: 'G8', frac: 8 / 8.5 },
    ]);
    drawPanelBox(yPedalsTop, hPedals, 'THROTTLE (GREEN %) / BRAKE (RED %)', [
        { v: '0%', frac: 0 },
        { v: '50%', frac: 0.5 },
        { v: '100%', frac: 1.0 },
    ]);

    // Highlight DRS active regions on Speed panel
    ctx.fillStyle = 'rgba(0, 230, 118, 0.09)';
    for (let i = 0; i < pSamples.length - 1; i++) {
        if (pSamples[i].drs > 0 && pSamples[i][xKey] >= xMin && pSamples[i][xKey] <= xMax) {
            const x0 = mapX(pSamples[i][xKey]);
            const x1 = mapX(pSamples[i + 1][xKey]);
            ctx.fillRect(x0, ySpeedTop, Math.max(2, x1 - x0), hSpeed);
        }
    }

    const drawTrace = (samples, valKey, yTop, h, minV, maxV, color, dashed = false, lineWidth = 2) => {
        ctx.save();
        ctx.beginPath();
        ctx.rect(padL, yTop, plotW, h);
        ctx.clip();
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        if (dashed) ctx.setLineDash([5, 4]);
        let started = false;
        for (let i = 0; i < samples.length; i++) {
            const xv = samples[i][xKey];
            if (xv < xMin || xv > xMax) continue;
            const px = mapX(xv);
            const norm = (samples[i][valKey] - minV) / Math.max(1e-3, maxV - minV);
            const py = yTop + h - Math.max(0.02, Math.min(0.98, norm)) * h;
            if (!started) {
                ctx.moveTo(px, py);
                started = true;
            } else {
                ctx.lineTo(px, py);
            }
        }
        ctx.stroke();
        ctx.restore();
    };

    // Compare driver traces (drawn first, dashed)
    if (showCompare && cSamples.length) {
        drawTrace(cSamples, 'speed', ySpeedTop, hSpeed, 50, 360, cColor, true, 1.6);
        drawTrace(cSamples, 'gear', yGearTop, hGear, 0, 8.5, cColor, true, 1.4);
        drawTrace(cSamples, 'throttle', yPedalsTop, hPedals, 0, 105, 'rgba(0, 210, 190, 0.55)', true, 1.3);
    }

    // Primary driver traces
    drawTrace(pSamples, 'speed', ySpeedTop, hSpeed, 50, 360, pColor, false, 2.3);
    drawTrace(pSamples, 'gear', yGearTop, hGear, 0, 8.5, '#ffb300', false, 2.0);
    drawTrace(pSamples, 'throttle', yPedalsTop, hPedals, 0, 105, '#00e676', false, 1.9);
    drawTrace(pSamples, 'brake', yPedalsTop, hPedals, 0, 105, '#ff1744', false, 1.9);

    // Active playhead cursor or hover crosshair
    const activeRatio = pitwallState.hoverTelemetryRatio !== null ? pitwallState.hoverTelemetryRatio : playRatio;
    const sampleIdx = Math.min(pSamples.length - 1, Math.max(0, Math.round(activeRatio * (pSamples.length - 1))));
    const curSample = pSamples[sampleIdx];
    const cmpSample = (showCompare && cSamples.length) ? cSamples[Math.min(cSamples.length - 1, sampleIdx)] : null;

    if (curSample) {
        const cursorX = mapX(curSample[xKey]);
        ctx.strokeStyle = pitwallState.hoverTelemetryRatio !== null ? '#ffffff' : '#ff1744';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(cursorX, padT);
        ctx.lineTo(cursorX, H - padB);
        ctx.stroke();
    }

    // X-axis distance/time ticks
    ctx.fillStyle = '#9aa5b4';
    ctx.font = '10px Rajdhani, monospace';
    for (let t = 0; t <= 5; t++) {
        const frac = t / 5;
        const val = Math.round(xMin + frac * (xMax - xMin));
        const tx = padL + frac * plotW;
        ctx.fillText(`${val}${xUnit}`, tx - 14, H - 8);
    }

    // Legend & instant delta readout
    const legendEl = document.getElementById('pitwallTelemetryLegend');
    if (legendEl && curSample) {
        let html = `<span><strong style="color:${pColor}">■ ${escapeHtml(s.selected_driver)}</strong>: ${curSample.speed} km/h • G${curSample.gear} • Thr ${curSample.throttle}% • Brk ${curSample.brake}%</span>`;
        if (cmpSample && compareObj) {
            const dSpd = (curSample.speed - cmpSample.speed).toFixed(1);
            const sign = Number(dSpd) >= 0 ? '+' : '';
            html += `<span><strong style="color:${cColor}">┅ ${escapeHtml(compareObj.driver)}</strong>: ${cmpSample.speed} km/h • G${cmpSample.gear} (Δ Speed: ${sign}${dSpd} km/h)</span>`;
        }
        legendEl.innerHTML = html;
    }
}

// ==============================================================================
// INSIGHT 2: TRACK POSITION MAP & SAFETY CAR (track_position_window.py)
// ==============================================================================

function renderPitwallTrackMapCanvas() {
    const canvas = document.getElementById('pitwallTrackMapCanvas');
    if (!canvas || !pitwallState.session) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const s = pitwallState.session;
    const geo = s.track_geometry || {};
    const mode = document.getElementById('pitwallMapMode')?.value || 'circuit';
    const labelMode = document.getElementById('pitwallMapLabels')?.value || 'all';
    const frames = s.replay_frames || [];
    const frameObj = frames[pitwallState.frameIndex] || frames[0];
    const driversFrame = (frameObj && frameObj.frame && frameObj.frame.drivers) || {};
    const scState = (frameObj && frameObj.frame && frameObj.frame.safety_car) || null;

    const drvColorMap = {};
    (s.drivers || []).forEach(d => { drvColorMap[d.code] = d.color || '#E10600'; });

    if (mode === 'radar') {
        // Circular Gap-Radar schematic (leader at 12 o'clock)
        const cx = W / 2;
        const cy = H / 2;
        const R = Math.min(W, H) * 0.39;

        ctx.strokeStyle = 'rgba(255,255,255,0.14)';
        ctx.lineWidth = 14;
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = '#00e676';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(cx, cy, R, -Math.PI / 2, -Math.PI / 2 + 0.45);
        ctx.stroke();

        // Start/Finish tick at 12 o'clock
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(cx, cy - R - 10);
        ctx.lineTo(cx, cy - R + 10);
        ctx.stroke();

        Object.entries(driversFrame).forEach(([code, st]) => {
            const angle = -Math.PI / 2 + (st.rel_dist || 0) * Math.PI * 2;
            const px = cx + R * Math.cos(angle);
            const py = cy + R * Math.sin(angle);
            drawCarNode(ctx, px, py, code, drvColorMap[code] || '#fff', code === s.selected_driver, code === s.compare_driver, labelMode);
        });

        if (scState && scState.active) {
            const scAngle = -Math.PI / 2 + (scState.rel_dist || 0) * Math.PI * 2;
            drawSafetyCarNode(ctx, cx + R * Math.cos(scAngle), cy + R * Math.sin(scAngle), scState);
        }
        return;
    }

    // 2D Real Circuit Geometry mode
    const xc = geo.x_center || [];
    const yc = geo.y_center || [];
    const xi = geo.x_inner || [];
    const yi = geo.y_inner || [];
    const xo = geo.x_outer || [];
    const yo = geo.y_outer || [];
    if (!xc.length) return;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < xc.length; i++) {
        if (xc[i] < minX) minX = xc[i];
        if (xc[i] > maxX) maxX = xc[i];
        if (yc[i] < minY) minY = yc[i];
        if (yc[i] > maxY) maxY = yc[i];
    }
    const pad = 42;
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const scale = Math.min((W - pad * 2) / spanX, (H - pad * 2) / spanY);
    const offX = (W - spanX * scale) / 2;
    const offY = (H - spanY * scale) / 2;

    const toScreen = (wx, wy) => [
        offX + (wx - minX) * scale,
        H - (offY + (wy - minY) * scale),
    ];

    // Asphalt ribbon
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.14)';
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    xc.forEach((wx, idx) => {
        const [sx, sy] = toScreen(wx, yc[idx]);
        if (idx === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
    });
    ctx.closePath();
    ctx.stroke();

    // Inner & Outer track edges
    const strokeEdge = (xArr, yArr) => {
        if (!xArr.length) return;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.28)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        xArr.forEach((wx, idx) => {
            const [sx, sy] = toScreen(wx, yArr[idx]);
            if (idx === 0) ctx.moveTo(sx, sy);
            else ctx.lineTo(sx, sy);
        });
        ctx.closePath();
        ctx.stroke();
    };
    strokeEdge(xi, yi);
    strokeEdge(xo, yo);

    // DRS Zones highlighted in green
    (geo.drs_zones || []).forEach(([zStart, zEnd]) => {
        ctx.strokeStyle = 'rgba(0, 230, 118, 0.65)';
        ctx.lineWidth = 4;
        ctx.beginPath();
        const n = xc.length;
        const i0 = Math.floor(zStart * (n - 1));
        const i1 = Math.floor(zEnd * (n - 1));
        for (let i = i0; i <= i1; i++) {
            const [sx, sy] = toScreen(xc[i % n], yc[i % n]);
            if (i === i0) ctx.moveTo(sx, sy);
            else ctx.lineTo(sx, sy);
        }
        ctx.stroke();
    });

    // Start/Finish marker
    const [sfx, sfy] = toScreen(xc[0], yc[0]);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(sfx - 5, sfy - 5, 10, 10);

    // Draw non-selected drivers first, then selected drivers on top
    const entries = Object.entries(driversFrame);
    entries.sort((a, b) => {
        const aFocus = (a[0] === s.selected_driver || a[0] === s.compare_driver) ? 1 : 0;
        const bFocus = (b[0] === s.selected_driver || b[0] === s.compare_driver) ? 1 : 0;
        return aFocus - bFocus;
    });

    entries.forEach(([code, st]) => {
        const [sx, sy] = toScreen(st.x || 0, st.y || 0);
        drawCarNode(
            ctx,
            sx,
            sy,
            code,
            drvColorMap[code] || '#ffffff',
            code === s.selected_driver,
            code === s.compare_driver,
            labelMode
        );
    });

    if (scState && scState.active) {
        const [scx, scy] = toScreen(scState.x || 0, scState.y || 0);
        drawSafetyCarNode(ctx, scx, scy, scState);
    }
}

function drawCarNode(ctx, x, y, code, color, isPrimary, isCompare, labelMode) {
    ctx.save();
    if (isPrimary || isCompare) {
        ctx.beginPath();
        ctx.arc(x, y, isPrimary ? 11 : 9, 0, Math.PI * 2);
        ctx.strokeStyle = isPrimary ? '#ffffff' : '#00d2be';
        ctx.lineWidth = 2;
        ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(x, y, isPrimary ? 6.5 : 5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#070a12';
    ctx.lineWidth = 1.2;
    ctx.stroke();

    if (labelMode === 'all' || isPrimary || isCompare) {
        ctx.font = (isPrimary || isCompare) ? 'bold 11px Rajdhani, sans-serif' : '600 9.5px Rajdhani, sans-serif';
        ctx.fillStyle = isPrimary ? '#ffffff' : 'rgba(255,255,255,0.85)';
        ctx.fillText(code, x + 8, y + 3);
    }
    ctx.restore();
}

function drawSafetyCarNode(ctx, x, y, scState) {
    ctx.save();
    ctx.globalAlpha = scState.alpha ?? 1.0;
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, Math.PI * 2);
    ctx.fillStyle = '#ff9100';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.font = 'bold 11px Rajdhani, sans-serif';
    ctx.fillStyle = '#ffb300';
    ctx.fillText('SC', x + 10, y + 4);
    ctx.restore();
}

function renderPitwallTimingTower(frameObj) {
    const listEl = document.getElementById('pitwallTowerList');
    if (!listEl || !pitwallState.session || !frameObj) return;
    const s = pitwallState.session;
    const driversFrame = (frameObj.frame && frameObj.frame.drivers) || {};
    const drvMap = {};
    (s.drivers || []).forEach(d => { drvMap[d.code] = d; });

    const rows = Object.entries(driversFrame).map(([code, st]) => ({
        code,
        ...st,
        color: (drvMap[code] && drvMap[code].color) || '#888',
    }));
    rows.sort((a, b) => (a.position || 99) - (b.position || 99));

    listEl.innerHTML = rows.map(r => {
        const tyre = getTyreMeta(r.tyre);
        const isSel = r.code === s.selected_driver;
        const gapTxt = r.status === 'OUT' ? 'OUT' : (r.position === 1 ? 'Leader' : `+${(r.gap_s || 0).toFixed(1)}s`);
        return `
            <div class="tower-row ${isSel ? 'selected' : ''}" onclick="selectPitwallDriverFromUI('${escapeHtml(r.code)}')">
                <span class="tower-pos">${r.position || '—'}</span>
                <span class="tower-team-bar" style="background:${r.color}"></span>
                <span class="tower-code">${escapeHtml(r.code)}</span>
                <span class="tower-gap">${gapTxt}</span>
                <span class="tower-tyre" style="background:${tyre.hex}">${tyre.abbr}</span>
            </div>
        `;
    }).join('');
}

function selectPitwallDriverFromUI(code) {
    const drvSel = document.getElementById('pitwallDriverSelect');
    if (drvSel) {
        drvSel.value = code;
        onPitwallDriverChange();
    }
}

// ==============================================================================
// INSIGHT 3: LIVE TYRE STRATEGY GANTT (tyre_strategy_window.py)
// ==============================================================================

function renderPitwallTyreGantt() {
    const container = document.getElementById('pitwallTyreGantt');
    if (!container || !pitwallState.session) return;
    const s = pitwallState.session;
    const strategies = s.tyre_strategy || [];
    const totalLaps = (s.session_info && s.session_info.total_laps) || 57;
    const playheadPct = Math.min(100, Math.max(0, (s.selected_lap / Math.max(1, totalLaps)) * 100));

    container.innerHTML = strategies.map(row => {
        const drvCode = row.driver || row.code || '';
        const isSel = drvCode === s.selected_driver;
        const barsHtml = (row.stints || []).map(st => {
            const leftPct = ((st.start_lap - 1) / totalLaps) * 100;
            const widthPct = Math.max(1.5, ((st.end_lap - st.start_lap + 1) / totalLaps) * 100);
            const compUpper = String(st.compound || '').toUpperCase();
            const textColor = (compUpper === 'SOFT' || compUpper === 'WET' || compUpper === 'INTERMEDIATE') ? '#ffffff' : '#0b0d14';
            return `
                <div class="gantt-stint-bar"
                     style="left:${leftPct.toFixed(2)}%;width:${widthPct.toFixed(2)}%;background:${st.color};color:${textColor}"
                     title="${escapeHtml(row.name)}: ${st.compound} (Laps ${st.start_lap}–${st.end_lap}, ${st.laps_count}L)">
                    ${st.abbr} (${st.laps_count}L)
                </div>
            `;
        }).join('');

        const stopsArr = row.pit_stops || row.pit_laps || [];
        const stopsTxt = stopsArr.length ? `${stopsArr.length} stop(s)` : '0 stops';
        return `
            <div class="gantt-row ${isSel ? 'active-driver' : ''}" onclick="selectPitwallDriverFromUI('${escapeHtml(drvCode)}')">
                <div class="gantt-driver-label">
                    <span class="tower-team-bar" style="background:${row.color}"></span>
                    <span>P${row.position} <strong>${escapeHtml(drvCode)}</strong></span>
                </div>
                <div class="gantt-track">
                    ${barsHtml}
                    <div class="gantt-playhead" style="left:${playheadPct.toFixed(2)}%"></div>
                </div>
                <div class="text-muted" style="font-size:11px;text-align:right;">${stopsTxt}</div>
            </div>
        `;
    }).join('');
}

// ==============================================================================
// INSIGHT 4: LAP TIME & GAP CHART + BAYESIAN TYRE MODEL (lap_time_chart_window.py)
// ==============================================================================

function renderPitwallLapChartCanvas() {
    const canvas = document.getElementById('pitwallLapChartCanvas');
    if (!canvas || !pitwallState.session) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const s = pitwallState.session;
    const yMode = document.getElementById('pitwallLapYMode')?.value || 'laptime';
    const purePace = document.getElementById('pitwallPurePace')?.checked || false;
    const showBayes = document.getElementById('pitwallShowBayesian')?.checked || false;

    const pCode = s.selected_driver;
    const cCode = (s.compare_driver && s.compare_driver !== 'none') ? s.compare_driver : null;
    const pLapsAll = (s.lap_times && s.lap_times[pCode]) || [];
    const cLapsAll = (cCode && s.lap_times && s.lap_times[cCode]) ? s.lap_times[cCode] : [];

    const filterLaps = (arr) => purePace
        ? arr.filter(l => !l.is_pit_in && !l.is_pit_out && !l.is_sc)
        : arr;

    const pLaps = filterLaps(pLapsAll);
    const cLaps = filterLaps(cLapsAll);
    if (!pLaps.length) return;

    const drvMap = {};
    (s.drivers || []).forEach(d => { drvMap[d.code] = d; });
    const pColor = (drvMap[pCode] && drvMap[pCode].color) || '#E10600';
    const cColor = (cCode && drvMap[cCode] && drvMap[cCode].color) || '#00D2BE';

    const getVal = (l) => yMode === 'gap' ? (l.gap_to_leader_s ?? 0) : (l.time_s ?? l.lap_time_s ?? 0);
    const getLapNum = (l) => l.lap ?? l.lap_number ?? 1;

    const allVals = [...pLaps.map(getVal), ...cLaps.map(getVal)].filter(v => typeof v === 'number' && isFinite(v));
    const minY = Math.min(...allVals) - (yMode === 'gap' ? 0.5 : 0.8);
    const maxY = Math.max(...allVals) + (yMode === 'gap' ? 1.5 : 1.2);
    const totalLaps = (s.session_info && s.session_info.total_laps) || 57;

    const padL = 56, padR = 18, padT = 18, padB = 28;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;

    const mapX = (lap) => padL + ((lap - 1) / Math.max(1, totalLaps - 1)) * plotW;
    const mapY = (v) => padT + plotH - Math.max(0, Math.min(1, (v - minY) / Math.max(0.1, maxY - minY))) * plotH;

    ctx.fillStyle = 'rgba(13, 18, 32, 0.92)';
    ctx.fillRect(padL, padT, plotW, plotH);

    // Shade SC / VSC zones
    (s.sc_vsc_zones || []).forEach(z => {
        const x0 = mapX(z.start_lap);
        const x1 = mapX(z.end_lap + 0.8);
        ctx.fillStyle = z.status === 'VSC' ? 'rgba(255, 214, 0, 0.10)' : 'rgba(255, 145, 0, 0.14)';
        ctx.fillRect(x0, padT, Math.max(4, x1 - x0), plotH);
        ctx.fillStyle = '#ffb300';
        ctx.font = 'bold 9.5px Inter, sans-serif';
        ctx.fillText(z.status, x0 + 3, padT + 12);
    });

    // Horizontal grid lines
    for (let i = 0; i <= 4; i++) {
        const frac = i / 4;
        const v = minY + frac * (maxY - minY);
        const py = mapY(v);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
        ctx.beginPath();
        ctx.moveTo(padL, py);
        ctx.lineTo(padL + plotW, py);
        ctx.stroke();
        ctx.fillStyle = '#8b95a5';
        ctx.font = '10px Rajdhani, monospace';
        ctx.fillText(yMode === 'gap' ? `+${v.toFixed(1)}s` : `${v.toFixed(1)}s`, 6, py + 3);
    }

    // Bayesian State-Space Tyre Degradation Model overlay (in laptime mode)
    const bayesModel = s.bayesian_tyre_model || {};
    const pBayesRaw = (bayesModel.driver_curves && bayesModel.driver_curves[pCode]) || null;
    const preds = Array.isArray(pBayesRaw) ? pBayesRaw : (pBayesRaw && pBayesRaw.predicted_laps ? pBayesRaw.predicted_laps : []);
    if (showBayes && yMode === 'laptime' && preds.length) {
        ctx.save();
        ctx.fillStyle = 'rgba(176, 39, 201, 0.16)';
        ctx.beginPath();
        preds.forEach((pt, idx) => {
            const px = mapX(pt.lap ?? pt.lap_number);
            const std = pt.std_dev_s ?? 0.35;
            const py = mapY(pt.upper_95_s ?? (pt.predicted_s + 1.96 * std));
            if (idx === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        });
        for (let idx = preds.length - 1; idx >= 0; idx--) {
            const pt = preds[idx];
            const std = pt.std_dev_s ?? 0.35;
            ctx.lineTo(mapX(pt.lap ?? pt.lap_number), mapY(pt.lower_95_s ?? (pt.predicted_s - 1.96 * std)));
        }
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = '#e580ff';
        ctx.lineWidth = 1.8;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        preds.forEach((pt, idx) => {
            const px = mapX(pt.lap ?? pt.lap_number);
            const py = mapY(pt.predicted_s);
            if (idx === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.restore();
    }

    // Draw comparison driver series
    if (cLaps.length) {
        ctx.strokeStyle = cColor;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        cLaps.forEach((l, idx) => {
            const px = mapX(getLapNum(l));
            const py = mapY(getVal(l));
            if (idx === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        });
        ctx.stroke();
    }

    // Draw primary driver series + compound-colored dots
    ctx.strokeStyle = pColor;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    pLaps.forEach((l, idx) => {
        const px = mapX(getLapNum(l));
        const py = mapY(getVal(l));
        if (idx === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    });
    ctx.stroke();

    pLaps.forEach(l => {
        const px = mapX(getLapNum(l));
        const py = mapY(getVal(l));
        const tm = getTyreMeta(l.tyre ?? l.tyre_code ?? l.compound);
        ctx.beginPath();
        ctx.arc(px, py, 3.2, 0, Math.PI * 2);
        ctx.fillStyle = tm.hex;
        ctx.fill();
    });

    // Active lap playhead line
    const curX = mapX(s.selected_lap);
    ctx.strokeStyle = '#ff1744';
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(curX, padT);
    ctx.lineTo(curX, padT + plotH);
    ctx.stroke();

    // Bayesian summary strip
    const sumEl = document.getElementById('pitwallBayesianSummary');
    if (sumEl && bayesModel) {
        const profiles = bayesModel.profiles || [];
        const profHtml = profiles.slice(0, 3).map(p =>
            `<span class="bayesian-chip">${escapeHtml(p.compound)}: <strong>+${p.degradation_rate_sec_per_lap}s/lap</strong> (Base ${p.reset_pace_s}s)</span>`
        ).join('');
        sumEl.innerHTML = `
            <span class="bayesian-chip">🔬 <strong>Bayesian State-Space Model</strong></span>
            <span class="bayesian-chip">Track Abrasion: <strong>${bayesModel.track_abrasion_factor ?? 1.0}x</strong></span>
            <span class="bayesian-chip">Fuel Effect: <strong>${bayesModel.fuel_effect_sec_per_kg || 0.032}s/kg</strong></span>
            ${profHtml}
        `;
    }
}

// ==============================================================================
// INSIGHT 5: SECTOR TIMES & PURPLE/GREEN SPLITS (sector_times_window.py & sectors.py)
// ==============================================================================

function mapSectorStatusClass(st) {
    if (st === 'session_best' || st === 'purple') return 'purple';
    if (st === 'personal_best' || st === 'green') return 'green';
    return 'normal';
}

function renderPitwallSectorTable() {
    const kpiEl = document.getElementById('pitwallSectorKpis');
    const tbody = document.getElementById('pitwallSectorTableBody');
    if (!kpiEl || !tbody || !pitwallState.session) return;

    const s = pitwallState.session;
    const sec = s.sector_analysis || {};
    const holders = sec.session_best_holders || {};
    const h1 = holders.sector1_s || holders.s1 || {};
    const h2 = holders.sector2_s || holders.s2 || {};
    const h3 = holders.sector3_s || holders.s3 || {};

    kpiEl.innerHTML = `
        <div class="sector-kpi-card">
            <div class="kpi-title">Theoretical Best (${escapeHtml(s.selected_driver)})</div>
            <div class="kpi-val" style="color:#e580ff">${escapeHtml(sec.theoretical_best_str || sec.theoretical_best_formatted || '—')}</div>
        </div>
        <div class="sector-kpi-card">
            <div class="kpi-title">Actual Personal Best</div>
            <div class="kpi-val" style="color:#5af772">${escapeHtml(sec.actual_best_str || sec.actual_best_formatted || '—')}</div>
        </div>
        <div class="sector-kpi-card">
            <div class="kpi-title">Potential Delta</div>
            <div class="kpi-val">${sec.potential_gain_s !== null && sec.potential_gain_s !== undefined ? `-${Number(sec.potential_gain_s).toFixed(3)}s` : '—'}</div>
        </div>
        <div class="sector-kpi-card">
            <div class="kpi-title">Session Purple Sectors</div>
            <div class="kpi-val" style="font-size:13px">
                S1: ${escapeHtml(h1.driver || '—')} (${h1.time_s ? h1.time_s.toFixed(3) : '—'}s) •
                S2: ${escapeHtml(h2.driver || '—')} (${h2.time_s ? h2.time_s.toFixed(3) : '—'}s) •
                S3: ${escapeHtml(h3.driver || '—')} (${h3.time_s ? h3.time_s.toFixed(3) : '—'}s)
            </div>
        </div>
    `;

    const laps = sec.laps || [];
    tbody.innerHTML = laps.map(l => {
        const lapNum = l.lap ?? l.lap_number ?? 1;
        const tm = getTyreMeta(l.tyre ?? l.tyre_code ?? l.compound);
        const isCur = lapNum === s.selected_lap;
        const s1v = l.sector1_s ?? l.s1;
        const s2v = l.sector2_s ?? l.s2;
        const s3v = l.sector3_s ?? l.s3;
        const s1Cls = mapSectorStatusClass(l.sector1_status || l.s1_status);
        const s2Cls = mapSectorStatusClass(l.sector2_status || l.s2_status);
        const s3Cls = mapSectorStatusClass(l.sector3_status || l.s3_status);
        const lapCls = (s1Cls === 'purple' && s2Cls === 'purple' && s3Cls === 'purple')
            ? 'purple'
            : ((l.time_s && sec.actual_best_s && Math.abs(l.time_s - sec.actual_best_s) < 1e-4) ? 'green' : 'normal');
        const statusTxt = l.is_pit_in ? '🔧 PIT IN' : (l.is_pit_out ? '🔧 OUT LAP' : '🟢 TRACK');
        return `
            <tr class="${isCur ? 'active-lap-row' : ''}" onclick="jumpToPitwallLap(${lapNum})">
                <td><strong>L${lapNum}</strong></td>
                <td><span class="tower-tyre" style="background:${tm.hex}">${tm.abbr}</span> ${escapeHtml(l.compound)}</td>
                <td><span class="sector-pill ${lapCls}">${escapeHtml(l.lap_time_str || formatLapTimeSec(l.time_s))}</span></td>
                <td><span class="sector-pill ${s1Cls}">${s1v ? s1v.toFixed(3) + 's' : '—'}</span></td>
                <td><span class="sector-pill ${s2Cls}">${s2v ? s2v.toFixed(3) + 's' : '—'}</span></td>
                <td><span class="sector-pill ${s3Cls}">${s3v ? s3v.toFixed(3) + 's' : '—'}</span></td>
                <td>${statusTxt}</td>
            </tr>
        `;
    }).join('');
}

function jumpToPitwallLap(lapNum) {
    const lapSel = document.getElementById('pitwallLapSelect');
    if (lapSel) {
        lapSel.value = String(lapNum);
        onPitwallLapChange();
    }
}

// ==============================================================================
// INSIGHT 6: FIA RACE CONTROL LIVE FEED (race_control_feed_window.py)
// ==============================================================================

function renderPitwallRaceControl() {
    const listEl = document.getElementById('pitwallRaceControlList');
    if (!listEl || !pitwallState.session) return;

    const s = pitwallState.session;
    const catFilter = document.getElementById('pitwallRcFilter')?.value || 'all';
    const syncLap = document.getElementById('pitwallRcSyncLap')?.checked || false;

    let events = s.race_control || [];
    if (catFilter !== 'all') {
        events = events.filter(ev => {
            const c = (ev.category || '').toLowerCase();
            if (catFilter === 'Penalty') return c === 'penalty' || c === 'carevent' || c === 'other';
            return c === catFilter.toLowerCase();
        });
    }
    if (syncLap) {
        events = events.filter(ev => (ev.lap || 1) <= s.selected_lap);
    }

    if (!events.length) {
        listEl.innerHTML = `<div class="text-muted">No Race Control messages matching current filter.</div>`;
        return;
    }

    listEl.innerHTML = events.map(ev => `
        <div class="rc-card" style="border-left-color:${ev.accent_color || ev.color || '#3b82f6'}" onclick="jumpToPitwallLap(${ev.lap || 1})">
            <div class="rc-card-top">
                <span>LAP ${ev.lap || 1} • ${escapeHtml(ev.category || 'Info').toUpperCase()} (${escapeHtml(ev.flag || '')})</span>
                <span>${escapeHtml(ev.time_str || ev.timestamp || '')}</span>
            </div>
            <div class="rc-card-msg">${escapeHtml(ev.message || '')}</div>
        </div>
    `).join('');
}

function copyPitwallStreamPacket() {
    const pre = document.getElementById('pitwallRawStreamPre');
    if (!pre) return;
    navigator.clipboard.writeText(pre.textContent).then(() => {
        showToast('Copied live JSON telemetry frame to clipboard!');
    }).catch(() => {
        showToast('Could not copy to clipboard', 'error');
    });
}

function setupPitwallCanvasInteractions() {
    const telCanvas = document.getElementById('pitwallTelemetryCanvas');
    if (telCanvas && !telCanvas._boundHover) {
        telCanvas._boundHover = true;
        telCanvas.addEventListener('mousemove', (e) => {
            const rect = telCanvas.getBoundingClientRect();
            const relX = (e.clientX - rect.left) / Math.max(1, rect.width);
            pitwallState.hoverTelemetryRatio = Math.max(0, Math.min(1, relX));
            renderPitwallTelemetryCanvas();
        });
        telCanvas.addEventListener('mouseleave', () => {
            pitwallState.hoverTelemetryRatio = null;
            renderPitwallTelemetryCanvas();
        });
    }
}

// Keyboard shortcuts when Pit Wall section is active (Space = Play/Pause, Arrows = Step Frame, 1-4 = Speed, R = Restart)
document.addEventListener('keydown', (e) => {
    const sec = document.getElementById('section-pitwall');
    if (!sec || !sec.classList.contains('active')) return;
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : '';
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;

    if (e.code === 'Space') {
        e.preventDefault();
        togglePitwallPlayback();
    } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        stepPitwallFrame(1);
    } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        stepPitwallFrame(-1);
    } else if (e.key === 'r' || e.key === 'R') {
        restartPitwallLap();
    } else if (['1', '2', '3', '4'].includes(e.key)) {
        const speeds = { '1': 0.5, '2': 1, '3': 2, '4': 4 };
        setPitwallSpeed(speeds[e.key]);
    }
});

// ==============================================================================
// 2D TRACK REPLAY & INTERACTIVE CONTROLS (race_replay.py, qualifying.py, practice.py)
// ==============================================================================

const trackReplayState = {
    season: 2024,
    round: 1,
    sessionType: 'Race',     // 'Race' | 'Sprint' | 'Qualifying' | 'FP1' | 'FP2' | 'FP3'
    qualiSegment: 'Q3',      // 'Q1' | 'Q2' | 'Q3'
    catalogRaces: [],
    data: null,
    frameIndex: 0,
    playing: false,
    speed: 1.0,
    timerId: null,
    animFrameId: null,
    interpRatio: 0,
    rotationDeg: 0,
    showDrsZones: true,
    showSectorMarkers: true,
    showDriverLabels: true,
    showSplitChart: false,
    showChampionship: false,
    champTab: 'drivers',
    visibleHud: true,
    gapMode: 'leader',       // 'leader' (L) | 'interval' (I)
    selectedDrivers: [],     // [primaryCode, ...comparisonCodes]
};

async function openTrackReplayFor(season, roundNumber = 1, sessionType = 'Race') {
    trackReplayState.season = parseInt(season, 10) || 2024;
    trackReplayState.round = parseInt(roundNumber, 10) || 1;
    trackReplayState.sessionType = sessionType || 'Race';
    trackReplayState.frameIndex = 0;
    navigateTo('replay');
}

function openPitwallFromReplay() {
    const primary = trackReplayState.selectedDrivers[0] || '';
    openPitwallFor(trackReplayState.season, trackReplayState.round, primary, null);
}

async function loadTrackReplay() {
    const seasonSel = document.getElementById('replaySeasonSelect');
    if (seasonSel) {
        seasonSel.value = String(trackReplayState.season || 2024);
    }
    await loadReplayCatalog(trackReplayState.season, trackReplayState.round);
}

async function loadReplayCatalog(season, preferredRound = 1) {
    try {
        const cat = await apiFetch(`/api/pitwall/catalog?season=${encodeURIComponent(season)}`);
        trackReplayState.season = cat.season || season;
        trackReplayState.catalogRaces = cat.races || [];

        const raceSel = document.getElementById('replayRaceSelect');
        if (raceSel) {
            raceSel.innerHTML = trackReplayState.catalogRaces.map(r =>
                `<option value="${r.round_number}">R${r.round_number}: ${escapeHtml(r.race_name)} (${escapeHtml(r.circuit_name || '')})</option>`
            ).join('');
            const match = trackReplayState.catalogRaces.find(r => r.round_number === Number(preferredRound));
            raceSel.value = match ? String(match.round_number) : (trackReplayState.catalogRaces[0] ? String(trackReplayState.catalogRaces[0].round_number) : '1');
            trackReplayState.round = parseInt(raceSel.value, 10) || 1;
        }
        await reloadTrackReplaySession();
    } catch (err) {
        showToast(`2D Track Replay catalog error: ${err.message}`, 'error');
    }
}

function onReplaySeasonChange() {
    const sel = document.getElementById('replaySeasonSelect');
    if (!sel) return;
    const yearParsed = parseInt(parseSeasonInput(sel.value, '2024'), 10);
    trackReplayState.season = (isNaN(yearParsed) || yearParsed < 1950 || yearParsed > 2030) ? 2024 : yearParsed;
    trackReplayState.round = 1;
    loadReplayCatalog(trackReplayState.season, 1);
}

function loadReplayCustomYear() {
    onReplaySeasonChange();
}

function onReplayRaceChange() {
    const raceSel = document.getElementById('replayRaceSelect');
    if (!raceSel) return;
    trackReplayState.round = parseInt(raceSel.value, 10) || 1;
    reloadTrackReplaySession();
}

function setReplaySessionMode(mode) {
    trackReplayState.sessionType = mode;
    document.querySelectorAll('.replay-mode-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    const qualiSegField = document.getElementById('replayQualiSegmentField');
    if (qualiSegField) {
        qualiSegField.classList.toggle('hidden', mode !== 'Qualifying');
    }

    // In Qualifying and Practice modes, auto-enable the split telemetry trace chart just like qualifying.py / practice.py
    if (mode === 'Qualifying' || mode.startsWith('FP')) {
        trackReplayState.showSplitChart = true;
    }
    updateReplayOptionButtonsUI();
    reloadTrackReplaySession();
}

function setReplayQualiSegment(seg) {
    trackReplayState.qualiSegment = seg;
    document.querySelectorAll('.replay-seg-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.seg === seg);
    });
    trackReplayState.frameIndex = 0;
    renderTrackReplayAll();
}

function toggleReplayOption(opt) {
    if (opt === 'drs') trackReplayState.showDrsZones = !trackReplayState.showDrsZones;
    else if (opt === 'sectors') trackReplayState.showSectorMarkers = !trackReplayState.showSectorMarkers;
    else if (opt === 'labels') trackReplayState.showDriverLabels = !trackReplayState.showDriverLabels;
    else if (opt === 'chart') trackReplayState.showSplitChart = !trackReplayState.showSplitChart;
    else if (opt === 'championship') trackReplayState.showChampionship = !trackReplayState.showChampionship;
    else if (opt === 'hud') trackReplayState.visibleHud = !trackReplayState.visibleHud;

    updateReplayOptionButtonsUI();
    renderTrackReplayAll();
}

function updateReplayOptionButtonsUI() {
    document.getElementById('btnReplayToggleDrs')?.classList.toggle('active', trackReplayState.showDrsZones);
    document.getElementById('btnReplayToggleSectors')?.classList.toggle('active', trackReplayState.showSectorMarkers);
    document.getElementById('btnReplayToggleLabels')?.classList.toggle('active', trackReplayState.showDriverLabels);
    document.getElementById('btnReplayToggleChart')?.classList.toggle('active', trackReplayState.showSplitChart);
    document.getElementById('btnReplayToggleChamp')?.classList.toggle('active', trackReplayState.showChampionship);
    document.getElementById('btnReplayToggleHud')?.classList.toggle('active', trackReplayState.visibleHud);

    document.getElementById('replaySplitChartWrap')?.classList.toggle('hidden', !trackReplayState.showSplitChart);
    document.getElementById('replayChampBox')?.classList.toggle('hidden', !trackReplayState.showChampionship);
    document.getElementById('replayTheaterStage')?.classList.toggle('hud-hidden', !trackReplayState.visibleHud);
}

function onReplayRotationChange(deg) {
    trackReplayState.rotationDeg = parseFloat(deg) || 0;
    const lbl = document.getElementById('replayRotationVal');
    if (lbl) lbl.textContent = `${Math.round(trackReplayState.rotationDeg)}°`;
    renderTrackReplayCanvas();
}

function setReplayGapMode(mode) {
    trackReplayState.gapMode = mode === 'interval' ? 'interval' : 'leader';
    document.getElementById('btnLbIntervalGap')?.classList.toggle('active', trackReplayState.gapMode === 'interval');
    document.getElementById('btnLbLeaderGap')?.classList.toggle('active', trackReplayState.gapMode === 'leader');
    renderTrackReplayLeaderboard();
}

function setReplayChampTab(tab) {
    trackReplayState.champTab = tab;
    document.getElementById('btnChampDrivers')?.classList.toggle('active', tab === 'drivers');
    document.getElementById('btnChampConstructors')?.classList.toggle('active', tab === 'constructors');
    renderTrackReplayChampionship();
}

function toggleReplayControlsHelp(force) {
    const popup = document.getElementById('replayControlsPopup');
    if (!popup) return;
    if (typeof force === 'boolean') {
        popup.classList.toggle('hidden', !force);
    } else {
        popup.classList.toggle('hidden');
    }
}

async function reloadTrackReplaySession() {
    stopTrackReplayPlayback();
    try {
        const qs = new URLSearchParams({
            season: String(trackReplayState.season),
            round: String(trackReplayState.round),
            session_type: trackReplayState.sessionType,
            segment: trackReplayState.qualiSegment,
        });
        const data = await apiFetch(`/api/replay/session?${qs.toString()}`);
        trackReplayState.data = data;
        trackReplayState.frameIndex = 0;

        // Default primary & comparison drivers
        const drivers = data.drivers || [];
        if (!trackReplayState.selectedDrivers.length || !drivers.some(d => d.code === trackReplayState.selectedDrivers[0])) {
            trackReplayState.selectedDrivers = drivers.slice(0, 2).map(d => d.code);
        }

        // Configure progress bar range
        const frames = getActiveReplayFrames();
        const scrubber = document.getElementById('replayProgressScrubber');
        if (scrubber) {
            scrubber.max = String(Math.max(0, frames.length - 1));
            scrubber.value = '0';
        }

        renderReplayProgressEvents();
        updateReplayOptionButtonsUI();
        renderTrackReplayAll();
    } catch (err) {
        showToast(`2D Track Replay error: ${err.message}`, 'error');
    }
}

function getActiveReplayFrames() {
    const d = trackReplayState.data;
    if (!d) return [];
    return d.race_frames || [];
}

// ==============================================================================
// PLAYBACK TRANSPORT CONTROLS (RaceControlsComponent)
// ==============================================================================

function toggleTrackReplayPlayback() {
    if (trackReplayState.playing) {
        stopTrackReplayPlayback();
    } else {
        startTrackReplayPlayback();
    }
}

function formatReplayClockTime(secTotal) {
    const s = Math.max(0, Math.floor(secTotal || 0));
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function startTrackReplayPlayback() {
    if (!trackReplayState.data) return;
    stopTrackReplayPlayback();
    trackReplayState.playing = true;
    const btn = document.getElementById('btnTrackReplayPlay');
    if (btn) btn.textContent = '⏸ Pause Replay';

    // Target lap duration at 1x speed: 18.0 seconds per lap (~9x slower than the initial pacing)
    // Continuous dynamic playback: calculates exact frame spacing so 1 lap is always 18s at 1x
    const frames = getActiveReplayFrames();
    const totalLaps = (trackReplayState.data && trackReplayState.data.session_info && trackReplayState.data.session_info.total_laps) || 57;
    const framesPerLap = Math.max(1, (frames.length || 1) / Math.max(1, totalLaps));
    const targetLapDurationMs = 18000;
    const baseFrameDurationMs = Math.max(100, Math.round(targetLapDurationMs / framesPerLap));

    let lastTime = performance.now();
    let accumulatedMs = trackReplayState.interpRatio * (baseFrameDurationMs / trackReplayState.speed);

    function step(now) {
        if (!trackReplayState.playing) return;
        const delta = Math.min(100, now - lastTime);
        lastTime = now;

        const frameIntervalMs = Math.max(30, Math.round(baseFrameDurationMs / trackReplayState.speed));
        accumulatedMs += delta;

        const curFrames = getActiveReplayFrames();
        if (!curFrames.length) return;

        let frameChanged = false;
        while (accumulatedMs >= frameIntervalMs) {
            accumulatedMs -= frameIntervalMs;
            if (trackReplayState.frameIndex < curFrames.length - 1) {
                trackReplayState.frameIndex++;
                frameChanged = true;
            } else {
                trackReplayState.frameIndex = curFrames.length - 1;
                trackReplayState.interpRatio = 0;
                renderTrackReplayAll();
                stopTrackReplayPlayback();
                return;
            }
        }

        trackReplayState.interpRatio = Math.max(0, Math.min(1, accumulatedMs / frameIntervalMs));

        // When stepping into a new keyframe, update heavy DOM tables (Leaderboard, Weather, Cards)
        if (frameChanged) {
            renderTrackReplayDOM(curFrames[trackReplayState.frameIndex]);
        }

        // Every 60 FPS tick: continuously glide cars, update scrubber, tick race clock
        renderTrackReplayContinuous(curFrames);

        trackReplayState.animFrameId = requestAnimationFrame(step);
    }

    trackReplayState.animFrameId = requestAnimationFrame(step);
}

function stopTrackReplayPlayback() {
    trackReplayState.playing = false;
    trackReplayState.interpRatio = 0;
    if (trackReplayState.animFrameId) {
        cancelAnimationFrame(trackReplayState.animFrameId);
        trackReplayState.animFrameId = null;
    }
    if (trackReplayState.timerId) {
        clearInterval(trackReplayState.timerId);
        trackReplayState.timerId = null;
    }
    const btn = document.getElementById('btnTrackReplayPlay');
    if (btn) btn.textContent = '▶ Play Replay';
}

function setTrackReplaySpeed(spd) {
    trackReplayState.speed = Number(spd) || 1.0;
    document.querySelectorAll('[data-rspeed]').forEach(b => {
        b.classList.toggle('active', Number(b.getAttribute('data-rspeed')) === trackReplayState.speed);
    });
    if (trackReplayState.playing) {
        startTrackReplayPlayback();
    }
}

function jumpTrackReplayFrames(delta) {
    const frames = getActiveReplayFrames();
    if (!frames.length) return;
    trackReplayState.interpRatio = 0;
    trackReplayState.frameIndex = Math.max(0, Math.min(frames.length - 1, trackReplayState.frameIndex + delta));
    renderTrackReplayAll();
}

function restartTrackReplay() {
    trackReplayState.interpRatio = 0;
    trackReplayState.frameIndex = 0;
    renderTrackReplayAll();
}

function onReplayScrubberInput(val) {
    const floatVal = parseFloat(val) || 0;
    const baseFrame = Math.floor(floatVal);
    trackReplayState.frameIndex = baseFrame;
    trackReplayState.interpRatio = Math.max(0, Math.min(1, floatVal - baseFrame));
    renderTrackReplayAll();
}

// ==============================================================================
// RENDER ALL 2D TRACK REPLAY COMPONENTS (Continuous 60 FPS + DOM Keyframe)
// ==============================================================================

function renderTrackReplayAll() {
    const d = trackReplayState.data;
    if (!d) return;
    const frames = getActiveReplayFrames();
    const frame = frames[trackReplayState.frameIndex] || frames[0];
    if (!frame) return;

    renderTrackReplayDOM(frame);
    renderTrackReplayContinuous(frames);
}

// 1. Heavy DOM elements updated on keyframe boundaries (Leaderboard, Weather, Cards)
function renderTrackReplayDOM(frame) {
    const d = trackReplayState.data;
    if (!d || !frame) return;
    const info = d.session_info || {};
    const mode = trackReplayState.sessionType;

    const evEl = document.getElementById('replayBannerEvent');
    if (evEl) evEl.textContent = `${info.season || ''} ${info.race_name || ''}`;
    const cirEl = document.getElementById('replayBannerCircuit');
    if (cirEl) cirEl.textContent = `${info.circuit_name || ''} • ${info.circuit_length_m || 5000}m`;

    const lapEl = document.getElementById('replayLapText');
    if (lapEl) {
        if (mode === 'Qualifying') {
            lapEl.textContent = `QUALIFYING • ${trackReplayState.qualiSegment}`;
        } else if (mode.startsWith('FP')) {
            lapEl.textContent = `PRACTICE • ${mode}`;
        } else {
            lapEl.textContent = `LAP ${frame.lap} / ${frame.total_laps}`;
        }
    }

    const stBadge = document.getElementById('replayTrackStatusBadge');
    if (stBadge) {
        const st = frame.track_status || 'GREEN';
        if (st === 'SC') {
            stBadge.className = 'replay-status-badge sc';
            stBadge.textContent = '🟠 SAFETY CAR DEPLOYED';
        } else if (st === 'VSC') {
            stBadge.className = 'replay-status-badge vsc';
            stBadge.textContent = '🟡 VIRTUAL SAFETY CAR';
        } else if (st === 'CHEQUERED') {
            stBadge.className = 'replay-status-badge chequered';
            stBadge.textContent = '🏁 CHEQUERED FLAG';
        } else {
            stBadge.className = 'replay-status-badge green';
            stBadge.textContent = '🟢 TRACK CLEAR';
        }
    }

    // Weather HUD (WeatherComponent)
    const w = frame.weather || {};
    const setTxt = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };
    setTxt('rwTrackTemp', `${w.track_temp ?? 37.5}°C`);
    setTxt('rwAirTemp', `${w.air_temp ?? 26.0}°C`);
    setTxt('rwHumidity', `${w.humidity ?? 48}%`);
    setTxt('rwWind', `${w.wind_speed ?? 9.0} km/h ${w.wind_cardinal || 'NNE'}`);
    setTxt('rwRain', w.rain_state || 'DRY (0%)');

    // Selected Driver Telemetry Card
    renderReplaySelectedDriverInfo(frame);

    // Championship Overlay (if visible)
    if (trackReplayState.showChampionship) {
        renderTrackReplayChampionship();
    }

    // Leaderboard Timing Tower
    renderTrackReplayLeaderboard(frame);
}

// 2. Continuous 60 FPS updates: Smooth Canvas, Continuous Scrubber, Live Clock, Split Playhead
function renderTrackReplayContinuous(curFrames) {
    if (!curFrames || !curFrames.length) return;
    const fIdx = trackReplayState.frameIndex;
    const frame = curFrames[fIdx] || curFrames[0];
    const nextFrame = curFrames[Math.min(curFrames.length - 1, fIdx + 1)] || frame;
    const interp = (trackReplayState.playing && typeof trackReplayState.interpRatio === 'number') ? trackReplayState.interpRatio : (trackReplayState.interpRatio || 0);

    // Continuous Scrubber
    const scrubber = document.getElementById('replayProgressScrubber');
    if (scrubber) {
        scrubber.value = String((fIdx + interp).toFixed(2));
    }

    // Continuous Stopwatch Clock
    if (frame && nextFrame) {
        const t0 = frame.t || 0;
        const t1 = nextFrame.t || t0;
        const dT = Math.max(0, t1 - t0);
        const curSeconds = t0 + dT * interp;
        const timeStr = formatReplayClockTime(curSeconds);
        const clkEl = document.getElementById('replayClockText');
        if (clkEl) clkEl.textContent = timeStr;
        const rightLbl = document.getElementById('replayProgressRightLabel');
        if (rightLbl) rightLbl.textContent = timeStr;

        const leftLbl = document.getElementById('replayProgressLeftLabel');
        if (leftLbl) {
            const p0 = frame.progress_pct || 0;
            const p1 = nextFrame.progress_pct || p0;
            const curPct = (p0 + Math.max(0, p1 - p0) * interp).toFixed(1);
            const mode = trackReplayState.sessionType;
            if (mode === 'Qualifying') {
                leftLbl.textContent = `${trackReplayState.qualiSegment} Flying Lap (${curPct}%)`;
            } else if (mode.startsWith('FP')) {
                leftLbl.textContent = `${mode} Practice Lap (${curPct}%)`;
            } else {
                leftLbl.textContent = `Lap ${frame.lap} / ${frame.total_laps} (${curPct}%)`;
            }
        }
    }

    // Redraw 2D Track Canvas with smooth car motion
    renderTrackReplayCanvas();

    // Redraw Split Telemetry Trace with continuous playhead
    if (trackReplayState.showSplitChart) {
        renderReplaySplitTelemetryCanvas(frame);
    }
}

function renderReplayProgressEvents() {
    const layer = document.getElementById('replayProgressEventsLayer');
    if (!layer || !trackReplayState.data) return;
    const events = trackReplayState.data.race_events || [];
    layer.innerHTML = events.map(ev => `
        <div class="replay-event-marker"
             style="left:${ev.progress_pct}%;width:${Math.max(0.5, ev.width_pct || 0.8)}%;background:${ev.color || '#FF9100'}"
             title="${escapeHtml(ev.label || ev.type)}"></div>
    `).join('');
}

function renderReplaySelectedDriverInfo(frame) {
    const box = document.getElementById('replaySelectedDriverContent');
    if (!box || !trackReplayState.data || !frame) return;
    const drvMap = {};
    (trackReplayState.data.drivers || []).forEach(d => { drvMap[d.code] = d; });

    const sel = trackReplayState.selectedDrivers.slice(0, 2);
    if (!sel.length) {
        box.innerHTML = `<div class="text-muted">Click any driver on the leaderboard to inspect telemetry &amp; tyre health.</div>`;
        return;
    }

    box.innerHTML = sel.map((code, idx) => {
        const st = (frame.drivers && frame.drivers[code]) || {};
        const meta = drvMap[code] || { name: code, color: '#E10600' };
        const health = st.tyre_health ?? 85;
        const healthColor = health > 60 ? '#00e676' : (health > 30 ? '#ffb300' : '#ff1744');
        const roleTag = idx === 0 ? 'PRIMARY' : 'COMPARE';
        return `
            <div class="driver-info-card">
                <div class="driver-info-head">
                    <span><strong style="color:${meta.color}">■ ${escapeHtml(code)}</strong> <small class="text-muted">${escapeHtml(meta.name)}</small></span>
                    <span class="badge badge-${idx === 0 ? 'danger' : 'info'}">${roleTag} • P${st.position || '—'}</span>
                </div>
                <div class="driver-info-metrics">
                    <span>SPD: <strong>${Math.round(st.speed || 0)}</strong> km/h</span>
                    <span>GEAR: <strong>${st.gear || 'N'}</strong></span>
                    <span>DRS: <strong style="color:${st.drs ? '#00e676' : '#888'}">${st.drs ? 'ON' : 'OFF'}</strong></span>
                    <span>THR: <strong style="color:#00e676">${Math.round(st.throttle || 0)}%</strong></span>
                    <span>BRK: <strong style="color:#ff1744">${Math.round(st.brake || 0)}%</strong></span>
                    <span>LAP: <strong>${st.lap || frame.lap}</strong></span>
                </div>
                <div class="tyre-health-strip">
                    <span class="lb-tyre-badge" style="background:${st.compound_color || '#FFF200'}">${escapeHtml(st.compound_abbr || 'M')}</span>
                    <div class="tyre-health-bar-outer">
                        <div class="tyre-health-bar-inner" style="width:${health}%;background:${healthColor}"></div>
                    </div>
                    <span><strong>${Math.round(health)}%</strong> (${st.tyre_life || 1}L)</span>
                </div>
            </div>
        `;
    }).join('');
}

function renderTrackReplayChampionship() {
    const listEl = document.getElementById('replayChampList');
    if (!listEl || !trackReplayState.data) return;
    const champ = trackReplayState.data.championship_overlay || {};
    if (trackReplayState.champTab === 'constructors') {
        const rows = champ.constructors || [];
        listEl.innerHTML = rows.map(r => `
            <div class="champ-row">
                <span><strong>P${r.position}</strong> <i style="display:inline-block;width:3px;height:10px;background:${r.color};margin:0 4px"></i> ${escapeHtml(r.team)}</span>
                <span><strong>${r.live_points} pts</strong> <small style="color:#00e676">(+${r.live_gain})</small></span>
            </div>
        `).join('');
    } else {
        const rows = champ.drivers || [];
        listEl.innerHTML = rows.map(r => `
            <div class="champ-row">
                <span><strong>P${r.position}</strong> <i style="display:inline-block;width:3px;height:10px;background:${r.color};margin:0 4px"></i> ${escapeHtml(r.code)}</span>
                <span><strong>${r.live_points} pts</strong> <small style="color:#00e676">(+${r.live_gain})</small></span>
            </div>
        `).join('');
    }
}

// ==============================================================================
// LIVE LEADERBOARD COMPONENT (LeaderboardComponent & LapTimeLeaderboardComponent)
// ==============================================================================

function renderTrackReplayLeaderboard(frameInput) {
    const rowsEl = document.getElementById('replayLeaderboardRows');
    const titleEl = document.getElementById('replayLeaderboardTitle');
    const radiosEl = document.getElementById('replayLbGapRadios');
    if (!rowsEl || !trackReplayState.data) return;

    const d = trackReplayState.data;
    const mode = trackReplayState.sessionType;
    const frames = getActiveReplayFrames();
    const frame = frameInput || frames[trackReplayState.frameIndex] || frames[0];

    // QUALIFYING MODE (LapTimeLeaderboardComponent)
    if (mode === 'Qualifying' && d.qualifying) {
        if (titleEl) titleEl.textContent = `QUALIFYING (${trackReplayState.qualiSegment})`;
        if (radiosEl) radiosEl.classList.add('hidden');
        const seg = trackReplayState.qualiSegment;
        const results = d.qualifying.results || [];

        rowsEl.innerHTML = results.map(r => {
            const isPrimary = trackReplayState.selectedDrivers[0] === r.code;
            const isCompare = trackReplayState.selectedDrivers.slice(1).includes(r.code);
            const rowCls = isPrimary ? 'selected-primary' : (isCompare ? 'selected-compare' : '');
            const segTime = r[seg] || r.time;
            const isElim = (seg === 'Q2' && r.pos > 15) || (seg === 'Q3' && r.pos > 10);
            return `
                <div class="replay-lb-row ${rowCls}" onclick="onReplayLeaderboardClick(event, '${escapeHtml(r.code)}')">
                    <span class="lb-pos">${r.pos}.</span>
                    <span class="tower-team-bar" style="background:${r.color}"></span>
                    <span class="lb-code" style="color:${r.color}">
                        ${escapeHtml(r.code)}
                        ${isElim ? '<span class="lb-out-tag">OUT</span>' : ''}
                    </span>
                    <span class="lb-gap">${escapeHtml(segTime)}</span>
                    <span class="lb-tyre-cell">
                        <span class="lb-tyre-badge" style="background:#E8002D">S</span>
                    </span>
                </div>
            `;
        }).join('');
        return;
    }

    // PRACTICE MODE (FP1 / FP2 / FP3 — LapTimeLeaderboardComponent)
    if (mode.startsWith('FP') && d.practice && d.practice[mode]) {
        if (titleEl) titleEl.textContent = `${mode} TIMES`;
        if (radiosEl) radiosEl.classList.add('hidden');
        const results = d.practice[mode].results || [];

        rowsEl.innerHTML = results.map(r => {
            const isPrimary = trackReplayState.selectedDrivers[0] === r.code;
            const isCompare = trackReplayState.selectedDrivers.slice(1).includes(r.code);
            const rowCls = isPrimary ? 'selected-primary' : (isCompare ? 'selected-compare' : '');
            return `
                <div class="replay-lb-row ${rowCls}" onclick="onReplayLeaderboardClick(event, '${escapeHtml(r.code)}')">
                    <span class="lb-pos">${r.pos}.</span>
                    <span class="tower-team-bar" style="background:${r.color}"></span>
                    <span class="lb-code" style="color:${r.color}" title="${escapeHtml(r.full_name)}">${escapeHtml(r.code)}</span>
                    <span class="lb-gap">${escapeHtml(r.time)} <small class="text-muted">(${escapeHtml(r.gap_str)})</small></span>
                    <span class="lb-tyre-cell">
                        <span class="lb-tyre-badge" style="background:${r.compound_color}">${escapeHtml(r.compound_abbr)}</span>
                        <span class="lb-tyre-life">${r.tyre_life}</span>
                    </span>
                </div>
            `;
        }).join('');
        return;
    }

    // RACE / SPRINT MODE (LeaderboardComponent with Interval I / Leader L toggle, PIT/OUT, Tyre Health)
    if (titleEl) titleEl.textContent = mode === 'Sprint' ? 'SPRINT TOWER' : 'LEADERBOARD';
    if (radiosEl) radiosEl.classList.remove('hidden');
    if (!frame || !frame.drivers) return;

    const drvColorMap = {};
    (d.drivers || []).forEach(drv => { drvColorMap[drv.code] = drv.color || '#ffffff'; });

    const entries = Object.entries(frame.drivers).map(([code, st]) => ({
        code,
        color: drvColorMap[code] || '#ffffff',
        ...st,
    }));
    entries.sort((a, b) => (a.position || 99) - (b.position || 99));

    rowsEl.innerHTML = entries.map((e, i) => {
        const isPrimary = trackReplayState.selectedDrivers[0] === e.code;
        const isCompare = trackReplayState.selectedDrivers.slice(1).includes(e.code);
        const rowCls = isPrimary ? 'selected-primary' : (isCompare ? 'selected-compare' : '');

        let gapText = '-';
        if (e.is_out) {
            gapText = '';
        } else if (i === 0) {
            gapText = 'Leader';
        } else if (trackReplayState.gapMode === 'interval') {
            gapText = e.interval !== null && e.interval !== undefined ? `+${Number(e.interval).toFixed(1)}s` : '';
        } else {
            gapText = e.gap_to_leader !== null && e.gap_to_leader !== undefined ? `+${Number(e.gap_to_leader).toFixed(1)}s` : '';
        }

        const posDelta = e.pos_change || 0;
        const arrowHtml = posDelta > 0
            ? `<small style="color:#00e676">▲</small>`
            : (posDelta < 0 ? `<small style="color:#ff1744">▼</small>` : '');

        const healthPct = Math.round(e.tyre_health ?? 100);
        return `
            <div class="replay-lb-row ${rowCls}" onclick="onReplayLeaderboardClick(event, '${escapeHtml(e.code)}')">
                <span class="lb-pos">${e.position}.</span>
                <span class="tower-team-bar" style="background:${e.color}"></span>
                <span class="lb-code" style="color:${e.color}">
                    ${escapeHtml(e.code)} ${arrowHtml}
                    ${e.in_pit ? '<span class="lb-pit-tag">PIT</span>' : ''}
                    ${e.is_out ? '<span class="lb-out-tag">OUT</span>' : ''}
                </span>
                <span class="lb-gap">${escapeHtml(gapText)}</span>
                <span class="lb-tyre-cell" title="Tyre Health: ${healthPct}% (${e.tyre_life || 1} laps)">
                    <span class="lb-tyre-badge" style="background:${e.compound_color || '#FFF200'};opacity:${Math.max(0.45, healthPct / 100)}">${escapeHtml(e.compound_abbr || 'M')}</span>
                    <span class="lb-tyre-life">${e.tyre_life || 0}</span>
                </span>
            </div>
        `;
    }).join('');
}

function onReplayLeaderboardClick(event, code) {
    if (event && event.shiftKey) {
        // Shift+Click: toggle comparison driver (PracticeReplay / QualifyingReplay behavior)
        if (trackReplayState.selectedDrivers[0] === code) return;
        const idx = trackReplayState.selectedDrivers.indexOf(code);
        if (idx > 0) {
            trackReplayState.selectedDrivers.splice(idx, 1);
        } else {
            trackReplayState.selectedDrivers.push(code);
        }
    } else {
        // Primary selection
        const existingComp = trackReplayState.selectedDrivers.filter(c => c !== code);
        trackReplayState.selectedDrivers = [code, ...existingComp.slice(0, 1)];
    }
    renderTrackReplayAll();
}

function cycleReplayComparisonDriver() {
    if (!trackReplayState.data) return;
    const drivers = (trackReplayState.data.drivers || []).map(d => d.code);
    if (drivers.length < 2) return;
    const primary = trackReplayState.selectedDrivers[0] || drivers[0];
    const currentComp = trackReplayState.selectedDrivers[1] || null;
    const candidates = drivers.filter(c => c !== primary);
    const nextIdx = currentComp ? (candidates.indexOf(currentComp) + 1) % candidates.length : 0;
    trackReplayState.selectedDrivers = [primary, candidates[nextIdx]];
    if (!trackReplayState.showSplitChart) {
        trackReplayState.showSplitChart = true;
        updateReplayOptionButtonsUI();
    }
    renderTrackReplayAll();
}

function clearReplayComparisonDrivers() {
    if (trackReplayState.selectedDrivers.length > 1) {
        trackReplayState.selectedDrivers = [trackReplayState.selectedDrivers[0]];
    }
    renderTrackReplayAll();
}

// Interpolate world (x, y) coordinates along track centerline geometry at fractional lap distance relDist in [0, 1]
function getReplayTrackXY(geo, relDist) {
    if (!geo) return [0, 0];
    const cx = geo.x_center || [];
    const cy = geo.y_center || [];
    const n = cx.length;
    if (n < 2) return [0, 0];
    let frac = (Number(relDist) || 0) % 1.0;
    if (frac < 0) frac += 1.0;
    const idxF = frac * (n - 1);
    const i0 = Math.floor(idxF) % (n - 1);
    const i1 = (i0 + 1) % n;
    const alpha = idxF - Math.floor(idxF);
    const x = cx[i0] * (1.0 - alpha) + cx[i1] * alpha;
    const y = cy[i0] * (1.0 - alpha) + cy[i1] * alpha;
    return [x, y];
}

function renderTrackReplayCanvas(frameInput) {
    const canvas = document.getElementById('trackReplayCanvas');
    if (!canvas || !trackReplayState.data) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const d = trackReplayState.data;
    const geo = d.track_geometry || {};
    const xc = geo.x_center || [];
    const yc = geo.y_center || [];
    const xi = geo.x_inner || [];
    const yi = geo.y_inner || [];
    const xo = geo.x_outer || [];
    const yo = geo.y_outer || [];
    if (!xc.length) return;

    const frames = getActiveReplayFrames();
    const frame = frameInput || frames[trackReplayState.frameIndex] || frames[0];

    // Rotate world coordinates around circuit center (ported from update_scaling in race_replay.py)
    const rawMinX = Math.min(...xc), rawMaxX = Math.max(...xc);
    const rawMinY = Math.min(...yc), rawMaxY = Math.max(...yc);
    const worldCx = (rawMinX + rawMaxX) / 2;
    const worldCy = (rawMinY + rawMaxY) / 2;
    const rad = (trackReplayState.rotationDeg * Math.PI) / 180.0;
    const cosR = Math.cos(rad);
    const sinR = Math.sin(rad);

    const rotatePt = (wx, wy) => {
        const tx = wx - worldCx;
        const ty = wy - worldCy;
        return [
            tx * cosR - ty * sinR + worldCx,
            tx * sinR + ty * cosR + worldCy,
        ];
    };

    const rotCenter = xc.map((wx, i) => rotatePt(wx, yc[i]));
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    rotCenter.forEach(([rx, ry]) => {
        if (rx < minX) minX = rx;
        if (rx > maxX) maxX = rx;
        if (ry < minY) minY = ry;
        if (ry > maxY) maxY = ry;
    });

    const pad = 48;
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const scale = Math.min((W - pad * 2) / spanX, (H - pad * 2) / spanY);
    const offX = (W - spanX * scale) / 2;
    const offY = (H - spanY * scale) / 2;

    const worldToScreen = (wx, wy) => {
        const [rx, ry] = rotatePt(wx, wy);
        return [
            offX + (rx - minX) * scale,
            H - (offY + (ry - minY) * scale),
        ];
    };

    // 1. Draw track asphalt ribbon
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.13)';
    ctx.lineWidth = 18;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    xc.forEach((wx, idx) => {
        const [sx, sy] = worldToScreen(wx, yc[idx]);
        if (idx === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
    });
    ctx.closePath();
    ctx.stroke();

    // 2. Draw inner and outer GPS track boundaries
    const drawBoundary = (xArr, yArr) => {
        if (!xArr.length) return;
        ctx.strokeStyle = 'rgba(205, 214, 230, 0.42)';
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        xArr.forEach((wx, idx) => {
            const [sx, sy] = worldToScreen(wx, yArr[idx]);
            if (idx === 0) ctx.moveTo(sx, sy);
            else ctx.lineTo(sx, sy);
        });
        ctx.closePath();
        ctx.stroke();
    };
    drawBoundary(xi, yi);
    drawBoundary(xo, yo);

    // 3. Draw DRS Zones along outer/center track (toggleable via 'D')
    if (trackReplayState.showDrsZones) {
        (geo.drs_zones || []).forEach(([zStart, zEnd], zIdx) => {
            ctx.strokeStyle = '#00e676';
            ctx.lineWidth = 5;
            ctx.beginPath();
            const n = xc.length;
            const i0 = Math.floor(zStart * (n - 1));
            const i1 = Math.floor(zEnd * (n - 1));
            for (let i = i0; i <= i1; i++) {
                const [sx, sy] = worldToScreen(xc[i % n], yc[i % n]);
                if (i === i0) ctx.moveTo(sx, sy);
                else ctx.lineTo(sx, sy);
            }
            ctx.stroke();

            const midI = Math.floor(((i0 + i1) / 2) % n);
            const [mx, my] = worldToScreen(xc[midI], yc[midI]);
            ctx.fillStyle = '#00e676';
            ctx.font = 'bold 10px Rajdhani, sans-serif';
            ctx.fillText(`DRS ${zIdx + 1}`, mx + 8, my - 8);
        });
    }

    // 4. Draw Sector Markers (SF Checkered Line, S1, S2 — toggleable via 'S')
    if (trackReplayState.showSectorMarkers) {
        (geo.sector_markers || []).forEach(m => {
            const [ixS, iyS] = worldToScreen(m.x_inner, m.y_inner);
            const [oxS, oyS] = worldToScreen(m.x_outer, m.y_outer);
            const [cxS, cyS] = worldToScreen(m.x, m.y);

            ctx.save();
            ctx.strokeStyle = m.code === 'SF' ? '#ffffff' : m.color;
            ctx.lineWidth = m.code === 'SF' ? 3.5 : 2.5;
            ctx.beginPath();
            ctx.moveTo(ixS, iyS);
            ctx.lineTo(oxS, oyS);
            ctx.stroke();

            ctx.fillStyle = m.color;
            ctx.font = 'bold 11px Rajdhani, sans-serif';
            ctx.fillText(m.code, cxS + 9, cyS - 7);
            ctx.restore();
        });
    }

    // 5. Draw all 20 cars (or Qualifying flying lap ghost comparison)
    const drvColorMap = {};
    (d.drivers || []).forEach(drv => { drvColorMap[drv.code] = drv.color || '#ffffff'; });

    const driversObj = (frame && frame.drivers) || {};
    const entries = Object.entries(driversObj);

    // Look ahead to next frame for smooth sub-frame interpolation
    const nextFrame = frames[Math.min(frames.length - 1, trackReplayState.frameIndex + 1)];
    const interp = (trackReplayState.playing && typeof trackReplayState.interpRatio === 'number') ? trackReplayState.interpRatio : 0;

    // Draw non-selected cars first, then selected cars on top
    entries.sort((a, b) => {
        const aSel = trackReplayState.selectedDrivers.includes(a[0]) ? 1 : 0;
        const bSel = trackReplayState.selectedDrivers.includes(b[0]) ? 1 : 0;
        return aSel - bSel;
    });

    entries.forEach(([code, st]) => {
        if (st.is_out) return; // Retired cars shown as OUT on leaderboard
        let curRel = st.rel_dist || 0;

        // Smooth track-following position interpolation towards nextFrame
        if (interp > 0 && typeof st.rel_dist === 'number' && nextFrame && nextFrame.drivers && nextFrame.drivers[code] && !nextFrame.drivers[code].is_out) {
            const nextSt = nextFrame.drivers[code];
            let dRel = (nextSt.rel_dist || 0) - st.rel_dist;
            // Handle lap wrap-around across start/finish line
            if (dRel < -0.5) dRel += 1.0;
            else if (dRel > 0.5) dRel -= 1.0;
            curRel = st.rel_dist + dRel * interp;
        }

        const [wx, wy] = getReplayTrackXY(geo, curRel);
        const [sx, sy] = worldToScreen(wx, wy);

        // Compute forward heading in screen space along the track curve
        const [aheadWx, aheadWy] = getReplayTrackXY(geo, curRel + 0.003);
        const [aheadSx, aheadSy] = worldToScreen(aheadWx, aheadWy);
        const screenAngle = Math.atan2(aheadSy - sy, aheadSx - sx);

        const isPrimary = trackReplayState.selectedDrivers[0] === code;
        const isCompare = trackReplayState.selectedDrivers.slice(1).includes(code);
        const col = drvColorMap[code] || '#ffffff';

        ctx.save();

        // Subtle motion trail behind each car (gives real broadcast GPS stream effect)
        const [trailWx1, trailWy1] = getReplayTrackXY(geo, curRel - 0.0035);
        const [trailSx1, trailSy1] = worldToScreen(trailWx1, trailWy1);
        const [trailWx2, trailWy2] = getReplayTrackXY(geo, curRel - 0.007);
        const [trailSx2, trailSy2] = worldToScreen(trailWx2, trailWy2);

        ctx.strokeStyle = col;
        ctx.lineCap = 'round';
        ctx.globalAlpha = 0.28;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.moveTo(trailSx2, trailSy2);
        ctx.lineTo(trailSx1, trailSy1);
        ctx.lineTo(sx, sy);
        ctx.stroke();
        ctx.globalAlpha = 1.0;

        // Selection halo
        if (isPrimary || isCompare) {
            ctx.beginPath();
            ctx.arc(sx, sy, isPrimary ? 13 : 11, 0, Math.PI * 2);
            ctx.strokeStyle = isPrimary ? '#ffffff' : '#00d2be';
            ctx.lineWidth = 2.2;
            ctx.stroke();
        }

        // Draw sleek directional car body
        ctx.translate(sx, sy);
        ctx.rotate(screenAngle);

        // Car main body dot / capsule
        ctx.fillStyle = col;
        ctx.beginPath();
        if (isPrimary || isCompare) {
            ctx.ellipse(0, 0, 7.5, 5, 0, 0, Math.PI * 2);
        } else {
            ctx.ellipse(0, 0, 6, 4, 0, 0, Math.PI * 2);
        }
        ctx.fill();
        ctx.strokeStyle = '#060911';
        ctx.lineWidth = 1.3;
        ctx.stroke();

        // Forward nose pointer
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.moveTo(isPrimary ? 6.5 : 5, -1.8);
        ctx.lineTo(isPrimary ? 9.5 : 7.8, 0);
        ctx.lineTo(isPrimary ? 6.5 : 5, 1.8);
        ctx.closePath();
        ctx.fill();

        ctx.restore(); // Restores translation & rotation

        // High-contrast driver code label
        if (trackReplayState.showDriverLabels || isPrimary || isCompare) {
            ctx.save();
            ctx.font = (isPrimary || isCompare) ? 'bold 11px Rajdhani, sans-serif' : '600 9.5px Rajdhani, sans-serif';
            const labelX = sx + 10;
            const labelY = sy + 3.5;
            ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
            ctx.fillText(code, labelX + 1, labelY + 1);
            ctx.fillStyle = isPrimary ? '#ffffff' : (isCompare ? '#00d2be' : 'rgba(255, 255, 255, 0.92)');
            ctx.fillText(code, labelX, labelY);
            ctx.restore();
        }
    });

    // 6. Draw Safety Car (if active on track)
    const sc = frame && frame.safety_car;
    if (sc && sc.active) {
        let scWx = sc.x || 0;
        let scWy = sc.y || 0;
        if (interp > 0 && typeof sc.rel_dist === 'number' && nextFrame && nextFrame.safety_car && nextFrame.safety_car.active) {
            const nextSc = nextFrame.safety_car;
            let dScRel = (nextSc.rel_dist || 0) - sc.rel_dist;
            if (dScRel < -0.5) dScRel += 1.0;
            else if (dScRel > 0.5) dScRel -= 1.0;
            const curScRel = sc.rel_dist + dScRel * interp;
            const [twx, twy] = getReplayTrackXY(geo, curScRel);
            if (twx !== 0 || twy !== 0) {
                scWx = twx;
                scWy = twy;
            }
        }
        const [scx, scy] = worldToScreen(scWx, scWy);
        drawSafetyCarNode(ctx, scx, scy, sc);
    }
}

// ==============================================================================
// SPLIT-SCREEN TELEMETRY CHART (QualifyingReplay & PracticeReplay top half)
// ==============================================================================

function renderReplaySplitTelemetryCanvas(frame) {
    const canvas = document.getElementById('replaySplitTelemetryCanvas');
    if (!canvas || !trackReplayState.data) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const d = trackReplayState.data;
    const primary = trackReplayState.selectedDrivers[0] || (d.drivers && d.drivers[0]?.code) || 'VER';
    const compare = trackReplayState.selectedDrivers[1] || null;
    const seg = trackReplayState.qualiSegment || 'Q3';

    const titleEl = document.getElementById('replaySplitChartTitle');
    if (titleEl) {
        titleEl.textContent = compare
            ? `Telemetry Overlay: ${primary} (Solid) vs ${compare} (Dashed) — Speed • Gear • Throttle/Brake`
            : `Telemetry Trace: ${primary} — Speed • Gear • Throttle/Brake`;
    }

    const qTel = (d.qualifying && d.qualifying.telemetry) || {};
    const pSamples = (qTel[primary] && (qTel[primary][seg] || qTel[primary].Q1)) || [];
    const cSamples = (compare && qTel[compare] && (qTel[compare][seg] || qTel[compare].Q1)) || [];
    if (!pSamples.length) return;

    const drvMap = {};
    (d.drivers || []).forEach(drv => { drvMap[drv.code] = drv.color || '#E10600'; });
    const pColor = drvMap[primary] || '#E10600';
    const cColor = (compare && drvMap[compare]) || '#00D2BE';

    const padL = 44, padR = 14, padT = 8, padB = 18, gap = 6;
    const plotW = W - padL - padR;
    const availH = H - padT - padB - gap * 2;
    const hSpd = Math.round(availH * 0.48);
    const hGear = Math.round(availH * 0.25);
    const hPed = availH - hSpd - hGear;

    const ySpd = padT;
    const yGear = ySpd + hSpd + gap;
    const yPed = yGear + hGear + gap;

    [
        [ySpd, hSpd, 'SPD'],
        [yGear, hGear, 'GEAR'],
        [yPed, hPed, 'THR/BRK'],
    ].forEach(([y0, h, lbl]) => {
        ctx.fillStyle = 'rgba(13, 18, 32, 0.92)';
        ctx.fillRect(padL, y0, plotW, h);
        ctx.fillStyle = '#8b95a5';
        ctx.font = 'bold 9.5px Rajdhani, monospace';
        ctx.fillText(lbl, 4, y0 + h / 2 + 3);
    });

    const drawSeries = (samples, key, y0, h, minV, maxV, col, dashed = false) => {
        ctx.save();
        ctx.strokeStyle = col;
        ctx.lineWidth = dashed ? 1.5 : 2.0;
        if (dashed) ctx.setLineDash([4, 3]);
        ctx.beginPath();
        samples.forEach((pt, idx) => {
            const px = padL + (idx / Math.max(1, samples.length - 1)) * plotW;
            const norm = (pt[key] - minV) / Math.max(1e-3, maxV - minV);
            const py = y0 + h - Math.max(0.04, Math.min(0.96, norm)) * h;
            if (idx === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.restore();
    };

    if (cSamples.length) {
        drawSeries(cSamples, 'speed', ySpd, hSpd, 60, 355, cColor, true);
        drawSeries(cSamples, 'gear', yGear, hGear, 0, 8.5, cColor, true);
        drawSeries(cSamples, 'throttle', yPed, hPed, 0, 105, cColor, true);
    }
    drawSeries(pSamples, 'speed', ySpd, hSpd, 60, 355, pColor, false);
    drawSeries(pSamples, 'gear', yGear, hGear, 0, 8.5, '#ffb300', false);
    drawSeries(pSamples, 'throttle', yPed, hPed, 0, 105, '#00e676', false);
    drawSeries(pSamples, 'brake', yPed, hPed, 0, 105, '#ff1744', false);

    // Playhead cursor synced to current car rel_dist
    const pState = (frame && frame.drivers && frame.drivers[primary]) || {};
    const rel = pState.rel_dist ?? ((trackReplayState.frameIndex % 25) / 25);
    const curX = padL + Math.max(0, Math.min(1, rel)) * plotW;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.moveTo(curX, padT);
    ctx.lineTo(curX, H - padB);
    ctx.stroke();
}

// Keyboard shortcuts when 2D Track Replay section is active
document.addEventListener('keydown', (e) => {
    const sec = document.getElementById('section-replay');
    if (!sec || !sec.classList.contains('active')) return;
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : '';
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;

    if (e.code === 'Space') {
        e.preventDefault();
        toggleTrackReplayPlayback();
    } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        jumpTrackReplayFrames(4);
    } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        jumpTrackReplayFrames(-4);
    } else if (e.code === 'ArrowUp') {
        e.preventDefault();
        setTrackReplaySpeed(Math.min(8, trackReplayState.speed * 2));
    } else if (e.code === 'ArrowDown') {
        e.preventDefault();
        setTrackReplaySpeed(Math.max(0.1, trackReplayState.speed / 2));
    } else if (e.key === 'r' || e.key === 'R') {
        restartTrackReplay();
    } else if (e.key === 'd' || e.key === 'D') {
        toggleReplayOption('drs');
    } else if (e.key === 's' || e.key === 'S') {
        toggleReplayOption('sectors');
    } else if (e.key === 'c' || e.key === 'C') {
        cycleReplayComparisonDriver();
    } else if (e.key === 'v' || e.key === 'V') {
        clearReplayComparisonDrivers();
    } else if (e.key === 'h' || e.key === 'H') {
        toggleReplayControlsHelp();
    } else if (['1', '2', '3', '4', '5', '6'].includes(e.key)) {
        const speeds = { '1': 0.1, '2': 0.25, '3': 0.5, '4': 1, '5': 2, '6': 4 };
        setTrackReplaySpeed(speeds[e.key]);
    }
});

// ==============================================================================
// INITIALIZATION
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Restore sidebar collapse state
    const savedSidebarState = localStorage.getItem('f1_sidebar_collapsed');
    if (savedSidebarState === 'true' || (savedSidebarState === null && window.innerWidth <= 1024)) {
        document.body.classList.add('sidebar-collapsed');
    }
    updateSidebarToggleUI();

    checkBackendStatus();
    loadDashboard();
    populateAllStrategyDropdowns(); // Pre-load dropdown data for Analytics & Notes
    // Re-check status every 30s
    setInterval(checkBackendStatus, 30000);
});
