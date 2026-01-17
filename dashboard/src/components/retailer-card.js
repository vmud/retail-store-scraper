/**
 * Retailer Card Component - Individual retailer status cards
 * Uses targeted DOM updates to avoid visual flash on refresh
 */

import { store, RETAILERS, actions } from '../state.js';
import api from '../api.js';
import { formatNumber, formatPercent, escapeHtml } from '../utils/format.js';
import { showToast } from './toast.js';

/**
 * Retailer logo SVGs - simplified brand marks
 */
const RETAILER_LOGOS = {
  verizon: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M1.734 0L0 3.82l9.566 20.178L14.69 14.1 22.136.002h-3.863l-4.6 9.2-3.462-6.934H3.467L6.2 8.2l3.366 6.733L4.35 3.82l1.25-2.5H1.734z"/></svg>`,
  att: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="11" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4c-4.4 0-8 3.6-8 8s3.6 8 8 8c1.8 0 3.5-.6 4.9-1.6L12 12V4z"/></svg>`,
  target: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="2.5"/></svg>`,
  tmobile: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 6h20v3H2V6zm7 5h6v10h-2v-8h-2v8H9V11z"/></svg>`,
  walmart: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 7h-4.8L12 2zm0 20l-2.4-7h4.8L12 22zm-10-10l7-2.4v4.8L2 12zm20 0l-7 2.4v-4.8L22 12zM4.9 4.9l6.2 3.6-2.4 2.4-3.8-6zm14.2 0l-3.6 6.2-2.4-2.4 6-3.8zM4.9 19.1l3.6-6.2 2.4 2.4-6 3.8zm14.2 0l-6.2-3.6 2.4-2.4 3.8 6z"/></svg>`,
  bestbuy: `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M7 8h4v3H7V8zm0 5h4v3H7v-3zm6-5h4v3h-4V8zm0 5h4v3h-4v-3z"/></svg>`
};

/**
 * Track if cards have been initially rendered
 */
let cardsRendered = false;

/**
 * Get status class for retailer
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
 */
function getCurrentPhase(phases) {
  if (!phases || phases.length === 0) return '—';

  const activePhase = phases.find(p => p.status === 'in_progress');
  if (activePhase) return activePhase.name;

  const allComplete = phases.every(p => p.status === 'complete');
  if (allComplete && phases.length > 0) {
    return '✓ All phases';
  }

  const pendingPhase = phases.find(p => p.status === 'pending');
  if (pendingPhase) return pendingPhase.name;

  return '—';
}

/**
 * Extract store count from progress text
 */
function extractStoreCount(progressText) {
  if (!progressText) return '—';
  const match = progressText.match(/^([\d,]+)/);
  return match ? match[1] : '—';
}

/**
 * Render a single retailer card (initial render only)
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

  const isRunning = status === 'running';
  const isDisabled = status === 'disabled';

  const logo = RETAILER_LOGOS[retailerId] || '';

  return `
    <div class="retailer-card retailer-card--${retailerId} card-enter" data-retailer="${escapeHtml(retailerId)}">
      <div class="retailer-card__header">
        <div class="retailer-card__identity">
          <div class="retailer-card__accent"></div>
          <div class="retailer-card__logo">${logo}</div>
          <span class="retailer-card__name">${escapeHtml(retailerConfig.name)}</span>
        </div>
        <span class="retailer-card__status retailer-card__status--${statusClass}" data-field="status">
          ${statusText}
        </span>
      </div>

      <div class="retailer-card__body">
        <div class="retailer-card__progress">
          <div class="retailer-card__progress-header">
            <span class="retailer-card__progress-percent" data-field="percent">${formatPercent(progress)}</span>
            <span class="retailer-card__progress-text" data-field="store-text">${escapeHtml(storeCount)} stores</span>
          </div>
          <div class="progress ${isRunning ? 'progress--active' : ''}" data-field="progress-bar">
            <div class="progress__fill progress__fill--${isRunning ? 'live' : (progress >= 100 ? 'done' : 'idle')}"
                 data-field="progress-fill"
                 style="width: ${progress}%"></div>
          </div>
        </div>

        <div class="retailer-card__stats">
          <div class="retailer-card__stat">
            <div class="retailer-card__stat-value" data-field="stores">${escapeHtml(storeCount)}</div>
            <div class="retailer-card__stat-label">Stores</div>
          </div>
          <div class="retailer-card__stat">
            <div class="retailer-card__stat-value" data-field="duration">${escapeHtml(duration)}</div>
            <div class="retailer-card__stat-label">Duration</div>
          </div>
        </div>

        <div class="retailer-card__phase" data-field="phase">
          <span class="retailer-card__phase-label">Phase:</span>
          <span data-field="phase-text">${escapeHtml(currentPhase)}</span>
        </div>

        <div class="retailer-card__divider"></div>
      </div>

      <div class="retailer-card__actions" data-field="actions">
        ${renderActions(retailerId, status, progress)}
      </div>

      <div class="run-history" data-retailer="${escapeHtml(retailerId)}">
        <button class="run-history__toggle" data-action="toggle-history" data-retailer="${escapeHtml(retailerId)}">
          ▼ View Run History
        </button>
        <div class="run-history__list" id="history-list-${escapeHtml(retailerId)}">
          <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
            Click to load history
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Render action buttons
 */
