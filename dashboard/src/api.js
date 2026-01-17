/**
 * API Client - Fetch wrapper for dashboard API endpoints
 */

const BASE_URL = '/api';

/**
 * Make an API request
 * @param {string} endpoint - API endpoint path
 * @param {object} options - Fetch options
 * @returns {Promise<object>} Response data
 */
async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;

  const config = {
    headers: {
      'Content-Type': 'application/json',
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
    proxy: options.proxy ?? null,
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
    timeout: options.timeout ?? 30
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
 * @param {number} tail - Number of lines from end
 * @returns {Promise<object>} Log content
 */
export function getLogs(retailer, runId, tail = null) {
  const params = tail ? `?tail=${tail}` : '';
  return get(`/logs/${retailer}/${runId}${params}`);
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
  updateConfig
};
