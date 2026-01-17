/**
 * Modal Component - Config editor and log viewer modals
 */

import { store, actions, RETAILERS } from '../state.js';
import api from '../api.js';
import { escapeHtml } from '../utils/format.js';
import { showToast } from './toast.js';

// Log filter state
let activeLogFilters = new Set(['ALL']);

/**
 * Open the config modal
 */
async function openConfigModal() {
  const modal = document.getElementById('config-modal');
  const editor = document.getElementById('config-editor');
  const alert = document.getElementById('config-alert');

  if (!modal || !editor) return;

  // Show modal
  modal.classList.add('modal-overlay--open');
  actions.toggleConfigModal(true);

  // Clear alert
  if (alert) {
    alert.style.display = 'none';
  }

  // Load config
  editor.value = 'Loading configuration...';
  editor.disabled = true;

  try {
    const data = await api.getConfig();
    editor.value = data.content || '';
    editor.disabled = false;
  } catch (error) {
    editor.value = '';
    editor.disabled = false;
    showConfigAlert(`Failed to load configuration: ${error.message}`, 'error');
  }
}

/**
 * Close the config modal
 */
function closeConfigModal() {
  const modal = document.getElementById('config-modal');
  if (modal) {
    modal.classList.remove('modal-overlay--open');
  }
  actions.toggleConfigModal(false);
}

/**
 * Save the config
 */
async function saveConfig() {
  const editor = document.getElementById('config-editor');
  const saveBtn = document.getElementById('config-save');

  if (!editor) return;

  const content = editor.value;

  // Basic validation
  if (!content || content.trim().length === 0) {
    showConfigAlert('Configuration cannot be empty', 'error');
    return;
  }

  if (!content.includes('retailers:')) {
    showConfigAlert('Configuration must contain "retailers:" key', 'error');
    return;
  }

  // Disable save button
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
  }

  try {
    const result = await api.updateConfig(content);

    showConfigAlert(
      `Configuration saved successfully!\nBackup created at: ${result.backup || 'unknown'}`,
      'success'
    );
    showToast('Configuration updated successfully', 'success');

    // Close modal after delay
    setTimeout(() => {
      closeConfigModal();
    }, 2000);
  } catch (error) {
    let errorMessage = error.message || 'Unknown error';

    if (error.data?.details && Array.isArray(error.data.details)) {
      errorMessage += '\n\nDetails:\n' + error.data.details.map(d => `• ${d}`).join('\n');
    }

    showConfigAlert(`Failed to save configuration:\n${errorMessage}`, 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Configuration';
    }
  }
}

/**
 * Show config modal alert
 * @param {string} message - Alert message
 * @param {string} type - Alert type (success, error, warning, info)
 */
function showConfigAlert(message, type = 'info') {
  const alert = document.getElementById('config-alert');
  if (!alert) return;

  alert.className = `alert alert--${type}`;
  alert.textContent = message;
  alert.style.display = 'block';
}

/**
 * Open the log viewer modal
 * @param {string} retailer - Retailer ID
 * @param {string} runId - Run ID
 */
async function openLogModal(retailer, runId) {
  const modal = document.getElementById('log-modal');
  const title = document.getElementById('log-modal-title');
  const content = document.getElementById('log-content');
  const stats = document.getElementById('log-stats');

  if (!modal || !content) return;

  // Reset filters
  activeLogFilters = new Set(['ALL']);
  updateLogFilterButtons();

  // Update title
  const retailerName = RETAILERS[retailer]?.name || retailer;
  if (title) {
    title.textContent = `Logs — ${retailerName} — ${runId}`;
  }

  // Show modal
  modal.classList.add('modal-overlay--open');

  // Show loading
  content.innerHTML = `
    <div style="text-align: center; padding: var(--space-8); color: var(--text-muted);">
      Loading logs...
    </div>
  `;

  try {
    const data = await api.getLogs(retailer, runId);
    const logContent = data.content || '';
    const lines = logContent.split('\n').filter(line => line.trim());

    // Parse log lines
    const parsedLines = lines.map(line => parseLogLine(line));

    // Render logs
    renderLogs(parsedLines);

    // Update stats
    if (stats) {
      stats.textContent = `${parsedLines.length} lines`;
    }
  } catch (error) {
    content.innerHTML = `
      <div class="alert alert--error">
        Error loading logs: ${escapeHtml(error.message)}
      </div>
    `;
  }
}

/**
 * Close the log modal
 */
function closeLogModal() {
  const modal = document.getElementById('log-modal');
  if (modal) {
    modal.classList.remove('modal-overlay--open');
  }
  actions.closeLogModal();
}

/**
 * Parse a log line to extract level and timestamp
 * @param {string} line - Raw log line
 * @returns {object} Parsed log data
 */
