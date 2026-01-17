/**
 * State Management - Simple reactive state store
 * Minimal implementation for dashboard state without heavy dependencies
 */

/**
 * Create a reactive state store
 * @param {object} initialState - Initial state object
 * @returns {object} State store with update and subscribe methods
 */
export function createStore(initialState = {}) {
  let state = { ...initialState };
  const listeners = new Set();
  const selectorListeners = new Map(); // Map<selectorKey, Set<{selector, callback}>>

  /**
   * Get the current state
   * @returns {object} Current state
   */
  function getState() {
    return state;
  }

  /**
   * Update state and notify listeners
   * @param {object|function} updates - New state values or updater function
   */
  function update(updates) {
    const prevState = state;

    if (typeof updates === 'function') {
      state = { ...state, ...updates(state) };
    } else {
      state = { ...state, ...updates };
    }

    // Notify all general listeners
    listeners.forEach(listener => {
      try {
        listener(state, prevState);
      } catch (error) {
        console.error('State listener error:', error);
      }
    });

    // Notify selector-based listeners only if their selected value changed
    selectorListeners.forEach((listenerSet) => {
      listenerSet.forEach(({ selector, callback }) => {
        const prevValue = selector(prevState);
        const newValue = selector(state);

        if (!shallowEqual(prevValue, newValue)) {
          try {
            callback(newValue, prevValue);
          } catch (error) {
            console.error('Selector listener error:', error);
          }
        }
      });
    });
  }

  /**
   * Subscribe to all state changes
   * @param {function} listener - Callback function(newState, prevState)
   * @returns {function} Unsubscribe function
   */
  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  /**
   * Subscribe to specific state slice changes
   * @param {function} selector - Selector function to extract state slice
   * @param {function} callback - Callback function(newValue, prevValue)
   * @returns {function} Unsubscribe function
   */
  function subscribeSelector(selector, callback) {
    const key = selector.toString();
    if (!selectorListeners.has(key)) {
      selectorListeners.set(key, new Set());
    }

    const entry = { selector, callback };
    selectorListeners.get(key).add(entry);

    return () => {
      const set = selectorListeners.get(key);
      if (set) {
        set.delete(entry);
        if (set.size === 0) {
          selectorListeners.delete(key);
        }
      }
    };
  }

  /**
   * Reset state to initial values
   */
  function reset() {
    update({ ...initialState });
  }

  return {
    getState,
    update,
    subscribe,
    subscribeSelector,
    reset
  };
}

/**
 * Shallow equality check for objects and arrays
 */
function shallowEqual(a, b) {
  if (a === b) return true;
  if (a == null || b == null) return false;
  if (typeof a !== typeof b) return false;

  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((val, i) => val === b[i]);
  }

  if (typeof a === 'object') {
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);
    if (keysA.length !== keysB.length) return false;
    return keysA.every(key => a[key] === b[key]);
  }

  return false;
}

// ============================================
// Dashboard State Store
// ============================================

/**
 * Retailer configuration constants
 */
export const RETAILERS = {
  verizon: { id: 'verizon', name: 'Verizon', abbr: 'VZ' },
  att: { id: 'att', name: 'AT&T', abbr: 'AT' },
  target: { id: 'target', name: 'Target', abbr: 'TG' },
  tmobile: { id: 'tmobile', name: 'T-Mobile', abbr: 'TM' },
  walmart: { id: 'walmart', name: 'Walmart', abbr: 'WM' },
  bestbuy: { id: 'bestbuy', name: 'Best Buy', abbr: 'BB' }
};

/**
 * Initial dashboard state
 */
const initialDashboardState = {
  // Loading and error states
  isLoading: true,
  error: null,
  lastUpdate: null,

  // Global metrics
  summary: {
    totalStores: 0,
    activeRetailers: 0,
    totalRetailers: 6,
    overallProgress: 0,
    activeScrapers: 0
  },

  // Per-retailer status
  retailers: {},

  // Change detection
  changes: {
    new: 0,
    closed: 0,
    modified: 0
  },

  // UI state
  ui: {
    configModalOpen: false,
    logModalOpen: false,
    currentLogRetailer: null,
    currentLogRunId: null,
    expandedCards: new Set(),
    changePanelOpen: false
  }
};

/**
 * Create the main dashboard store
 */
export const store = createStore(initialDashboardState);

// ============================================
// Selectors
// ============================================

export const selectors = {
  isLoading: (state) => state.isLoading,
  error: (state) => state.error,
  summary: (state) => state.summary,
  retailers: (state) => state.retailers,
  retailer: (retailerId) => (state) => state.retailers[retailerId],
  changes: (state) => state.changes,
  ui: (state) => state.ui,
  isConfigModalOpen: (state) => state.ui.configModalOpen,
  isLogModalOpen: (state) => state.ui.logModalOpen,
  activeScrapers: (state) => state.summary.activeScrapers
};

// ============================================
// Actions
// ============================================

export const actions = {
  /**
   * Update status data from API response
   */
  setStatusData(data) {
    const { summary, retailers } = data;

    store.update({
      isLoading: false,
      error: null,
      lastUpdate: Date.now(),
      summary: {
        totalStores: summary?.total_stores ?? 0,
        activeRetailers: summary?.active_retailers ?? 0,
        totalRetailers: summary?.total_retailers ?? 6,
        overallProgress: summary?.overall_progress ?? 0,
        activeScrapers: summary?.active_scrapers ?? 0
      },
      retailers: retailers || {}
    });
  },

  /**
   * Set error state
   */
  setError(error) {
    store.update({
      isLoading: false,
      error: error?.message || String(error)
    });
  },

  /**
   * Set loading state
   */
  setLoading(isLoading) {
    store.update({ isLoading });
  },

  /**
   * Toggle config modal
   */
  toggleConfigModal(open) {
    store.update((state) => ({
      ui: { ...state.ui, configModalOpen: open ?? !state.ui.configModalOpen }
    }));
  },

  /**
   * Open log modal
   */
  openLogModal(retailer, runId) {
    store.update((state) => ({
      ui: {
        ...state.ui,
        logModalOpen: true,
        currentLogRetailer: retailer,
        currentLogRunId: runId
      }
    }));
  },

  /**
   * Close log modal
   */
  closeLogModal() {
    store.update((state) => ({
      ui: {
        ...state.ui,
        logModalOpen: false,
        currentLogRetailer: null,
        currentLogRunId: null
      }
    }));
  },

  /**
   * Toggle card expansion
   */
  toggleCardExpansion(retailerId) {
    store.update((state) => {
      const expanded = new Set(state.ui.expandedCards);
      if (expanded.has(retailerId)) {
        expanded.delete(retailerId);
      } else {
        expanded.add(retailerId);
      }
      return { ui: { ...state.ui, expandedCards: expanded } };
    });
  },

  /**
   * Toggle change panel
   */
  toggleChangePanel(open) {
    store.update((state) => ({
      ui: { ...state.ui, changePanelOpen: open ?? !state.ui.changePanelOpen }
    }));
  },

  /**
   * Set change detection data
   */
  setChanges(changes) {
    store.update({ changes });
  }
};

export default store;
