# Bell Mobility Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Bell Mobility scraper that extracts ~251 store locations from storelocator.bell.ca using sitemap discovery and JSON-LD schema parsing.

**Architecture:** Sitemap-based URL discovery followed by HTML/JSON-LD extraction from each store page. Similar pattern to AT&T scraper but simpler (no rating data, different store type detection). Uses shared URLCache for URL caching and checkpoint system for resume support.

**Tech Stack:** Python 3.8+, requests, BeautifulSoup4, lxml (XML parsing), dataclasses

---

## Task 1: Create Feature Branch

**Files:**
- None (git operations only)

**Step 1: Ensure clean state and create branch**

```bash
git checkout main
git pull origin main
git checkout -b feat/bell-scraper
```

**Step 2: Verify branch**

Run: `git branch --show-current`
Expected: `feat/bell-scraper`

---

## Task 2: Create Bell Config Module

**Files:**
- Create: `config/bell_config.py`

**Step 1: Write the config module**

```python
"""Configuration constants for Bell Store Scraper"""

import random

# Sitemap configuration
SITEMAP_URL = "https://storelocator.bell.ca/sitemap.xml"

# Base URLs
BASE_URL = "https://storelocator.bell.ca"
STORE_PAGE_BASE = "https://storelocator.bell.ca/bellca/en"

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


def get_headers(user_agent=None):
    """Get headers dict with optional user agent rotation"""
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": BASE_URL,
    }


# Canadian province name to abbreviation mapping (reused from telus)
PROVINCE_ABBREVIATIONS = {
    'Alberta': 'AB',
    'British Columbia': 'BC',
    'Manitoba': 'MB',
    'New Brunswick': 'NB',
    'Newfoundland and Labrador': 'NL',
    'Northwest Territories': 'NT',
    'Nova Scotia': 'NS',
    'Nunavut': 'NU',
    'Ontario': 'ON',
    'Prince Edward Island': 'PE',
    'Quebec': 'QC',
    'Québec': 'QC',
    'Saskatchewan': 'SK',
    'Yukon': 'YT',
}

# Store URL pattern regex for filtering sitemap
# Matches: /bellca/en/{Province}/{City}/{StoreName}/{StoreID}
# where StoreID is BE followed by digits
STORE_URL_PATTERN = r'/bellca/en/[^/]+/[^/]+/[^/]+/BE\d+'

# Rate limiting (robots.txt specifies Crawl-delay: 10)
MIN_DELAY = 10.0
MAX_DELAY = 12.0

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30
```

**Step 2: Verify file created**

Run: `python -c "from config import bell_config; print(bell_config.SITEMAP_URL)"`
Expected: `https://storelocator.bell.ca/sitemap.xml`

**Step 3: Commit**

```bash
git add config/bell_config.py
git commit -m "feat(bell): Add Bell config module with sitemap URL and province mappings"
```

---

## Task 3: Create Bell Scraper Module - Dataclass and Helpers

**Files:**
- Create: `src/scrapers/bell.py`

**Step 1: Write the scraper module with dataclass and helper functions**