function parseLogLine(line) {
  const levelMatch = line.match(/\b(DEBUG|INFO|WARNING|ERROR)\b/);
  const level = levelMatch ? levelMatch[1] : 'INFO';

  const timestampMatch = line.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/);
  const timestamp = timestampMatch ? timestampMatch[1] : null;

  return { raw: line, level, timestamp };
}

/**
 * Render parsed log lines
 * @param {Array} parsedLines - Array of parsed log objects
 */
function renderLogs(parsedLines) {
  const content = document.getElementById('log-content');
  if (!content) return;

  const html = parsedLines.map(logLine => {
    const shouldShow = activeLogFilters.has('ALL') || activeLogFilters.has(logLine.level);
    const hiddenClass = shouldShow ? '' : 'hidden';
    const levelClass = logLine.level.toLowerCase();

    // Escape and format the line
    let formattedLine = escapeHtml(logLine.raw);

    // Highlight timestamp
    if (logLine.timestamp) {
      formattedLine = formattedLine.replace(
        escapeHtml(logLine.timestamp),
        `<span class="log-timestamp">${escapeHtml(logLine.timestamp)}</span>`
      );
    }

    // Highlight level
    if (logLine.level) {
      formattedLine = formattedLine.replace(
        new RegExp(`\\b${logLine.level}\\b`),
        `<span class="log-level">${logLine.level}</span>`
      );
    }

    return `<div class="log-line log-line--${levelClass} ${hiddenClass}" data-level="${logLine.level}">${formattedLine}</div>`;
  }).join('');

  content.innerHTML = html || '<div style="text-align: center; padding: var(--space-4); color: var(--text-muted);">No logs found</div>';
}

/**
 * Toggle log filter
 * @param {string} level - Log level to toggle
 */
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

    // Reset to ALL if nothing selected
    if (activeLogFilters.size === 0) {
      activeLogFilters.add('ALL');
    }
  }

  updateLogFilterButtons();
  applyLogFilters();
}

/**
 * Update filter button states
 */
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

/**
 * Apply log filters to displayed lines
 */
function applyLogFilters() {
  const lines = document.querySelectorAll('.log-line');
  let visibleCount = 0;

  lines.forEach(line => {
    const level = line.dataset.level;
    const shouldShow = activeLogFilters.has('ALL') || activeLogFilters.has(level);

    if (shouldShow) {
      line.classList.remove('hidden');
      visibleCount++;
    } else {
      line.classList.add('hidden');
    }
  });

  // Update stats
  const stats = document.getElementById('log-stats');
  if (stats) {
    stats.textContent = `Showing ${visibleCount} of ${lines.length} lines`;
  }
}

/**
 * Initialize the modal components
 */
export function init() {
  // Config modal handlers
  const configBtn = document.getElementById('config-btn');
  const configCloseBtn = document.getElementById('config-modal-close');
  const configCancelBtn = document.getElementById('config-cancel');
  const configSaveBtn = document.getElementById('config-save');
  const configModal = document.getElementById('config-modal');

  if (configBtn) configBtn.addEventListener('click', openConfigModal);
  if (configCloseBtn) configCloseBtn.addEventListener('click', closeConfigModal);
  if (configCancelBtn) configCancelBtn.addEventListener('click', closeConfigModal);
  if (configSaveBtn) configSaveBtn.addEventListener('click', saveConfig);

  // Close on overlay click
  if (configModal) {
    configModal.addEventListener('click', (e) => {
      if (e.target === configModal) closeConfigModal();
    });
  }

  // Log modal handlers
  const logCloseBtn = document.getElementById('log-modal-close');
  const logModal = document.getElementById('log-modal');

  if (logCloseBtn) logCloseBtn.addEventListener('click', closeLogModal);

  // Close on overlay click
  if (logModal) {
    logModal.addEventListener('click', (e) => {
      if (e.target === logModal) closeLogModal();
    });
  }

  // Log filter buttons
  const filterBtns = document.querySelectorAll('.log-filter-btn');
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      toggleLogFilter(btn.dataset.level);
    });
  });

  // Subscribe to state changes for log modal
  store.subscribe((state) => {
    if (state.ui.logModalOpen && state.ui.currentLogRetailer && state.ui.currentLogRunId) {
      // Modal is already open, check if retailer/run changed
      const modal = document.getElementById('log-modal');
      if (modal && !modal.classList.contains('modal-overlay--open')) {
        openLogModal(state.ui.currentLogRetailer, state.ui.currentLogRunId);
      }
    }
  });
}

/**
 * Cleanup
 */
export function destroy() {
  // Remove event listeners if needed
}

export { openConfigModal, closeConfigModal, openLogModal, closeLogModal };

export default {
  init,
  destroy,
  openConfigModal,
  closeConfigModal,
  openLogModal,
  closeLogModal
};
