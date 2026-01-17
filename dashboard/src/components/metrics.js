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

  // Update stores metric
  const storesEl = document.getElementById('metric-stores');
  if (storesEl) {
    if (metrics.stores !== prevValues.stores) {
      animateValue(storesEl, prevValues.stores, metrics.stores, 500, (n) => formatNumber(n));
    }
  }

  // Update requests metric (placeholder for now)
  const requestsEl = document.getElementById('metric-requests');
  if (requestsEl) {
    if (metrics.requests !== prevValues.requests) {
      animateValue(requestsEl, prevValues.requests, metrics.requests, 500, (n) => formatNumber(n));
    }
  }

  // Update duration metric (show elapsed time for active scrapers)
  const durationEl = document.getElementById('metric-duration');
  if (durationEl) {
    // This would need actual duration tracking from backend
    // For now, show a placeholder or calculate from run history
    durationEl.textContent = summary.activeScrapers > 0 ? '--:--:--' : '00:00:00';
  }

  // Update rate metric
  const rateEl = document.getElementById('metric-rate');
  if (rateEl) {
    if (summary.activeScrapers > 0 && metrics.stores > 0) {
      // Estimate rate based on stores and assumed duration
      const estimatedRate = (metrics.stores / 60).toFixed(1); // Rough estimate
      rateEl.textContent = `${estimatedRate}/sec`;
    } else {
      rateEl.textContent = '—/sec';
    }
  }

  // Highlight values when scrapers are active
  const storesValueEl = storesEl;
  if (storesValueEl) {
    if (summary.activeScrapers > 0) {
      storesValueEl.classList.add('metric__value--highlight');
    } else {
      storesValueEl.classList.remove('metric__value--highlight');
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
}

export default {
  init,
  destroy
};
