"""Core scraping functions for Walmart Store Locator"""

import gzip
import hashlib
import json
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from config import walmart_config
from src.shared import utils
from src.shared.request_counter import RequestCounter
from src.shared.proxy_client import ProxyClient, ProxyConfig, ProxyMode


# Global request counter
_request_counter = RequestCounter()


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


# =============================================================================
# RESPONSE CACHING - Avoid expensive Web Scraper API re-fetches
# =============================================================================

# Default response cache expiry: 30 days (store pages rarely change structure)
RESPONSE_CACHE_EXPIRY_DAYS = 30


def _get_response_cache_dir(retailer: str) -> Path:
    """Get directory for response cache files."""
    return Path(f"data/{retailer}/response_cache")


def _get_cached_response(url: str, retailer: str) -> Optional[str]:
    """Check cache for stored Web Scraper API response.

    Args:
        url: Store page URL
        retailer: Retailer name

    Returns:
        Cached HTML response if valid, None otherwise
    """
    cache_dir = _get_response_cache_dir(retailer)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = cache_dir / f"{url_hash}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cached_at = data.get('cached_at')
        if cached_at:
            cached_time = datetime.fromisoformat(cached_at)
            age = datetime.now() - cached_time

            if age < timedelta(days=RESPONSE_CACHE_EXPIRY_DAYS):
                logging.debug(f"[{retailer}] Cache hit for {url}")
                return data.get('html')
            else:
                logging.debug(f"[{retailer}] Response cache expired for {url}")

        return None

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logging.debug(f"[{retailer}] Error reading response cache: {e}")
        return None


def _cache_response(url: str, html: str, retailer: str) -> None:
    """Cache Web Scraper API response to avoid re-fetching.

    Args:
        url: Store page URL
        html: HTML response content
        retailer: Retailer name
    """
    cache_dir = _get_response_cache_dir(retailer)
    cache_dir.mkdir(parents=True, exist_ok=True)

    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_file = cache_dir / f"{url_hash}.json"

    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'url': url,
                'cached_at': datetime.now().isoformat(),
                'html': html
            }, f)
        logging.debug(f"[{retailer}] Cached response for {url}")
    except IOError as e:
        logging.warning(f"[{retailer}] Failed to cache response: {e}")


@dataclass
class WalmartStore:
    """Data model for Walmart store information"""
    store_id: str
    store_type: str
    name: str
    phone_number: str
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    capabilities: Optional[List[str]]
    is_glass_eligible: bool
    url: str
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        result = asdict(self)
        # Convert capabilities list to JSON string for CSV compatibility
        if result.get('capabilities'):
            result['capabilities'] = json.dumps(result['capabilities'])
        elif result.get('capabilities') is None:
            result['capabilities'] = ''  # Empty string for CSV when None
        # Convert numeric types to appropriate format
        if result.get('latitude') is None:
            result['latitude'] = ''
        else:
            result['latitude'] = str(result['latitude'])
        if result.get('longitude') is None:
            result['longitude'] = ''
        else:
            result['longitude'] = str(result['longitude'])
        # Convert boolean fields to strings for CSV compatibility
        if result.get('is_glass_eligible') is None:
            result['is_glass_eligible'] = False
        result['is_glass_eligible'] = 'True' if result['is_glass_eligible'] else 'False'
        return result


