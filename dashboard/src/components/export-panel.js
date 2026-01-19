/**
 * Export Panel Component
 * Provides multi-retailer export functionality with format selection
 */

import { store } from '../state.js';
import { exportMulti } from '../api.js';
import toast from './toast.js';

// Available export formats
const EXPORT_FORMATS = [
  { value: 'json', label: 'JSON', description: 'Standard JSON format' },
  { value: 'csv', label: 'CSV', description: 'Comma-separated values' },
  { value: 'excel', label: 'Excel', description: 'Multi-sheet workbook' },
  { value: 'geojson', label: 'GeoJSON', description: 'Geographic data format' }
];

// State
let selectedFormat = 'excel';
let combineFiles = true;
let isExporting = false;

/**
 * Get available retailers from state
 * @returns {Array<string>} List of retailer IDs
 */
function getAvailableRetailers() {
  const state = store.getState();
  return Object.keys(state.retailers || {});
}

/**
 * Get retailers with data (have stores)
 * @returns {Array<string>} List of retailer IDs with data
 */
function getRetailersWithData() {
  const state = store.getState();
  const retailers = state.retailers || {};

  return Object.entries(retailers)
    .filter(([_, data]) => {
      // Check if retailer has any phases with discovered stores (total > 0)
      const phases = data.phases || [];
      return phases.some(phase => phase.total > 0);
    })
    .map(([id]) => id);
}

/**
 * Render the export panel HTML
 */
function render() {
  const container = document.getElementById('export-panel');
  if (!container) return;

  const retailersWithData = getRetailersWithData();
  const hasData = retailersWithData.length > 0;

  container.innerHTML = `
    <div class="export-panel__header" id="export-panel-toggle">
      <span class="export-panel__title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        Export Data
      </span>
      <span class="export-panel__toggle">▼</span>
    </div>
    <div class="export-panel__content">
      <div class="export-panel__body">
        <div class="export-panel__options">
          <div class="export-panel__option-group">
            <label class="export-panel__label">Format</label>
            <div class="export-panel__format-grid">
              ${EXPORT_FORMATS.map(fmt => `
                <button
                  class="export-panel__format-btn ${selectedFormat === fmt.value ? 'export-panel__format-btn--active' : ''}"
                  data-format="${fmt.value}"
                  data-tooltip="${fmt.description}"
                >
                  ${fmt.label}
                </button>
              `).join('')}
            </div>
          </div>

          <div class="export-panel__option-group">
            <label class="export-panel__checkbox">
              <input
                type="checkbox"
                id="export-combine"
                ${combineFiles ? 'checked' : ''}
                ${!hasData ? 'disabled' : ''}
              />
              <span>Combine into single file</span>
            </label>
            <span class="export-panel__hint">
              ${selectedFormat === 'excel' ? 'Creates multi-sheet workbook (one sheet per retailer)' : 'Merges all stores with retailer field'}
            </span>
          </div>
        </div>

        <div class="export-panel__actions">
          <div class="export-panel__retailers-info">
            ${hasData
              ? `<span class="export-panel__count">${retailersWithData.length}</span> retailers with data`
              : '<span class="export-panel__no-data">No data available</span>'
            }
          </div>
          <button
            class="btn btn--primary export-panel__export-btn"
            id="export-all-btn"
            ${!hasData || isExporting ? 'disabled' : ''}
          >
            ${isExporting
              ? '<span class="spinner"></span> Exporting...'
              : `Export All Retailers`
            }
          </button>
        </div>
      </div>
    </div>
  `;

  // Re-attach event listeners
  attachEventListeners();
}

/**
 * Attach event listeners to panel elements
 */
function attachEventListeners() {
  // Toggle panel
  const toggle = document.getElementById('export-panel-toggle');
  if (toggle) {
    toggle.addEventListener('click', togglePanel);
  }

  // Format buttons
  const formatBtns = document.querySelectorAll('.export-panel__format-btn');
  formatBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      selectedFormat = e.target.dataset.format;
      render();
    });
  });

  // Combine checkbox
  const combineCheckbox = document.getElementById('export-combine');
  if (combineCheckbox) {
    combineCheckbox.addEventListener('change', (e) => {
      combineFiles = e.target.checked;
      render();
    });
  }

  // Export button
  const exportBtn = document.getElementById('export-all-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', handleExportAll);
  }
}

/**
 * Toggle panel open/closed
 */
function togglePanel() {
  const panel = document.getElementById('export-panel');
  if (!panel) return;
  panel.classList.toggle('export-panel--open');
}

/**
 * Handle export all retailers
 */
async function handleExportAll() {
  const retailers = getRetailersWithData();

  if (retailers.length === 0) {
    toast.showWarning('No retailers have data to export');
    return;
  }

  isExporting = true;
  render();

  try {
    toast.showInfo(`Generating ${selectedFormat.toUpperCase()} export for ${retailers.length} retailers...`);

    await exportMulti(retailers, selectedFormat, combineFiles);

    toast.showSuccess(`Export complete! Downloaded ${selectedFormat.toUpperCase()} file.`);
  } catch (error) {
    console.error('Export failed:', error);
    toast.showError(`Export failed: ${error.message}`);
  } finally {
    isExporting = false;
    render();
  }
}

/**
 * Initialize the export panel component
 */
export function init() {
  // Initial render
  render();

  // Subscribe to state changes to update retailer counts
  store.subscribe(() => {
    // Only re-render if panel exists and is open
    const panel = document.getElementById('export-panel');
    if (panel && panel.classList.contains('export-panel--open')) {
      render();
    }
  });
}

/**
 * Cleanup
 */
export function destroy() {
  const toggle = document.getElementById('export-panel-toggle');
  if (toggle) {
    toggle.removeEventListener('click', togglePanel);
  }

  // Reset state
  selectedFormat = 'excel';
  combineFiles = true;
  isExporting = false;
}

export default {
  init,
  destroy
};
