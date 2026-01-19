# Empty Retailers Export Fix

## Issue Summary

When exporting multiple retailers to Excel format where all requested retailers have empty store arrays (`[]`), the system would crash with a 500 error.

### Root Cause

The `generate_multi_sheet_excel` function in `src/shared/export_service.py` had the following issue:

1. **Line 330**: Removed the default worksheet
2. **Lines 332-334**: Skipped retailers with empty store lists (`if not stores: continue`)
3. **Line 374**: Attempted to save the workbook

If all retailers had empty stores, no sheets were created. Calling `wb.save()` on an openpyxl Workbook with zero worksheets raises:
```
IndexError: At least one sheet must be visible
```

Additionally, the API validation in `dashboard/app.py` at line 769 only checked if `retailer_data` was an empty dict, not whether all values were empty lists.

## Solution

### 1. Export Service Fix (`src/shared/export_service.py`)

Added a check after the retailer loop to create a placeholder sheet if no data sheets were created:

```python
# If no sheets were created (all retailers had empty data), create a placeholder sheet
if sheets_created == 0:
    ws = wb.create_sheet(title="No Data")
    ws['A1'] = "No store data available for any retailer"
    ws['A1'].font = Font(bold=True)
```

This ensures the workbook always has at least one sheet, preventing the IndexError.

### 2. API Validation Fix (`dashboard/app.py`)

Added validation to check if all retailers have empty store lists before attempting to generate the export:

```python
# Check if all retailers have empty store lists
all_empty = all(not stores for stores in retailer_data.values())
if all_empty:
    return jsonify({"error": "All retailers have empty data"}), 404
```

This provides a clearer error message to the user before attempting to create the file.

## Testing

### Test Case 1: All Empty Retailers (Export Service)

Added test in `tests/test_export_service.py`:

```python
def test_generate_multi_sheet_excel_all_empty_retailers(self):
    """Test that multi-sheet Excel with all empty retailers doesn't crash"""
    retailer_data = {
        'retailer1': [],
        'retailer2': [],
        'retailer3': []
    }

    # Should not raise IndexError
    result = ExportService.generate_multi_sheet_excel(retailer_data)
    assert isinstance(result, bytes)
```

**Result**: ✅ Creates Excel file with placeholder sheet

### Test Case 2: All Empty Retailers (API)

Added test in `tests/test_api.py`:

```python
def test_api_export_multi_all_empty_stores_returns_404(self, client, tmp_path, monkeypatch):
    """Test that multi export with all retailers having empty stores returns 404"""
    # Creates temp data directory with empty store files
    # ...
    
    response = client.post('/api/export/multi',
                          json={'retailers': ['verizon', 'att'], 'format': 'excel'},
                          content_type='application/json')
    assert response.status_code == 404
    data = response.get_json()
    assert 'error' in data
    assert 'empty' in data['error'].lower()
```

**Result**: ✅ Returns 404 with clear error message

### Test Case 3: Mixed Empty/Non-Empty Retailers

Verified existing test still works:

```python
def test_generate_multi_sheet_excel_empty_retailer_skipped(self):
    """Test that empty retailers are skipped in multi-sheet Excel"""
    retailer_data = {
        'retailer1': SAMPLE_STORES,
        'empty_retailer': []
    }

    result = ExportService.generate_multi_sheet_excel(retailer_data)
    assert isinstance(result, bytes)
```

**Result**: ✅ Creates Excel with only non-empty retailers

## Verification

All tests pass:

```bash
# Export service tests
pytest tests/test_export_service.py -v
# Result: 29 passed

# API tests
pytest tests/test_api.py -v
# Result: 30 passed
```

Manual verification shows the placeholder sheet contains:
- Sheet name: "No Data"
- Cell A1: "No store data available for any retailer" (bold)

## Impact

- **User Experience**: Instead of a 500 error, users get a clear 404 response with a descriptive error message
- **Excel Export**: When generating Excel files directly (not via API), a placeholder sheet is created with a helpful message
- **Backwards Compatibility**: No changes to existing behavior when retailers have data
- **Code Quality**: Added comprehensive test coverage for edge cases

## Files Modified

1. `src/shared/export_service.py` - Added placeholder sheet creation
2. `dashboard/app.py` - Added validation for all-empty retailers
3. `tests/test_export_service.py` - Added test case
4. `tests/test_api.py` - Added test case

## Related Issues

None - proactive fix identified during code review.
