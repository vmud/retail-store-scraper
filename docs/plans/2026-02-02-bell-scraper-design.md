# Bell Mobility Scraper Design

**Date:** 2026-02-02
**Status:** Ready for implementation

## Overview

Add a new scraper for Bell Mobility (Canadian mobile retailer) to collect store locations across Canada.

## Research Findings

### Data Source
- **Store Locator URL:** `https://storelocator.bell.ca/bellca/en/locations.html`
- **Sitemap:** `https://storelocator.bell.ca/sitemap.xml` (~251 store URLs)
- **Store URL Pattern:** `/bellca/en/{Province}/{City}/{StoreName}/{StoreID}`
- **Store ID Format:** `BE###` (e.g., BE516, BE086)

### Available Data
From LocalBusiness JSON-LD schema on each store page:
- Name
- Street address, city, province, postal code
- Phone number
- Opening hours (in format "Mo 1100-1800")

From HTML parsing:
- Services offered (e.g., "Mobile devices for business + consumer", "Sign Language Interpreter")
- Store type (Bell corporate vs authorized dealer - inferred from name)
- Curbside pickup availability

### Limitations
- **No coordinates:** Store pages don't include lat/lng in schema or HTML
- **Rate limiting:** robots.txt specifies `Crawl-delay: 10` (10 seconds between requests)

## Architecture

### Discovery Method: Sitemap
Similar to AT&T and Best Buy scrapers - fetch sitemap XML, extract store page URLs.

### Extraction Method: JSON-LD + HTML Parsing
1. Fetch store page HTML
2. Parse `<script type="application/ld+json">` for LocalBusiness schema
3. Parse HTML for additional data (services, features)

### Scraper Pattern
Follows existing patterns from `telus.py` (another Canadian carrier):
- Dataclass for store model
- Province abbreviation mapping
- Hours formatting

## Output Fields

```yaml
output_fields:
  - store_id        # BE516
  - name            # Bell - Queen St W
  - street_address  # 316 Queen St W
  - city            # Toronto
  - state           # ON (province abbreviation)
  - postal_code     # M5V2A2
  - country         # CA
  - phone           # 416 977-6969
  - hours           # JSON string of formatted hours
  - services        # List of services offered
  - store_type      # corporate, authorized_dealer
  - has_curbside    # boolean
  - url             # Full store page URL
  - scraped_at      # ISO timestamp
```

## Configuration

```yaml
bell:
  name: "Bell"
  enabled: true
  base_url: "https://storelocator.bell.ca"
  sitemap_urls:
    - "https://storelocator.bell.ca/sitemap.xml"
  discovery_method: "sitemap"

  # Conservative delays (robots.txt says 10s, we'll be respectful)
  delays:
    direct:
      min_delay: 10.0
      max_delay: 12.0
    proxied:
      min_delay: 2.0
      max_delay: 4.0

  checkpoint_interval: 25
  parallel_workers: 1  # Single worker due to crawl-delay

  proxy:
    mode: "direct"  # No aggressive bot protection observed
    render_js: false
```

## Implementation Plan

### Files to Create
1. `src/scrapers/bell.py` - Main scraper module
2. `config/bell_config.py` - Retailer-specific configuration
3. `tests/test_scrapers/test_bell.py` - Unit tests

### Files to Modify
1. `src/scrapers/__init__.py` - Register bell scraper
2. `config/retailers.yaml` - Add bell configuration block

### Implementation Steps

1. **Create feature branch**
   ```bash
   git checkout main && git pull
   git checkout -b feat/bell-scraper
   ```

2. **Create config module** (`config/bell_config.py`)
   - Define sitemap URL
   - Province abbreviations (reuse from telus_config.py)
   - Request headers
   - Field mappings for JSON-LD schema

3. **Create scraper module** (`src/scrapers/bell.py`)
   - `BellStore` dataclass
   - `fetch_sitemap()` - Get store URLs from sitemap
   - `parse_store_page()` - Extract data from HTML
   - `_parse_json_ld()` - Parse LocalBusiness schema
   - `_parse_services()` - Extract services from HTML
   - `_format_hours()` - Convert schema hours to standard format
   - `run()` - Main entry point

4. **Register scraper** (`src/scrapers/__init__.py`)
   - Import bell_run
   - Add to SCRAPERS dict

5. **Add YAML config** (`config/retailers.yaml`)
   - Add bell configuration block

6. **Create tests** (`tests/test_scrapers/test_bell.py`)
   - Test JSON-LD parsing
   - Test hours formatting
   - Test services extraction
   - Test run with mock responses

7. **Validate**
   - `pylint src/scrapers/bell.py config/bell_config.py`
   - `pytest tests/test_scrapers/test_bell.py`
   - `python run.py --retailer bell --test`

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| robots.txt 10s crawl-delay | Slow scraping (~40 min for 251 stores) | Use proxy mode with reduced delays when needed |
| Schema format changes | Extraction breaks | Validate schema structure, add fallback HTML parsing |
| Sitemap outdated | Missing new stores | Add refresh mechanism, monitor store count |

## Success Criteria

- [ ] Scrapes all ~251 Bell stores successfully
- [ ] Extracts address, phone, hours, and services
- [ ] Respects rate limits in direct mode
- [ ] Tests pass with >90% coverage
- [ ] Integrates with existing CLI (`python run.py --retailer bell`)
