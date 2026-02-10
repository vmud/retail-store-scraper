---
name: migration-validator
description: Validates that scraper output is identical before and after migration from function-based to class-based pattern. Runs test mode, captures output, and diffs store data to catch regressions.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# Migration Validator Agent

Ensures scraper migrations (function-based `run()` to `BaseScraper` subclass) produce identical output.

## When to Use

- Before merging a PR that migrates a scraper to a base class
- After refactoring a scraper's discovery or extraction logic
- When changing shared utilities that multiple scrapers depend on

## Validation Process

### 1. Capture Baseline (pre-migration)

```bash
# Checkout main branch version
git stash  # or use worktree
git checkout main -- src/scrapers/{retailer}.py

# Run in test mode and save output
python run.py --retailer {retailer} --test --limit 5 --format json
cp data/{retailer}/output/stores_latest.json /tmp/migration_baseline_{retailer}.json

# Restore migration version
git checkout - -- src/scrapers/{retailer}.py  # or git stash pop
```

### 2. Capture Migration Output

```bash
# Run migrated version
python run.py --retailer {retailer} --test --limit 5 --format json
cp data/{retailer}/output/stores_latest.json /tmp/migration_result_{retailer}.json
```

### 3. Compare Outputs

Compare the two JSON files, ignoring timestamp fields that naturally differ:

```python
import json

def normalize_store(store):
    """Remove volatile fields for comparison."""
    volatile = {'scraped_at', 'scrape_timestamp', 'last_updated'}
    return {k: v for k, v in sorted(store.items()) if k not in volatile}

with open('/tmp/migration_baseline_{retailer}.json') as f:
    baseline = json.load(f)
with open('/tmp/migration_result_{retailer}.json') as f:
    result = json.load(f)

baseline_normalized = [normalize_store(s) for s in baseline]
result_normalized = [normalize_store(s) for s in result]

# Sort by store_id for stable comparison
baseline_sorted = sorted(baseline_normalized, key=lambda s: s.get('store_id', ''))
result_sorted = sorted(result_normalized, key=lambda s: s.get('store_id', ''))

if baseline_sorted == result_sorted:
    print("PASS: Output identical")
else:
    print("FAIL: Output differs")
    # Show specific differences
```

### 4. Report

Generate a validation report:

```
Migration Validation: {retailer}
================================
Baseline stores: {N}
Migration stores: {N}
Store count match: YES/NO

Field-by-field comparison:
  store_id:       MATCH
  name:           MATCH
  street_address: MATCH (3 whitespace diffs normalized)
  latitude:       MISMATCH (2 stores differ)
    - Store VZW-123: "40.7128" vs "40.71280"
    - Store VZW-456: "" vs None

Verdict: PASS / FAIL (with details)
```

## Acceptable Differences

These are NOT failures:
- Whitespace normalization (leading/trailing spaces)
- Coordinate precision differences ("40.7128" vs "40.71280")
- `scraped_at` timestamp differences
- Field ordering within store dicts

These ARE failures:
- Missing stores (different count)
- Missing fields (field present in baseline but absent in migration)
- Different store_id values
- Different addresses, phone numbers, or coordinates (beyond precision)
- New unexpected fields not in baseline

## Usage from PR Review

When reviewing a migration PR:

1. Check out the PR branch
2. Run this agent with the retailer name
3. Agent captures baseline from main, runs migration, and diffs
4. Report posted as PR comment if validation passes/fails
