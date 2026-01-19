let refreshInterval = null;
let refreshTimeInterval = null;
let lastUpdateTime = null;

const RETAILER_CONFIG = {
    verizon: { name: 'Verizon', logo: 'VZ', class: 'verizon' },
    att: { name: 'AT&T', logo: 'AT', class: 'att' },
    target: { name: 'Target', logo: 'TG', class: 'target' },
    tmobile: { name: 'T-Mobile', logo: 'TM', class: 'tmobile' },
    walmart: { name: 'Walmart', logo: 'WM', class: 'walmart' },
    bestbuy: { name: 'Best Buy', logo: 'BB', class: 'bestbuy' }
};

function formatNumber(num) {
    if (num === null || num === undefined) return '—';
    return num.toLocaleString();
}

function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '—';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
    } else if (minutes > 0) {
        return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
    } else {
        return `${secs}s`;
    }
}

function getTimeSinceUpdate() {
    if (!lastUpdateTime) return '';
    
    const now = Date.now();
    const diff = Math.floor((now - lastUpdateTime) / 1000);
    
    if (diff < 5) return 'just now';
    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) {
        const mins = Math.floor(diff / 60);
        return `${mins} minute${mins > 1 ? 's' : ''} ago`;
    }
    
    const hours = Math.floor(diff / 3600);
    return `${hours} hour${hours > 1 ? 's' : ''} ago`;
}

function updateLastRefreshTime() {
    const element = document.getElementById('last-refresh');
    if (element && lastUpdateTime) {
        element.textContent = `Last refresh: ${getTimeSinceUpdate()}`;
    }
}

function getStatusInfo(retailer) {
    const status = retailer.status || 'pending';
    const statusMap = {
        running: { class: 'status-running', text: 'Running' },
        complete: { class: 'status-complete', text: 'Complete' },
        pending: { class: 'status-pending', text: 'Pending' },
        disabled: { class: 'status-disabled', text: 'Disabled' }
    };
    
    return statusMap[status] || statusMap.pending;
}

function renderPhases(retailer) {
    const phases = retailer.phases || [];
    if (phases.length === 0) {
        return '<span class="phase-tag phase-pending">No data</span>';
    }
    
    return phases.map(phase => {
        let statusClass = 'phase-pending';
        let icon = '';
        
        if (phase.status === 'complete') {
            statusClass = 'phase-complete';
            icon = ' ✓';
        } else if (phase.status === 'in_progress') {
            statusClass = 'phase-active';
            icon = ' ⟳';
        }
        
        return `<span class="phase-tag ${statusClass}">${phase.name}${icon}</span>`;
    }).join('');
}

function renderRetailerCard(retailerId, data) {
    const config = RETAILER_CONFIG[retailerId];
    if (!config) return '';
    
    const statusInfo = getStatusInfo(data);
    const progress = data.progress?.percentage || 0;
    const progressText = data.progress?.text || '0 / 0 stores (0%)';
    
    const stats = data.stats || {};
    const stat1Value = stats.stat1_value || '—';
    const stat1Label = stats.stat1_label || 'Stores';
    const stat2Value = stats.stat2_value || '—';
    const stat2Label = stats.stat2_label || 'Duration';
    const stat3Value = stats.stat3_value || '—';
    const stat3Label = stats.stat3_label || 'Requests';
    
    return `
        <div class="retailer-card ${config.class}">
            <div class="retailer-header">
                <div class="retailer-name">
                    <div class="retailer-logo">${config.logo}</div>
                    ${config.name}
                </div>
                <span class="retailer-status ${statusInfo.class}">${statusInfo.text}</span>
            </div>
            <div class="retailer-body">
                <div class="progress-section">
                    <div class="progress-header">
                        <span class="progress-label">Extraction Progress</span>
                        <span class="progress-value">${progressText}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                </div>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">${stat1Value}</div>
                        <div class="stat-label">${stat1Label}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stat2Value}</div>
                        <div class="stat-label">${stat2Label}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${stat3Value}</div>
                        <div class="stat-label">${stat3Label}</div>
                    </div>
                </div>
                <div class="phase-indicators">
                    ${renderPhases(data)}
                </div>
            </div>
            <div class="control-buttons">
                <button class="control-btn start-btn" onclick="startScraper('${retailerId}')" title="Start scraper">
                    ▶ Start
                </button>
                <button class="control-btn stop-btn" onclick="stopScraper('${retailerId}')" title="Stop scraper">
                    ⏹ Stop
                </button>
                <button class="control-btn restart-btn" onclick="restartScraper('${retailerId}')" title="Restart scraper">
                    🔄 Restart
                </button>
            </div>
            <button class="run-history-toggle" onclick="toggleRunHistory('${retailerId}')">
                📜 View Run History
            </button>
            <div class="run-history-panel" id="history-${retailerId}">
                <div class="run-history-list" id="history-list-${retailerId}">
                    <div class="run-history-empty">Loading...</div>
                </div>
            </div>
        </div>
    `;
}

