# Data Quality Reviewer Agent

Reviews scraped store data for quality, completeness, and consistency before GCS sync or production use.

## Purpose

Catch data quality issues early, before bad data propagates to downstream systems or gets synced to cloud storage.

## Quality Checks

### 1. Required Fields

Every store must have:
- [ ] `store_id` - Non-empty, unique within retailer
- [ ] `name` - Non-empty string
- [ ] `street_address` - Non-empty, not "N/A" or placeholder
- [ ] `city` - Non-empty string
- [ ] `state` - Valid 2-letter state/province code

### 2. Coordinate Validation

- [ ] `latitude` present and valid (-90 to 90)
- [ ] `longitude` present and valid (-180 to 180)
- [ ] Coordinates not (0, 0) unless genuinely at null island
- [ ] Coordinates within expected geographic bounds for retailer:
  - US retailers: lat 24-50, lon -125 to -66
  - Canadian retailers (Telus): lat 42-83, lon -141 to -52
- [ ] Coordinates stored as strings (project convention)

### 3. Phone Number Validation

- [ ] Phone present (recommended)
- [ ] Format consistent within retailer
- [ ] Valid US/CA phone format: 10 digits, area code valid
- [ ] No placeholder values ("000-000-0000", "TBD")

### 4. URL Validation

- [ ] Store URL present (recommended)
- [ ] URL format valid (starts with http/https)
- [ ] Domain matches retailer's expected domain
- [ ] No URL encoding issues

### 5. Duplicate Detection

- [ ] No duplicate `store_id` within retailer
- [ ] Check for potential duplicates by address similarity
- [ ] Flag stores at same coordinates (possible duplicates)

### 6. Timestamp Validation

- [ ] `scraped_at` present on all stores
- [ ] Timestamp in ISO format
- [ ] Timestamp within reasonable range (not in future, not too old)

### 7. Store Type Consistency

- [ ] `store_type` values are from expected set (corporate, authorized, dealer, etc.)
- [ ] No unexpected/unknown store types

## Usage

Run after scraping completes:

```python
from src.shared.utils import validate_stores_batch
import json

# Load scraped data
with open('data/{retailer}/output/stores_latest.json') as f:
    stores = json.load(f)

# Run validation
summary = validate_stores_batch(stores)
print(f"Valid: {summary['valid_count']}/{summary['total_count']}")
print(f"Issues: {summary['issues']}")
```

Or from command line:

```bash
python -c "
import json
from src.shared.utils import validate_stores_batch

with open('data/verizon/output/stores_latest.json') as f:
    stores = json.load(f)

summary = validate_stores_batch(stores)
for issue_type, count in summary.get('issues', {}).items():
    if count > 0:
        print(f'{issue_type}: {count}')
"
```

## Quality Report Format

```
Data Quality Report: {retailer}
==============================
Total Stores: {count}
Valid Stores: {valid_count} ({percentage}%)

Field Completeness:
  store_id:       100%
  name:           100%
  street_address: 100%
  city:           100%
  state:          100%
  latitude:       {pct}%
  longitude:      {pct}%
  phone:          {pct}%
  url:            {pct}%

Issues Found:
  Missing coordinates: {count}
  Invalid coordinates: {count}
  Duplicate store_ids: {count}
  Invalid phone format: {count}
  Missing timestamps: {count}

Coordinate Distribution:
  Within US bounds: {count}
  Outside US bounds: {count}
  At (0,0): {count}

Recommendations:
- {recommendation based on issues found}
```

## Trigger Points

Run this reviewer:
1. After any scraper `run()` completes
2. Before GCS sync (`--cloud` flag)
3. Before generating change detection reports
4. As part of CI/CD pipeline for data validation

## Common Data Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Zero coordinates | Falsy check on 0.0 | Use `is not None` check |
| Missing phone | Not extracted from page | Update field extraction |
| Duplicate IDs | Same store in multiple sitemaps | Deduplicate by store_id |
| Invalid state | Full state name instead of code | Add state code mapping |
| Old timestamps | Using cached data | Clear cache, re-scrape |
