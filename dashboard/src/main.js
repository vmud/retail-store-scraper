/**
 * Main Entry Point - Retail Scraper Command Center
 * Initializes all components and starts the data polling loop
 */

// Import core modules
import { store, actions } from './state.js';
import api from './api.js';

// Import components
import header from './components/header.js';
import metrics from './components/metrics.js';
import retailerCard from './components/retailer-card.js';
import changePanel from './components/change-panel.js';
import modal from './components/modal.js';
import toast from './components/toast.js';

// Import utilities
import keyboard from './utils/keyboard.js';
import { formatRelativeTime } from './utils/format.js';

// Constants
const POLL_INTERVAL = 5000; // 5 seconds
const RETRY_DELAY = 10000;  // 10 seconds on error

// State
let pollInterval = null;
let timestampInterval = null;
let isPolling = false;

/**
 * Fetch status data from API
 */
async function fetchStatus() {
  try {
    const data = await api.getStatus();
    actions.setStatusData(data);
    return true;
  } catch (error) {
    console.error('Failed to fetch status:', error);
    actions.setError(error);
    return false;
  }
}

/**
 * Start the polling loop
 */
function startPolling() {
  if (isPolling) return;

  isPolling = true;

  // Initial fetch
  fetchStatus();

  // Set up interval
  pollInterval = setInterval(async () => {
    const success = await fetchStatus();

    // If error, pause and retry with longer delay
    if (!success) {
      stopPolling();
      setTimeout(() => {
        startPolling();
      }, RETRY_DELAY);
    }
  }, POLL_INTERVAL);
}

/**
 * Stop the polling loop
 */
function stopPolling() {
  isPolling = false;
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

/**
 * Handle visibility change - pause polling when tab is hidden
 */
function handleVisibilityChange() {
  if (document.hidden) {
    stopPolling();
  } else {
    startPolling();
  }
}

/**
 * Handle manual refresh request
 */
function handleManualRefresh() {
  fetchStatus();
  toast.showInfo('Refreshing data...');
}

/**
 * Update footer timestamp
 */
function updateFooterTimestamp() {
  const el = document.getElementById('footer-timestamp');
  const state = store.getState();

  if (el && state.lastUpdate) {
    el.textContent = formatRelativeTime(state.lastUpdate);
  }
}

/**
 * Initialize the application
 */
function init() {
  console.log('Initializing Retail Scraper Command Center...');

  // Initialize components
  toast.init();
  header.init();
  metrics.init();
  retailerCard.init();
  changePanel.init();
  modal.init();
  keyboard.init();

  // Set up visibility change handler
  document.addEventListener('visibilitychange', handleVisibilityChange);

  // Set up manual refresh handler
  window.addEventListener('manual-refresh', handleManualRefresh);

  // Update footer timestamp periodically
  timestampInterval = setInterval(updateFooterTimestamp, 1000);

  // Start polling
  startPolling();

  // Subscribe to state changes for error display
  store.subscribe((state, prevState) => {
    // Show error toast if error state changed
    if (state.error && state.error !== prevState?.error) {
      toast.showError(`Connection error: ${state.error}`);
    }
  });

  console.log('Dashboard initialized');
}

/**
 * Cleanup the application
 */
function destroy() {
  stopPolling();

  if (timestampInterval) {
    clearInterval(timestampInterval);
    timestampInterval = null;
  }

  document.removeEventListener('visibilitychange', handleVisibilityChange);
  window.removeEventListener('manual-refresh', handleManualRefresh);

  // Cleanup components
  header.destroy();
  metrics.destroy();
  retailerCard.destroy();
  changePanel.destroy();
  modal.destroy();
  toast.destroy();
  keyboard.destroy();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Export for potential external use
export { init, destroy, startPolling, stopPolling, fetchStatus };