function updateGlobalStatus(data) {
    const globalStatusEl = document.getElementById('global-status');
    const activeCount = data.summary?.active_scrapers || 0;
    
    if (activeCount > 0) {
        globalStatusEl.className = 'global-status active';
        globalStatusEl.innerHTML = `
            <div class="pulse"></div>
            ${activeCount} Scraper${activeCount > 1 ? 's' : ''} Running
        `;
    } else {
        globalStatusEl.className = 'global-status inactive';
        globalStatusEl.innerHTML = 'All Scrapers Idle';
    }
}

function updateSummaryCards(data) {
    const summary = data.summary || {};
    
    document.getElementById('total-stores').textContent = formatNumber(summary.total_stores || 0);
    document.getElementById('active-retailers').textContent = `${summary.active_retailers || 0} / ${summary.total_retailers || 6}`;
    document.getElementById('overall-progress').textContent = `${(summary.overall_progress || 0).toFixed(1)}%`;
    document.getElementById('estimated-time').textContent = formatDuration(summary.estimated_remaining_seconds);
}

function updateRetailers(data) {
    const container = document.getElementById('retailer-grid');
    const retailers = data.retailers || {};
    
    // Preserve UI state before update
    const uiState = {};
    for (const [retailerId] of Object.entries(RETAILER_CONFIG)) {
        const panel = document.getElementById(`history-${retailerId}`);
        if (panel) {
            uiState[retailerId] = {
                isOpen: panel.classList.contains('open'),
                content: panel.querySelector('.run-history-list')?.innerHTML || ''
            };
        }
    }
    
    // Render new HTML
    let html = '';
    for (const [retailerId, retailerData] of Object.entries(RETAILER_CONFIG)) {
        const data = retailers[retailerId] || { status: 'pending' };
        html += renderRetailerCard(retailerId, data);
    }
    
    container.innerHTML = html;
    
    // Restore UI state after update
    for (const [retailerId, state] of Object.entries(uiState)) {
        if (state.isOpen) {
            const panel = document.getElementById(`history-${retailerId}`);
            const button = panel?.previousElementSibling;
            const listContainer = document.getElementById(`history-list-${retailerId}`);
            
            if (panel && button && listContainer) {
                panel.classList.add('open');
                button.classList.add('active');
                button.textContent = '📜 Hide Run History';
                
                // Restore the loaded content
                if (state.content && !state.content.includes('Loading...')) {
                    listContainer.innerHTML = state.content;
                }
            }
        }
    }
}

async function updateDashboard() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        updateGlobalStatus(data);
        updateSummaryCards(data);
        updateRetailers(data);
        
        lastUpdateTime = Date.now();
        updateLastRefreshTime();
        
        const errorEl = document.getElementById('error-message');
        if (errorEl) {
            errorEl.style.display = 'none';
        }
        
    } catch (error) {
        console.error('Error fetching status:', error);
        
        let errorEl = document.getElementById('error-message');
        if (!errorEl) {
            errorEl = document.createElement('div');
            errorEl.id = 'error-message';
            errorEl.className = 'error';
            document.querySelector('.container').insertBefore(
                errorEl,
                document.querySelector('.summary-row')
            );
        }
        
        // SECURITY: Use textContent for error message to prevent XSS
        // Build the error message safely without innerHTML
        errorEl.textContent = '';
        const strong = document.createElement('strong');
        strong.textContent = 'Error loading dashboard:';
        errorEl.appendChild(strong);
        errorEl.appendChild(document.createTextNode(' ' + error.message));
        errorEl.style.display = 'block';
    }
}

function startAutoRefresh(intervalSeconds = 5) {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    if (refreshTimeInterval) {
        clearInterval(refreshTimeInterval);
    }
    
    updateDashboard();
    
    refreshInterval = setInterval(updateDashboard, intervalSeconds * 1000);
    refreshTimeInterval = setInterval(updateLastRefreshTime, 1000);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
    if (refreshTimeInterval) {
        clearInterval(refreshTimeInterval);
        refreshTimeInterval = null;
    }
}

