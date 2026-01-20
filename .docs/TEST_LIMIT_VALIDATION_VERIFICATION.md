# Test + Limit Validation Verification

## Issue Summary

The dashboard's `_validate_scraper_options` function was missing the `test + limit` conflict check that existed in the CLI's `validate_cli_options`. When a user submitted `{test: true, limit: 50}` via the dashboard API, validation would pass, but the `_build_command` logic in `scraper_manager.py` would silently discard the limit value (using `if test: ... elif limit:` logic).

**Result**: User expected 50 stores but got 10 (test mode default) with no error or warning.

## Fix Implementation

### Dashboard Validation (`dashboard/app.py:354-358`)

```python
# Validate test + limit conflict (matches CLI validation)
test = data.get('test', False)
if test and limit is not None:
    return False, "Cannot use 'test' with 'limit' (test mode already sets limit to 10)"
```

### CLI Validation (`run.py:498-500`)

```python
# Check for conflicting options
if args.test and args.limit:
    errors.append("Cannot use --test with --limit (--test already sets limit to 10)")
```

## Verification Results

### ✅ Unit Tests Pass

```bash
$ pytest tests/test_api.py::TestAPIEndpoints::test_api_scraper_start_test_and_limit_conflict_returns_400 -v

tests/test_api.py::TestAPIEndpoints::test_api_scraper_start_test_and_limit_conflict_returns_400 PASSED [100%]
```

### ✅ CLI Validation Works

```python
args = Namespace(test=True, limit=50, ...)
errors = validate_cli_options(args)
# Result: ['Cannot use --test with --limit (--test already sets limit to 10)']
```

### ✅ Dashboard Validation Works

```python
data = {'retailer': 'verizon', 'test': True, 'limit': 50}
is_valid, result = _validate_scraper_options(data)
# Result: is_valid=False, result="Cannot use 'test' with 'limit' (test mode already sets limit to 10)"
```

### ✅ Individual Options Work Correctly

| Option | Valid | Result |
|--------|-------|--------|
| `test: True` only | ✅ Yes | Passes validation |
| `limit: 50` only | ✅ Yes | Passes validation |
| `test: True, limit: 50` | ❌ No | Returns 400 error |

## Test Coverage

### API Test (`tests/test_api.py:63-72`)

```python
def test_api_scraper_start_test_and_limit_conflict_returns_400(self, client):
    """Test that start with both test and limit returns 400"""
    response = client.post('/api/scraper/start',
                          json={'retailer': 'verizon', 'test': True, 'limit': 50},
                          content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
    assert 'test' in data['error'].lower()
    assert 'limit' in data['error'].lower()
```

## Error Message Consistency

Both CLI and Dashboard now return consistent, user-friendly error messages:

- **CLI**: `Cannot use --test with --limit (--test already sets limit to 10)`
- **Dashboard**: `Cannot use 'test' with 'limit' (test mode already sets limit to 10)`

The messages are consistent in:
- Explaining why the options conflict
- Providing actionable information (test mode already sets limit to 10)
- Using clear, non-technical language

## Impact

This fix prevents silent data loss scenarios where:

1. ✅ User explicitly requests `limit: 50` expecting 50 stores
2. ✅ User also sets `test: true` thinking it's a separate "test run" flag
3. ❌ Previously: System would silently use `test` and ignore `limit`, returning only 10 stores
4. ✅ Now: System returns 400 error with clear explanation before running

## Status

**✅ VERIFIED AND FIXED**

- Dashboard validation matches CLI validation
- Unit tests pass
- Manual verification confirms correct behavior
- Error messages are clear and actionable