```python
"""Core scraping functions for Bell Store Locator

Bell uses storelocator.bell.ca with:
- Sitemap at /sitemap.xml (~251 store URLs)
- LocalBusiness JSON-LD schema on each store page
- Store IDs in format BE### (e.g., BE516)
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup

from config import bell_config
from src.shared import utils
from src.shared.cache import URLCache
from src.shared.request_counter import RequestCounter, check_pause_logic


# Global request counter
_request_counter = RequestCounter()


@dataclass
class BellStore:
    """Data model for Bell store information"""
    store_id: str           # BE516
    name: str               # Bell - Queen St W
    street_address: str     # 316 Queen St W
    city: str               # Toronto
    state: str              # ON (province abbreviation)
    postal_code: str        # M5V2A2
    country: str            # CA
    phone: str              # 416 977-6969
    hours: Optional[str]    # JSON string of formatted hours
    services: Optional[str] # JSON string of services list
    store_type: str         # corporate, authorized_dealer
    has_curbside: bool      # Curbside pickup available
    url: str                # Full store page URL
    scraped_at: str         # ISO timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        return asdict(self)


def _format_schema_hours(opening_hours: List[str]) -> Optional[str]:
    """Format schema.org openingHours to JSON string.

    Args:
        opening_hours: List of hours in schema.org format
            Example: ["Su 1200-1700", "Mo 1100-1800", ...]

    Returns:
        JSON string of formatted hours or None if no hours
    """
    if not opening_hours:
        return None

    day_map = {
        'Su': 'Sunday', 'Mo': 'Monday', 'Tu': 'Tuesday',
        'We': 'Wednesday', 'Th': 'Thursday', 'Fr': 'Friday', 'Sa': 'Saturday'
    }

    formatted = []
    for entry in opening_hours:
        # Parse format: "Mo 1100-1800"
        match = re.match(r'(\w{2})\s+(\d{4})-(\d{4})', entry)
        if match:
            day_abbr, open_time, close_time = match.groups()
            day_name = day_map.get(day_abbr, day_abbr)
            # Convert 1100 to 11:00
            open_fmt = f"{open_time[:2]}:{open_time[2:]}"
            close_fmt = f"{close_time[:2]}:{close_time[2:]}"
            formatted.append({
                'day': day_name,
                'open': open_fmt,
                'close': close_fmt
            })

    return json.dumps(formatted) if formatted else None


def _extract_store_type(store_name: str) -> str:
    """Determine store type from store name.

    Bell corporate stores typically have "Bell" as the primary name.
    Authorized dealers have different business names.

    Args:
        store_name: Store name from JSON-LD schema

    Returns:
        'corporate' or 'authorized_dealer'
    """
    # Corporate stores are simply named "Bell" or "Bell - Location"
    if store_name.lower().strip() == 'bell':
        return 'corporate'
    return 'authorized_dealer'


def _extract_services(soup: BeautifulSoup) -> Optional[str]:
    """Extract services list from HTML.

    Args:
        soup: BeautifulSoup object of store page

    Returns:
        JSON string of services list or None
    """
    services = []

    # Look for services in the rsx-list under "Products and services"
    service_list = soup.find('ul', class_='rsx-list')
    if service_list:
        for li in service_list.find_all('li'):
            text = li.get_text(strip=True)
            if text:
                services.append(text)

    return json.dumps(services) if services else None


def _has_curbside_pickup(soup: BeautifulSoup) -> bool:
    """Check if store offers curbside pickup.

    Args:
        soup: BeautifulSoup object of store page

    Returns:
        True if curbside pickup is available
    """
    # Look for curbside pickup indicator
    curbside_img = soup.find('img', src=lambda x: x and 'curbside' in x.lower() if x else False)
    curbside_text = soup.find(string=lambda x: x and 'curbside' in x.lower() if x else False)
    return bool(curbside_img or curbside_text)


def reset_request_counter() -> None:
    """Reset the global request counter"""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count
```

**Step 2: Verify syntax**

Run: `python -c "from src.scrapers.bell import BellStore, _format_schema_hours; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/scrapers/bell.py
git commit -m "feat(bell): Add BellStore dataclass and helper functions"
```

---

## Task 4: Add Sitemap Fetching Function

**Files:**
- Modify: `src/scrapers/bell.py`

**Step 1: Add get_store_urls_from_sitemap function after the helper functions**

```python
def get_store_urls_from_sitemap(
    session,
    retailer: str = 'bell',
    yaml_config: dict = None
) -> List[str]:
    """Fetch all store URLs from the Bell sitemap.

    Args:
        session: Requests session object
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        List of store URLs (filtered to only those with BE### store IDs)
    """
    logging.info(f"[{retailer}] Fetching sitemap from {bell_config.SITEMAP_URL}")

    response = utils.get_with_retry(session, bell_config.SITEMAP_URL)
    if not response:
        logging.error(f"[{retailer}] Failed to fetch sitemap")
        return []

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    try:
        # Parse XML
        root = ET.fromstring(response.content)
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Extract all URLs
        all_urls = []
        for loc in root.findall(".//ns:loc", namespace):
            url = loc.text
            if url:
                all_urls.append(url)

        logging.info(f"[{retailer}] Found {len(all_urls)} total URLs in sitemap")

        # Filter to only store URLs (containing /BE followed by digits)
        store_pattern = re.compile(bell_config.STORE_URL_PATTERN)
        store_urls = [url for url in all_urls if store_pattern.search(url)]

        logging.info(f"[{retailer}] Filtered to {len(store_urls)} store URLs")

        return store_urls

    except ET.ParseError as e:
        logging.error(f"[{retailer}] Failed to parse XML sitemap: {e}")
        return []
    except Exception as e:
        logging.error(f"[{retailer}] Unexpected error parsing sitemap: {e}")
        return []
```