let currentLogRetailer = null;
let currentLogRunId = null;
let activeLogFilters = new Set(['ALL']);

function toggleRunHistory(retailer) {
    const panel = document.getElementById(`history-${retailer}`);
    const button = panel.previousElementSibling;
    const isOpen = panel.classList.contains('open');
    
    if (isOpen) {
        panel.classList.remove('open');
        button.classList.remove('active');
        button.textContent = '📜 View Run History';
    } else {
        panel.classList.add('open');
        button.classList.add('active');
        button.textContent = '📜 Hide Run History';
        loadRunHistory(retailer);
    }
}

async function loadRunHistory(retailer) {
    const listContainer = document.getElementById(`history-list-${retailer}`);
    listContainer.innerHTML = '<div class="run-history-empty">Loading...</div>';
    
    try {
        const response = await fetch(`/api/runs/${retailer}?limit=5`);
        const data = await response.json();
        
        if (data.error) {
            // SECURITY: Escape error message to prevent XSS
            listContainer.innerHTML = `<div class="run-history-empty">Error: ${escapeHtml(data.error)}</div>`;
            return;
        }
        
        if (!data.runs || data.runs.length === 0) {
            listContainer.innerHTML = '<div class="run-history-empty">No runs found</div>';
            return;
        }
        
        listContainer.innerHTML = data.runs.map(run => createRunItem(retailer, run)).join('');
    } catch (error) {
        console.error('Error loading run history:', error);
        listContainer.innerHTML = `<div class="run-history-empty">Failed to load run history</div>`;
    }
}

function createRunItem(retailer, run) {
    const config = RETAILER_CONFIG[retailer];
    const runId = run.run_id || 'unknown';
    const status = run.status || 'unknown';
    const startTime = run.started_at ? new Date(run.started_at).toLocaleString() : '—';
    const endTime = run.completed_at ? new Date(run.completed_at).toLocaleString() : 'In progress';
    const stores = run.stats?.stores_scraped || 0;

    let statusClass = '';
    let statusText = status;

    if (status === 'complete') {
        statusClass = 'complete';
        statusText = 'Complete';
    } else if (status === 'failed') {
        statusClass = 'failed';
        statusText = 'Failed';
    } else if (status === 'running') {
        statusClass = 'running';
        statusText = 'Running';
    }

    // SECURITY: Escape retailer and runId for use in onclick handlers to prevent XSS
    // These values come from server data and could potentially contain malicious content
    const safeRetailer = escapeHtml(retailer).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const safeRunId = escapeHtml(runId).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const safeStatus = escapeHtml(status);
    const safeStatusClass = escapeHtml(statusClass);
    const safeStatusText = escapeHtml(statusText);
    const safeRunIdDisplay = escapeHtml(runId);

    return `
        <div class="run-item status-${safeStatus}">
            <div class="run-item-header">
                <span class="run-id">${safeRunIdDisplay}</span>
                <span class="run-status-badge ${safeStatusClass}">${safeStatusText}</span>
            </div>
            <div class="run-item-details">
                Started: ${escapeHtml(startTime)}<br>
                ${run.completed_at ? `Ended: ${escapeHtml(endTime)}<br>` : ''}
                Stores: ${formatNumber(stores)}
            </div>
            <div class="run-item-actions">
                <button class="btn-view-logs" onclick="openLogViewer('${safeRetailer}', '${safeRunId}')">
                    View Logs
                </button>
            </div>
        </div>
    `;
}

function openLogViewer(retailer, runId) {
    currentLogRetailer = retailer;
    currentLogRunId = runId;
    activeLogFilters = new Set(['ALL']);
    
    const config = RETAILER_CONFIG[retailer];
    const modal = document.getElementById('log-modal');
    const modalTitle = document.getElementById('log-modal-title');
    const logContainer = document.getElementById('log-content');
    
    modalTitle.textContent = `Logs - ${config.name} - ${runId}`;
    logContainer.innerHTML = '<div class="log-loading">Loading logs...</div>';
    
    modal.classList.add('open');
    
    updateLogFilterButtons();
    loadLogs();
}

function closeLogViewer() {
    const modal = document.getElementById('log-modal');
    modal.classList.remove('open');
    currentLogRetailer = null;
    currentLogRunId = null;
}

