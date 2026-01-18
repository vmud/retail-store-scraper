# Live Log Race Condition Fix

## Issue

The `setInterval` with an async callback in the live log polling feature didn't wait for the previous request to complete. When a network request took longer than the 2-second polling interval, multiple requests could be in-flight simultaneously, all using the same `lastLineCount` offset value.

### Race Condition Scenario

```
t=0s:  Request A starts with lastLineCount=100
t=2s:  Request B starts with lastLineCount=100 (Request A hasn't completed yet)
t=3s:  Request A completes, appends lines 100-150, sets lastLineCount=150
t=4s:  Request B completes, appends lines 100-150 (duplicate!), sets lastLineCount=150
```

When these overlapping requests completed, each would append all lines from its response based on `data.total_lines > lastLineCount`. Since the offset was captured before previous requests updated `lastLineCount`, the responses contained overlapping line ranges, causing duplicate log lines to appear in the viewer.

## Solution

Added an `isPolling` flag to prevent overlapping requests:

### Changes Made

1. **Added `isPolling` flag** (line 19):
   ```javascript
   let isPolling = false; // Prevent overlapping requests
   ```

2. **Check flag before polling** (lines 224-227):
   ```javascript
   // Skip if previous request is still in-flight
   if (isPolling) {
     return;
   }
   ```

3. **Set flag before request** (line 242):
   ```javascript
   isPolling = true;
   ```

4. **Clear flag in finally block** (lines 278-280):
   ```javascript
   } finally {
     isPolling = false;
   }
   ```

5. **Reset flag on cleanup**:
   - In `stopLivePolling()` (line 292)
   - In `openLogModal()` reset section (line 157)

## How It Works

Now when the interval fires:

```
t=0s:  Request A starts, isPolling=true
t=2s:  Interval fires, but isPolling=true, so skip
t=3s:  Request A completes, isPolling=false
t=4s:  Interval fires, isPolling=false, Request B starts with lastLineCount=150
```

Only one request can be in-flight at a time, preventing duplicate log lines.

## Testing

To verify the fix:

1. Start a scraper that generates logs slowly
2. Open the log viewer to enable live polling
3. Simulate slow network by throttling in DevTools (Network → Throttling → Slow 3G)
4. Observe that log lines appear once, without duplicates
5. Check browser console for timing: requests should be serialized, not overlapping

## Files Changed

- `dashboard/src/components/modal.js`
  - Lines 19: Added `isPolling` flag
  - Lines 157, 224-227, 242, 278-280, 292: Flag usage and reset

## Related

- Feature: Live log monitoring with auto-refresh
- Branch: `feat/live-log-monitoring`