**Step 2: Verify function exists**

Run: `python -c "from src.scrapers.bell import get_store_urls_from_sitemap; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/scrapers/bell.py
git commit -m "feat(bell): Add sitemap fetching function"
```

---

## Task 5: Add Store Details Extraction Function

**Files:**
- Modify: `src/scrapers/bell.py`

**Step 1: Add extract_store_details function**

```python
def extract_store_details(
    session,
    url: str,
    retailer: str = 'bell',
    yaml_config: dict = None
) -> Optional[BellStore]:
    """Extract store data from a single Bell store page.

    Args:
        session: Requests session object
        url: Store page URL
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        BellStore object if successful, None otherwise
    """
    logging.debug(f"[{retailer}] Extracting details from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store details: {url}")
        return None

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find JSON-LD script with LocalBusiness schema
        scripts = soup.find_all('script', type='application/ld+json')
        if not scripts:
            logging.warning(f"[{retailer}] No JSON-LD found for {url}")
            return None

        # Find LocalBusiness schema
        data = None
        for script in scripts:
            try:
                script_data = json.loads(script.string)
                if script_data.get('@type') == 'LocalBusiness':
                    data = script_data
                    break
            except json.JSONDecodeError:
                continue

        if not data:
            logging.debug(f"[{retailer}] No LocalBusiness schema found for {url}")
            return None

        # Extract store ID from URL (e.g., BE516)
        store_id_match = re.search(r'(BE\d+)$', url)
        store_id = store_id_match.group(1) if store_id_match else ''

        # Extract address components
        address = data.get('address', {})

        # Get province - already abbreviated in schema (ON, QC, etc.)
        state = address.get('addressRegion', '')

        # Extract phone - clean formatting
        phone = data.get('telephone', '')
        if phone:
            phone = re.sub(r'[^\d-]', '', phone)  # Keep digits and dashes

        # Extract hours
        opening_hours = data.get('openingHours', [])
        hours = _format_schema_hours(opening_hours)

        # Extract services from HTML
        services = _extract_services(soup)

        # Determine store type and curbside availability
        store_name = data.get('name', 'Bell')
        store_type = _extract_store_type(store_name)
        has_curbside = _has_curbside_pickup(soup)

        # Create BellStore object
        store = BellStore(
            store_id=store_id,
            name=store_name,
            street_address=address.get('streetAddress', ''),
            city=address.get('addressLocality', ''),
            state=state,
            postal_code=address.get('postalCode', ''),
            country='CA',
            phone=phone,
            hours=hours,
            services=services,
            store_type=store_type,
            has_curbside=has_curbside,
            url=url,
            scraped_at=datetime.now().isoformat()
        )

        logging.debug(f"[{retailer}] Extracted store: {store.name} ({store.store_id})")
        return store

    except Exception as e:
        logging.warning(f"[{retailer}] Error extracting store data from {url}: {e}")
        return None
```

**Step 2: Verify function exists**

Run: `python -c "from src.scrapers.bell import extract_store_details; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/scrapers/bell.py
git commit -m "feat(bell): Add store details extraction function"
```

---

## Task 6: Add Main Run Function

**Files:**
- Modify: `src/scrapers/bell.py`

**Step 1: Add run function (main entry point)**

