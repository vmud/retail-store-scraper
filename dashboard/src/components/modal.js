/**
 * Modal Component - Config editor and log viewer modals
 * Manages modal state and interactions with live log monitoring
 */

import { store, actions, RETAILERS } from '../state.js';
import api from '../api.js';
import { escapeHtml } from '../utils/format.js';
import { showToast } from './toast.js';

// Log filter state
let activeLogFilters = new Set(['ALL']);

// Live log polling state
let liveLogInterval = null;
let parsedLogLines = [];
let lastLineCount = 0;
let userHasScrolled = false;
let isPolling = false; // Prevent overlapping requests
let pollErrors = 0; // Track consecutive errors for backoff
let currentPollInterval = 2000; // Dynamic polling interval
const LIVE_POLL_INTERVAL = 2000; // Base: 2 seconds
const MAX_POLL_INTERVAL = 10000; // Max: 10 seconds on errors
const BACKOFF_MULTIPLIER = 1.5; // Increase interval by 1.5x on each error

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

  // Reset state
  activeLogFilters = new Set(['ALL']);
  updateLogFilterButtons();
  parsedLogLines = [];
  lastLineCount = 0;
  userHasScrolled = false;
  isPolling = false; // Reset polling flag
  actions.resetLiveLogState();

  // Update title
  const retailerName = RETAILERS[retailer]?.name || retailer;
  if (title) {
    title.textContent = `Logs — ${retailerName} — ${runId}`;
  }

  // Show modal
  modal.classList.add('modal-overlay--open');

  // Update state
  actions.openLogModal(retailer, runId);

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
    parsedLogLines = lines.map(line => parseLogLine(line));
    lastLineCount = data.total_lines || parsedLogLines.length;

    // Render logs
    renderLogs(parsedLogLines);

    // Update stats
    updateLogStats();

    // Check if scraper is active and start live polling
    if (data.is_active) {
      actions.setLogIsActive(true);
      actions.setLiveLogEnabled(true);
      updateLiveIndicator(true);
      startLivePolling(retailer, runId);
      // Scroll to bottom for live logs
      scrollToBottom();
    } else {
      updateLiveIndicator(false);
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
 * Start live polling for log updates
 * @param {string} retailer - Retailer ID
 * @param {string} runId - Run ID
 */
function startLivePolling(retailer, runId) {
  // Clear any existing interval
  stopLivePolling();
  
  // Reset polling state for fresh start
  pollErrors = 0;
  currentPollInterval = LIVE_POLL_INTERVAL;

  // Define the polling function so it can be referenced by name (not arguments.callee)
  const pollFunction = async () => {
    // Skip if previous request is still in-flight
    if (isPolling) {
      return;
    }

    const state = store.getState();

    // Check if modal is still open
    if (!state.ui.logModalOpen) {
      stopLivePolling();
      return;
    }

    // Check if paused
    if (state.ui.liveLogPaused) {
      return;
    }

    isPolling = true;

    try {
      // Fetch only new lines using offset
      const data = await api.getLogs(retailer, runId, { offset: lastLineCount });

      // CRITICAL: Re-check state after async request completes
      // User may have closed modal and opened a different log view while request was in-flight
      const currentState = store.getState();
      if (!currentState.ui.logModalOpen ||
          currentState.ui.currentLogRetailer !== retailer ||
          currentState.ui.currentLogRunId !== runId) {
        // Stale request - wrong retailer/run is now displayed, discard this response
        stopLivePolling();
        return;
      }

      // Check if scraper has stopped
      if (!data.is_active) {
        stopLivePolling();
        actions.setLogIsActive(false);
        actions.setLiveLogEnabled(false);
        updateLiveIndicator(false);
        showToast('Scraper completed', 'info');
        return;
      }

      // If there are new lines, append them
      if (data.lines > 0 && data.total_lines > lastLineCount) {
        const newContent = data.content || '';
        const newLines = newContent.split('\n').filter(line => line.trim());
        const newParsedLines = newLines.map(line => parseLogLine(line));

        // Append new lines
        appendLogLines(newParsedLines);
        lastLineCount = data.total_lines;

        // Update stats
        updateLogStats();

        // Auto-scroll if not paused and user hasn't scrolled up
        if (!userHasScrolled) {
          scrollToBottom();
        }
      }
      
      // Reset error count on successful fetch
      pollErrors = 0;

      // Restore base polling interval if we were in backoff mode
      if (currentPollInterval !== LIVE_POLL_INTERVAL) {
        currentPollInterval = LIVE_POLL_INTERVAL;
        if (liveLogInterval) {
          clearInterval(liveLogInterval);
          liveLogInterval = setInterval(pollFunction, LIVE_POLL_INTERVAL);
        }
      }

    } catch (error) {
      console.error('Error fetching live logs:', error);

      // Re-check state after async request completes
      const currentState = store.getState();
      if (!currentState.ui.logModalOpen ||
          currentState.ui.currentLogRetailer !== retailer ||
          currentState.ui.currentLogRunId !== runId) {
        // Stale request - modal closed or different log now displayed
        stopLivePolling();
        return;
      }
      
      // Handle rate limiting (429) - stop polling temporarily
      if (error.status === 429) {
        pollErrors++;
        const backoffInterval = Math.min(
          LIVE_POLL_INTERVAL * Math.pow(BACKOFF_MULTIPLIER, pollErrors),
          MAX_POLL_INTERVAL
        );
        
        console.warn(`Rate limited (429). Slowing polling to ${(backoffInterval/1000).toFixed(1)}s`);
        showToast(`Log polling rate limited. Slowing down to ${(backoffInterval/1000).toFixed(1)}s intervals`, 'warning');
        
        // If repeatedly rate limited, stop polling
        if (pollErrors >= 3) {
          console.error('Repeated rate limiting - stopping live log polling');
          stopLivePolling();
          actions.setLiveLogEnabled(false);
          updateLiveIndicator(false);
          showToast('Live log polling stopped due to repeated rate limiting. Refresh to try again.', 'error');
          return;
        }
        
        // Restart interval with new backoff delay using the named function reference
        // IMPORTANT: Don't call stopLivePolling() here as it would reset pollErrors counter
        // Just clear the interval and restart with backoff - preserve error tracking
        if (liveLogInterval) {
          clearInterval(liveLogInterval);
        }
        currentPollInterval = backoffInterval;
        liveLogInterval = setInterval(pollFunction, backoffInterval);
      }
      // Handle other errors (network, server errors)
      else if (error.status >= 500 || error.isNetworkError) {
        pollErrors++;
        if (pollErrors >= 5) {
          console.error('Too many polling errors - stopping');
          stopLivePolling();
          actions.setLiveLogEnabled(false);
          updateLiveIndicator(false);
          showToast('Live log polling stopped due to server errors', 'error');
        }
      }
    } finally {
      isPolling = false;
    }
  };

  liveLogInterval = setInterval(pollFunction, currentPollInterval);
}

/**
 * Stop live polling
 */
function stopLivePolling() {
  if (liveLogInterval) {
    clearInterval(liveLogInterval);
    liveLogInterval = null;
  }
  isPolling = false; // Reset polling flag
  pollErrors = 0; // Reset error counter
  currentPollInterval = LIVE_POLL_INTERVAL; // Reset to base interval
}

/**
 * Append new log lines to the viewer
 * @param {Array} newParsedLines - Array of parsed log objects
 */
function appendLogLines(newParsedLines) {
  const content = document.getElementById('log-content');
  if (!content) return;

  // Add to parsed lines array
  parsedLogLines = [...parsedLogLines, ...newParsedLines];

  // Create HTML for new lines
  const html = newParsedLines.map(logLine => {
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
        new RegExp(`\\b${escapeHtml(logLine.level)}\\b`),
        `<span class="log-level">${escapeHtml(logLine.level)}</span>`
      );
    }

    // Add 'new' class for animation
    return `<div class="log-line log-line--${levelClass} log-line--new ${hiddenClass}" data-level="${escapeHtml(logLine.level)}">${formattedLine}</div>`;
  }).join('');

  // Append to content
  content.insertAdjacentHTML('beforeend', html);

  // Remove 'new' class after animation completes
  setTimeout(() => {
    const newLines = content.querySelectorAll('.log-line--new');
    newLines.forEach(line => line.classList.remove('log-line--new'));
  }, 500);
}

