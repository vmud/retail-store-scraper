# Fix: Dashboard render_js Validation Inconsistency

## Issue

The dashboard's `_validate_scraper_options` function incorrectly allowed `render_js=True` when `proxy` was `None` (not specified), while the CLI correctly rejected this combination.

### Root Cause

**Dashboard validation (app.py:351):**
```python
if render_js and proxy is not None and proxy != 'web_scraper_api':
```

The `proxy is not None` condition caused validation to be skipped when proxy was None, allowing invalid configurations to pass through.

**CLI validation (run.py:502):**
```python
if args.render_js and args.proxy != 'web_scraper_api':
```

The CLI correctly rejected the combination without the `proxy is not None` check.

### Impact

Dashboard users could start scrapers with `render_js=True` and no proxy specified, which would fail at runtime since JavaScript rendering requires the `web_scraper_api` proxy mode.

## Solution

Removed the `proxy is not None` condition from the dashboard validation to match the CLI's behavior:

```python
if render_js and proxy != 'web_scraper_api':
    return False, "--render-js requires proxy mode 'web_scraper_api'"
```

Now both the dashboard and CLI consistently reject:
- `render_js=True` with `proxy=None`
- `render_js=True` with `proxy='residential'`
- `render_js=True` with `proxy='direct'`

And both accept:
- `render_js=True` with `proxy='web_scraper_api'`

## Testing

Added two new test cases to `tests/test_api.py`:

1. `test_api_scraper_start_render_js_without_proxy_returns_400` - Verifies that `render_js=True` without proxy returns 400
2. `test_api_scraper_start_render_js_with_wrong_proxy_returns_400` - Verifies that `render_js=True` with `proxy='residential'` returns 400

All existing tests continue to pass.

## Files Changed

- `dashboard/app.py` - Fixed validation condition
- `tests/test_api.py` - Added validation tests
