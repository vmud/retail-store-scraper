/**
 * Change Detection Panel Component
 * Displays new, closed, and modified store counts
 */

import { store, actions } from '../state.js';
import { formatNumber, animateValue } from '../utils/format.js';

let prevValues = { new: 0, closed: 0, modified: 0 };

/**
 * Render the change panel content
 * @param {object} changes - Changes data from state
 */
function render(changes) {
  const newEl = document.getElementById('change-new');
  const closedEl = document.getElementById('change-closed');
  const modifiedEl = document.getElementById('change-modified');

  // Animate value changes
  if (newEl && changes.new !== prevValues.new) {
    animateValue(newEl, prevValues.new, changes.new, 500, (n) => `+${formatNumber(n)}`);
  }

  if (closedEl && changes.closed !== prevValues.closed) {
    animateValue(closedEl, prevValues.closed, changes.closed, 500, (n) => `-${formatNumber(n)}`);
  }

  if (modifiedEl && changes.modified !== prevValues.modified) {
    animateValue(modifiedEl, prevValues.modified, changes.modified, 500, (n) => `~${formatNumber(n)}`);
  }

  prevValues = { ...changes };
}

/**
 * Toggle panel open/closed
 */
function togglePanel() {
  const panel = document.getElementById('change-panel');
  if (!panel) return;

  const isOpen = panel.classList.toggle('change-panel--open');
  actions.toggleChangePanel(isOpen);
}

/**
 * Initialize the change panel component
 */
export function init() {
  const toggle = document.getElementById('change-panel-toggle');
  const panel = document.getElementById('change-panel');

  // Set up toggle click handler
  if (toggle) {
    toggle.addEventListener('click', togglePanel);
  }

  // Subscribe to state changes
  store.subscribe((state) => {
    render(state.changes);

    // Sync panel open state
    if (panel) {
      if (state.ui.changePanelOpen) {
        panel.classList.add('change-panel--open');
      } else {
        panel.classList.remove('change-panel--open');
      }
    }
  });

  // Initial render
  render(store.getState().changes);
}

/**
 * Cleanup
 */
export function destroy() {
  const toggle = document.getElementById('change-panel-toggle');
  if (toggle) {
    toggle.removeEventListener('click', togglePanel);
  }
  prevValues = { new: 0, closed: 0, modified: 0 };
}

export default {
  init,
  destroy
};
