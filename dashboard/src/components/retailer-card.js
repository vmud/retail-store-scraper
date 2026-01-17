/**
 * Retailer Card Component - Individual retailer status cards
 */

import { store, RETAILERS, actions } from '../state.js';
import api from '../api.js';
import { formatNumber, formatPercent, escapeHtml } from '../utils/format.js';
import { showToast } from './toast.js';

/**
 * Get status class for retailer
 * @param {string} status - Retailer status
 * @returns {string} CSS class modifier
 */
function getStatusClass(status) {
  const statusMap = {
    running: 'running',
    complete: 'complete',
    pending: 'pending',
    disabled: 'disabled',
    error: 'error',
    failed: 'error'
  };
  return statusMap[status] || 'pending';
}

/**
 * Get status display text
 * @param {string} status - Retailer status
 * @returns {string} Display text
 */
function getStatusText(status) {
  const textMap = {
    running: 'RUNNING',
    complete: 'COMPLETE',
    pending: 'PENDING',
    disabled: 'DISABLED',
    error: 'ERROR',
    failed: 'FAILED'
  };
  return textMap[status] || 'PENDING';
}

/**
 * Get current phase name from phases array
 * @param {Array} phases - Phases array
 * @returns {string} Current phase name
 */
function getCurrentPhase(phases) {
  if (!phases || phases.length === 0) return '—';

  // Find the currently active phase
  const activePhase = phases.find(p => p.status === 'in_progress');
  if (activePhase) return activePhase.name;

  // If all complete, show last phase
  const allComplete = phases.every(p => p.status === 'complete');
  if (allComplete && phases.length > 0) {
    return '✓ All phases';
  }

  // Show first pending phase
  const pendingPhase = phases.find(p => p.status === 'pending');
  if (pendingPhase) return pendingPhase.name;

  return '—';
}

/**
 * Extract store count from progress text
 * @param {string} progressText - Progress text (e.g., "12,847 / 15,000 stores (87.3%)")
 * @returns {string} Store count string
 */
function extractStoreCount(progressText) {
  if (!progressText) return '—';
  const match = progressText.match(/^([\d,]+)/);
  return match ? match[1] : '—';
}

/**
 * Render a single retailer card
 * @param {string} retailerId - Retailer ID
 * @param {object} data - Retailer data
 * @returns {string} HTML string
 */