```python
def run(session, config: dict, **kwargs) -> dict:
    """Standard scraper entry point with URL caching and checkpoints.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - retailer: str - Retailer name for logging
            - resume: bool - Resume from checkpoint
            - limit: int - Max stores to process
            - refresh_urls: bool - Force URL re-discovery (ignore cache)

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = kwargs.get('retailer', 'bell')
    logging.info(f"[{retailer_name}] Starting scrape run")

    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        refresh_urls = kwargs.get('refresh_urls', False)

        reset_request_counter()

        # Auto-select delays based on proxy mode
        proxy_mode = config.get('proxy', {}).get('mode', 'direct')
        min_delay, max_delay = utils.select_delays(config, proxy_mode)
        logging.info(f"[{retailer_name}] Using delays: {min_delay:.1f}-{max_delay:.1f}s (mode: {proxy_mode})")

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = config.get('checkpoint_interval', 25)

        stores = []
        completed_urls = set()
        checkpoints_used = False

        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores = checkpoint.get('stores', [])
                completed_urls = set(checkpoint.get('completed_urls', []))
                logging.info(f"[{retailer_name}] Resuming from checkpoint: {len(stores)} stores already collected")
                checkpoints_used = True

        # Try to load cached URLs
        url_cache = URLCache(retailer_name)
        store_urls = None
        if not refresh_urls:
            store_urls = url_cache.get()

        if store_urls is None:
            # Cache miss - fetch from sitemap
            store_urls = get_store_urls_from_sitemap(session, retailer_name, yaml_config=config)
            logging.info(f"[{retailer_name}] Found {len(store_urls)} store URLs from sitemap")

            if store_urls:
                url_cache.set(store_urls)
        else:
            logging.info(f"[{retailer_name}] Using {len(store_urls)} cached store URLs")

        if not store_urls:
            logging.warning(f"[{retailer_name}] No store URLs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        remaining_urls = [url for url in store_urls if url not in completed_urls]

        if resume and completed_urls:
            logging.info(f"[{retailer_name}] Skipping {len(store_urls) - len(remaining_urls)} already-processed stores")

        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} stores")
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_urls = remaining_urls[:total_needed]
            else:
                remaining_urls = []

        total_to_process = len(remaining_urls)
        if total_to_process > 0:
            logging.info(f"[{retailer_name}] Extracting details for {total_to_process} stores")
        else:
            logging.info(f"[{retailer_name}] No new stores to process")

        # Sequential extraction (Bell requires conservative rate limiting)
        for i, url in enumerate(remaining_urls, 1):
            store_obj = extract_store_details(session, url, retailer_name, yaml_config=config)
            if store_obj:
                stores.append(store_obj.to_dict())
                completed_urls.add(url)

            # Progress logging every 25 stores
            if i % 25 == 0:
                logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")

            # Checkpoint at intervals
            if i % checkpoint_interval == 0:
                utils.save_checkpoint({
                    'completed_count': len(stores),
                    'completed_urls': list(completed_urls),
                    'stores': stores,
                    'last_updated': datetime.now().isoformat()
                }, checkpoint_path)
                logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores")

            # Respect rate limiting
            utils.random_delay(config, proxy_mode)

        # Final checkpoint
        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_urls': list(completed_urls),
                'stores': stores,
                'last_updated': datetime.now().isoformat()
            }, checkpoint_path)

        # Validate store data
        validation_summary = utils.validate_stores_batch(stores)
        logging.info(
            f"[{retailer_name}] Validation: {validation_summary['valid']}/{validation_summary['total']} valid, "
            f"{validation_summary['warning_count']} warnings"
        )

        logging.info(f"[{retailer_name}] Completed: {len(stores)} stores scraped")

        return {
            'stores': stores,
            'count': len(stores),
            'checkpoints_used': checkpoints_used
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
```

**Step 2: Verify function exists**

Run: `python -c "from src.scrapers.bell import run; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/scrapers/bell.py
git commit -m "feat(bell): Add main run() entry point with checkpoint support"
```

---

## Task 7: Register Bell Scraper

**Files:**
- Modify: `src/scrapers/__init__.py`

**Step 1: Add bell to SCRAPER_REGISTRY**

In `src/scrapers/__init__.py`, add `'bell': 'src.scrapers.bell'` to the SCRAPER_REGISTRY dict:

```python
SCRAPER_REGISTRY: Dict[str, str] = {
    'verizon': 'src.scrapers.verizon',
    'att': 'src.scrapers.att',
    'target': 'src.scrapers.target',
    'tmobile': 'src.scrapers.tmobile',
    'walmart': 'src.scrapers.walmart',
    'bestbuy': 'src.scrapers.bestbuy',
    'telus': 'src.scrapers.telus',
    'cricket': 'src.scrapers.cricket',
    'samsclub': 'src.scrapers.samsclub',
    'bell': 'src.scrapers.bell',
}
```

**Step 2: Verify registration**

