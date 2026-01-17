# Escape Key Modal Bug Fix

## Issue Description

The Escape key handler was not properly closing the log modal because:

1. **Wrong CSS class**: The handler looked for `.modal-overlay--open` (with double dash) but the actual class is `.open`
2. **No state update**: The handler only removed the CSS class without calling `closeLogViewer()` to update application state
3. **State subscription conflict**: The modal.js subscription watches for `state.ui.logModalOpen === true` and adds the `open` class if it's missing, causing the modal to automatically reopen on the next state update (within 5 seconds from polling)

## The Bug Flow

1. User presses Escape key
2. `keyboard.js` removes `modal-overlay--open` class (wrong class name)
3. Modal stays visible because `open` class is still present
4. Even if we fixed the class name:
   - `keyboard.js` would remove `open` class
   - Modal would close visually
   - But `state.ui.logModalOpen` is still `true` (no state update)
5. Within 5 seconds, polling triggers state update
6. `modal.js` subscription sees `state.ui.logModalOpen === true` but no `open` class
7. `modal.js` adds `open` class back (thinking DOM is out of sync)
8. Modal reopens automatically

## The Fix

### 1. Fixed keyboard.js (dashboard/src/utils/keyboard.js)

**Before:**
```javascript
registerShortcut('escape', () => {
  // Close any open modals
  document.querySelectorAll('.modal-overlay--open').forEach(modal => {
    modal.classList.remove('modal-overlay--open');
  });
}, { description: 'Close modal' });
```

**After:**
```javascript
registerShortcut('escape', () => {
  // Close log viewer modal if open
  const logModal = document.getElementById('log-modal');
  if (logModal && logModal.classList.contains('open')) {
    // Use the proper close function to update state
    if (typeof closeLogViewer === 'function') {
      closeLogViewer();
    } else {
      // Fallback: just remove the class
      logModal.classList.remove('open');
    }
  }
  
  // Close config modal if open
  const configModal = document.getElementById('config-modal');
  if (configModal && configModal.classList.contains('open')) {
    if (typeof closeConfigModal === 'function') {
      closeConfigModal();
    } else {
      configModal.classList.remove('open');
    }
  }
}, { description: 'Close modal' });
```

**Changes:**
- ✅ Fixed class name from `modal-overlay--open` to `open`
- ✅ Call `closeLogViewer()` to properly update state via `actions.closeLogModal()`
- ✅ Fallback to just removing class if function not available
- ✅ Handle both log modal and config modal

### 2. Created modal.js component (dashboard/src/components/modal.js)

The modal component now properly:
- ✅ Manages modal state through the store
- ✅ Syncs DOM state with application state via subscription
- ✅ Provides `open()` and `close()` functions that update state
- ✅ Only reopens modal if state says it should be open AND class is missing (detecting genuine desync)

### 3. State Flow (After Fix)

1. User presses Escape key
2. `keyboard.js` calls `closeLogViewer()` or `actions.closeLogModal()`
3. State updated: `state.ui.logModalOpen = false`
4. Modal component subscription sees state change
5. Modal removes `open` class
6. Modal closes visually
7. Polling triggers state update (5 seconds later)
8. Modal subscription sees `state.ui.logModalOpen === false`
9. Modal stays closed ✅

## Files Changed

- ✅ Created: `dashboard/src/utils/keyboard.js` - Keyboard shortcut handler with proper modal closing
- ✅ Created: `dashboard/src/components/modal.js` - Modal component with state management

## Testing

To test the fix:

1. Open the dashboard
2. Click "View Logs" on any retailer
3. Press Escape key
4. Modal should close immediately
5. Wait 5+ seconds for next polling update
6. Modal should stay closed ✅

Without the fix, the modal would reopen after step 5.

## Root Cause

The root cause was a mismatch between:
- **UI-only operation** (keyboard.js removing CSS class)
- **State-driven UI** (modal.js watching state and syncing DOM)

When UI operations don't update state, state-driven components will "correct" the DOM back to match the state, causing unexpected behavior.

## Prevention

To prevent similar issues:
1. ✅ Always update state when performing UI operations
2. ✅ Use action creators (`actions.closeLogModal()`) instead of direct DOM manipulation
3. ✅ Subscribe to state changes to keep DOM in sync
4. ✅ Use specific class names (avoid generic patterns that might not match)