function renderActions(retailerId, status, progress) {
  const isRunning = status === 'running';
  const isDisabled = status === 'disabled';

  if (isDisabled) {
    return `
      <button class="btn btn--flex" disabled data-tooltip="Scraper disabled in config">
        <span>DISABLED</span>
      </button>
    `;
  }

  return `
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
  `;
}

/**
 * Update a single card with new data (no re-render, just DOM updates)
 */
function updateCard(retailerId, data) {
  const card = document.querySelector(`.retailer-card[data-retailer="${retailerId}"]`);
  if (!card) return;

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

  const isRunning = status === 'running';

  // Update status badge
  const statusEl = card.querySelector('[data-field="status"]');
  if (statusEl) {
    statusEl.textContent = statusText;
    statusEl.className = `retailer-card__status retailer-card__status--${statusClass}`;
  }

  // Update progress percent
  const percentEl = card.querySelector('[data-field="percent"]');
  if (percentEl) {
    percentEl.textContent = formatPercent(progress);
  }

  // Update store text
  const storeTextEl = card.querySelector('[data-field="store-text"]');
  if (storeTextEl) {
    storeTextEl.textContent = `${storeCount} stores`;
  }

  // Update progress bar
  const progressBar = card.querySelector('[data-field="progress-bar"]');
  if (progressBar) {
    progressBar.className = `progress ${isRunning ? 'progress--active' : ''}`;
  }

  // Update progress fill
  const progressFill = card.querySelector('[data-field="progress-fill"]');
  if (progressFill) {
    progressFill.style.width = `${progress}%`;
    progressFill.className = `progress__fill progress__fill--${isRunning ? 'live' : (progress >= 100 ? 'done' : 'idle')}`;
  }

  // Update stores stat
  const storesEl = card.querySelector('[data-field="stores"]');
  if (storesEl) {
    storesEl.textContent = storeCount;
  }

  // Update duration stat
  const durationEl = card.querySelector('[data-field="duration"]');
  if (durationEl) {
    durationEl.textContent = duration;
  }

  // Update phase
  const phaseTextEl = card.querySelector('[data-field="phase-text"]');
  if (phaseTextEl) {
    phaseTextEl.textContent = currentPhase;
  }

  // Update action buttons (only if status changed significantly)
  const actionsEl = card.querySelector('[data-field="actions"]');
  if (actionsEl) {
    const startBtn = actionsEl.querySelector('[data-action="start"]');
    const stopBtn = actionsEl.querySelector('[data-action="stop"]');

    if (startBtn) {
      startBtn.disabled = isRunning;
    }
    if (stopBtn) {
      stopBtn.disabled = !isRunning;
    }
  }
}

/**
 * Initial render of all cards
 */
function renderAll(retailers) {
  const container = document.getElementById('operations-grid');
  if (!container) return;

  let html = '';
  Object.keys(RETAILERS).forEach(retailerId => {
    const data = retailers[retailerId] || { status: 'pending' };
    html += renderCard(retailerId, data);
  });

  container.innerHTML = html;
  cardsRendered = true;
}

/**
 * Update all cards without re-rendering
 */
function updateAll(retailers) {
  Object.keys(RETAILERS).forEach(retailerId => {
    const data = retailers[retailerId] || { status: 'pending' };
    updateCard(retailerId, data);
  });
}

/**
 * Load run history for a retailer
 */
async function loadRunHistory(retailerId) {
  const listContainer = document.getElementById(`history-list-${retailerId}`);
  if (!listContainer) return;

  listContainer.innerHTML = `
    <div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">
      Loading...
    </div>
  `;

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
    if (!cardsRendered) {
      // First render - create all cards
      renderAll(state.retailers);
    } else {
      // Subsequent updates - just update values, no re-render
      updateAll(state.retailers);
    }
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
  cardsRendered = false;
}

export default {
  init,
  destroy
};