Run: `python -c "from src.scrapers import get_available_retailers; print('bell' in get_available_retailers())"`
Expected: `True`

**Step 3: Commit**

```bash
git add src/scrapers/__init__.py
git commit -m "feat(bell): Register bell scraper in SCRAPER_REGISTRY"
```

---

## Task 8: Add Bell Configuration to retailers.yaml

**Files:**
- Modify: `config/retailers.yaml`

**Step 1: Add bell configuration block at the end of retailers section**

Add this YAML block under the `retailers:` section (after the last retailer):

```yaml
  bell:
    name: "Bell"
    enabled: true
    base_url: "https://storelocator.bell.ca"
    sitemap_urls:
      - "https://storelocator.bell.ca/sitemap.xml"
    discovery_method: "sitemap"

    # Conservative delays (robots.txt specifies Crawl-delay: 10)
    delays:
      direct:
        min_delay: 10.0
        max_delay: 12.0
      proxied:
        min_delay: 2.0
        max_delay: 4.0

    # Checkpoint interval for resume support
    checkpoint_interval: 25

    # Single worker due to crawl-delay requirement
    parallel_workers: 1

    # Disable long pauses (already respecting crawl-delay)
    pause_50_requests: 999999
    pause_200_requests: 999999
    pause_50_min: 0
    pause_50_max: 0
    pause_200_min: 0
    pause_200_max: 0

    # Direct mode - no aggressive bot protection observed
    proxy:
      mode: "direct"
      render_js: false

    output_fields:
      - store_id
      - name
      - street_address
      - city
      - state
      - postal_code
      - country
      - phone
      - hours
      - services
      - store_type
      - has_curbside
      - url
      - scraped_at
```

**Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('config/retailers.yaml')); print('OK')"`
Expected: `OK`

**Step 3: Verify bell is enabled**

Run: `python -c "from src.scrapers import get_enabled_retailers; print('bell' in get_enabled_retailers())"`
Expected: `True`

**Step 4: Commit**

```bash
git add config/retailers.yaml
git commit -m "feat(bell): Add Bell configuration to retailers.yaml"
```

---

## Task 9: Create Unit Tests

**Files:**
- Create: `tests/test_scrapers/test_bell.py`

**Step 1: Write comprehensive unit tests**

