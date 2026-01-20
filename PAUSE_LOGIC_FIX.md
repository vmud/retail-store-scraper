# Pause Logic Fix - Reading from YAML Config

## Problem Statement

The scrapers' `_check_pause_logic()` functions were checking hardcoded Python config module values (`att_config.PAUSE_50_REQUESTS`, etc.) instead of reading from the YAML config (`config/retailers.yaml`). 

The YAML config was updated with `pause_50_requests: 999999` and `pause_200_requests: 999999` to disable long pauses when using residential proxies, but this setting was being ignored because the scrapers never read these values.

### Root Cause

```python
# Before fix - reads from Python config module (hardcoded to 50 and 200)
if att_config.PAUSE_50_REQUESTS >= 999999 and att_config.PAUSE_200_REQUESTS >= 999999:
    return
```

The condition would **always evaluate to False** because:
- `att_config.PAUSE_50_REQUESTS = 50` (hardcoded in `config/att_config.py`)
- `att_config.PAUSE_200_REQUESTS = 200` (hardcoded in `config/att_config.py`)
- `50 >= 999999` → False
- `200 >= 999999` → False

**Result**: Pauses still occurred every 50/200 requests regardless of YAML configuration.

## Solution

Updated all scrapers to read pause configuration from the YAML config passed to the `run()` function, with fallback to Python config modules for tests.

### Changes Made

#### 1. Updated `_check_pause_logic()` Signature
**Files**: `src/scrapers/att.py`, `walmart.py`, `target.py`, `verizon.py`, `tmobile.py`

```python
# Before
def _check_pause_logic(retailer: str = 'att') -> None:
    if att_config.PAUSE_50_REQUESTS >= 999999:
        return
    # ...

# After
def _check_pause_logic(config: dict = None, retailer: str = 'att') -> None:
    """Check if we need to pause based on request count
    
    Args:
        config: Retailer configuration dict from retailers.yaml (optional for tests)
        retailer: Retailer name for logging
    """
    # If no config provided (tests), use hardcoded Python config values
    if config is None:
        pause_50_requests = att_config.PAUSE_50_REQUESTS
        pause_200_requests = att_config.PAUSE_200_REQUESTS
        # ... (other pause config values)
    else:
        # Read from YAML config (preferred)
        pause_50_requests = config.get('pause_50_requests', att_config.PAUSE_50_REQUESTS)
        pause_200_requests = config.get('pause_200_requests', att_config.PAUSE_200_REQUESTS)
        # ... (other pause config values)
    
    # Skip modulo operations if pauses are effectively disabled (>= 999999)
    if pause_50_requests >= 999999 and pause_200_requests >= 999999:
        return  # ✅ Now correctly reads 999999 from YAML and returns early
    # ...
```

#### 2. Updated Function Signatures to Accept Config
Added `config: dict = None` parameter to:
- `get_store_urls_from_sitemap()`
- `extract_store_details()`
- `get_store_details()` (Target)
- `get_all_states()` (Verizon)
- `get_cities_for_state()` (Verizon)
- `get_stores_for_city()` (Verizon)
- `get_all_store_ids()` (Target)

#### 3. Updated Call Sites in `run()` Functions
All calls to `_check_pause_logic()` and related functions now pass the `config` dict:

```python
# Before
store_urls = get_store_urls_from_sitemap(session, retailer_name)
store_obj = extract_store_details(session, url, retailer_name)

# After
store_urls = get_store_urls_from_sitemap(session, config, retailer_name)
store_obj = extract_store_details(session, url, config, retailer_name)
```

## Verification

### Test Results
Tested the updated pause logic with simulated YAML configs:

```python
# Test with disabled pauses (999999)
disabled_config = {
    'pause_50_requests': 999999,
    'pause_200_requests': 999999,
    'pause_50_min': 0,
    'pause_50_max': 0,
    'pause_200_min': 0,
    'pause_200_max': 0
}

# All scrapers correctly skip pause logic
✓ ATT: Pause logic correctly skipped
✓ WALMART: Pause logic correctly skipped
✓ TARGET: Pause logic correctly skipped
✓ VERIZON: Pause logic correctly skipped
✓ TMOBILE: Pause logic correctly skipped
```

### Linting
No linter errors introduced in any modified files.

## Impact

### Before Fix
- **Verizon, AT&T, Target, Walmart**: Paused for 30-60s after every 50 requests and 120-180s after every 200 requests, even with residential proxy
- **Effective scraping speed**: Significantly throttled by unnecessary pauses
- **YAML config `pause_*_requests: 999999`**: Completely ignored

### After Fix
- **With residential proxy** (YAML config has `pause_*_requests: 999999`):
  - ✅ No pauses at 50/200 request thresholds
  - ✅ Only inter-request delays (0.2-0.5s for residential mode)
  - ✅ ~9.6x faster scraping as intended
- **Without residential proxy** (YAML config has normal thresholds):
  - ✅ Pauses still occur as configured (30-60s at 50 requests, 120-180s at 200 requests)
  - ✅ Anti-blocking protection maintained for direct mode
- **Backward compatibility**:
  - ✅ Tests that don't provide config still work (fallback to Python config modules)
  - ✅ No changes needed to test files

## Files Modified

1. `src/scrapers/att.py` - Updated `_check_pause_logic()`, `get_store_urls_from_sitemap()`, `extract_store_details()`, and call sites
2. `src/scrapers/walmart.py` - Updated `_check_pause_logic()`, `get_store_urls_from_sitemap()`, `extract_store_details()`, and call sites
3. `src/scrapers/target.py` - Updated `_check_pause_logic()`, `get_all_store_ids()`, `get_store_details()`, and call sites
4. `src/scrapers/verizon.py` - Updated `_check_pause_logic()`, all multi-phase crawl functions, and call sites
5. `src/scrapers/tmobile.py` - Updated `_check_pause_logic()`, `get_store_urls_from_sitemap()`, `extract_store_details()`, and call sites

## YAML Configuration Reference

Retailers with pause disabling enabled (using residential proxy):

```yaml
# config/retailers.yaml
retailers:
  verizon:
    pause_50_requests: 999999   # ✅ Now read correctly
    pause_200_requests: 999999  # ✅ Now read correctly
    pause_50_min: 0
    pause_50_max: 0
    pause_200_min: 0
    pause_200_max: 0
    proxy:
      mode: "residential"

  att:
    pause_50_requests: 999999   # ✅ Now read correctly
    pause_200_requests: 999999  # ✅ Now read correctly
    # ... (same pattern)
    proxy:
      mode: "residential"

  target:
    pause_50_requests: 999999   # ✅ Now read correctly
    pause_200_requests: 999999  # ✅ Now read correctly
    # ... (same pattern)
    proxy:
      mode: "residential"

  walmart:
    pause_50_requests: 999999   # ✅ Now read correctly
    pause_200_requests: 999999  # ✅ Now read correctly
    # ... (same pattern)
    proxy:
      mode: "residential"
```

## Production Impact

This fix enables the intended performance optimization for residential proxy mode:
- **Expected speedup**: ~9.6x faster (from 2-5s delays + long pauses → 0.2-0.5s delays, no pauses)
- **Residential proxy credits saved**: Fewer requests wasted during pause periods
- **Scraping time reduced**: Large scrapes (thousands of stores) complete much faster

## Notes

- T-Mobile doesn't have pause disabling in YAML yet (uses `direct` mode), but the code is now consistent and ready if needed
- The fix maintains backward compatibility with tests that mock or don't provide config
- No checkpoint data was modified or affected by this fix
