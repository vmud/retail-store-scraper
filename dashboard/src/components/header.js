/**
 * Header Component - Top navigation bar with status indicators
 */

import { store, actions } from '../state.js';
import { formatTimeUTC } from '../utils/format.js';

let timeInterval = null;

/**
 * Render status indicators in the header nav
 * @param {HTMLElement} container - Header nav container
 * @param {object} summary - Summary data from state
 */
function renderStatusIndicators(container, summary) {
  const { activeScrapers, activeRetailers, totalRetailers, overallProgress } = summary;

  const activeText = activeScrapers > 0
    ? `${activeScrapers} ACTIVE`
    : 'ALL IDLE';

  // Calculate enabled-but-not-running retailers (truly idle)
  const idleCount = activeRetailers - activeScrapers;

  container.innerHTML = `
    <div class="status-indicator ${activeScrapers > 0 ? 'status-indicator--active' : 'status-indicator--idle'}">
      <span class="status-indicator__dot"></span>
      <span>${activeText}</span>
    </div>
    ${idleCount > 0 ? `
      <div class="status-indicator status-indicator--idle">
        <span class="status-indicator__dot"></span>
        <span>${idleCount} IDLE</span>
      </div>
    ` : ''}
    <div class="progress" style="width: 200px; margin-left: var(--space-4);">
      <div class="progress__fill ${activeScrapers > 0 ? 'progress__fill--live' : 'progress__fill--done'}"
           style="width: ${overallProgress}%"></div>
    </div>
    <span style="font-family: var(--font-mono); font-size: var(--text-sm); color: var(--text-muted); margin-left: var(--space-2);">
      ${overallProgress.toFixed(1)}%
    </span>
  `;
}

/**
 * Update the current time display
 */
function updateTime() {
  const timeEl = document.getElementById('current-time');
  if (timeEl) {
    timeEl.textContent = formatTimeUTC();
  }
}

/**
 * Initialize the header component
 */
export function init() {
  const headerNav = document.getElementById('header-status');
  const configBtn = document.getElementById('config-btn');

  // Subscribe to state changes
  store.subscribe((state) => {
    if (headerNav) {
      renderStatusIndicators(headerNav, state.summary);
    }
  });

  // Config button click handler
  if (configBtn) {
    configBtn.addEventListener('click', () => {
      actions.toggleConfigModal(true);
    });
  }

  // Start time update interval
  updateTime();
  timeInterval = setInterval(updateTime, 1000);

  // Initial render with current state
  const currentState = store.getState();
  if (headerNav) {
    renderStatusIndicators(headerNav, currentState.summary);
  }
}

/**
 * Cleanup the header component
 */
export function destroy() {
  if (timeInterval) {
    clearInterval(timeInterval);
    timeInterval = null;
  }
}

export default {
  init,
  destroy
};