```python
"""Unit tests for Bell scraper."""
# pylint: disable=no-member

import json
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.scrapers.bell import (
    BellStore,
    _format_schema_hours,
    _extract_store_type,
    _extract_services,
    _has_curbside_pickup,
    get_store_urls_from_sitemap,
    extract_store_details,
    run,
    reset_request_counter,
)


class TestBellStore:
    """Tests for BellStore dataclass."""

    def test_to_dict(self):
        """Test dict conversion."""
        store = BellStore(
            store_id='BE516',
            name='Bell',
            street_address='316 Queen St W',
            city='Toronto',
            state='ON',
            postal_code='M5V2A2',
            country='CA',
            phone='416-977-6969',
            hours='[{"day": "Monday", "open": "10:00", "close": "18:00"}]',
            services='["Mobile devices"]',
            store_type='corporate',
            has_curbside=True,
            url='https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell-Queen-St-W/BE516',
            scraped_at='2026-02-02T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == 'BE516'
        assert result['city'] == 'Toronto'
        assert result['state'] == 'ON'
        assert result['has_curbside'] is True


class TestFormatSchemaHours:
    """Tests for _format_schema_hours function."""

    def test_valid_hours(self):
        """Test formatting valid hours."""
        hours = ["Mo 1000-1800", "Tu 1000-1800", "Su 1200-1700"]
        result = _format_schema_hours(hours)
        parsed = json.loads(result)

        assert len(parsed) == 3
        assert parsed[0]['day'] == 'Monday'
        assert parsed[0]['open'] == '10:00'
        assert parsed[0]['close'] == '18:00'

    def test_empty_hours(self):
        """Test empty hours returns None."""
        assert _format_schema_hours([]) is None
        assert _format_schema_hours(None) is None

    def test_invalid_format_skipped(self):
        """Test invalid hour format is skipped."""
        hours = ["Mo 1000-1800", "invalid", "Tu 0900-1700"]
        result = _format_schema_hours(hours)
        parsed = json.loads(result)

        assert len(parsed) == 2


class TestExtractStoreType:
    """Tests for _extract_store_type function."""

    def test_corporate_store(self):
        """Test corporate store detection."""
        assert _extract_store_type('Bell') == 'corporate'
        assert _extract_store_type('bell') == 'corporate'
        assert _extract_store_type(' Bell ') == 'corporate'

    def test_authorized_dealer(self):
        """Test authorized dealer detection."""
        assert _extract_store_type('RWireless') == 'authorized_dealer'
        assert _extract_store_type('TNT Digital') == 'authorized_dealer'
        assert _extract_store_type('Go West Wireless') == 'authorized_dealer'


class TestGetStoreUrlsFromSitemap:
    """Tests for get_store_urls_from_sitemap function."""

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_parse_sitemap(self, mock_counter, mock_get):
        """Test parsing sitemap XML."""
        sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell-Queen-St-W/BE516</loc></url>
    <url><loc>https://storelocator.bell.ca/bellca/en/AB/Calgary/Bell/BE086</loc></url>
    <url><loc>https://storelocator.bell.ca/bellca/en/Ontario.html</loc></url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = sitemap_xml.encode('utf-8')
        mock_get.return_value = mock_response
        mock_session = Mock()

        urls = get_store_urls_from_sitemap(mock_session)

        # Should only include URLs with BE### pattern
        assert len(urls) == 2
        assert 'BE516' in urls[0]
        assert 'BE086' in urls[1]

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_failed_fetch(self, mock_counter, mock_get):
        """Test failed fetch returns empty list."""
        mock_get.return_value = None
        mock_session = Mock()

        urls = get_store_urls_from_sitemap(mock_session)

        assert urls == []


class TestExtractStoreDetails:
    """Tests for extract_store_details function."""

    def _make_store_page_html(self, store_id='BE516', name='Bell', has_curbside=True):
        """Helper to create store page HTML."""
        curbside_html = '<img src="/bellca/Icon/curbside.png"> Curbside pickup' if has_curbside else ''
        return f'''<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{{
    "@type": "LocalBusiness",
    "name": "{name}",
    "telephone": "416 977-6969",
    "address": {{
        "streetAddress": "316 Queen St W",
        "addressLocality": "Toronto",
        "addressRegion": "ON",
        "postalCode": "M5V2A2"
    }},
    "openingHours": ["Mo 1000-1800", "Tu 1000-1800"]
}}
</script>
</head>
<body>
<ul class="rsx-list">
    <li>Mobile devices for business + consumer</li>
    <li>Residential: Internet + TV + Phone</li>
</ul>
{curbside_html}
</body>
</html>'''

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_extract_valid_store(self, mock_counter, mock_get):
        """Test extracting valid store data."""
        mock_response = Mock()
        mock_response.text = self._make_store_page_html()
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell-Queen-St-W/BE516'
        store = extract_store_details(mock_session, url)

        assert store is not None
        assert store.store_id == 'BE516'
        assert store.name == 'Bell'
        assert store.city == 'Toronto'
        assert store.state == 'ON'
        assert store.store_type == 'corporate'
        assert store.has_curbside is True

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_extract_dealer_store(self, mock_counter, mock_get):
        """Test extracting dealer store."""
        mock_response = Mock()
        mock_response.text = self._make_store_page_html(name='RWireless')
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/AB/Calgary/RWireless/BE725'
        store = extract_store_details(mock_session, url)

        assert store is not None
        assert store.store_type == 'authorized_dealer'

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_no_curbside(self, mock_counter, mock_get):
        """Test store without curbside pickup."""
        mock_response = Mock()
        mock_response.text = self._make_store_page_html(has_curbside=False)
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell/BE516'
        store = extract_store_details(mock_session, url)

        assert store is not None
        assert store.has_curbside is False

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_missing_json_ld(self, mock_counter, mock_get):
        """Test handling missing JSON-LD."""
        mock_response = Mock()
        mock_response.text = '<html><body>No schema</body></html>'
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell/BE516'
        store = extract_store_details(mock_session, url)

        assert store is None


class TestBellRun:
    """Tests for Bell run() function."""

    def _make_sitemap_response(self, store_ids):
        """Helper to create sitemap response."""
        urls = '\n'.join(
            f'<url><loc>https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell/BE{sid}</loc></url>'
            for sid in store_ids
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_response(self):
        """Helper to create store page response."""
        html = '''<!DOCTYPE html>
<html><head>
<script type="application/ld+json">
{
    "@type": "LocalBusiness",
    "name": "Bell",
    "telephone": "416 977-6969",
    "address": {
        "streetAddress": "316 Queen St W",
        "addressLocality": "Toronto",
        "addressRegion": "ON",
        "postalCode": "M5V2A2"
    }
}
</script>
</head><body></body></html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.bell.URLCache')
    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell.utils.random_delay')
    @patch('src.scrapers.bell._request_counter')
    def test_run_returns_structure(self, mock_counter, mock_delay, mock_get, mock_cache_class):
        """Test run() returns expected structure."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache
        mock_get.side_effect = [
            self._make_sitemap_response([516]),
            self._make_store_response()
        ]
        mock_session = Mock()

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='bell')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result

    @patch('src.scrapers.bell.URLCache')
    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell.utils.random_delay')
    @patch('src.scrapers.bell._request_counter')
    def test_run_with_limit(self, mock_counter, mock_delay, mock_get, mock_cache_class):
        """Test run() respects limit parameter."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache
        mock_get.side_effect = [
            self._make_sitemap_response([516, 517, 518, 519, 520]),
            self._make_store_response(),
            self._make_store_response(),
        ]
        mock_session = Mock()

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='bell', limit=2)

        assert result['count'] == 2

    @patch('src.scrapers.bell.URLCache')
    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_cache_class):
        """Test run() with empty sitemap."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response
        mock_session = Mock()

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='bell')

        assert result['stores'] == []
        assert result['count'] == 0


@pytest.fixture
def mock_session():
    """Fixture for mock session."""
    return Mock()
```

