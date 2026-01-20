/**
 * API Client - Fetch wrapper for dashboard API endpoints
 */

const BASE_URL = '/api';

// CSRF token storage
let csrfToken = null;

/**
 * Fetch CSRF token from server
 * @returns {Promise<string>} CSRF token
 */
async function fetchCsrfToken() {
  if (csrfToken) {
    return csrfToken;
  }

  try {
    const response = await fetch(`${BASE_URL}/csrf-token`);
    if (response.ok) {
      const data = await response.json();
      csrfToken = data.csrf_token;
      return csrfToken;
    }
  } catch (error) {
    console.warn('Failed to fetch CSRF token:', error);
  }
  return null;
}

/**
 * Get CSRF headers for POST requests
 * @returns {Promise<object>} Headers object with CSRF token
 */
async function getCsrfHeaders() {
  const token = await fetchCsrfToken();
  if (token) {
    return { 'X-CSRFToken': token };
  }
  return {};
}

/**
 * Make an API request
 * @param {string} endpoint - API endpoint path
 * @param {object} options - Fetch options
 * @returns {Promise<object>} Response data
 */
async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;

  // Add CSRF headers for non-GET requests
  let csrfHeaders = {};
  if (options.method && options.method !== 'GET') {
    csrfHeaders = await getCsrfHeaders();
  }

  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...csrfHeaders,
      ...options.headers
    },
    ...options
  };

  try {
    const response = await fetch(url, config);

    // Try to parse JSON response
    let data;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      const error = new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (error) {
    // Re-throw API errors, wrap network errors
    if (error.status) {
      throw error;
    }
    const networkError = new Error(`Network error: ${error.message}`);
    networkError.isNetworkError = true;
    throw networkError;
  }
}

/**
 * GET request helper
 */
function get(endpoint) {
  return request(endpoint, { method: 'GET' });
}

/**
 * POST request helper
 */
function post(endpoint, data) {
  return request(endpoint, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}

// ============================================
// Status APIs
// ============================================

/**
 * Get status for all retailers
 * @returns {Promise<object>} Status data with summary and retailers
 */
export function getStatus() {
  return get('/status');
}

/**
 * Get status for a single retailer
 * @param {string} retailer - Retailer ID
 * @returns {Promise<object>} Retailer status
 */
export function getRetailerStatus(retailer) {
  return get(`/status/${retailer}`);
}

// ============================================
// Scraper Control APIs
// ============================================

/**
 * Start scraper(s)
 * @param {string} retailer - Retailer ID or 'all'
 * @param {object} options - Start options
 * @returns {Promise<object>} Start result
 */
export function startScraper(retailer, options = {}) {
  return post('/scraper/start', {
    retailer,
    resume: options.resume ?? true,
    incremental: options.incremental ?? false,
    limit: options.limit ?? null,
    test: options.test ?? false,
    proxy: options.proxy ?? 'direct',  // Default to direct mode (no proxy)
    render_js: options.renderJs ?? false,
    proxy_country: options.proxyCountry ?? 'us',
    verbose: options.verbose ?? false
  });
}

/**
 * Stop scraper(s)
 * @param {string} retailer - Retailer ID or 'all'
 * @param {number} timeout - Shutdown timeout in seconds
 * @returns {Promise<object>} Stop result
 */
export function stopScraper(retailer, timeout = 30) {
  return post('/scraper/stop', {
    retailer,
    timeout
  });
}

/**
 * Restart scraper(s)
 * @param {string} retailer - Retailer ID or 'all'
 * @param {object} options - Restart options
 * @returns {Promise<object>} Restart result
 */
export function restartScraper(retailer, options = {}) {
  return post('/scraper/restart', {
    retailer,
    resume: options.resume ?? true,
    timeout: options.timeout ?? 30,
    proxy: options.proxy ?? 'direct'  // Default to direct mode (no proxy)
  });
}

// ============================================
// Run History APIs
// ============================================

/**
 * Get run history for a retailer
 * @param {string} retailer - Retailer ID
 * @param {number} limit - Number of runs to return
 * @returns {Promise<object>} Run history
 */
export function getRunHistory(retailer, limit = 10) {
  return get(`/runs/${retailer}?limit=${limit}`);
}

/**
 * Get logs for a specific run
 * @param {string} retailer - Retailer ID
 * @param {string} runId - Run ID
 * @param {object} options - Options for fetching logs
 * @param {number} options.tail - Number of lines from end
 * @param {number} options.offset - Line number to start from (for incremental fetch)
 * @returns {Promise<object>} Log content with total_lines, is_active, etc.
 */
export function getLogs(retailer, runId, options = {}) {
  const params = new URLSearchParams();
  if (options.tail) params.append('tail', options.tail);
  if (options.offset) params.append('offset', options.offset);

  const queryString = params.toString();
  return get(`/logs/${retailer}/${runId}${queryString ? '?' + queryString : ''}`);
}

// ============================================
// Configuration APIs
// ============================================

/**
 * Get current configuration
 * @returns {Promise<object>} Config content
 */
export function getConfig() {
  return get('/config');
}

/**
 * Update configuration
 * @param {string} content - YAML content
 * @returns {Promise<object>} Update result
 */
export function updateConfig(content) {
  return post('/config', { content });
}

// ============================================
// Export APIs
// ============================================

/**
 * Get list of available export formats
 * @returns {Promise<object>} Formats list
 */
export function getExportFormats() {
  return get('/export/formats');
}

/**
 * Export retailer data in specified format
 * Downloads the file directly in the browser
 * @param {string} retailer - Retailer ID
 * @param {string} format - Export format (json|csv|excel|geojson)
 * @returns {Promise<void>}
 */
export async function exportRetailer(retailer, format) {
  const url = `${BASE_URL}/export/${retailer}/${format}`;

  const response = await fetch(url);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Export failed: ${response.statusText}`);
  }

  // Get filename from Content-Disposition header or generate one
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `${retailer}_stores.${format === 'excel' ? 'xlsx' : format}`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
    if (match) filename = match[1];
  }

  // Download the file
  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}

/**
 * Export multiple retailers combined
 * @param {Array<string>} retailers - Retailer IDs
 * @param {string} format - Export format
 * @param {boolean} combine - Combine into single file
 * @returns {Promise<void>}
 */
export async function exportMulti(retailers, format, combine = true) {
  const url = `${BASE_URL}/export/multi`;
  const csrfHeaders = await getCsrfHeaders();

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...csrfHeaders
    },
    body: JSON.stringify({ retailers, format, combine })
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `Export failed: ${response.statusText}`);
  }

  // Get filename from Content-Disposition header or generate one
  const contentDisposition = response.headers.get('Content-Disposition');
  let filename = `stores_combined.${format === 'excel' ? 'xlsx' : format}`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
    if (match) filename = match[1];
  }

  // Download the file
  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(downloadUrl);
}

// ============================================
// Export API object
// ============================================

export default {
  getStatus,
  getRetailerStatus,
  startScraper,
  stopScraper,
  restartScraper,
  getRunHistory,
  getLogs,
  getConfig,
  updateConfig,
  getExportFormats,
  exportRetailer,
  exportMulti
};