async function loadLogs() {
    const logContainer = document.getElementById('log-content');
    
    try {
        const response = await fetch(`/api/logs/${currentLogRetailer}/${currentLogRunId}`);
        const data = await response.json();
        
        if (data.error) {
            // SECURITY: Escape error message to prevent XSS
            logContainer.innerHTML = `<div class="log-error">Error loading logs: ${escapeHtml(data.error)}</div>`;
            return;
        }
        
        const logContent = data.content || '';
        const lines = logContent.split('\n');
        
        const parsedLines = lines
            .filter(line => line.trim())
            .map(line => parseLogLine(line));
        
        displayLogs(parsedLines);
        updateLogStats(parsedLines);
    } catch (error) {
        console.error('Error loading logs:', error);
        // SECURITY: Escape error message to prevent XSS
        logContainer.innerHTML = `<div class="log-error">Failed to load logs: ${escapeHtml(error.message)}</div>`;
    }
}

function parseLogLine(line) {
    const levelMatch = line.match(/\b(DEBUG|INFO|WARNING|ERROR)\b/);
    const level = levelMatch ? levelMatch[1] : 'INFO';
    
    const timestampMatch = line.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/);
    const timestamp = timestampMatch ? timestampMatch[1] : null;
    
    return {
        raw: line,
        level: level,
        timestamp: timestamp
    };
}

