# Restart Button Re-render Bug Fix

## Issue Verified ✅

The issue was **confirmed and fixed** in `dashboard/src/components/retailer-card.js`.

### The Problem

The `shouldShowRestart` calculation in `updateCard()` didn't account for disabled status, causing unnecessary DOM re-renders on every polling update for disabled retailers with 100% progress.

**Root Cause:**
```javascript
// Line 297 (OLD)
const shouldShowRestart = !isRunning && progress >= 100;
```

This condition evaluates to `true` for disabled retailers with 100% progress, but `renderActions()` returns early for disabled retailers without a restart button (lines 183-189). This creates a persistent mismatch:

- `hasRestartBtn` = `false` (disabled template has no restart button)
- `shouldShowRestart` = `true` (condition ignores disabled status)
- Condition `(!hasRestartBtn && shouldShowRestart)` = **always true**
- Result: `actionsEl.innerHTML` re-rendered on **every polling update** (every 5 seconds)

### The Impact

**Performance:**
- Unnecessary DOM operations every 5 seconds for each disabled retailer with 100% progress
- Browser reflows/repaints triggered unnecessarily
- Event listeners potentially detached and reattached

**Symptoms:**
- No visible UI issues (output is identical each time)
- Wasted CPU cycles and memory allocations
- Potential for subtle bugs if event handlers rely on element identity

### The Fix

Added `isDisabled` check to the `shouldShowRestart` condition:

```javascript
// Lines 296-299 (NEW)
const isDisabled = status === 'disabled';
const hasRestartBtn = actionsEl.querySelector('[data-action="restart"]');
// Only show restart button if not disabled, not running, and progress is 100%
const shouldShowRestart = !isDisabled && !isRunning && progress >= 100;
```

**Now the logic is:**
- Disabled retailer with 100% progress:
  - `shouldShowRestart` = `false` ✅
  - `hasRestartBtn` = `false` ✅
  - Condition `(!hasRestartBtn && shouldShowRestart)` = `false` ✅
  - **No re-render** ✅

- Enabled retailer with 100% progress and not running:
  - `shouldShowRestart` = `true` ✅
  - `hasRestartBtn` = initially `false`, then `true` after render ✅
  - **Re-render once when state changes** ✅

## Code Flow Analysis

### Before Fix (Buggy Behavior)

```
Disabled Retailer (100% progress)
│
├─ Initial render: renderActions() returns disabled template
│  └─ No restart button in DOM
│
└─ Every polling update (5 seconds):
   ├─ shouldShowRestart = true (!false && 100 >= 100) ❌
   ├─ hasRestartBtn = false (no button in disabled template)
   ├─ Condition: (!false && true) = true
   ├─ Re-render: actionsEl.innerHTML = renderActions(...)
   │  └─ Returns same disabled template (no restart button)
   └─ Repeat indefinitely... ❌
```

### After Fix (Correct Behavior)

```
Disabled Retailer (100% progress)
│
├─ Initial render: renderActions() returns disabled template
│  └─ No restart button in DOM
│
└─ Every polling update (5 seconds):
   ├─ isDisabled = true ✅
   ├─ shouldShowRestart = false (!true && !false && 100 >= 100) ✅
   ├─ hasRestartBtn = false
   ├─ Condition: (!false && false) = false ✅
   ├─ No re-render, just update button states
   └─ No unnecessary DOM operations ✅
```

## Testing

### Test Scenario 1: Disabled Retailer with 100% Progress
**Before Fix:**
- Every 5 seconds: Re-render actions with identical output
- Console shows repeated DOM mutations

**After Fix:**
- Initial render only
- No subsequent re-renders
- Console shows no action button mutations

### Test Scenario 2: Enabled Retailer Transitioning to Complete
**Before Fix:**
- Works correctly (not affected by bug)

**After Fix:**
- Still works correctly
- Re-renders once when progress reaches 100%
- Restart button appears

### Test Scenario 3: Status Changes to/from Disabled
**Before Fix:**
- Re-renders correctly on status change
- But continues unnecessary re-renders afterward

**After Fix:**
- Re-renders correctly on status change
- No unnecessary subsequent re-renders

## Files Changed

```
✅ Modified: dashboard/src/components/retailer-card.js
   - Line 296: Added `const isDisabled = status === 'disabled';`
   - Line 299: Updated condition to include `!isDisabled`
   - Added clarifying comment about button visibility logic
```

## Benefits

✅ **Performance**: Eliminates unnecessary DOM operations for disabled retailers
✅ **Correctness**: Condition now matches actual button rendering logic
✅ **Maintainability**: Clear comment explains the three-part condition
✅ **Consistency**: `shouldShowRestart` logic now matches `renderActions()` logic

## Prevention

To prevent similar issues in the future:

1. **Keep conditions in sync**: When a render function has early returns, ensure update logic accounts for all branches
2. **Add clarifying comments**: Explain multi-part boolean conditions
3. **Test edge cases**: Verify disabled/error states don't cause unnecessary updates
4. **Monitor performance**: Watch for repeated DOM operations in DevTools

## Related Code

The fix aligns with the logic in `renderActions()` (lines 179-218):

```javascript
function renderActions(retailerId, status, progress) {
  const isRunning = status === 'running';
  const isDisabled = status === 'disabled';

  // Early return for disabled - no restart button
  if (isDisabled) {
    return `<button class="btn btn--flex" disabled>DISABLED</button>`;
  }

  // Normal template includes restart button when: !isRunning && progress >= 100
  return `... ${!isRunning && progress >= 100 ? '... RESTART ...' : ''} ...`;
}
```

The update logic now properly mirrors this three-state check:
1. Not disabled (`!isDisabled`)
2. Not running (`!isRunning`)
3. 100% progress (`progress >= 100`)

---

**Status**: ✅ Verified and Fixed
**Branch**: fix/front-end-bugs
**Impact**: Performance improvement (reduced DOM operations)
**Risk**: Low (aligns logic, doesn't change behavior)
