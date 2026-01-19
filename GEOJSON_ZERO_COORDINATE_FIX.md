# GeoJSON Zero Coordinate Fix

## Issue Summary

The `generate_geojson` function in `src/shared/export_service.py` incorrectly handled coordinate values of `0`, causing silent data loss for stores located at the equator (latitude=0) or prime meridian (longitude=0).

### Root Cause

**Lines 203-204** used the `or` operator for coordinate field fallback:

```python
# BUGGY CODE (before fix)
lat = store.get('latitude') or store.get('lat')
lng = store.get('longitude') or store.get('lng') or store.get('lon')
```

**Problem**: In Python, `0` is falsy, so the expression evaluates like this:
- `store.get('latitude')` returns `0` → falsy → evaluates to `store.get('lat')`
- If `store.get('lat')` returns `None`, then `lat = None`
- Store is skipped as having "missing coordinates"

### Real-World Impact

This bug would silently drop stores in countries/regions along:

1. **Equator (latitude = 0)**:
   - Ecuador (Quito region)
   - Gabon
   - Republic of the Congo
   - Democratic Republic of Congo
   - Uganda
   - Kenya
   - Somalia
   - Indonesia (Sumatra, Borneo)
   - Brazil (Macapá region)

2. **Prime Meridian (longitude = 0)**:
   - United Kingdom (Greenwich)
   - France (western regions)
   - Spain (eastern regions)
   - Algeria
   - Mali
   - Burkina Faso
   - Ghana
   - Togo

3. **Null Island (latitude = 0, longitude = 0)**:
   - Point in the Atlantic Ocean
   - Used as placeholder in some databases

### Example Data Loss

```python
# Store at the equator
store = {
    'name': 'Quito Store',
    'latitude': 0,      # ← Treated as falsy!
    'longitude': -78.5
}
# Result: SKIPPED (silent data loss)

# Store in Ghana (prime meridian)
store = {
    'name': 'Accra Store',
    'latitude': 5.6,
    'longitude': 0      # ← Treated as falsy!
}
# Result: SKIPPED (silent data loss)
```

## Solution

Changed the coordinate field selection logic to use explicit `None` checks:

```python
# FIXED CODE
lat = store.get('latitude') if store.get('latitude') is not None else store.get('lat')
lng = store.get('longitude') if store.get('longitude') is not None else (
    store.get('lng') if store.get('lng') is not None else store.get('lon')
)
```

**Why this works**:
- Only `None` is treated as missing
- `0` is a valid coordinate value
- Primary field names (`latitude`, `longitude`) take precedence even when `0`
- Fallback to alternative names (`lat`, `lng`, `lon`) only when primary is truly missing

## Testing

### Test Cases Added

Added comprehensive tests in `tests/test_export_service.py`:

1. **test_geojson_handles_zero_coordinates**:
   - Store at equator (lat=0)
   - Store at prime meridian (lng=0)
   - Null Island (lat=0, lng=0)
   - Normal store for comparison

2. **test_geojson_fallback_coordinate_field_names**:
   - Alternative field names with zero values
   - Primary field precedence verification

### Verification Results

```bash
✓ Test 1: Equator (lat=0) handled correctly
✓ Test 2: Prime meridian (lng=0) handled correctly
✓ Test 3: Null Island (lat=0, lng=0) handled correctly
✓ Test 4: Alternative field names with zero handled correctly
✓ Test 5: Primary fields take precedence over alternatives
```

### Bug Demonstration

The old logic would fail:

```python
# Old logic simulation
store = {'latitude': 0, 'longitude': 100.0}
lat = store.get('latitude') or store.get('lat')
lng = store.get('longitude') or store.get('lng')
# Result: lat=None, lng=100.0 ❌ BUG

store = {'latitude': 50.0, 'longitude': 0}
lat = store.get('latitude') or store.get('lat')
lng = store.get('longitude') or store.get('lng')
# Result: lat=50.0, lng=None ❌ BUG

store = {'latitude': 0, 'longitude': 0}
lat = store.get('latitude') or store.get('lat')
lng = store.get('longitude') or store.get('lng')
# Result: lat=None, lng=None ❌ BUG (both coordinates lost!)
```

## Impact

- **Data Integrity**: No more silent data loss for stores at special coordinates
- **Geographic Coverage**: Proper handling of stores in equatorial and prime meridian regions
- **Backwards Compatibility**: No changes to existing behavior for non-zero coordinates
- **Code Quality**: Explicit intent makes the code more maintainable

## Files Modified

1. **src/shared/export_service.py** (lines 201-207):
   - Changed `or` to explicit `is not None` checks
   - Added comment explaining the fix

2. **tests/test_export_service.py**:
   - Added `test_geojson_handles_zero_coordinates`
   - Added `test_geojson_fallback_coordinate_field_names`

## Related Issues

None - proactive fix identified during code review of export service functionality.

## Prevention

To prevent similar issues in the future:

1. **Code Review Checklist**: Always consider numeric zero as a valid value
2. **Testing Standards**: Include boundary value tests (0, negative, extreme values)
3. **Linting Rule**: Consider adding a linter rule to flag `or` usage with dict.get()
4. **Documentation**: Document that `0` is a valid coordinate value in docstrings

## References

- **Null Island**: https://en.wikipedia.org/wiki/Null_Island
- **Equator**: Latitude 0°
- **Prime Meridian**: Longitude 0° (Greenwich)
- **Python Truthiness**: `0`, `None`, `False`, `""`, `[]`, `{}` are all falsy