function renderCard(retailerId, data) {
  const retailerConfig = RETAILERS[retailerId];
  if (!retailerConfig) return '';

  const status = data.status || 'pending';
  const statusClass = getStatusClass(status);
  const statusText = getStatusText(status);

  const progress = data.progress?.percentage || 0;
  const progressText = data.progress?.text || 'No data';
  const storeCount = extractStoreCount(progressText);

  const phases = data.phases || [];
  const currentPhase = getCurrentPhase(phases);

  const stats = data.stats || {};
  const duration = stats.stat2_value || '—';
  const requests = stats.stat3_value || '—';

  const isRunning = status === 'running';
  const isDisabled = status === 'disabled';

  return `
    <div class="retailer-card retailer-card--${retailerId} card-enter" data-retailer="${escapeHtml(retailerId)}">
      <div class="retailer-card__header">
        <div class="retailer-card__identity">
          <div class="retailer-card__accent"></div>
          <span class="retailer-card__name">${escapeHtml(retailerConfig.name)}</span>
        </div>
        <span class="retailer-card__status retailer-card__status--${statusClass}">
          ${statusText}
        </span>
      </div>

      <div class="retailer-card__body">
        <div class="retailer-card__progress">
          <div class="retailer-card__progress-header">
            <span class="retailer-card__progress-percent">${formatPercent(progress)}</span>
            <span class="retailer-card__progress-text">${escapeHtml(storeCount)} stores</span>
          </div>
          <div class="progress ${isRunning ? 'progress--active' : ''}">
            <div class="progress__fill progress__fill--${isRunning ? 'live' : (progress >= 100 ? 'done' : 'idle')}"
                 style="width: ${progress}%"></div>
          </div>
        </div>

        <div class="retailer-card__stats">
          <div class="retailer-card__stat">
            <div class="retailer-card__stat-value">${escapeHtml(storeCount)}</div>
            <div class="retailer-card__stat-label">Stores</div>
          </div>
          <div class="retailer-card__stat">
            <div class="retailer-card__stat-value">${escapeHtml(duration)}</div>
            <div class="retailer-card__stat-label">Duration</div>
          </div>
        </div>

        <div class="retailer-card__phase">
          <span class="retailer-card__phase-label">Phase:</span>
          ${escapeHtml(currentPhase)}
        </div>

        <div class="retailer-card__divider"></div>
      </div>

      <div class="retailer-card__actions">
        ${isDisabled ? `
          <button class="btn btn--flex" disabled data-tooltip="Scraper disabled in config">
            <span>DISABLED</span>
          </button>
        ` : `
          <button class="btn btn--primary btn--flex"
                  data-action="start"
                  data-retailer="${escapeHtml(retailerId)}"
                  ${isRunning ? 'disabled' : ''}
                  data-tooltip="Start scraper">
            <span>▶</span>
            <span>START</span>
          </button>
          <button class="btn btn--danger btn--flex"
                  data-action="stop"
                  data-retailer="${escapeHtml(retailerId)}"
                  ${!isRunning ? 'disabled' : ''}
                  data-tooltip="Stop scraper">
            <span>■</span>
            <span>STOP</span>
          </button>
          ${!isRunning && progress >= 100 ? `
            <button class="btn btn--flex"
                    data-action="restart"
                    data-retailer="${escapeHtml(retailerId)}"
                    data-tooltip="Restart scraper">
              <span>↻</span>
              <span>RESTART</span>
            </button>
          ` : ''}
        `}
      </div>

      <div class="run-history" data-retailer="${escapeHtml(retailerId)}">
        <button class="run-history__toggle" data-action="toggle-history" data-retailer="${escapeHtml(retailerId)}">
          ▼ View Run History
        </button>
        <div class="run-history__list" id="history-list-${escapeHtml(retailerId)}">
          <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
            Loading...
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Render all retailer cards
 * @param {object} retailers - Retailers data from state
 */
function renderAll(retailers) {
  const container = document.getElementById('operations-grid');
  if (!container) return;

  // Preserve expanded history panels
  const expandedPanels = new Set();
  container.querySelectorAll('.run-history--open').forEach(panel => {
    const retailer = panel.dataset.retailer;
    if (retailer) expandedPanels.add(retailer);
  });

  // Render cards
  let html = '';
  Object.keys(RETAILERS).forEach(retailerId => {
    const data = retailers[retailerId] || { status: 'pending' };
    html += renderCard(retailerId, data);
  });

  container.innerHTML = html;

  // Restore expanded history panels
  expandedPanels.forEach(retailerId => {
    const historyDiv = container.querySelector(`.run-history[data-retailer="${retailerId}"]`);
    if (historyDiv) {
      historyDiv.classList.add('run-history--open');
      loadRunHistory(retailerId);
    }
  });
}

/**
 * Load run history for a retailer
 * @param {string} retailerId - Retailer ID
 */
async function loadRunHistory(retailerId) {
  const listContainer = document.getElementById(`history-list-${retailerId}`);
  if (!listContainer) return;

  try {
    const data = await api.getRunHistory(retailerId, 5);

    if (!data.runs || data.runs.length === 0) {
      listContainer.innerHTML = `
        <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
          No runs found
        </div>
      `;
      return;
    }

    listContainer.innerHTML = data.runs.map(run => {
      const runId = run.run_id || 'unknown';
      const status = run.status || 'unknown';
      const startTime = run.started_at ? new Date(run.started_at).toLocaleString() : '—';
      const stores = run.stats?.stores_scraped || 0;

      return `
        <div class="run-item">
          <div class="run-item__info">
            <span class="run-item__id">${escapeHtml(runId)}</span>
            <span class="run-item__time">${escapeHtml(startTime)}</span>
          </div>
          <div class="run-item__actions">
            <span class="badge badge--${status === 'complete' ? 'done' : (status === 'running' ? 'live' : 'idle')}">
              ${escapeHtml(status)}
            </span>
            <button class="btn"
                    data-action="view-logs"
                    data-retailer="${escapeHtml(retailerId)}"
                    data-run-id="${escapeHtml(runId)}">
              Logs
            </button>
          </div>
        </div>
      `;
    }).join('');
  } catch (error) {
    listContainer.innerHTML = `
      <div style="text-align: center; padding: var(--space-4); color: var(--signal-fail);">
        Failed to load run history
      </div>
    `;
  }
}

/**
 * Handle card action clicks
 * @param {Event} event - Click event
 */
async function handleAction(event) {
  const target = event.target.closest('[data-action]');
  if (!target) return;

  const action = target.dataset.action;
  const retailerId = target.dataset.retailer;
  const runId = target.dataset.runId;

  switch (action) {
    case 'start':
      await handleStart(retailerId);
      break;
    case 'stop':
      await handleStop(retailerId);
      break;
    case 'restart':
      await handleRestart(retailerId);
      break;
    case 'toggle-history':
      handleToggleHistory(retailerId);
      break;
    case 'view-logs':
      handleViewLogs(retailerId, runId);
      break;
  }
}

async function handleStart(retailerId) {
  try {
    await api.startScraper(retailerId, { resume: true });
    showToast(`Started ${RETAILERS[retailerId]?.name || retailerId} scraper`, 'success');
  } catch (error) {
    showToast(`Failed to start scraper: ${error.message}`, 'error');
  }
}

async function handleStop(retailerId) {
  try {
    await api.stopScraper(retailerId);
    showToast(`Stopped ${RETAILERS[retailerId]?.name || retailerId} scraper`, 'success');
  } catch (error) {
    showToast(`Failed to stop scraper: ${error.message}`, 'error');
  }
}

async function handleRestart(retailerId) {
  try {
    await api.restartScraper(retailerId, { resume: true });
    showToast(`Restarted ${RETAILERS[retailerId]?.name || retailerId} scraper`, 'success');
  } catch (error) {
    showToast(`Failed to restart scraper: ${error.message}`, 'error');
  }
}

function handleToggleHistory(retailerId) {
  const historyDiv = document.querySelector(`.run-history[data-retailer="${retailerId}"]`);
  if (!historyDiv) return;

  const isOpen = historyDiv.classList.toggle('run-history--open');

  const toggle = historyDiv.querySelector('.run-history__toggle');
  if (toggle) {
    toggle.textContent = isOpen ? '▲ Hide Run History' : '▼ View Run History';
  }

  if (isOpen) {
    loadRunHistory(retailerId);
  }
}

function handleViewLogs(retailerId, runId) {
  actions.openLogModal(retailerId, runId);
}

/**
 * Initialize the retailer cards component
 */
export function init() {
  const container = document.getElementById('operations-grid');
  if (!container) return;

  // Subscribe to state changes
  store.subscribe((state) => {
    renderAll(state.retailers);
  });

  // Event delegation for card actions
  container.addEventListener('click', handleAction);

  // Initial render
  renderAll(store.getState().retailers);
}

/**
 * Cleanup
 */
export function destroy() {
  const container = document.getElementById('operations-grid');
  if (container) {
    container.removeEventListener('click', handleAction);
  }
}

export default {
  init,
  destroy
};
