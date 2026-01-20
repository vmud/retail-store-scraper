# Collision Disambiguation Stability Fix

## Problem

The change detection system had a critical bug where store keys would change across runs when collision status changed, causing false positives in change detection.

### Bug Scenario

**Run 1:** Only 1 store at "123 Main St"
- Key: `addr:123-main-st` (no fingerprint suffix)

**Run 2:** 2 stores at "123 Main St" (new store opened)
- Both stores get fingerprint suffixes
- Original store key changes to: `addr:123-main-st::abc123de`
- New store gets: `addr:123-main-st::xyz789ab`

**Result:** False positives!
- `addr:123-main-st` missing in run 2 → marked as CLOSED
- `addr:123-main-st::abc123de` new in run 2 → marked as NEW
- `addr:123-main-st::xyz789ab` new in run 2 → marked as NEW

Expected: 0 closed, 1 new store
Actual: 1 closed, 2 new stores ❌

## Solution

Always include fingerprint suffixes in address-based keys, regardless of collision status. This ensures keys are deterministic and stable across runs.

### Implementation

1. **Modified `_get_store_key()`**: Address-based keys always include fingerprint suffix
   - Before: `addr:123-main-st` (no suffix when unique)
   - After: `addr:123-main-st::abc123de` (always includes suffix)

2. **Simplified `_build_store_index()`**: No longer needs complex collision detection
   - Collision count now only tracks TRUE collisions (identical keys including fingerprints)
   - Much simpler logic, easier to maintain

3. **Key stability**: Stores with store_id or URL still use simple keys (no fingerprints needed)
   - `id:1001` - no fingerprint (already unique)
   - `url:https://example.com/store` - no fingerprint (already unique)
   - `addr:123-main-st::abc123de` - includes fingerprint (address-based)

## Impact

### ✅ Benefits
- **No false positives**: Store keys remain stable across runs
- **Order independence**: Same store always gets same key regardless of input order
- **Cross-run stability**: Adding/removing stores at same address doesn't affect existing keys
- **Simpler code**: Removed complex conditional logic

### ⚠️ Trade-offs
- Slightly longer keys for address-based stores
- All address-based stores now have fingerprint suffixes (even when unique)

## Testing

Added comprehensive test coverage:
1. `test_all_address_based_stores_get_suffixes` - Verifies all address-based keys include fingerprints
2. `test_keys_stable_across_input_order` - Confirms deterministic key generation
3. `test_stores_with_ids_dont_need_suffixes` - Verifies ID-based keys remain simple
4. `test_stable_keys_when_new_store_added_at_same_address` - **Tests the main bug fix**

All 227 tests pass ✅

## Related Issues

- Fixes: **Collision disambiguation produces unstable keys across runs** (Medium Severity)
- PR #123 comment from code review
- Issue #57: Key collision handling with disambiguation indices
- Review feedback #9: Stable collision disambiguation
