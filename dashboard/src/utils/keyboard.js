/**
 * Keyboard Shortcut Handler
 * Manages global keyboard shortcuts for the dashboard
 */

const shortcuts = new Map();
let isEnabled = true;

/**
 * Register a keyboard shortcut
 * @param {string} key - Key combination (e.g., 'Escape', 'ctrl+s', 'shift+r')
 * @param {function} callback - Function to call when shortcut is triggered
 * @param {object} options - Options (preventDefault, description)
 */
export function registerShortcut(key, callback, options = {}) {
  const normalizedKey = normalizeKey(key);
  shortcuts.set(normalizedKey, {
    callback,
    preventDefault: options.preventDefault ?? true,
    description: options.description || ''
  });
}

/**
 * Unregister a keyboard shortcut
 * @param {string} key - Key combination to remove
 */
export function unregisterShortcut(key) {
  const normalizedKey = normalizeKey(key);
  shortcuts.delete(normalizedKey);
}

/**
 * Enable keyboard shortcuts
 */
export function enable() {
  isEnabled = true;
}

/**
 * Disable keyboard shortcuts
 */
export function disable() {
  isEnabled = false;
}

/**
 * Check if shortcuts are enabled
 * @returns {boolean}
 */
export function isActive() {
  return isEnabled;
}

/**
 * Get all registered shortcuts
 * @returns {Array} Array of { key, description } objects
 */
export function getShortcuts() {
  return Array.from(shortcuts.entries()).map(([key, value]) => ({
    key,
    description: value.description
  }));
}

/**
 * Normalize key combination string
 * @param {string} key - Raw key string
 * @returns {string} Normalized key string
 */
function normalizeKey(key) {
  return key.toLowerCase().replace(/\s+/g, '');
}

/**
 * Build key string from event
 * @param {KeyboardEvent} event
 * @returns {string} Key string
 */
function buildKeyString(event) {
  const parts = [];

  if (event.ctrlKey || event.metaKey) parts.push('ctrl');
  if (event.altKey) parts.push('alt');
  if (event.shiftKey) parts.push('shift');

  // Normalize key name
  let key = event.key.toLowerCase();
  if (key === ' ') key = 'space';

  // Don't add modifier keys as the main key
  if (!['control', 'alt', 'shift', 'meta'].includes(key)) {
    parts.push(key);
  }

  return parts.join('+');
}

/**
 * Check if event target is an input element
 * @param {Event} event
 * @returns {boolean}
 */
function isInputTarget(event) {
  const tagName = event.target.tagName.toLowerCase();
  const isEditable = event.target.isContentEditable;
  return tagName === 'input' || tagName === 'textarea' || tagName === 'select' || isEditable;
}

/**
 * Handle keydown event
 * @param {KeyboardEvent} event
 */
function handleKeydown(event) {
  if (!isEnabled) return;

  // Skip if typing in an input field (unless it's Escape)
  if (isInputTarget(event) && event.key !== 'Escape') {
    return;
  }

  const keyString = buildKeyString(event);
  const shortcut = shortcuts.get(keyString);

  if (shortcut) {
    if (shortcut.preventDefault) {
      event.preventDefault();
    }
    shortcut.callback(event);
  }
}

/**
 * Initialize keyboard handler
 */
export function init() {
  document.addEventListener('keydown', handleKeydown);

  // Register default shortcuts
  registerShortcut('escape', () => {
    // Close any open modals
    document.querySelectorAll('.modal-overlay--open').forEach(modal => {
      modal.classList.remove('modal-overlay--open');
    });
  }, { description: 'Close modal' });

  registerShortcut('?', () => {
    // Could show help modal with shortcuts
    console.log('Keyboard shortcuts:', getShortcuts());
  }, { description: 'Show keyboard shortcuts' });

  registerShortcut('r', () => {
    // Trigger manual refresh
    window.dispatchEvent(new CustomEvent('manual-refresh'));
  }, { description: 'Refresh data' });
}

/**
 * Cleanup keyboard handler
 */
export function destroy() {
  document.removeEventListener('keydown', handleKeydown);
  shortcuts.clear();
}

export default {
  init,
  destroy,
  registerShortcut,
  unregisterShortcut,
  enable,
  disable,
  isActive,
  getShortcuts
};
