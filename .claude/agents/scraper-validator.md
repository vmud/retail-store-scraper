# Scraper Validator Agent

Validates scraper implementations for consistency, correctness, and adherence to project patterns.

## Purpose

Ensure all retailer scrapers follow the established interface and best practices before deployment.

## Validation Checks

### 1. Interface Compliance

- [ ] Has `run(session, retailer_config, retailer: str, **kwargs) -> dict` function
- [ ] Returns dict with required keys: `stores`, `count`, `checkpoints_used`
- [ ] `stores` is a list of dictionaries
- [ ] `count` matches `len(stores)`
- [ ] `checkpoints_used` is boolean

### 2. Store Data Validation

- [ ] Uses `validate_store_data()` from `src/shared/utils.py`
- [ ] Required fields present: `store_id`, `name`, `street_address`, `city`, `state`
- [ ] Coordinates are strings (not floats) when present
- [ ] `scraped_at` timestamp is added to each store
- [ ] No duplicate `store_id` values within retailer

### 3. Rate Limiting & Delays

- [ ] Uses `random_delay()` or `get_delay_for_mode()` between requests
- [ ] Respects dual delay profiles (direct vs proxied)
- [ ] Handles 429 responses with exponential backoff
- [ ] Handles 503 responses gracefully

### 4. Session & Requests

- [ ] Uses provided `session` object (not creating new sessions)
- [ ] Uses `make_request_with_retry()` for HTTP requests
- [ ] Passes `proxy_mode` to request helpers when available
- [ ] Handles connection errors without crashing

### 5. Checkpoint Support

- [ ] Implements checkpoint saving for long-running scrapes
- [ ] Can resume from saved checkpoints when `--resume` flag used
- [ ] Checkpoints stored in `data/{retailer}/checkpoints/`

### 6. Configuration

- [ ] Registered in `src/scrapers/__init__.py` SCRAPERS dict
- [ ] Has config block in `config/retailers.yaml`
- [ ] Optional: Has `config/{retailer}_config.py` for complex settings

### 7. Logging

- [ ] Uses module-level logger: `logger = logging.getLogger(__name__)`
- [ ] Logs progress at INFO level (stores found, pages processed)
- [ ] Logs errors at ERROR level with context
- [ ] No print() statements

## Usage

To validate a specific scraper:

```bash
# Run unit tests
pytest tests/test_scrapers/test_{retailer}.py -v

# Run lint
pylint src/scrapers/{retailer}.py

# Test run with small limit
python run.py --retailer {retailer} --test --limit 5

# Validate store data output
python -c "
from src.shared.utils import validate_stores_batch
import json
with open('data/{retailer}/output/stores_latest.json') as f:
    stores = json.load(f)
print(validate_stores_batch(stores))
"
```

## Validation Report Format

```
Scraper Validation: {retailer}
================================
Interface Compliance: ✓/✗
Store Data Validation: ✓/✗
Rate Limiting: ✓/✗
Session Management: ✓/✗
Checkpoint Support: ✓/✗
Configuration: ✓/✗
Logging: ✓/✗

Issues Found:
- {issue description}
- {issue description}

Recommendations:
- {recommendation}
```

## Common Issues

1. **Zero coordinates as falsy**: Check `if lat is not None` not `if lat`
2. **Missing delay between requests**: Add `random_delay()` in extraction loop
3. **Hardcoded delays**: Use `get_delay_for_mode()` for proxy-aware delays
4. **Creating new sessions**: Use the provided `session` parameter
5. **Missing checkpoint save**: Add checkpoint after each batch of stores
