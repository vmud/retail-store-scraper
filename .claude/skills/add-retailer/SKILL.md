---
name: add-retailer
description: Guide for adding new retailer scrapers following project patterns
---

# Add New Retailer

Structured guide for adding a new retailer to the scraper system.

## Step 0: Research with Kapture (Browser DevTools)

Use Kapture to discover hidden APIs by inspecting network traffic on the retailer's store locator.

### Research Workflow

1. **Navigate to store locator**
   ```
   mcp__kapture__navigate → {retailer}.com/stores or /store-locator
   ```

2. **Open Network tab and interact**
   - Search for a location (e.g., "New York" or zip code "10001")
   - Click on a store to view details
   - Watch for XHR/Fetch requests

3. **Inspect network requests**
   ```
   mcp__kapture__console_logs  → Check for API calls
   mcp__kapture__dom           → Inspect page structure for embedded JSON
   ```

4. **Look for these patterns**:
   - **Yext API**: `liveapi.yext.com` (used by Cricket, many retailers)
   - **Internal API**: `/api/stores`, `/api/locations`, `redsky.target.com`
   - **Sitemap**: `/sitemap.xml`, `/sitemap-stores.xml`, `/store-sitemap.xml.gz`
   - **Embedded JSON**: `<script type="application/ld+json">` or `window.__INITIAL_STATE__`

5. **Document findings**:
   - [ ] API endpoint URL and required parameters
   - [ ] Authentication (API keys, headers)
   - [ ] Response format (JSON structure, field names)
   - [ ] Pagination method (offset, cursor, page number)
   - [ ] Rate limiting headers

### Common API Providers

| Provider | URL Pattern | Used By |
|----------|-------------|---------|
| Yext | `liveapi.yext.com/v2/accounts/*/entities` | Cricket, many retail chains |
| Uberall | `uberall.com/api/storefinders/*/locations` | Telus |
| Locally | `locally.com/stores/conversion_data` | Various |
| Google Places | Embedded maps with place IDs | Some retailers |

### Example: Discovering Cricket's Yext API

```
1. Navigate to cricketwireless.com/stores
2. Search for "10001"
3. Network tab shows: liveapi.yext.com/v2/accounts/me/search/vertical/query?...
4. Response contains store data with all fields needed
5. API key visible in URL parameters
```

## Prerequisites

After research, you should have:
- [ ] API endpoint URL or sitemap URL
- [ ] Required headers/authentication
- [ ] Sample API response or page HTML
- [ ] List of available data fields

## Step 1: Create Scraper Module

Create `src/scrapers/{retailer}.py` implementing the standard interface:

```python
"""
{Retailer} store scraper.

Discovery method: {sitemap|api|crawl}
Data source: {URL or API endpoint}
"""

import logging
from src.shared.utils import (
    make_request_with_retry,
    random_delay,
    validate_store_data,
    get_delay_for_mode
)
from src.shared.cache import URLCache

logger = logging.getLogger(__name__)


def run(session, retailer_config, retailer: str, **kwargs) -> dict:
    """
    Main entry point for {retailer} scraper.

    Args:
        session: requests.Session with configured headers
        retailer_config: Config from retailers.yaml
        retailer: Retailer name string
        **kwargs: Additional args (limit, test_mode, proxy_mode, etc.)

    Returns:
        dict with keys:
            - stores: list of store dictionaries
            - count: number of stores scraped
            - checkpoints_used: bool indicating if resumed from checkpoint
    """
    stores = []
    checkpoints_used = False

    # 1. Discover store URLs (from sitemap, API, or crawl)
    store_urls = discover_store_urls(session, retailer_config, **kwargs)

    # 2. Extract store data from each URL
    for url in store_urls:
        store_data = extract_store_data(session, url, retailer_config, **kwargs)
        if store_data:
            # 3. Validate before adding
            validation = validate_store_data(store_data)
            if validation.is_valid:
                stores.append(store_data)
            else:
                logger.warning(f"Invalid store data: {validation.errors}")

        # 4. Respect rate limits
        random_delay(retailer_config, kwargs.get('proxy_mode'))

    return {
        'stores': stores,
        'count': len(stores),
        'checkpoints_used': checkpoints_used
    }
```

