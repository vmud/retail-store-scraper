# CLI Validation Fix: `--render-js` Flag

## Problem

The CLI validation for `--render-js` had an inconsistency with the dashboard API validation that allowed invalid usage to slip through:

### Issue 1: Incorrect Validation Logic

**Before (line 502 in run.py):**
```python
if args.render_js and args.proxy is not None and args.proxy != 'web_scraper_api':
    errors.append("--render-js requires --proxy web_scraper_api")
```

This validation included an extra `args.proxy is not None` check, which meant:
- ✅ `--render-js --proxy residential` → Correctly rejected
- ❌ `--render-js` (no proxy) → Incorrectly allowed to pass validation
- ✅ `--render-js --proxy web_scraper_api` → Correctly allowed

**Dashboard API validation (line 352 in app.py):**
```python
if render_js and proxy != 'web_scraper_api':
    return False, "--render-js requires proxy mode 'web_scraper_api'"
```

The dashboard correctly catches both missing proxy and wrong proxy.

### Issue 2: Silent Discarding of `render_js` Flag

Even if the validation passed incorrectly, the `render_js` setting was silently discarded at lines 625-631:

```python
cli_proxy_override = args.proxy if args.proxy else None
cli_proxy_settings = None
if cli_proxy_override:  # ← Only sets cli_proxy_settings when proxy is specified
    cli_proxy_settings = {
        'country_code': args.proxy_country,
        'render_js': args.render_js,
    }
```

When `args.proxy` is `None`, `cli_proxy_settings` never gets set, so the `render_js` flag is lost.

## Solution

Fixed the CLI validation to match the dashboard API validation by removing the extra `args.proxy is not None` check:

**After (line 502 in run.py):**
```python
if args.render_js and args.proxy != 'web_scraper_api':
    errors.append("--render-js requires --proxy web_scraper_api")
```

Now the validation correctly rejects:
- ❌ `--render-js` (no proxy specified) → Rejected
- ❌ `--render-js --proxy residential` → Rejected
- ❌ `--render-js --proxy direct` → Rejected
- ✅ `--render-js --proxy web_scraper_api` → Allowed

## Testing

Added comprehensive test coverage in `tests/test_cli_validation.py`:

1. ✅ `test_render_js_without_proxy_fails` - Validates that `--render-js` without `--proxy` is rejected
2. ✅ `test_render_js_with_wrong_proxy_fails` - Validates that `--render-js` with non-web_scraper_api proxy is rejected
3. ✅ `test_render_js_with_correct_proxy_passes` - Validates that `--render-js` with web_scraper_api proxy is allowed
4. ✅ `test_render_js_false_without_proxy_passes` - Validates that not using `--render-js` works fine

All 253 tests pass, including 7 new CLI validation tests.

## Impact

### ✅ Benefits
- **Consistent validation**: CLI now matches dashboard API validation logic
- **Early error detection**: Users get immediate feedback when using `--render-js` incorrectly
- **No silent failures**: Invalid configurations are caught before execution
- **Better user experience**: Clear error message explains the requirement

### Example User Experience

**Before fix:**
```bash
$ python run.py --retailer verizon --render-js
# Validation passes, but render_js is silently ignored
# Scraper runs without JavaScript rendering
```

**After fix:**
```bash
$ python run.py --retailer verizon --render-js
Validation errors:
  - --render-js requires --proxy web_scraper_api
# User gets immediate, clear feedback
```

## Related Code

- CLI validation: `run.py:validate_cli_options()` (line 487)
- Dashboard validation: `dashboard/app.py:validate_scraper_start_options()` (line 288)
- Proxy settings construction: `run.py:main()` (lines 624-631)

## Notes

The fix only addresses the validation logic. The proxy settings construction (lines 624-631) remains unchanged because with proper validation, `render_js` should never be True unless `proxy` is also set to `web_scraper_api`.
