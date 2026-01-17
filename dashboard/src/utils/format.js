/**
 * Format Utilities - Number and time formatting for the dashboard
 */

/**
 * Format a number with locale-aware separators
 * @param {number} num - The number to format
 * @param {object} options - Formatting options
 * @returns {string} Formatted number string
 */
export function formatNumber(num, options = {}) {
  if (num === null || num === undefined || isNaN(num)) {
    return '—';
  }

  const {
    decimals = 0,
    prefix = '',
    suffix = ''
  } = options;

  const formatted = num.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });

  return `${prefix}${formatted}${suffix}`;
}

/**
 * Format a number in compact form (e.g., 1.2K, 3.4M)
 * @param {number} num - The number to format
 * @returns {string} Compact formatted string
 */
export function formatCompact(num) {
  if (num === null || num === undefined || isNaN(num)) {
    return '—';
  }

  if (num < 1000) return num.toString();
  if (num < 1000000) return `${(num / 1000).toFixed(1)}K`;
  if (num < 1000000000) return `${(num / 1000000).toFixed(1)}M`;
  return `${(num / 1000000000).toFixed(1)}B`;
}

/**
 * Format seconds as duration string (HH:MM:SS or MM:SS)
 * @param {number} seconds - Duration in seconds
 * @param {boolean} forceHours - Always show hours even if 0
 * @returns {string} Formatted duration string
 */
export function formatDuration(seconds, forceHours = true) {
  if (!seconds || seconds <= 0 || isNaN(seconds)) {
    return forceHours ? '00:00:00' : '00:00';
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  const pad = (n) => n.toString().padStart(2, '0');

  if (forceHours || hours > 0) {
    return `${pad(hours)}:${pad(minutes)}:${pad(secs)}`;
  }

  return `${pad(minutes)}:${pad(secs)}`;
}

/**
 * Format duration in human-readable form
 * @param {number} seconds - Duration in seconds
 * @returns {string} Human-readable duration
 */
export function formatDurationHuman(seconds) {
  if (!seconds || seconds <= 0) return '—';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  if (minutes > 0) {
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  }
  return `${secs}s`;
}

/**
 * Format a rate (per second)
 * @param {number} rate - The rate value
 * @returns {string} Formatted rate string
 */
export function formatRate(rate) {
  if (rate === null || rate === undefined || isNaN(rate)) {
    return '—/sec';
  }

  if (rate >= 100) {
    return `${Math.round(rate)}/sec`;
  }

  return `${rate.toFixed(1)}/sec`;
}

/**
 * Format a percentage
 * @param {number} value - Percentage value (0-100)
 * @param {number} decimals - Decimal places
 * @returns {string} Formatted percentage string
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined || isNaN(value)) {
    return '0%';
  }

  return `${value.toFixed(decimals)}%`;
}

/**
 * Format current time in UTC
 * @returns {string} Formatted time string
 */
export function formatTimeUTC() {
  const now = new Date();
  const hours = now.getUTCHours().toString().padStart(2, '0');
  const minutes = now.getUTCMinutes().toString().padStart(2, '0');
  const seconds = now.getUTCSeconds().toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds} UTC`;
}

/**
 * Format a timestamp for display
 * @param {string|number|Date} timestamp - The timestamp to format
 * @returns {string} Formatted timestamp
 */
export function formatTimestamp(timestamp) {
  if (!timestamp) return '—';

  const date = new Date(timestamp);
  if (isNaN(date.getTime())) return '—';

  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * Format relative time (e.g., "2 minutes ago")
 * @param {Date|number} timestamp - The timestamp
 * @returns {string} Relative time string
 */
export function formatRelativeTime(timestamp) {
  if (!timestamp) return '';

  const now = Date.now();
  const diff = Math.floor((now - new Date(timestamp).getTime()) / 1000);

  if (diff < 5) return 'just now';
  if (diff < 60) return `${diff} seconds ago`;
  if (diff < 3600) {
    const mins = Math.floor(diff / 60);
    return `${mins} minute${mins > 1 ? 's' : ''} ago`;
  }
  if (diff < 86400) {
    const hours = Math.floor(diff / 3600);
    return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  }

  const days = Math.floor(diff / 86400);
  return `${days} day${days > 1 ? 's' : ''} ago`;
}

/**
 * Animate a number change with easing
 * @param {HTMLElement} element - Element to animate
 * @param {number} start - Starting value
 * @param {number} end - Ending value
 * @param {number} duration - Animation duration in ms
 * @param {function} formatter - Optional formatting function
 */
export function animateValue(element, start, end, duration = 500, formatter = formatNumber) {
  if (!element) return;

  const startVal = start || 0;
  const endVal = end || 0;
  const range = endVal - startVal;

  if (range === 0) {
    element.textContent = formatter(endVal);
    return;
  }

  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);

    // easeOutCubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(startVal + range * eased);

    element.textContent = formatter(current);

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      element.textContent = formatter(endVal);
    }
  }

  requestAnimationFrame(update);
}

/**
 * HTML-encode a string to prevent XSS
 * @param {string} str - String to encode
 * @returns {string} HTML-encoded string
 */
export function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