### Required Store Fields

```python
store = {
    'store_id': str,        # Required: Unique identifier
    'name': str,            # Required: Store name
    'street_address': str,  # Required: Street address
    'city': str,            # Required: City
    'state': str,           # Required: State/province code
    'zip_code': str,        # Recommended
    'latitude': str,        # Recommended: As string
    'longitude': str,       # Recommended: As string
    'phone': str,           # Recommended
    'url': str,             # Recommended: Store page URL
    'store_type': str,      # Optional: corporate, authorized, etc.
    'hours': dict,          # Optional: Operating hours
    'scraped_at': str,      # Auto-added: ISO timestamp
}
```

## Step 2: Create Config Module

Create `config/{retailer}_config.py`:

```python
"""Configuration for {retailer} scraper."""

# Discovery settings
SITEMAP_URL = "https://example.com/sitemap.xml"
# or
API_URL = "https://api.example.com/stores"

# Store page URL pattern (for validation)
STORE_URL_PATTERN = r"https://example\.com/stores/[\w-]+"

# Fields to extract (maps source field to output field)
FIELD_MAPPING = {
    'storeNumber': 'store_id',
    'storeName': 'name',
    'address1': 'street_address',
    # ...
}

# Rate limiting (overrides retailers.yaml if needed)
MIN_DELAY = 2.0
MAX_DELAY = 5.0
```

## Step 3: Register Scraper

Update `src/scrapers/__init__.py`:

```python
# Add import
from src.scrapers.{retailer} import run as {retailer}_run

# Add to SCRAPERS dict
SCRAPERS = {
    # ... existing scrapers
    '{retailer}': {retailer}_run,
}
```

## Step 4: Add YAML Configuration

Add to `config/retailers.yaml`:

```yaml
retailers:
  {retailer}:
    enabled: true
    display_name: "{Retailer Display Name}"

    # Discovery
    discovery_method: sitemap  # or: api, crawl
    sitemap_urls:
      - "https://example.com/sitemap.xml"
    # or
    api_url: "https://api.example.com/stores"

    # Delays
    delays:
      direct:
        min_delay: 2.0
        max_delay: 5.0
      proxied:
        min_delay: 0.2
        max_delay: 0.5

    # Proxy settings
    proxy:
      mode: direct  # or: residential, web_scraper_api
      required: false

    # Parallelization
    discovery_workers: 1
    parallel_workers: 5

    # Output
    output_fields:
      - store_id
      - name
      - street_address
      - city
      - state
      - zip_code
      - latitude
      - longitude
      - phone
      - url
      - store_type
```

## Step 5: Add Tests

Create `tests/test_scrapers/test_{retailer}.py`:

```python
"""Tests for {retailer} scraper."""

import pytest
from unittest.mock import Mock, patch
from src.scrapers.{retailer} import run, extract_store_data


class Test{Retailer}Scraper:
    """Test {retailer} scraper functionality."""

    def test_extract_store_data_valid(self):
        """Test extraction from valid store page."""
        # Mock response with sample HTML/JSON
        pass

    def test_extract_store_data_missing_fields(self):
        """Test handling of missing required fields."""
        pass

    def test_run_with_limit(self):
        """Test --limit flag respected."""
        pass

    def test_run_handles_rate_limit(self):
        """Test 429 response handling."""
        pass
```

## Verification Checklist

- [ ] Scraper implements `run()` with correct signature
- [ ] Returns dict with `stores`, `count`, `checkpoints_used`
- [ ] Uses `validate_store_data()` before adding stores
- [ ] Respects delay profiles (direct vs proxied)
- [ ] Handles 429/503 responses gracefully
- [ ] Supports checkpoint/resume
- [ ] Tests pass: `pytest tests/test_scrapers/test_{retailer}.py`
- [ ] Lint passes: `pylint src/scrapers/{retailer}.py`
- [ ] Test run works: `python run.py --retailer {retailer} --test`
