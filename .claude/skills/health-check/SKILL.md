---
name: health-check
description: Check health and freshness of all scraper outputs
---

# Scraper Health Check

Reads `data/*/output/stores_latest.json` for all retailers and reports operational health. Lightweight precursor to the Phase 3 run ledger and status dashboard.

## Usage

| Command | Description |
|---------|-------------|
| `/health-check` | Check all retailers |
| `/health-check verizon` | Check specific retailer |
| `/health-check --stale 3` | Flag anything older than 3 days |

## What Gets Checked

For each retailer with output data:

1. **Freshness**: When was `stores_latest.json` last modified?
2. **Store count**: How many stores in the current output?
3. **Previous comparison**: If `stores_previous.json` exists, what changed?
4. **Checkpoint state**: Any incomplete checkpoints in `checkpoints/`?
5. **Data quality**: Quick field completeness check (required + recommended fields)

## Health Status Rules

| Status | Condition |
|--------|-----------|
| OK | Last modified within threshold (default: 7 days) |
| STALE | Last modified older than threshold |
| DEGRADED | Store count dropped >10% from previous |
| EMPTY | `stores_latest.json` missing or has 0 stores |
| NEW | Retailer registered but never run |

## Implementation Steps

1. Get list of registered retailers from `src/scrapers/__init__.py` via `get_available_retailers()`
2. For each retailer, check `data/{retailer}/output/stores_latest.json`:
   - File exists? → read and count stores, check modification time
   - File missing? → mark as NEW or EMPTY
3. If `stores_previous.json` exists, compare counts for delta
4. Check `data/{retailer}/checkpoints/` for incomplete state
5. For sampled stores (first 10), check field completeness
6. Output summary table

## Expected Output

```
Retailer       Stores  Last Modified    Delta   Health
────────────────────────────────────────────────────────
verizon         1,847  2h ago           +1/-0   OK
att             5,312  2h ago           +3/-2   OK
target          1,893  3d ago           0       OK
walmart         4,706  8d ago           0       STALE
gamestop            —  never            —       NEW
bestbuy         1,042  1d ago          -142     DEGRADED
────────────────────────────────────────────────────────
Total: 15 retailers | 12 OK | 2 STALE | 1 NEW

Field Completeness (sampled):
  store_id: 100% | name: 100% | address: 100%
  lat/lon: 97% | phone: 84% | url: 91%
```

## Implementation

```python
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from src.scrapers import get_available_retailers

stale_threshold_days = 7  # or from args

for retailer in get_available_retailers():
    data_path = Path(f"data/{retailer}/output/stores_latest.json")
    prev_path = Path(f"data/{retailer}/output/stores_previous.json")
    ckpt_path = Path(f"data/{retailer}/checkpoints")

    if not data_path.exists():
        # NEW - never run
        continue

    # Freshness
    mtime = datetime.fromtimestamp(data_path.stat().st_mtime, tz=timezone.utc)
    age_days = (datetime.now(timezone.utc) - mtime).total_seconds() / 86400

    # Store count
    with open(data_path) as f:
        stores = json.load(f)
    count = len(stores)

    # Delta from previous
    delta = None
    if prev_path.exists():
        with open(prev_path) as f:
            prev_stores = json.load(f)
        delta = count - len(prev_stores)

    # Health determination
    if age_days > stale_threshold_days:
        health = "STALE"
    elif delta is not None and delta < 0 and abs(delta) > count * 0.1:
        health = "DEGRADED"
    elif count == 0:
        health = "EMPTY"
    else:
        health = "OK"
```

## Error Handling

- If `data/` directory doesn't exist, report "No scraper data found — run scrapers first"
- If JSON is malformed, report parse error for that retailer
- If retailer not in registry, skip (may be from old/removed scraper)