def _check_pause_logic(retailer: str = 'walmart') -> None:
    """Check if we need to pause based on request count"""
    # Skip modulo operations if pauses are effectively disabled (>= 999999)
    try:
        if walmart_config.PAUSE_50_REQUESTS >= 999999 and walmart_config.PAUSE_200_REQUESTS >= 999999:
            return
    except (TypeError, AttributeError):
        pass  # Config mocked in tests, continue with normal pause logic
    
    count = _request_counter.count

    if count % walmart_config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(walmart_config.PAUSE_200_MIN, walmart_config.PAUSE_200_MAX)
        logging.info(f"[{retailer}] Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % walmart_config.PAUSE_50_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(walmart_config.PAUSE_50_MIN, walmart_config.PAUSE_50_MAX)
        logging.info(f"[{retailer}] Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)


def get_store_urls_from_sitemap(session: requests.Session, retailer: str = 'walmart') -> List[str]:
    """Fetch all store URLs from the Walmart gzipped sitemaps.

    Returns:
        List of store URLs from all sitemap types
    """
    all_store_urls = []

    for sitemap_url in walmart_config.SITEMAP_URLS:
        logging.info(f"[{retailer}] Fetching sitemap: {sitemap_url}")

        response = utils.get_with_retry(session, sitemap_url)
        if not response:
            logging.error(f"[{retailer}] Failed to fetch sitemap: {sitemap_url}")
            continue

        _request_counter.increment()
        _check_pause_logic(retailer)

        try:
            # Try to decompress gzipped content, fall back to plain text if not gzipped
            try:
                xml_content = gzip.decompress(response.content).decode('utf-8')
            except (gzip.BadGzipFile, OSError):
                # Content is not gzipped, try as plain text
                logging.debug(f"[{retailer}] Content from {sitemap_url} is not gzipped, using plain text")
                xml_content = response.content.decode('utf-8')

            # Parse XML
            root = ET.fromstring(xml_content)
            namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # Extract all URLs
            sitemap_urls = []
            for loc in root.findall(".//sm:loc", namespace):
                url = loc.text
                if url:
                    sitemap_urls.append(url)

            all_store_urls.extend(sitemap_urls)
            logging.info(f"[{retailer}] Found {len(sitemap_urls)} store URLs from {sitemap_url}")
        except ET.ParseError as e:
            logging.error(f"[{retailer}] Failed to parse XML sitemap {sitemap_url}: {e}")
            continue
        except Exception as e:
            logging.error(f"[{retailer}] Unexpected error processing sitemap {sitemap_url}: {e}")
            continue

    logging.info(f"[{retailer}] Total store URLs collected: {len(all_store_urls)}")
    return all_store_urls


def extract_store_details(client, url: str, retailer: str = 'walmart', use_cache: bool = True) -> Optional[WalmartStore]:
    """Extract store data from a single Walmart store page.

    Args:
        client: ProxyClient or requests.Session to use for fetching
        url: Store page URL
        retailer: Retailer name for logging
        use_cache: Whether to use response caching (default: True)

    Returns:
        WalmartStore object if successful, None otherwise
    """
    logging.debug(f"[{retailer}] Extracting details from {url}")

    response_text = None
    from_cache = False

    # Check response cache first (avoid expensive Web Scraper API call)
    if use_cache:
        cached_html = _get_cached_response(url, retailer)
        if cached_html:
            response_text = cached_html
            from_cache = True

    # If not cached, fetch from API
    if not response_text:
        # Use ProxyClient.get() if available (for Web Scraper API with JS rendering)
        # Otherwise fall back to utils.get_with_retry for regular sessions
        if hasattr(client, 'get') and callable(getattr(client, 'get')):
            # ProxyClient - use .get() method for proper Web Scraper API handling
            proxy_response = client.get(url)
            if not proxy_response or proxy_response.status_code != 200:
                logging.warning(f"[{retailer}] Failed to fetch store details: {url} (status={proxy_response.status_code if proxy_response else 'None'})")
                return None
            response_text = proxy_response.text
        else:
            # Regular requests.Session - use utils.get_with_retry
            response = utils.get_with_retry(client, url)
            if not response:
                logging.warning(f"[{retailer}] Failed to fetch store details: {url}")
                return None
            response_text = response.text

        _request_counter.increment()
        _check_pause_logic(retailer)

        # Cache the response for future runs (only if not from cache)
        if use_cache and response_text:
            _cache_response(url, response_text, retailer)

    try:
        # Use BeautifulSoup to extract __NEXT_DATA__ script tag
        # This is more robust than regex as it properly handles embedded scripts
        # that might contain </script> within JSON string values
        soup = BeautifulSoup(response_text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__', type='application/json')

        if not script_tag or not script_tag.string:
            logging.warning(f"[{retailer}] No __NEXT_DATA__ script tag found for {url}")
            logging.warning(f"[{retailer}] Walmart requires JavaScript rendering. Enable proxy with render_js=true in config/retailers.yaml")
            return None

        # Parse JSON from script tag
        try:
            data = json.loads(script_tag.string)
        except json.JSONDecodeError as e:
            logging.warning(f"[{retailer}] Failed to parse JSON from __NEXT_DATA__ for {url}: {e}")
            return None

        # Navigate to store data in Next.js structure: props.pageProps.initialData.initialDataNodeDetail.data.nodeDetail
        page_props = data.get('props', {})
        if not page_props:
            logging.warning(f"[{retailer}] No 'props' found in __NEXT_DATA__ for {url}")
            return None

        initial_data = page_props.get('pageProps', {}).get('initialData', {})
        if not initial_data:
            logging.warning(f"[{retailer}] No 'initialData' found in props.pageProps for {url}")
            return None

        node_detail_wrapper = initial_data.get('initialDataNodeDetail', {})
        if not node_detail_wrapper:
            logging.warning(f"[{retailer}] No 'initialDataNodeDetail' found in initialData for {url}")
            return None

        store_data = node_detail_wrapper.get('data', {}).get('nodeDetail', {})
        if not store_data:
            logging.warning(f"[{retailer}] No 'nodeDetail' found in data for {url}")
            return None

        # Extract store ID (from store_data.id or URL pattern)
        store_id = store_data.get('id', '')
        if not store_id:
            # Fallback: extract from URL pattern /store/{storeId}-{city}-{state}
            url_match = re.search(r'/store/(\d+)-', url)
            if url_match:
                store_id = url_match.group(1)

        # Extract address components
        address = store_data.get('address', {})

        # Extract geoPoint
        geo_point = store_data.get('geoPoint', {})
        latitude = geo_point.get('latitude') if geo_point else None
        longitude = geo_point.get('longitude') if geo_point else None

        # Convert latitude/longitude to float if they're strings
        if latitude is not None:
            try:
                latitude = float(latitude)
            except (ValueError, TypeError):
                latitude = None
        if longitude is not None:
            try:
                longitude = float(longitude)
            except (ValueError, TypeError):
                longitude = None

        # Extract capabilities (array)
        capabilities = store_data.get('capabilities', [])
        if capabilities is None:
            capabilities = []

        # Extract isGlassEligible (boolean, default to False if missing)
        is_glass_eligible = store_data.get('isGlassEligible', False)
        if is_glass_eligible is None:
            is_glass_eligible = False

        # Extract store type (name field typically contains "Supercenter", "Neighborhood Market", etc.)
        store_type = store_data.get('name', '')  # e.g., "Walmart Supercenter"
        # If store_type contains "Supercenter", "Neighborhood Market", etc., extract it
        if 'Supercenter' in store_type:
            store_type_clean = 'Supercenter'
        elif 'Neighborhood Market' in store_type:
            store_type_clean = 'Neighborhood Market'
        elif 'Discount' in store_type:
            store_type_clean = 'Discount Store'
        else:
            store_type_clean = store_type or 'Other'

        # Extract displayName for the actual store name
        display_name = store_data.get('displayName', store_data.get('name', ''))

        # Create WalmartStore object
        store = WalmartStore(
            store_id=store_id,
            store_type=store_type_clean,
            name=display_name,
            phone_number=store_data.get('phoneNumber', ''),
            street_address=address.get('addressLineOne', ''),
            city=address.get('city', ''),
            state=address.get('state', ''),
            postal_code=address.get('postalCode', ''),
            country=address.get('country', 'US'),
            latitude=latitude,
            longitude=longitude,
            capabilities=capabilities if capabilities else None,
            is_glass_eligible=bool(is_glass_eligible),
            url=url,
            scraped_at=datetime.now().isoformat()
        )

        logging.debug(f"[{retailer}] Extracted store: {store.name} ({store.store_type})")
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
    """Standard scraper entry point with URL caching and response caching.

    HYBRID PROXY MODE:
    - Uses passed-in session (residential) for fast sitemap fetching
    - Creates web_scraper_api session for store pages (JS rendering)

    COST-SAVING FEATURES:
    - URL caching (7-day TTL): Skip sitemap fetch on re-runs
    - Response caching (30-day TTL): Skip Web Scraper API for cached pages
    - Failed URL tracking: Enable targeted retries

    Args:
        session: Configured session for sitemaps (requests.Session or ProxyClient)
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
    retailer_name = kwargs.get('retailer', 'walmart')
    logging.info(f"[{retailer_name}] Starting scrape run")

    store_client = None

    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        refresh_urls = kwargs.get('refresh_urls', False)

        reset_request_counter()

        # Auto-select delays based on proxy mode for optimal performance
        proxy_mode = config.get('proxy', {}).get('mode', 'direct')
        min_delay, max_delay = utils.select_delays(config, proxy_mode)
        logging.info(f"[{retailer_name}] HYBRID MODE: Using residential for sitemaps, web_scraper_api for stores")
        logging.info(f"[{retailer_name}] Sitemap delays: {min_delay:.1f}-{max_delay:.1f}s (mode: {proxy_mode})")

        # Create web_scraper_api client for store extraction
        logging.info(f"[{retailer_name}] Creating web_scraper_api client for store extraction")
        proxy_config = ProxyConfig.from_env()
        proxy_config.mode = ProxyMode.WEB_SCRAPER_API
        proxy_config.render_js = True
        store_client = ProxyClient(proxy_config)
        logging.info(f"[{retailer_name}] Web Scraper API client ready (render_js=true)")

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = config.get('checkpoint_interval', 100)

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

        # Track failed URLs for retry
        failed_urls = []

        for i, url in enumerate(remaining_urls, 1):
            # Use web_scraper_api client for store extraction (JS rendering)
            # Response caching is enabled by default to save API costs
            store_obj = extract_store_details(store_client, url, retailer_name, use_cache=True)
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
    finally:
        # Clean up store extraction session
        if 'store_client' in locals() and store_client and hasattr(store_client, 'close'):
            try:
                store_client.close()
                logging.debug(f"[{retailer_name}] Closed web_scraper_api session")
            except Exception as e:
                logging.warning(f"[{retailer_name}] Error closing store session: {e}")
