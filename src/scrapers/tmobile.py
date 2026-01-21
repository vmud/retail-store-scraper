"""Core scraping functions for T-Mobile Store Locator"""

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

from config import tmobile_config
from src.shared import utils
from src.shared.request_counter import RequestCounter


# Global request counter
_request_counter = RequestCounter()


@dataclass
class TMobileStore:
    """Data model for T-Mobile store information"""
    store_id: str
    branch_code: str
    name: str
    phone: str
    street_address: str
    city: str
    state: str
    zip: str
    country: str
    latitude: str
    longitude: str
    url: str
    scraped_at: str
    # Optional fields with defaults (must come after required fields)
    store_type: Optional[str] = None
    opening_hours: Optional[List[str]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        result = asdict(self)
        # Convert opening_hours list to JSON string for CSV compatibility
        if result.get('opening_hours'):
            result['opening_hours'] = json.dumps(result['opening_hours'])
        elif result.get('opening_hours') is None:
            result['opening_hours'] = ''  # Empty string for CSV when None
        # Handle store_type (Optional[str]) - convert None to empty string for CSV
        if result.get('store_type') is None:
            result['store_type'] = ''  # Empty string for CSV when None
        return result


def _check_pause_logic(retailer: str = 'tmobile') -> None:
    """Check if we need to pause based on request count"""
    # Skip modulo operations if pauses are effectively disabled (>= 999999)
    try:
        if tmobile_config.PAUSE_50_REQUESTS >= 999999 and tmobile_config.PAUSE_200_REQUESTS >= 999999:
            return
    except (TypeError, AttributeError):
        pass  # Config mocked in tests, continue with normal pause logic
    
    count = _request_counter.count

    if count % tmobile_config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(tmobile_config.PAUSE_200_MIN, tmobile_config.PAUSE_200_MAX)
        logging.info(f"[{retailer}] Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % tmobile_config.PAUSE_50_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(tmobile_config.PAUSE_50_MIN, tmobile_config.PAUSE_50_MAX)
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
        store_obj = extract_store_details(session, url, retailer_name)
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


def _extract_store_type_from_title(page_title: str) -> Optional[str]:
    """Extract store type from T-Mobile store page title.

    Args:
        page_title: The HTML <title> content from a store detail page

    Returns:
        Normalized store type string, or None if not found

    Examples:
        >>> _extract_store_type_from_title("T-Mobile Penn & I-494: Experience Store in Bloomington, MN")
        'T-Mobile Experience Store'

        >>> _extract_store_type_from_title("T-Mobile The Richfield Hub: Authorized Retailer in Richfield, MN")
        'T-Mobile Authorized Retailer'
    """
    patterns = [
        (r':\s*(Authorized Retailer)\s+in', 'T-Mobile Authorized Retailer'),
        (r':\s*(Experience Store)\s+in', 'T-Mobile Experience Store'),
        (r':\s*(Neighborhood Store)\s+in', 'T-Mobile Neighborhood Store'),
        (r':\s*(Store)\s+in', 'T-Mobile Store'),
    ]

    for pattern, store_type in patterns:
        if re.search(pattern, page_title, re.IGNORECASE):
            return store_type

    return None


def _extract_store_type_from_dom(soup: BeautifulSoup) -> Optional[str]:
    """Extract store type from page DOM as fallback.

    Args:
        soup: BeautifulSoup parsed HTML

    Returns:
        Normalized store type string, or None if not found
    """
    store_types = [
        'T-Mobile Experience Store',
        'T-Mobile Authorized Retailer',
        'T-Mobile Neighborhood Store',
        'T-Mobile Store'
    ]

    page_text = soup.get_text()
    for store_type in store_types:
        if store_type in page_text:
            return store_type

    return None


def get_store_urls_from_sitemap(session: requests.Session, retailer: str = 'tmobile') -> List[str]:
    """Fetch all store URLs from the T-Mobile paginated sitemaps.

    Returns:
        List of retail store URLs (excludes service pages like business-internet, home-internet)
    """
    all_store_urls = []

    for page in tmobile_config.SITEMAP_PAGES:
        if page == 1:
            sitemap_url = tmobile_config.SITEMAP_BASE_URL
        else:
            sitemap_url = f"{tmobile_config.SITEMAP_BASE_URL}?p={page}"

        logging.info(f"[{retailer}] Fetching sitemap page {page} from {sitemap_url}")

        response = utils.get_with_retry(session, sitemap_url)
        if not response:
            logging.error(f"[{retailer}] Failed to fetch sitemap page {page}")
            continue

        _request_counter.increment()
        _check_pause_logic(retailer)

        try:
            # Parse XML
            root = ET.fromstring(response.content)
            namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # Extract all URLs
            for loc in root.findall(".//sm:loc", namespace):
                url = loc.text
                if url and '/stores/bd/' in url:
                    # Filter out service pages (business-internet, home-internet)
                    # Only include actual retail store URLs that start with 't-mobile-'
                    if 'business-internet' not in url and 'home-internet' not in url:
                        all_store_urls.append(url)

            logging.info(f"[{retailer}] Found {len(all_store_urls)} retail store URLs from page {page}")

        except ET.ParseError as e:
            logging.error(f"[{retailer}] Failed to parse XML sitemap page {page}: {e}")
            continue
        except Exception as e:
            logging.error(f"[{retailer}] Unexpected error parsing sitemap page {page}: {e}")
            continue

    logging.info(f"[{retailer}] Total retail store URLs collected: {len(all_store_urls)}")
    return all_store_urls


def extract_store_details(session: requests.Session, url: str, retailer: str = 'tmobile') -> Optional[TMobileStore]:
    """Extract store data from a single T-Mobile store page.

    Args:
        session: Requests session object
        url: Store page URL

    Returns:
        TMobileStore object if successful, None otherwise
    """
    logging.debug(f"[{retailer}] Extracting details from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store details: {url}")
        return None

    _request_counter.increment()
    _check_pause_logic(retailer)

    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract store type from page title (with DOM fallback)
        store_type = None
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            store_type = _extract_store_type_from_title(title_tag.string)

        # Fallback to DOM extraction if title parsing fails
        if not store_type:
            store_type = _extract_store_type_from_dom(soup)

        # Find all JSON-LD script tags (there may be multiple)
        scripts = soup.find_all('script', type='application/ld+json')
        if not scripts:
            logging.warning(f"[{retailer}] No JSON-LD found for {url}")
            return None

        # Try each script until we find a Store
        data = None
        for script in scripts:
            try:
                script_content = script.string
                if not script_content:
                    continue

                script_data = json.loads(script_content)

                # Handle both single objects and arrays
                if isinstance(script_data, list):
                    for item in script_data:
                        if item.get('@type') == 'Store':
                            data = item
                            break
                elif script_data.get('@type') == 'Store':
                    data = script_data

                if data:
                    break

            except json.JSONDecodeError as e:
                logging.debug(f"[{retailer}] Failed to parse JSON-LD script for {url}: {e}")
                continue

        # If no Store found, log and return None
        if not data:
            if scripts:
                try:
                    first_script = json.loads(scripts[0].string) if scripts[0].string else {}
                    first_type = first_script.get('@type', 'Unknown') if isinstance(first_script, dict) else 'Unknown'
                    if isinstance(first_script, list) and first_script:
                        first_type = first_script[0].get('@type', 'Unknown') if isinstance(first_script[0], dict) else 'Unknown'
                    logging.debug(f"[{retailer}] Skipping {url}: No Store found (first @type: '{first_type}')")
                except Exception:
                    logging.debug(f"[{retailer}] Skipping {url}: No Store found")
            return None

        # Extract address components
        address = data.get('address', {})

        # Handle addressCountry (can be string or object)
        address_country = address.get('addressCountry', 'US')
        if isinstance(address_country, dict):
            country = address_country.get('name', 'US')
        else:
            country = address_country if address_country else 'US'

        # Extract geo coordinates
        geo = data.get('geo', {})
        latitude = geo.get('latitude', '')
        longitude = geo.get('longitude', '')

        # Extract openingHours (array)
        opening_hours = data.get('openingHours', [])
        if isinstance(opening_hours, str):
            # If it's a single string, convert to list
            opening_hours = [opening_hours]

        # Extract branchCode (used as store_id)
        branch_code = data.get('branchCode', '')

        # Create TMobileStore object
        store = TMobileStore(
            store_id=branch_code,  # Use branch_code as the unique store identifier
            branch_code=branch_code,
            name=data.get('name', ''),
            store_type=store_type,
            phone=data.get('telephone', ''),
            street_address=address.get('streetAddress', ''),
            city=address.get('addressLocality', ''),
            state=address.get('addressRegion', ''),
            zip=address.get('postalCode', ''),
            country=country,
            latitude=str(latitude) if latitude else '',
            longitude=str(longitude) if longitude else '',
            opening_hours=opening_hours if opening_hours else None,
            url=url,
            scraped_at=datetime.now().isoformat()
        )

        logging.debug(f"[{retailer}] Extracted store: {store.name}")
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
    retailer_name = kwargs.get('retailer', 'tmobile')
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
            store_urls = get_store_urls_from_sitemap(session, retailer_name)
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

        # Track failed URLs for logging
        failed_urls = []

        # Use parallel extraction if workers > 1
        if parallel_workers > 1 and total_to_process > 0:
            logging.info(f"[{retailer_name}] Using parallel extraction with {parallel_workers} workers")

            # Create session factory for parallel workers (each worker needs its own session)
            session_factory = _create_session_factory(config)

            # Thread-safe counters for progress
            processed_count = [0]  # Use list for mutable closure
            successful_count = [0]
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
                            successful_count[0] += 1
                        else:
                            failed_urls.append(url)

                        # Progress logging every 25 stores for more frequent updates
                        if current_count % 25 == 0:
                            success_rate = (successful_count[0] / current_count * 100) if current_count > 0 else 0
                            logging.info(
                                f"[{retailer_name}] Progress: {current_count}/{total_to_process} "
                                f"({current_count/total_to_process*100:.1f}%) - "
                                f"{successful_count[0]} stores extracted ({success_rate:.0f}% success)"
                            )

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
                store_obj = extract_store_details(session, url, retailer_name)
                if store_obj:
                    stores.append(store_obj.to_dict())
                    completed_urls.add(url)

                    # Log successful extraction every 10 stores for more frequent updates
                    if i % 10 == 0:
                        logging.info(f"[{retailer_name}] Extracted {len(stores)} stores so far ({i}/{total_to_process})")
                else:
                    failed_urls.append(url)

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

        # Log failed extractions
        if failed_urls:
            logging.warning(f"[{retailer_name}] Failed to extract {len(failed_urls)} stores:")
            for failed_url in failed_urls[:10]:  # Log first 10
                logging.warning(f"[{retailer_name}]   - {failed_url}")
            if len(failed_urls) > 10:
                logging.warning(f"[{retailer_name}]   ... and {len(failed_urls) - 10} more")

            # Save failed URLs to file for followup
            failed_path = Path(f"data/{retailer_name}/failed_extractions.json")
            failed_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(failed_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'run_date': datetime.now().isoformat(),
                        'failed_count': len(failed_urls),
                        'failed_urls': failed_urls
                    }, f, indent=2)
                logging.info(f"[{retailer_name}] Saved {len(failed_urls)} failed URLs to {failed_path}")
            except IOError as e:
                logging.warning(f"[{retailer_name}] Failed to save failed URLs: {e}")

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
