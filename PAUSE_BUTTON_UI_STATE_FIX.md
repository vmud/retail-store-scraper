# Pause Button UI State Fix

## Issue

When re-opening the log modal for an active scraper, `actions.resetLiveLogState()` correctly resets `liveLogPaused` to `false` in the store, but the pause button's DOM state (text content and `btn--paused` class) from a previous session persisted.

### Reproduction Scenario

1. User opens log modal for an active scraper (button shows "⏸ Pause")
2. User clicks pause button (button changes to "▶ Resume" with `btn--paused` class)
3. User closes the modal
4. User opens log modal for another active scraper
5. **Bug**: Button still displays "▶ Resume" even though polling is running
6. Clicking the button pauses polling when the user intended to resume it (inverted behavior)

### Root Cause

The `updateLiveIndicator()` function only controlled visibility of the live indicator and controls, but never reset the button's text or class state. When the modal was closed, the button DOM persisted, and when reopened, the stale UI state remained.

## Solution

Modified `updateLiveIndicator()` to reset the pause button's UI state when showing live controls.

### Changes Made

**File**: `dashboard/src/components/modal.js`

Added pause button UI reset in `updateLiveIndicator()` function (lines 371-378):

```javascript
function updateLiveIndicator(isLive) {
  const indicator = document.getElementById('live-indicator');
  const liveControls = document.getElementById('log-live-controls');

  if (indicator) {
    indicator.style.display = isLive ? 'inline-flex' : 'none';
  }

  if (liveControls) {
    liveControls.style.display = isLive ? 'flex' : 'none';
  }

  // Reset pause button UI when showing live controls
  if (isLive) {
    const pauseBtn = document.getElementById('log-pause-btn');
    if (pauseBtn) {
      pauseBtn.textContent = '⏸ Pause';
      pauseBtn.classList.remove('btn--paused');
    }
  }
}
```

## How It Works

Now when `openLogModal()` calls `updateLiveIndicator(true)` for an active scraper:

1. Store state is reset via `actions.resetLiveLogState()` → `liveLogPaused = false`
2. Live indicator and controls are shown
3. **NEW**: Pause button UI is reset to default state ("⏸ Pause", no `btn--paused` class)
4. Button UI and store state are now synchronized

The button state accurately reflects the polling state regardless of what happened in previous modal sessions.

## Testing

To verify the fix:

1. Start a scraper to generate logs
2. Open the log viewer (button shows "⏸ Pause")
3. Click pause button (changes to "▶ Resume")
4. Close the modal
5. Open the log viewer again for the same or different active scraper
6. **Expected**: Button shows "⏸ Pause" and polling is active
7. Click pause → polling stops, button shows "▶ Resume"
8. Click resume → polling starts, button shows "⏸ Pause"

## Files Changed

- `dashboard/src/components/modal.js`
  - Lines 371-378: Added pause button UI reset in `updateLiveIndicator()`

## Related

- Feature: Live log monitoring with auto-refresh
- Branch: `feat/live-log-monitoring`
- Related Fix: `LIVE_LOG_RACE_CONDITION_FIX.md`