/**
 * HTML-encode a string to prevent XSS attacks
 * @param {string} str - The string to encode
 * @returns {string} - The HTML-encoded string
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function displayLogs(parsedLines) {
    const logContainer = document.getElementById('log-content');
    
    const html = parsedLines.map(logLine => {
        const shouldShow = activeLogFilters.has('ALL') || activeLogFilters.has(logLine.level);
        const hiddenClass = shouldShow ? '' : 'hidden';
        
        // SECURITY: HTML-encode the raw log content to prevent XSS
        // This protects against malicious content in scraped data (e.g., store names)
        // that could end up in logs and be executed when viewing the dashboard
        let formattedLine = escapeHtml(logLine.raw);
        
        // After escaping, we can safely add HTML formatting for known safe elements
        if (logLine.level) {
            // Escape the level for regex safety
            const escapedLevel = logLine.level.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            formattedLine = formattedLine.replace(
                new RegExp(`\\b${escapedLevel}\\b`),
                `<span class="log-level ${escapeHtml(logLine.level)}">${escapeHtml(logLine.level)}</span>`
            );
        }
        
        if (logLine.timestamp) {
            formattedLine = formattedLine.replace(
                escapeHtml(logLine.timestamp),
                `<span class="log-timestamp">${escapeHtml(logLine.timestamp)}</span>`
            );
        }
        
        // Also escape the level in the class name to prevent attribute injection
        const safeLevel = logLine.level ? escapeHtml(logLine.level) : 'unknown';
        return `<div class="log-line level-${safeLevel} ${hiddenClass}">${formattedLine}</div>`;
    }).join('');
    
    logContainer.innerHTML = `<div class="log-container">${html}</div>`;
}

function updateLogStats(parsedLines) {
    const total = parsedLines.length;
    const visible = parsedLines.filter(line => 
        activeLogFilters.has('ALL') || activeLogFilters.has(line.level)
    ).length;
    
    const statsElement = document.getElementById('log-stats');
    statsElement.textContent = `Showing ${visible} of ${total} lines`;
}

function toggleLogFilter(level) {
    if (level === 'ALL') {
        activeLogFilters.clear();
        activeLogFilters.add('ALL');
    } else {
        activeLogFilters.delete('ALL');
        
        if (activeLogFilters.has(level)) {
            activeLogFilters.delete(level);
        } else {
            activeLogFilters.add(level);
        }
        
        if (activeLogFilters.size === 0) {
            activeLogFilters.add('ALL');
        }
    }
    
    updateLogFilterButtons();
    
    const logLines = document.querySelectorAll('.log-line');
    logLines.forEach(line => {
        const lineLevel = Array.from(line.classList)
            .find(cls => cls.startsWith('level-'))
            ?.replace('level-', '');
        
        if (activeLogFilters.has('ALL') || activeLogFilters.has(lineLevel)) {
            line.classList.remove('hidden');
        } else {
            line.classList.add('hidden');
        }
    });
    
    const total = logLines.length;
    const visible = document.querySelectorAll('.log-line:not(.hidden)').length;
    document.getElementById('log-stats').textContent = `Showing ${visible} of ${total} lines`;
}

function updateLogFilterButtons() {
    const buttons = document.querySelectorAll('.log-filter-btn');
    buttons.forEach(btn => {
        const level = btn.dataset.level;
        if (activeLogFilters.has(level)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

async function startScraper(retailer) {
    try {
        const response = await fetch('/api/scraper/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                retailer: retailer,
                resume: true
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(`✅ Started ${retailer} scraper`, 'success');
            updateDashboard();
        } else {
            showNotification(`❌ Error: ${result.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ Failed to start scraper: ${error.message}`, 'error');
    }
}

async function stopScraper(retailer) {
    try {
        const response = await fetch('/api/scraper/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                retailer: retailer,
                timeout: 30
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(`⏹ Stopped ${retailer} scraper`, 'success');
            updateDashboard();
        } else {
            showNotification(`❌ Error: ${result.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ Failed to stop scraper: ${error.message}`, 'error');
    }
}

async function restartScraper(retailer) {
    try {
        const response = await fetch('/api/scraper/restart', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                retailer: retailer,
                resume: true,
                timeout: 30
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(`🔄 Restarted ${retailer} scraper`, 'success');
            updateDashboard();
        } else {
            showNotification(`❌ Error: ${result.error}`, 'error');
        }
    } catch (error) {
        showNotification(`❌ Failed to restart scraper: ${error.message}`, 'error');
    }
}

function showNotification(message, type = 'info') {
    const validTypes = ['success', 'error', 'info'];
    const notificationType = validTypes.includes(type) ? type : 'info';
    
    const notification = document.createElement('div');
    notification.className = `notification ${notificationType}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
}

async function openConfigModal() {
    const modal = document.getElementById('config-modal');
    const editor = document.getElementById('config-editor');
    const alertDiv = document.getElementById('modal-alert');
    
    alertDiv.style.display = 'none';
    editor.value = 'Loading configuration...';
    modal.classList.add('open');
    
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        if (response.ok) {
            editor.value = data.content;
        } else {
            showModalAlert(`Error loading configuration: ${data.error}`, 'error');
            editor.value = '';
        }
    } catch (error) {
        showModalAlert(`Failed to load configuration: ${error.message}`, 'error');
        editor.value = '';
    }
}

function closeConfigModal() {
    const modal = document.getElementById('config-modal');
    modal.classList.remove('open');
}

async function saveConfig() {
    const editor = document.getElementById('config-editor');
    const saveBtn = document.getElementById('save-config-btn');
    const alertDiv = document.getElementById('modal-alert');
    
    const content = editor.value;
    
    const validationError = validateConfigSyntax(content);
    if (validationError) {
        showModalAlert(validationError, 'error');
        return;
    }
    
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    alertDiv.style.display = 'none';
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content: content
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            const backupPath = result.backup || 'unknown';
            showModalAlert(`✅ Configuration saved successfully!\nBackup created at: ${backupPath}`, 'success');
            showNotification('Configuration updated successfully', 'success');
            
            setTimeout(() => {
                closeConfigModal();
                updateDashboard();
            }, 2000);
        } else {
            let errorMessage = result.error || 'Unknown error';
            
            if (result.details && Array.isArray(result.details)) {
                errorMessage += '\n\nDetails:\n' + result.details.map(d => `• ${d}`).join('\n');
            }
            
            showModalAlert(`❌ Failed to save configuration:\n${errorMessage}`, 'error');
        }
    } catch (error) {
        showModalAlert(`❌ Failed to save configuration: ${error.message}`, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Configuration';
    }
}

function validateConfigSyntax(content) {
    if (!content || content.trim().length === 0) {
        return 'Configuration cannot be empty';
    }
    
    if (!content.includes('retailers:')) {
        return 'Configuration must contain "retailers:" key';
    }
    
    const lines = content.split('\n').filter(line => line.trim() && !line.trim().startsWith('#'));
    if (lines.length < 3) {
        return 'Configuration appears to be incomplete';
    }
    
    return null;
}

function showModalAlert(message, type = 'info') {
    const validTypes = ['success', 'error', 'info'];
    const alertType = validTypes.includes(type) ? type : 'info';
    
    const alertDiv = document.getElementById('modal-alert');
    alertDiv.className = `alert ${alertType}`;
    alertDiv.textContent = message;
    alertDiv.style.display = 'block';
}

document.addEventListener('DOMContentLoaded', () => {
    startAutoRefresh(5);
    
    const logModal = document.getElementById('log-modal');
    if (logModal) {
        logModal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeLogViewer();
            }
        });
    }
    
    const configModal = document.getElementById('config-modal');
    if (configModal) {
        configModal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeConfigModal();
            }
        });
    }
});

document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        startAutoRefresh(5);
    }
});