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


def _format_schema_hours(opening_hours) -> Optional[str]:
    """Format schema.org openingHours to JSON string.

    Args:
        opening_hours: Hours in schema.org format - can be a single string
            or list of strings. Example: "Mo 1100-1800" or ["Su 1200-1700", ...]

    Returns:
        JSON string of formatted hours or None if no hours
    """
    if not opening_hours:
        return None

    # Normalize to list - schema.org allows single string or array
    if isinstance(opening_hours, str):
        opening_hours = [opening_hours]

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
    if store_name.lower().strip().startswith('bell'):
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
                if not script.string:
                    continue
                script_data = json.loads(script.string)
                if script_data.get('@type') == 'LocalBusiness':
                    data = script_data
                    break
            except (json.JSONDecodeError, TypeError):
                continue

        if not data:
            logging.debug(f"[{retailer}] No LocalBusiness schema found for {url}")
            return None

        # Extract store ID from URL (e.g., BE516)
        store_id_match = re.search(r'(BE\d+)$', data.get('url', url))
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
