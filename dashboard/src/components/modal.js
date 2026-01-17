/**
 * Modal Component - Log viewer modal
 * Manages log modal state and interactions
 */

import { store, actions } from '../state.js';
import api from '../api.js';
import { escapeHtml } from '../utils/format.js';

let activeLogFilters = new Set(['ALL']);

/**
 * Initialize modal component
 */
export function init() {
  const overlay = document.getElementById('log-modal');
  if (!overlay) return;

  // Close modal when clicking overlay background
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      actions.closeLogModal();
    }
  });

  // Subscribe to state changes to keep modal in sync
  store.subscribe((state) => {
    const isOpen = state.ui?.logModalOpen || false;
    const hasClass = overlay.classList.contains('open');

    // Sync DOM state with store state
    if (isOpen && !hasClass) {
      // State says open but class missing - add it
      overlay.classList.add('open');
    } else if (!isOpen && hasClass) {
      // State says closed but class present - remove it
      overlay.classList.remove('open');
    }
  });

  // Set up filter buttons
  const filterButtons = overlay.querySelectorAll('.log-filter-btn');
  filterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const level = btn.dataset.level;
      toggleLogFilter(level);
    });
  });

  // Set up close button
  const closeBtn = overlay.querySelector('.modal-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      actions.closeLogModal();
    });
  }
}

/**
 * Open modal with retailer logs
 */
export async function open(retailerId, runId) {
  const overlay = document.getElementById('log-modal');
  const titleEl = document.getElementById('log-modal-title');
  const contentEl = document.getElementById('log-content');
  
  if (!overlay || !titleEl || !contentEl) return;

  // Reset filters
  activeLogFilters = new Set(['ALL']);
  updateFilterButtons();

  // Update title
  titleEl.textContent = `Logs - ${retailerId} - ${runId}`;
  
  // Show loading state
  contentEl.innerHTML = '<div class="log-loading">Loading logs...</div>';
  
  // Open modal (updates state)
  actions.openLogModal(retailerId, runId);

  // Load logs
  try {
    const data = await api.getRunLogs(retailerId, runId);
    
    if (data.error) {
      contentEl.innerHTML = `<div class="log-error">Error: ${escapeHtml(data.error)}</div>`;
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
    contentEl.innerHTML = `<div class="log-error">Failed to load logs: ${escapeHtml(error.message)}</div>`;
  }
}

/**
 * Close modal
 */
export function close() {
  actions.closeLogModal();
}

/**
 * Parse a log line
 */
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
 * Display parsed log lines
 */
function displayLogs(parsedLines) {
  const contentEl = document.getElementById('log-content');
  if (!contentEl) return;
  
  const html = parsedLines.map(logLine => {
    const shouldShow = activeLogFilters.has('ALL') || activeLogFilters.has(logLine.level);
    const hiddenClass = shouldShow ? '' : 'hidden';
    
    // Escape HTML to prevent XSS
    let formattedLine = escapeHtml(logLine.raw);
    
    // Add formatting after escaping
    if (logLine.level) {
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
    
    const safeLevel = logLine.level ? escapeHtml(logLine.level) : 'unknown';
    return `<div class="log-line level-${safeLevel} ${hiddenClass}">${formattedLine}</div>`;
  }).join('');
  
  contentEl.innerHTML = `<div class="log-container">${html}</div>`;
}

/**
 * Update log stats display
 */
function updateLogStats(parsedLines) {
  const statsEl = document.getElementById('log-stats');
  if (!statsEl) return;
  
  const total = parsedLines.length;
  const visible = parsedLines.filter(line => 
    activeLogFilters.has('ALL') || activeLogFilters.has(line.level)
  ).length;
  
  statsEl.textContent = `Showing ${visible} of ${total} lines`;
}

/**
 * Toggle log filter
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
    
    if (activeLogFilters.size === 0) {
      activeLogFilters.add('ALL');
    }
  }
  
  updateFilterButtons();
  
  // Update visible lines
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
  
  // Update stats
  const total = logLines.length;
  const visible = document.querySelectorAll('.log-line:not(.hidden)').length;
  const statsEl = document.getElementById('log-stats');
  if (statsEl) {
    statsEl.textContent = `Showing ${visible} of ${total} lines`;
  }
}

/**
 * Update filter button active states
 */
function updateFilterButtons() {
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
 * Cleanup
 */
export function destroy() {
  // Remove event listeners if needed
}

export default {
  init,
  open,
  close,
  destroy
};