/**
 * Scroll log viewer to bottom
 */
function scrollToBottom() {
  const content = document.getElementById('log-content');
  if (content) {
    content.scrollTop = content.scrollHeight;
  }
}

/**
 * Update live indicator visibility
 * @param {boolean} isLive - Whether logs are live
 */
function updateLiveIndicator(isLive) {
  const indicator = document.getElementById('live-indicator');
  const liveControls = document.getElementById('log-live-controls');

  if (indicator) {
    indicator.style.display = isLive ? 'inline-flex' : 'none';
  }

  if (liveControls) {
    liveControls.style.display = isLive ? 'flex' : 'none';
  }

  // Reset pause button UI when showing live controls
  if (isLive) {
    const pauseBtn = document.getElementById('log-pause-btn');
    if (pauseBtn) {
      pauseBtn.textContent = '⏸ Pause';
      pauseBtn.classList.remove('btn--paused');
    }
  }
}

/**
 * Toggle pause/resume for live logs
 */
function toggleLivePause() {
  const state = store.getState();
  const newPaused = !state.ui.liveLogPaused;
  actions.setLiveLogPaused(newPaused);

  const pauseBtn = document.getElementById('log-pause-btn');
  if (pauseBtn) {
    if (newPaused) {
      pauseBtn.textContent = '▶ Resume';
      pauseBtn.classList.add('btn--paused');
    } else {
      pauseBtn.textContent = '⏸ Pause';
      pauseBtn.classList.remove('btn--paused');
      // Reset scroll tracking when resuming
      userHasScrolled = false;
      scrollToBottom();
    }
  }
}

