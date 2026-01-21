"""Core scraping functions for AT&T Store Locator"""

import json
import logging
import random
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
import requests

from config import att_config
from src.shared import utils
from src.shared.request_counter import RequestCounter


# Global request counter
_request_counter = RequestCounter()


@dataclass
class ATTStore:
    """Data model for AT&T store information"""
    store_id: str
    name: str
    telephone: str
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    rating_value: Optional[float]
    rating_count: Optional[int]
    url: str
    sub_channel: str  # "COR" or "Dealer"
    dealer_name: Optional[str]  # Dealer name (e.g., "PRIME COMMUNICATIONS") or None for COR
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        return asdict(self)


def _check_pause_logic(yaml_config: dict = None, retailer: str = 'att') -> None:
    """Check if we need to pause based on request count.

    Args:
        yaml_config: Retailer configuration dict from retailers.yaml (optional for tests)
        retailer: Retailer name for logging
    """
    # If no config provided (tests), use hardcoded Python config values
    if yaml_config is None:
        pause_50_requests = att_config.PAUSE_50_REQUESTS
        pause_200_requests = att_config.PAUSE_200_REQUESTS
        pause_50_min = att_config.PAUSE_50_MIN
        pause_50_max = att_config.PAUSE_50_MAX
        pause_200_min = att_config.PAUSE_200_MIN
        pause_200_max = att_config.PAUSE_200_MAX
    else:
        # Read from YAML config (preferred)
        pause_50_requests = yaml_config.get('pause_50_requests', att_config.PAUSE_50_REQUESTS)
        pause_200_requests = yaml_config.get('pause_200_requests', att_config.PAUSE_200_REQUESTS)
        pause_50_min = yaml_config.get('pause_50_min', att_config.PAUSE_50_MIN)
        pause_50_max = yaml_config.get('pause_50_max', att_config.PAUSE_50_MAX)
        pause_200_min = yaml_config.get('pause_200_min', att_config.PAUSE_200_MIN)
        pause_200_max = yaml_config.get('pause_200_max', att_config.PAUSE_200_MAX)

    # Skip modulo operations if pauses are effectively disabled (>= 999999)
    if pause_50_requests >= 999999 and pause_200_requests >= 999999:
        return

    count = _request_counter.count

    if count % pause_200_requests == 0 and count > 0:
        pause_time = random.uniform(pause_200_min, pause_200_max)
        logging.info(f"[{retailer}] Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % pause_50_requests == 0 and count > 0:
        pause_time = random.uniform(pause_50_min, pause_50_max)
        logging.info(f"[{retailer}] Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)


# =============================================================================
# PARALLEL EXTRACTION - Speed up store detail extraction
# =============================================================================


def _create_session_factory(retailer_config: dict):
    """Create a factory function that produces per-worker sessions.

    requests.Session is NOT thread-safe, so each worker thread needs its own
    session instance. This factory creates new sessions with the same proxy
    configuration as the original.

    Args:
        retailer_config: Retailer configuration dict with proxy settings

    Returns:
        Callable that creates new session instances
    """
    def factory():
        return utils.create_proxied_session(retailer_config)
    return factory


def _extract_single_store(
    url: str,
    session_factory,
    retailer_name: str,
    yaml_config: dict = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Worker function for parallel store extraction.

    Creates its own session for thread safety and extracts store details.

    Args:
        url: Store URL to extract
        session_factory: Callable that creates session instances
        retailer_name: Name of retailer for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        Tuple of (url, store_data_dict) where store_data_dict is None on failure
    """
    session = session_factory()
    try:
        store_obj = extract_store_details(session, url, retailer_name, yaml_config)
        if store_obj:
            return (url, store_obj.to_dict())
        return (url, None)
    except Exception as e:
        logging.warning(f"[{retailer_name}] Error extracting {url}: {e}")
        return (url, None)
    finally:
        # Clean up session resources
        if hasattr(session, 'close'):
            session.close()


def _extract_store_type_and_dealer(html_content: str) -> tuple:
    """
    Extract store type (COR or Dealer) and dealer name from AT&T store page HTML.

    Looks for JavaScript variables in the page:
    - topDisplayType: "AT&T Retail" (COR) or "Authorized Retail" (Dealer)
    - storeMasterDealer: Dealer name with suffix (e.g., "PRIME COMMUNICATIONS - 58")

    Args:
        html_content: Raw HTML content of store page

    Returns:
        Tuple of (sub_channel, dealer_name)
        - sub_channel: "COR" or "Dealer"
        - dealer_name: Dealer name string or None for COR stores
    """
    # Extract topDisplayType JavaScript variable
    # Use backreference (\1) to ensure opening and closing quotes match
    # This prevents matching mismatched quotes like 'value" or "value'
    display_type_match = re.search(
        r"let\s+topDisplayType\s*=\s*(['\"])([^'\"]+)\1",
        html_content
    )

    # Extract storeMasterDealer JavaScript variable
    # Use backreference (\1) to ensure opening and closing quotes match
    dealer_match = re.search(
        r"storeMasterDealer:\s*(['\"])([^'\"]+)\1",
        html_content
    )
    
    # Group 1 is the quote character, group 2 is the actual value
    display_type = display_type_match.group(2) if display_type_match else None
    dealer_raw = dealer_match.group(2) if dealer_match else None
    
    # Determine sub_channel and dealer_name based on display type
    if display_type == "AT&T Retail":
        # Corporate store
        sub_channel = "COR"
        dealer_name = None
    elif display_type == "Authorized Retail":
        # Dealer store
        sub_channel = "Dealer"
        # Clean dealer name - remove trailing dash and number suffix (e.g., " - 58")
        if dealer_raw:
            dealer_name = re.sub(r'\s*-\s*\d+\s*$', '', dealer_raw)
        else:
            dealer_name = None
    else:
        # Unable to determine - default to COR
        logging.debug(f"[att] Unknown display type: {display_type}, defaulting to COR")
        sub_channel = "COR"
        dealer_name = None
    
    return sub_channel, dealer_name


def get_store_urls_from_sitemap(
    session: requests.Session,
    retailer: str = 'att',
    yaml_config: dict = None
) -> List[str]:
    """Fetch all store URLs from the AT&T sitemap.

    Args:
        session: Requests session object
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        List of store URLs (filtered to only those ending in numeric IDs)
    """
    logging.info(f"[{retailer}] Fetching sitemap from {att_config.SITEMAP_URL}")

    response = utils.get_with_retry(session, att_config.SITEMAP_URL)
    if not response:
        logging.error(f"[{retailer}] Failed to fetch sitemap")
        return []

    _request_counter.increment()
    _check_pause_logic(yaml_config, retailer)

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

        # Filter to only store URLs (ending in numeric ID)
        store_urls = []
        for url in all_urls:
            # Extract the last segment of the URL path
            url_parts = url.rstrip('/').split('/')
            if url_parts:
                last_segment = url_parts[-1]
                # Check if it's a numeric ID (store page)
                if last_segment.isdigit():
                    store_urls.append(url)

        logging.info(f"[{retailer}] Filtered to {len(store_urls)} store URLs (ending in numeric IDs)")

        return store_urls

    except ET.ParseError as e:
        logging.error(f"[{retailer}] Failed to parse XML sitemap: {e}")
        return []
    except Exception as e:
        logging.error(f"[{retailer}] Unexpected error parsing sitemap: {e}")
        return []


def extract_store_details(
    session: requests.Session,
    url: str,
    retailer: str = 'att',
    yaml_config: dict = None
) -> Optional[ATTStore]:
    """Extract store data from a single AT&T store page.

    Args:
        session: Requests session object
        url: Store page URL
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        ATTStore object if successful, None otherwise
    """
    logging.debug(f"[{retailer}] Extracting details from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store details: {url}")
        return None

    _request_counter.increment()
    _check_pause_logic(yaml_config, retailer)

    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract store type (COR/Dealer) and dealer name from HTML
        sub_channel, dealer_name = _extract_store_type_and_dealer(response.text)

        # Find all JSON-LD script tags (there may be multiple)
        scripts = soup.find_all('script', type='application/ld+json')
        if not scripts:
            logging.warning(f"[{retailer}] No JSON-LD found for {url}")
            return None

        # Try each script until we find a MobilePhoneStore
        data = None
        for script in scripts:
            try:
                script_data = json.loads(script.string)
                if script_data.get('@type') == 'MobilePhoneStore':
                    data = script_data
                    break
            except json.JSONDecodeError as e:
                logging.debug(f"[{retailer}] Failed to parse JSON-LD script for {url}: {e}")
                continue

        # If no MobilePhoneStore found, log and return None
        if not data:
            if scripts:
                first_type = json.loads(scripts[0].string).get('@type', 'Unknown') if scripts[0].string else 'Unknown'
                logging.debug(f"[{retailer}] Skipping {url}: No MobilePhoneStore found (first @type: '{first_type}')")
            return None

        # Extract store ID from URL
        url_parts = url.rstrip('/').split('/')
        store_id = url_parts[-1] if url_parts else ''

        # Extract address components
        address = data.get('address', {})

        # Handle nested addressCountry structure
        address_country = address.get('addressCountry', {})
        if isinstance(address_country, dict):
            country = address_country.get('name', 'US')
        else:
            country = address_country if address_country else 'US'

        # Extract rating if available
        rating = data.get('aggregateRating', {})
        rating_value = None
        rating_count = None

        if rating:
            rating_val = rating.get('ratingValue')
            if rating_val:
                try:
                    rating_value = float(rating_val)
                except (ValueError, TypeError):
                    rating_value = None

            rating_cnt = rating.get('ratingCount')
            if rating_cnt:
                try:
                    rating_count = int(rating_cnt)
                except (ValueError, TypeError):
                    rating_count = None

        # Create ATTStore object
        store = ATTStore(
            store_id=store_id,
            name=data.get('name', ''),
            telephone=data.get('telephone', ''),
            street_address=address.get('streetAddress', ''),
            city=address.get('addressLocality', ''),
            state=address.get('addressRegion', ''),
            postal_code=address.get('postalCode', ''),
            country=country,
            rating_value=rating_value,
            rating_count=rating_count,
            url=url,
            sub_channel=sub_channel,
            dealer_name=dealer_name,
            scraped_at=datetime.now().isoformat()
        )

        dealer_info = f" - {dealer_name}" if dealer_name else ""
        logging.debug(f"[{retailer}] Extracted store: %s (%s%s)", store.name, sub_channel, dealer_info)
        return store

    except Exception as e:
        logging.warning(f"[{retailer}] Error extracting store data from {url}: {e}")
        return None


def reset_request_counter() -> None:
    """Reset the global request counter"""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count


# =============================================================================
# URL CACHING - Skip sitemap fetch on subsequent runs
# =============================================================================

# Default cache expiry: 7 days (stores don't change location frequently)
URL_CACHE_EXPIRY_DAYS = 7


def _get_url_cache_path(retailer: str) -> Path:
    """Get path to store URL cache file."""
    return Path(f"data/{retailer}/store_urls.json")


def _load_cached_urls(retailer: str, max_age_days: int = URL_CACHE_EXPIRY_DAYS) -> Optional[List[str]]:
    """Load cached store URLs if recent enough.

    Args:
        retailer: Retailer name
        max_age_days: Maximum cache age in days (default: 7)

    Returns:
        List of cached URLs if cache is valid, None otherwise
    """
    cache_path = _get_url_cache_path(retailer)

    if not cache_path.exists():
        logging.info(f"[{retailer}] No URL cache found at {cache_path}")
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        # Check cache freshness
        discovered_at = cache_data.get('discovered_at')
        if discovered_at:
            cache_time = datetime.fromisoformat(discovered_at)
            age_days = (datetime.now() - cache_time).days

            if age_days > max_age_days:
                logging.info(f"[{retailer}] URL cache expired ({age_days} days old, max: {max_age_days})")
                return None

            urls = cache_data.get('urls', [])
            if urls:
                logging.info(f"[{retailer}] Loaded {len(urls)} URLs from cache ({age_days} days old)")
                return urls

        logging.warning(f"[{retailer}] URL cache is invalid or empty")
        return None

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logging.warning(f"[{retailer}] Error loading URL cache: {e}")
        return None


def _save_cached_urls(retailer: str, urls: List[str]) -> None:
    """Save discovered store URLs to cache.

    Args:
        retailer: Retailer name
        urls: List of store URLs to cache
    """
    cache_path = _get_url_cache_path(retailer)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_data = {
        'discovered_at': datetime.now().isoformat(),
        'store_count': len(urls),
        'urls': urls
    }

    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        logging.info(f"[{retailer}] Saved {len(urls)} URLs to cache: {cache_path}")
    except IOError as e:
        logging.warning(f"[{retailer}] Failed to save URL cache: {e}")


def run(session, config: dict, **kwargs) -> dict:
    """Standard scraper entry point with parallel extraction and URL caching.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - resume: bool - Resume from checkpoint
            - limit: int - Max stores to process
            - incremental: bool - Only process changes
            - refresh_urls: bool - Force URL re-discovery (ignore cache)

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = kwargs.get('retailer', 'att')
    logging.info(f"[{retailer_name}] Starting scrape run")

    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        refresh_urls = kwargs.get('refresh_urls', False)

        reset_request_counter()

        # Auto-select delays based on proxy mode for optimal performance
        proxy_mode = config.get('proxy', {}).get('mode', 'direct')
        min_delay, max_delay = utils.select_delays(config, proxy_mode)
        logging.info(f"[{retailer_name}] Using delays: {min_delay:.1f}-{max_delay:.1f}s (mode: {proxy_mode})")

        # Get parallel workers count (default: 5 for residential proxy, 1 for direct)
        default_workers = 5 if proxy_mode in ('residential', 'web_scraper_api') else 1
        parallel_workers = config.get('parallel_workers', default_workers)
        logging.info(f"[{retailer_name}] Parallel workers: {parallel_workers}")

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        # Increase checkpoint interval when using parallel workers (less frequent saves)
        base_checkpoint_interval = config.get('checkpoint_interval', 100)
        checkpoint_interval = base_checkpoint_interval * max(1, parallel_workers) if parallel_workers > 1 else base_checkpoint_interval

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

        # Try to load cached URLs (skip sitemap fetch if cache is valid)
        store_urls = None
        if not refresh_urls:
            store_urls = _load_cached_urls(retailer_name)

        if store_urls is None:
            # Cache miss or refresh requested - fetch from sitemap
            store_urls = get_store_urls_from_sitemap(session, retailer_name, yaml_config=config)
            logging.info(f"[{retailer_name}] Found {len(store_urls)} store URLs from sitemap")

            # Save to cache for future runs
            if store_urls:
                _save_cached_urls(retailer_name, store_urls)
        else:
            logging.info(f"[{retailer_name}] Using {len(store_urls)} cached store URLs")

        if not store_urls:
            logging.warning(f"[{retailer_name}] No store URLs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        remaining_urls = [url for url in store_urls if url not in completed_urls]

        if resume and completed_urls:
            logging.info(f"[{retailer_name}] Skipping {len(store_urls) - len(remaining_urls)} already-processed stores from checkpoint")

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

        # Use parallel extraction if workers > 1
        if parallel_workers > 1 and total_to_process > 0:
            logging.info(f"[{retailer_name}] Using parallel extraction with {parallel_workers} workers")

            # Create session factory for parallel workers (each worker needs its own session)
            session_factory = _create_session_factory(config)

            # Thread-safe counter for progress
            processed_count = [0]  # Use list for mutable closure
            processed_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                # Submit all extraction tasks
                futures = {
                    executor.submit(_extract_single_store, url, session_factory, retailer_name, config): url
                    for url in remaining_urls
                }

                for future in as_completed(futures):
                    url, store_data = future.result()

                    with processed_lock:
                        processed_count[0] += 1
                        current_count = processed_count[0]

                        if store_data:
                            stores.append(store_data)
                            completed_urls.add(url)

                        # Progress logging every 25 stores for more frequent updates
                        if current_count % 25 == 0:
                            logging.info(f"[{retailer_name}] Progress: {current_count}/{total_to_process} ({current_count/total_to_process*100:.1f}%) - {len(stores)} stores extracted")

                        # Checkpoint at intervals
                        if current_count % checkpoint_interval == 0:
                            utils.save_checkpoint({
                                'completed_count': len(stores),
                                'completed_urls': list(completed_urls),
                                'stores': stores,
                                'last_updated': datetime.now().isoformat()
                            }, checkpoint_path)
                            logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores processed")
        else:
            # Sequential extraction (original behavior for direct mode)
            for i, url in enumerate(remaining_urls, 1):
                store_obj = extract_store_details(session, url, retailer_name, yaml_config=config)
                if store_obj:
                    stores.append(store_obj.to_dict())
                    completed_urls.add(url)

                    # Log successful extraction every 10 stores for more frequent updates
                    if i % 10 == 0:
                        logging.info(f"[{retailer_name}] Extracted {len(stores)} stores so far ({i}/{total_to_process})")

                # Progress logging every 100 stores
                if i % 100 == 0:
                    logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")

                if i % checkpoint_interval == 0:
                    utils.save_checkpoint({
                        'completed_count': len(stores),
                        'completed_urls': list(completed_urls),
                        'stores': stores,
                        'last_updated': datetime.now().isoformat()
                    }, checkpoint_path)
                    logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores processed")

        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_urls': list(completed_urls),
                'stores': stores,
                'last_updated': datetime.now().isoformat()
            }, checkpoint_path)
            logging.info(f"[{retailer_name}] Final checkpoint saved: {len(stores)} stores total")

        logging.info(f"[{retailer_name}] Completed: {len(stores)} stores successfully scraped")

        return {
            'stores': stores,
            'count': len(stores),
            'checkpoints_used': checkpoints_used
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