**Step 2: Run tests**

Run: `pytest tests/test_scrapers/test_bell.py -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/test_scrapers/test_bell.py
git commit -m "test(bell): Add comprehensive unit tests for Bell scraper"
```

---

## Task 10: Lint and Validate

**Files:**
- None (validation only)

**Step 1: Run pylint on new files**

Run: `pylint src/scrapers/bell.py config/bell_config.py`
Expected: Score >= 8.0 (fix any issues if lower)

**Step 2: Run all Bell tests**

Run: `pytest tests/test_scrapers/test_bell.py -v --tb=short`
Expected: All tests pass

**Step 3: Test CLI integration**

Run: `python run.py --retailer bell --test`
Expected: Scrapes ~10 stores in test mode (may take a few minutes due to rate limiting)

**Step 4: Push to remote**

```bash
git push -u origin feat/bell-scraper
```

---

## Task 11: Create Pull Request

**Files:**
- None (GitHub operations only)

**Step 1: Create PR**

```bash
gh pr create --title "feat: Add Bell Mobility store scraper" --body "$(cat <<'EOF'
## Summary
- Add Bell Mobility scraper for Canadian store locations
- Sitemap-based discovery (~251 stores)
- JSON-LD schema parsing for structured data
- Full extraction: address, phone, hours, services, store type

## Changes
- `src/scrapers/bell.py` - Main scraper module
- `config/bell_config.py` - Configuration constants
- `config/retailers.yaml` - Bell retailer config
- `src/scrapers/__init__.py` - Registry update
- `tests/test_scrapers/test_bell.py` - Unit tests

## Test plan
- [ ] `pytest tests/test_scrapers/test_bell.py -v`
- [ ] `python run.py --retailer bell --test`
- [ ] `pylint src/scrapers/bell.py config/bell_config.py`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 2: Verify PR created**

Run: `gh pr view --web`
Expected: PR opens in browser

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create feature branch | git |
| 2 | Bell config module | `config/bell_config.py` |
| 3 | Scraper dataclass + helpers | `src/scrapers/bell.py` |
| 4 | Sitemap fetching | `src/scrapers/bell.py` |
| 5 | Store extraction | `src/scrapers/bell.py` |
| 6 | Main run function | `src/scrapers/bell.py` |
| 7 | Register scraper | `src/scrapers/__init__.py` |
| 8 | YAML configuration | `config/retailers.yaml` |
| 9 | Unit tests | `tests/test_scrapers/test_bell.py` |
| 10 | Lint and validate | validation |
| 11 | Create PR | GitHub |
