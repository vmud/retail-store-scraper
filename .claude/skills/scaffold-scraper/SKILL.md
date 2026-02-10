---
name: scaffold-scraper
description: Generate a new retailer scraper skeleton with config and test fixtures
disable-model-invocation: true
---

# Scaffold New Retailer Scraper

Generates a working scraper skeleton for a new retailer. Creates 3 files and registers the scraper.

## Usage

| Command | Description |
|---------|-------------|
| `/scaffold-scraper walgreens sitemap` | Sitemap-based scraper |
| `/scaffold-scraper nordstrom api` | Paginated JSON API scraper |
| `/scaffold-scraper costco graphql` | GraphQL API scraper |
| `/scaffold-scraper gap html` | Multi-phase HTML crawl scraper |
| `/scaffold-scraper autozone locator` | Geo-radius store locator API |

## Arguments

1. **retailer** (required): Lowercase retailer name (becomes filename)
2. **type** (required): One of `sitemap`, `api`, `graphql`, `html`, `locator`

## What Gets Created

### 1. `src/scrapers/{retailer}.py`

Scraper module with `run()` function following the project contract:

```python
def run(session, retailer_config, retailer: str, **kwargs) -> dict:
    # Returns: {'stores': [...], 'count': int, 'checkpoints_used': bool}
```

Each type includes:
- Inline TODO comments pointing to a working example of the same type
- Proper imports from `src/shared/`
- Delay enforcement, checkpoint support, validation
- Type-specific discovery and extraction stubs

### Type → Example Reference

| Type | Base Pattern | Example Scraper |
|------|-------------|-----------------|
| `sitemap` | XML/gzipped sitemap parsing | `att.py`, `bestbuy.py` |
| `api` | Paginated JSON API | `cricket.py` (Yext), `telus.py` (Uberall) |
| `graphql` | GraphQL queries | `homedepot.py` |
| `html` | Multi-phase HTML crawl | `verizon.py` |
| `locator` | Geo-radius store locator | `staples.py` |

### 2. `config/{retailer}_config.py`

Config skeleton with:
- Discovery URL placeholder
- Field mapping template
- Store URL pattern

### 3. `tests/test_scrapers/fixtures/{retailer}/`

Empty fixture directory. Drop sample responses here:
- `sitemap.xml` or `api_response.json` or `graphql_response.json`
- `store_page.html` or `store_detail.json`
- `expected_stores.json`

### 4. Registration

Add entry to `SCRAPER_REGISTRY` in `src/scrapers/__init__.py`.

### 5. YAML config block

Add retailer block to `config/retailers.yaml` with:
- `enabled: true`
- Dual delay profiles (direct + proxied)
- Default proxy mode based on type
- Output fields list

## Implementation Steps

1. Validate retailer name doesn't already exist in `src/scrapers/`
2. Create `src/scrapers/{retailer}.py` from type template
3. Create `config/{retailer}_config.py` with placeholder values
4. Create `tests/test_scrapers/fixtures/{retailer}/` directory
5. Add to `SCRAPER_REGISTRY` in `src/scrapers/__init__.py`
6. Add config block to `config/retailers.yaml`
7. Run `pylint src/scrapers/{retailer}.py` to verify syntax
8. Report created files and next steps

## Templates by Type

### sitemap

```python
"""
{Retailer} store scraper.

Discovery: XML sitemap
Example reference: See att.py for a working sitemap scraper.
"""

import logging
from src.shared.utils import (
    make_request_with_retry,
    random_delay,
    validate_store_data,
    get_delay_for_mode,
)

logger = logging.getLogger(__name__)


def run(session, retailer_config, retailer: str, **kwargs) -> dict:
    """Main entry point for {retailer} scraper."""
    stores = []
    checkpoints_used = False
    limit = kwargs.get('limit')

    # TODO: Implement sitemap discovery
    # See att.py:discover_store_urls() for XML sitemap parsing
    store_urls = discover_store_urls(session, retailer_config, **kwargs)

    for i, url in enumerate(store_urls):
        if limit and i >= limit:
            break

        store_data = extract_store_data(session, url, retailer_config, **kwargs)
        if store_data:
            validation = validate_store_data(store_data)
            if validation.is_valid:
                stores.append(store_data)
            else:
                logger.warning("Invalid store data from %s: %s", url, validation.errors)

        random_delay(retailer_config, kwargs.get('proxy_mode'))

    return {'stores': stores, 'count': len(stores), 'checkpoints_used': checkpoints_used}


def discover_store_urls(session, retailer_config, **kwargs):
    """Parse sitemap XML to find store page URLs.

    TODO: Implement sitemap fetching and parsing.
    See att.py for XML sitemap, target.py for gzipped sitemaps.
    """
    raise NotImplementedError("TODO: Implement sitemap discovery")


def extract_store_data(session, url, retailer_config, **kwargs):
    """Extract store data from a single store page.

    TODO: Implement store page parsing.
    See att.py:extract_store_data() for HTML parsing example.
    """
    raise NotImplementedError("TODO: Implement store extraction")
```

### api

```python
"""
{Retailer} store scraper.

Discovery: Paginated JSON API
Example reference: See cricket.py (Yext API) or telus.py (Uberall API).
"""
# TODO: Implement paginated API discovery and extraction
# See cricket.py for geo-grid API pattern
# See telus.py for Uberall API pattern
```

### graphql

```python
"""
{Retailer} store scraper.

Discovery: GraphQL API
Example reference: See homedepot.py for GraphQL Federation Gateway pattern.
"""
# TODO: Implement GraphQL query and response parsing
# See homedepot.py for query construction and pagination
```

### html

```python
"""
{Retailer} store scraper.

Discovery: Multi-phase HTML crawl
Example reference: See verizon.py for 4-phase HTML crawl pattern.
"""
# TODO: Implement multi-phase crawl: index → region → city → store
# See verizon.py for the discovery phase chain
```

### locator

```python
"""
{Retailer} store scraper.

Discovery: Store locator API (geo-radius queries)
Example reference: See staples.py for API + gap-fill pattern.
"""
# TODO: Implement geo-radius store locator queries
# See staples.py for StaplesConnect API + gap-fill strategy
```

## Post-Scaffold Checklist

After scaffolding, the developer should:

- [ ] Fill in discovery URL in `config/{retailer}_config.py`
- [ ] Implement `discover_store_urls()` (fetch sitemap/API/crawl index)
- [ ] Implement `extract_store_data()` (parse store page/response)
- [ ] Add field mapping in config
- [ ] Drop sample fixtures in `tests/test_scrapers/fixtures/{retailer}/`
- [ ] Run: `python run.py --retailer {retailer} --test`
- [ ] Run: `pytest tests/test_scrapers/test_{retailer}.py`