/**
 * Update log stats display
 */
function updateLogStats() {
  const stats = document.getElementById('log-stats');
  const state = store.getState();

  if (stats) {
    const visibleCount = document.querySelectorAll('.log-line:not(.hidden)').length;
    const totalCount = parsedLogLines.length;

    if (state.ui.logIsActive) {
      stats.textContent = `${visibleCount} of ${totalCount} lines (live)`;
    } else {
      stats.textContent = `${visibleCount} of ${totalCount} lines`;
    }
  }

  actions.setLogLineCount(parsedLogLines.length);
}

/**
 * Close the log modal
 */
function closeLogModal() {
  // Stop live polling
  stopLivePolling();

  // Reset live log state
  actions.resetLiveLogState();

  // Hide live indicator
  updateLiveIndicator(false);

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
        new RegExp(`\\b${escapeHtml(logLine.level)}\\b`),
        `<span class="log-level">${escapeHtml(logLine.level)}</span>`
      );
    }

    return `<div class="log-line log-line--${levelClass} ${hiddenClass}" data-level="${escapeHtml(logLine.level)}">${formattedLine}</div>`;
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

  // Update stats using the shared function
  updateLogStats();
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
  const logContent = document.getElementById('log-content');

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

  // Live log control buttons
  const pauseBtn = document.getElementById('log-pause-btn');
  const scrollBtn = document.getElementById('log-scroll-btn');

  if (pauseBtn) {
    pauseBtn.addEventListener('click', toggleLivePause);
  }

  if (scrollBtn) {
    scrollBtn.addEventListener('click', () => {
      userHasScrolled = false;
      scrollToBottom();
    });
  }

  // Track user scroll to auto-pause
  if (logContent) {
    logContent.addEventListener('scroll', () => {
      const state = store.getState();
      if (!state.ui.liveLogEnabled) return;

      // Check if user has scrolled up (not at bottom)
      const isAtBottom = logContent.scrollHeight - logContent.scrollTop <= logContent.clientHeight + 50;

      if (!isAtBottom && !state.ui.liveLogPaused) {
        userHasScrolled = true;
      } else if (isAtBottom) {
        userHasScrolled = false;
      }
    });
  }

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
