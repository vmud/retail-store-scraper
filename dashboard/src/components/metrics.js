/**
 * Metrics Component - KPI strip with animated counters
 */

import { store } from '../state.js';
import { formatNumber, formatDuration, formatRate, animateValue } from '../utils/format.js';

// Track previous values for animation
let prevValues = {
  stores: 0,
  requests: 0,
  duration: 0,
  rate: 0
};

// Track when any scraper first became active (for global duration)
let globalScraperStartTime = null;

// Duration update interval
let durationInterval = null;

/**
 * Format duration in HH:MM:SS
 */
function formatDurationHHMMSS(seconds) {
  if (seconds < 0 || !Number.isFinite(seconds)) return '00:00:00';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Update duration display
 */
function updateDurationDisplay() {
  const durationEl = document.getElementById('metric-duration');
  if (!durationEl) return;

  if (globalScraperStartTime) {
    const elapsed = Math.floor((Date.now() - globalScraperStartTime) / 1000);
    durationEl.textContent = formatDurationHHMMSS(elapsed);
  } else {
    durationEl.textContent = '00:00:00';
  }
}

/**
 * Update a single metric with animation
 * @param {string} id - Element ID
 * @param {number} newValue - New value
 * @param {number} prevValue - Previous value
 * @param {function} formatter - Formatting function
 */
function updateMetric(id, newValue, prevValue, formatter) {
  const element = document.getElementById(id);
  if (!element) return;

  if (newValue !== prevValue) {
    animateValue(element, prevValue, newValue, 500, formatter);
  }
}

/**
 * Calculate aggregate metrics from retailer data
 * @param {object} retailers - Retailers data
 * @returns {object} Aggregated metrics
 */
function calculateMetrics(retailers) {
  let totalStores = 0;
  let totalRequests = 0;
  let activeRetailers = 0;

  Object.values(retailers).forEach(retailer => {
    // Extract stores from progress text
    const progressText = retailer.progress?.text || '';
    const storeMatch = progressText.match(/^([\d,]+)/);
    if (storeMatch) {
      totalStores += parseInt(storeMatch[1].replace(/,/g, ''), 10) || 0;
    }

    // Count active retailers
    if (retailer.status === 'running') {
      activeRetailers++;
    }

    // Estimate requests (this would need actual tracking in the backend)
    // For now, approximate based on stores scraped
    const stats = retailer.stats || {};
    if (stats.stat3_value && stats.stat3_value !== '—') {
      const requests = parseInt(String(stats.stat3_value).replace(/,/g, ''), 10);
      if (!isNaN(requests)) {
        totalRequests += requests;
      }
    }
  });

  return {
    stores: totalStores,
    requests: totalRequests,
    activeRetailers
  };
}

/**
 * Render the metrics strip
 * @param {object} state - Current state
 */
function render(state) {
  const { retailers, summary } = state;

  // Calculate aggregate metrics
  const metrics = calculateMetrics(retailers);

  // Track global scraper start time
  const hasActiveScrapers = summary.activeScrapers > 0;

  if (hasActiveScrapers && !globalScraperStartTime) {
    // Scrapers just became active - start tracking duration
    globalScraperStartTime = Date.now();

    // Start interval for duration updates if not already running
    if (!durationInterval) {
      durationInterval = setInterval(updateDurationDisplay, 1000);
    }
  } else if (!hasActiveScrapers && globalScraperStartTime) {
    // No more active scrapers - stop tracking
    globalScraperStartTime = null;

    // Clear interval
    if (durationInterval) {
      clearInterval(durationInterval);
      durationInterval = null;
    }

    // Reset duration display
    const durationEl = document.getElementById('metric-duration');
    if (durationEl) {
      durationEl.textContent = '00:00:00';
    }
  }

  // Update stores metric
  const storesEl = document.getElementById('metric-stores');
  if (storesEl) {
    if (metrics.stores !== prevValues.stores) {
      animateValue(storesEl, prevValues.stores, metrics.stores, 500, (n) => formatNumber(n));
    }
  }

  // Update requests metric
  const requestsEl = document.getElementById('metric-requests');
  if (requestsEl) {
    if (metrics.requests !== prevValues.requests) {
      animateValue(requestsEl, prevValues.requests, metrics.requests, 500, (n) => formatNumber(n));
    }
  }

  // Update duration display immediately
  updateDurationDisplay();

  // Update rate metric (stores per second based on elapsed time)
  const rateEl = document.getElementById('metric-rate');
  if (rateEl) {
    if (hasActiveScrapers && globalScraperStartTime && metrics.stores > 0) {
      const elapsedSeconds = Math.max(1, (Date.now() - globalScraperStartTime) / 1000);
      const rate = (metrics.stores / elapsedSeconds).toFixed(1);
      rateEl.textContent = `${rate}/sec`;
    } else {
      rateEl.textContent = '—/sec';
    }
  }

  // Highlight values when scrapers are active
  if (storesEl) {
    if (hasActiveScrapers) {
      storesEl.classList.add('metric__value--highlight');
    } else {
      storesEl.classList.remove('metric__value--highlight');
    }
  }

  // Store previous values for next animation
  prevValues = {
    stores: metrics.stores,
    requests: metrics.requests,
    duration: 0,
    rate: 0
  };
}

/**
 * Initialize the metrics component
 */
export function init() {
  // Subscribe to state changes
  store.subscribe((state) => {
    render(state);
  });

  // Initial render
  render(store.getState());
}

/**
 * Cleanup
 */
export function destroy() {
  prevValues = { stores: 0, requests: 0, duration: 0, rate: 0 };
  globalScraperStartTime = null;

  if (durationInterval) {
    clearInterval(durationInterval);
    durationInterval = null;
  }
}

export default {
  init,
  destroy
};
