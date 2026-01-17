# Fix: Stale Process Entry Blocking New Starts

## Issue Description

The `start()` method in `ScraperManager` checked `if retailer in self._processes` without verifying whether the process was actually still running. When a scraper process exited (completed or crashed), the entry remained in `_processes` because no cleanup mechanism was invoked during normal dashboard operation.

The dashboard's `/api/status` endpoint uses `status.get_all_retailers_status()` which reads checkpoint files—it doesn't call the manager's `is_running()` or `cleanup_exited()` methods. This caused subsequent start attempts to fail with "Scraper for {retailer} is already running" even when the scraper had finished.

## Root Cause

**Location:** `src/shared/scraper_manager.py:202-204` (before fix)

```python
if retailer in self._processes:
    raise ValueError(f"Scraper for {retailer} is already running")
```

**Problem:** The code only checked dictionary membership, not actual process state.

## Solution

Added automatic stale process detection and cleanup in the `start()` method:

1. **Check if process is actually running** using a new helper method `_is_process_running_unsafe()`
2. **Automatically clean up stale entries** using a new helper method `_cleanup_process_unsafe()`
3. **Proceed with starting** the new scraper after cleanup

### Changes Made

#### 1. Updated `start()` method logic (lines 266-273)

```python
# Check if process is actually still running (not just in tracking dict)
if retailer in self._processes:
    if self._is_process_running_unsafe(retailer):
        raise ValueError(f"Scraper for {retailer} is already running")
    else:
        # Process has exited, clean it up before proceeding
        logger.info(f"Cleaning up stale process entry for {retailer} before starting")
        self._cleanup_process_unsafe(retailer)
```

#### 2. Added `_is_process_running_unsafe()` helper method (lines 110-138)

```python
def _is_process_running_unsafe(self, retailer: str) -> bool:
    """Check if process is running without acquiring lock (internal use only)
    
    Args:
        retailer: Retailer name
    
    Returns:
        True if running, False otherwise
    
    Note:
        This method assumes the caller already holds self._lock
    """
    if retailer not in self._processes:
        return False
    
    process_info = self._processes[retailer]
    process = process_info.get("process")
    pid = process_info["pid"]
    
    if process:
        # Check subprocess.Popen object
        return process.poll() is None
    else:
        # Check PID for recovered processes
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
```

#### 3. Added `_cleanup_process_unsafe()` helper method (lines 140-171)

```python
def _cleanup_process_unsafe(self, retailer: str) -> None:
    """Clean up exited process without acquiring lock (internal use only)
    
    Args:
        retailer: Retailer name
    
    Note:
        This method assumes the caller already holds self._lock
    """
    if retailer not in self._processes:
        return
    
    process_info = self._processes[retailer]
    process = process_info.get("process")
    pid = process_info["pid"]
    run_id = process_info["run_id"]
    
    exit_code = None
    if process:
        exit_code = process.returncode
    
    logger.info(f"Cleaning up exited scraper for {retailer} (PID: {pid}, exit code: {exit_code})")
    
    # Update run tracker
    tracker = RunTracker(retailer, run_id=run_id)
    if exit_code == 0:
        tracker.complete()
    else:
        tracker.fail(f"Process exited with code {exit_code or 'unknown'}")
    
    # Remove from tracking
    del self._processes[retailer]
```

## Testing

Created comprehensive test: `tests/test_stale_process_cleanup.py`

**Test scenario:**
1. Create a dummy process and let it exit
2. Manually inject the stale entry into `_processes` dict
3. Attempt to start a new scraper for the same retailer
4. Verify the stale entry is automatically cleaned up
5. Verify the new scraper starts successfully

**Test results:**
```
✓ Manager detects when process in _processes dict has exited
✓ Manager automatically cleans up stale entry in start()
✓ New scraper can be started without 'already running' error
✓ RunTracker is properly updated when stale entry is cleaned
```

## Benefits

1. **No manual intervention required:** Stale entries are automatically detected and cleaned up
2. **Correct RunTracker state:** Exit status is properly recorded when stale entries are cleaned
3. **Thread-safe:** Uses existing lock mechanism, with lock-free helper methods for internal use
4. **Handles both process types:** Works for both subprocess.Popen objects and recovered PIDs
5. **Better logging:** Clear log messages when stale entries are detected and cleaned

## Impact

- **User Experience:** Users can now restart scrapers immediately after they complete/crash without getting "already running" errors
- **Dashboard Operation:** The dashboard API continues to work without modification
- **No Breaking Changes:** Existing functionality is preserved, only adding automatic cleanup
- **Backward Compatible:** No changes to public API or behavior of other methods

## Files Modified

- `src/shared/scraper_manager.py`: Added stale process detection and cleanup logic
- `tests/test_stale_process_cleanup.py`: Added comprehensive test

## Related Issues

This fix ensures that the process state in `_processes` dict accurately reflects actual process status, preventing false "already running" errors.
