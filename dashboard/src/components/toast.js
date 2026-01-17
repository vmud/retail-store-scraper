/**
 * Toast Component - Notification system
 */

const TOAST_DURATION = 5000; // 5 seconds
const toasts = new Map();
let toastCounter = 0;

/**
 * Get the toast container element
 * @returns {HTMLElement} Toast container
 */
function getContainer() {
  let container = document.getElementById('toast-container');

  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
      position: fixed;
      top: var(--space-4);
      right: var(--space-4);
      z-index: var(--z-toast);
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
      pointer-events: none;
    `;
    document.body.appendChild(container);
  }

  return container;
}

/**
 * Create a toast element
 * @param {string} message - Toast message
 * @param {string} type - Toast type (success, error, warning, info)
 * @param {number} id - Unique toast ID
 * @returns {HTMLElement} Toast element
 */
function createToastElement(message, type, id) {
  const toast = document.createElement('div');
  toast.id = `toast-${id}`;
  toast.className = 'toast toast-enter';
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'polite');

  // Get icon based on type
  let icon = '';
  switch (type) {
    case 'success':
      icon = '✓';
      break;
    case 'error':
      icon = '✕';
      break;
    case 'warning':
      icon = '!';
      break;
    default:
      icon = 'i';
  }

  toast.innerHTML = `
    <span class="toast__icon">${icon}</span>
    <span class="toast__message">${escapeHtml(message)}</span>
    <button class="toast__close" aria-label="Dismiss">&times;</button>
  `;

  // Add styles inline for simplicity (could move to CSS)
  toast.style.cssText = `
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--surface);
    border: var(--border-width) solid var(--border);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
    box-shadow: var(--shadow-lg);
    pointer-events: auto;
    max-width: 400px;
    animation: slide-in-right var(--duration-slow) var(--ease-spring) forwards;
  `;

  // Icon styling based on type
  const iconEl = toast.querySelector('.toast__icon');
  if (iconEl) {
    iconEl.style.cssText = `
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: var(--text-xs);
      font-weight: var(--weight-bold);
      flex-shrink: 0;
    `;

    switch (type) {
      case 'success':
        iconEl.style.background = 'rgba(34, 197, 94, 0.2)';
        iconEl.style.color = 'var(--signal-live)';
        toast.style.borderColor = 'var(--signal-live)';
        break;
      case 'error':
        iconEl.style.background = 'rgba(239, 68, 68, 0.2)';
        iconEl.style.color = 'var(--signal-fail)';
        toast.style.borderColor = 'var(--signal-fail)';
        break;
      case 'warning':
        iconEl.style.background = 'rgba(234, 179, 8, 0.2)';
        iconEl.style.color = 'var(--signal-warn)';
        toast.style.borderColor = 'var(--signal-warn)';
        break;
      default:
        iconEl.style.background = 'rgba(59, 130, 246, 0.2)';
        iconEl.style.color = 'var(--signal-done)';
        toast.style.borderColor = 'var(--signal-done)';
    }
  }

  // Message styling
  const messageEl = toast.querySelector('.toast__message');
  if (messageEl) {
    messageEl.style.cssText = 'flex: 1; word-break: break-word;';
  }

  // Close button styling
  const closeBtn = toast.querySelector('.toast__close');
  if (closeBtn) {
    closeBtn.style.cssText = `
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: var(--text-lg);
      cursor: pointer;
      padding: 0;
      line-height: 1;
      transition: color var(--duration-fast) var(--ease-out);
    `;

    closeBtn.addEventListener('click', () => {
      dismissToast(id);
    });

    closeBtn.addEventListener('mouseenter', () => {
      closeBtn.style.color = 'var(--text-primary)';
    });

    closeBtn.addEventListener('mouseleave', () => {
      closeBtn.style.color = 'var(--text-muted)';
    });
  }

  return toast;
}

/**
 * Escape HTML to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Show a toast notification
 * @param {string} message - Toast message
 * @param {string} type - Toast type (success, error, warning, info)
 * @param {number} duration - Duration in ms (0 for persistent)
 * @returns {number} Toast ID
 */
export function showToast(message, type = 'info', duration = TOAST_DURATION) {
  const container = getContainer();
  const id = ++toastCounter;

  const toast = createToastElement(message, type, id);
  container.appendChild(toast);

  // Store toast reference
  toasts.set(id, {
    element: toast,
    timeoutId: null
  });

  // Auto-dismiss after duration
  if (duration > 0) {
    const timeoutId = setTimeout(() => {
      dismissToast(id);
    }, duration);

    toasts.get(id).timeoutId = timeoutId;
  }

  return id;
}

/**
 * Dismiss a toast by ID
 * @param {number} id - Toast ID
 */
export function dismissToast(id) {
  const toastData = toasts.get(id);
  if (!toastData) return;

  const { element, timeoutId } = toastData;

  // Clear timeout if exists
  if (timeoutId) {
    clearTimeout(timeoutId);
  }

  // Animate out
  element.style.animation = 'slide-out-right var(--duration-normal) var(--ease-out) forwards';

  // Remove after animation
  setTimeout(() => {
    element.remove();
    toasts.delete(id);
  }, 300);
}

/**
 * Dismiss all toasts
 */
export function dismissAllToasts() {
  toasts.forEach((_, id) => {
    dismissToast(id);
  });
}

/**
 * Show a success toast
 * @param {string} message - Toast message
 * @returns {number} Toast ID
 */
export function showSuccess(message) {
  return showToast(message, 'success');
}

/**
 * Show an error toast
 * @param {string} message - Toast message
 * @returns {number} Toast ID
 */
export function showError(message) {
  return showToast(message, 'error');
}

/**
 * Show a warning toast
 * @param {string} message - Toast message
 * @returns {number} Toast ID
 */
export function showWarning(message) {
  return showToast(message, 'warning');
}

/**
 * Show an info toast
 * @param {string} message - Toast message
 * @returns {number} Toast ID
 */
export function showInfo(message) {
  return showToast(message, 'info');
}

/**
 * Initialize the toast system
 */
export function init() {
  // Ensure container exists
  getContainer();
}

/**
 * Cleanup
 */
export function destroy() {
  dismissAllToasts();
}

export default {
  init,
  destroy,
  showToast,
  dismissToast,
  dismissAllToasts,
  showSuccess,
  showError,
  showWarning,
  showInfo
};
