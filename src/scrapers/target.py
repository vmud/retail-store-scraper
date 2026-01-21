"""Core scraping functions for Target Store Locator"""

import gzip
import json
import logging
import random
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import requests

from config import target_config
from src.shared import utils
from src.shared.request_counter import RequestCounter


# Global request counter
_request_counter = RequestCounter()


@dataclass
class TargetStore:
    """Data model for Target store information"""
    store_id: str
    name: str
    status: str
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    phone: str
    capabilities: Optional[List[str]]
    format: Optional[str]
    building_area: Optional[int]
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
        if result.get('building_area') is None:
            result['building_area'] = ''
        else:
            result['building_area'] = str(result['building_area'])
        return result


def _check_pause_logic(retailer: str = 'target') -> None:
    """Check if we need to pause based on request count (#71).

    Uses standardized random delay ranges for consistency with other scrapers.
    """
    # Skip modulo operations if pauses are effectively disabled (>= 999999)
    try:
        if target_config.PAUSE_50_REQUESTS >= 999999 and target_config.PAUSE_200_REQUESTS >= 999999:
            return
    except (TypeError, AttributeError):
        pass  # Config mocked in tests, continue with normal pause logic
    
    count = _request_counter.count

    if count % target_config.PAUSE_200_REQUESTS == 0 and count > 0:
        # Use random delay range for 200-request pause (#71)
        pause_time = random.uniform(target_config.PAUSE_200_MIN, target_config.PAUSE_200_MAX)
        logging.info(f"[{retailer}] Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % target_config.PAUSE_50_REQUESTS == 0 and count > 0:
        # Use random delay range for 50-request pause (#71)
        pause_time = random.uniform(target_config.PAUSE_50_MIN, target_config.PAUSE_50_MAX)
        logging.info(f"[{retailer}] Pause after {count} requests: {pause_time:.1f} seconds")
        time.sleep(pause_time)


# =============================================================================
# URL CACHING - Skip sitemap fetch on subsequent runs
# =============================================================================

# Default cache expiry: 7 days (stores don't change location frequently)
URL_CACHE_EXPIRY_DAYS = 7


def _get_url_cache_path(retailer: str) -> Path:
    """Get path to store URL cache file."""
    return Path(f"data/{retailer}/store_urls.json")


def _load_cached_urls(retailer: str, max_age_days: int = URL_CACHE_EXPIRY_DAYS) -> Optional[List[Dict[str, Any]]]:
    """Load cached store URLs if recent enough.

    Args:
        retailer: Retailer name
        max_age_days: Maximum cache age in days (default: 7)

    Returns:
        List of cached store info dicts if cache is valid, None otherwise
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

            stores = cache_data.get('stores', [])
            if stores:
                logging.info(f"[{retailer}] Loaded {len(stores)} store URLs from cache ({age_days} days old)")
                return stores

        logging.warning(f"[{retailer}] URL cache is invalid or empty")
        return None

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logging.warning(f"[{retailer}] Error loading URL cache: {e}")
        return None


def _save_cached_urls(retailer: str, store_list: List[Dict[str, Any]]) -> None:
    """Save discovered store URLs to cache.

    Args:
        retailer: Retailer name
        store_list: List of store info dicts to cache
    """
    cache_path = _get_url_cache_path(retailer)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_data = {
        'discovered_at': datetime.now().isoformat(),
        'store_count': len(store_list),
        'stores': store_list
    }

    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        logging.info(f"[{retailer}] Saved {len(store_list)} store URLs to cache: {cache_path}")
    except IOError as e:
        logging.warning(f"[{retailer}] Failed to save URL cache: {e}")


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
    store_info: Dict[str, Any],
    session_factory,
    retailer_name: str,
    yaml_config: dict = None
) -> Tuple[int, Optional[Dict[str, Any]]]:
    """Worker function for parallel store extraction.

    Creates its own session for thread safety and extracts store details.

    Args:
        store_info: Store info dict with store_id, slug, url
        session_factory: Callable that creates session instances
        retailer_name: Name of retailer for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        Tuple of (store_id, store_data_dict) where store_data_dict is None on failure
    """
    session = session_factory()
    store_id = store_info.get('store_id')
    try:
        store_obj = get_store_details(session, store_id, retailer_name)
        if store_obj:
            return (store_id, store_obj.to_dict())
        return (store_id, None)
    except Exception as e:
        logging.warning(f"[{retailer_name}] Error extracting store {store_id}: {e}")
        return (store_id, None)
    finally:
        # Clean up session resources
        if hasattr(session, 'close'):
            session.close()


def _save_failed_extractions(retailer: str, failed_store_ids: List[int]) -> None:
    """Save failed store IDs for followup retries.

    Args:
        retailer: Retailer name
        failed_store_ids: List of store IDs that failed extraction
    """
    failed_path = Path(f"data/{retailer}/failed_extractions.json")
    failed_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(failed_path, 'w', encoding='utf-8') as f:
            json.dump({
                'run_date': datetime.now().isoformat(),
                'failed_count': len(failed_store_ids),
                'failed_store_ids': failed_store_ids
            }, f, indent=2)
        logging.info(f"[{retailer}] Saved {len(failed_store_ids)} failed store IDs to {failed_path}")
    except IOError as e:
        logging.warning(f"[{retailer}] Failed to save failed store IDs: {e}")


def get_all_store_ids(session: requests.Session, retailer: str = 'target') -> List[Dict[str, Any]]:
    """Extract all store IDs from Target's sitemap.

    Args:
        session: Requests session object

    Returns:
        List of store dictionaries with store_id, slug, and url
    """
    logging.info(f"[{retailer}] Fetching sitemap: {target_config.SITEMAP_URL}")

    response = utils.get_with_retry(session, target_config.SITEMAP_URL)
    if not response:
        logging.error(f"[{retailer}] Failed to fetch sitemap: {target_config.SITEMAP_URL}")
        return []

    _request_counter.increment()
    _check_pause_logic(retailer)

    try:
        # Check if content is already decompressed (starts with XML) or gzipped
        content_bytes = response.content
        if content_bytes.startswith(b'<?xml') or content_bytes.startswith(b'<urlset'):
            # Already decompressed XML
            content = content_bytes.decode('utf-8')
        else:
            # Try to decompress gzipped content
            try:
                with gzip.GzipFile(fileobj=BytesIO(content_bytes)) as f:
                    content = f.read().decode('utf-8')
            except (gzip.BadGzipFile, OSError):
                # If decompression fails, try as plain text
                content = content_bytes.decode('utf-8')

        # Extract store URLs with regex
        pattern = r'https://www\.target\.com/sl/([a-zA-Z0-9-]+)/(\d+)'
        matches = re.findall(pattern, content)

        stores = []
        seen_ids = set()
        for slug, store_id in matches:
            store_id_int = int(store_id)
            if store_id_int not in seen_ids:
                seen_ids.add(store_id_int)
                stores.append({
                    "store_id": store_id_int,
                    "slug": slug,
                    "url": f"https://www.target.com/sl/{slug}/{store_id}"
                })

        logging.info(f"[{retailer}] Found {len(stores)} stores in sitemap")
        return stores

    except gzip.BadGzipFile as e:
        logging.error(f"[{retailer}] Failed to decompress gzip sitemap: {e}")
        return []
    except Exception as e:
        logging.error(f"[{retailer}] Unexpected error processing sitemap: {e}")
        return []


def get_store_details(session: requests.Session, store_id: int, retailer: str = 'target') -> Optional[TargetStore]:
    """Fetch detailed store info from Redsky API.

    Args:
        session: Requests session object
        store_id: Numeric store ID

    Returns:
        TargetStore object if successful, None otherwise
    """
    params = {
        "store_id": store_id,
        "key": target_config.API_KEY,
        "channel": target_config.API_CHANNEL
    }

    # Build URL with params for get_with_retry
    url_with_params = f"{target_config.REDSKY_API_URL}?{urllib.parse.urlencode(params)}"
    response = utils.get_with_retry(session, url_with_params, max_retries=target_config.MAX_RETRIES)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store details for store_id={store_id}")
        return None

    _request_counter.increment()
    _check_pause_logic(retailer)

    try:
        if response.status_code == 200:
            data = response.json()
            store = data.get("data", {}).get("store", {})

            if not store:
                logging.warning(f"[{retailer}] No store data found for store_id={store_id}")
                return None

            # Extract address
            mailing_address = store.get("mailing_address", {})

            # Extract geographic specifications
            geo_specs = store.get("geographic_specifications", {})

            # Extract physical specifications
            physical_specs = store.get("physical_specifications", {})

            # Extract capabilities
            capabilities = [c.get("capability_name", "") for c in store.get("capabilities", [])]

            # Build store URL from slug if available, otherwise construct from store_id
            store_url = f"https://www.target.com/sl/store/{store_id}"
            # Try to get slug from original store data if available
            if 'slug' in store:
                store_url = f"https://www.target.com/sl/{store['slug']}/{store_id}"

            target_store = TargetStore(
                store_id=str(store.get("store_id", store_id)),
                name=store.get("location_name", ""),
                status=store.get("status", ""),
                street_address=mailing_address.get("address_line1", ""),
                city=mailing_address.get("city", ""),
                state=mailing_address.get("region", ""),  # State abbreviation
                postal_code=mailing_address.get("postal_code", ""),
                country=mailing_address.get("country", "United States of America"),
                latitude=geo_specs.get("latitude"),
                longitude=geo_specs.get("longitude"),
                phone=store.get("main_voice_phone_number", ""),
                capabilities=capabilities if capabilities else None,
                format=physical_specs.get("format"),
                building_area=physical_specs.get("total_building_area"),
                url=store_url,
                scraped_at=datetime.now().isoformat()
            )

            return target_store
        else:
            logging.warning(f"[{retailer}] API returned status {response.status_code} for store_id={store_id}")
            return None

    except json.JSONDecodeError as e:
        logging.warning(f"[{retailer}] Failed to parse JSON response for store_id={store_id}: {e}")
        return None
    except Exception as e:
        logging.warning(f"[{retailer}] Unexpected error processing store_id={store_id}: {e}")
        return None


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count


def reset_request_counter() -> None:
    """Reset request counter"""
    _request_counter.reset()


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
    retailer_name = kwargs.get('retailer', 'target')
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
        completed_ids = set()
        checkpoints_used = False

        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores = checkpoint.get('stores', [])
                completed_ids = set(checkpoint.get('completed_ids', []))
                logging.info(f"[{retailer_name}] Resuming from checkpoint: {len(stores)} stores already collected")
                checkpoints_used = True

        # Try to load cached URLs (skip sitemap fetch if cache is valid)
        store_list = None
        if not refresh_urls:
            store_list = _load_cached_urls(retailer_name)

        if store_list is None:
            # Cache miss or refresh requested - fetch from sitemap
            store_list = get_all_store_ids(session, retailer_name)
            logging.info(f"[{retailer_name}] Found {len(store_list)} store IDs from sitemap")

            # Save to cache for future runs
            if store_list:
                _save_cached_urls(retailer_name, store_list)
        else:
            logging.info(f"[{retailer_name}] Using {len(store_list)} cached store URLs")

        if not store_list:
            logging.warning(f"[{retailer_name}] No store IDs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        remaining_stores = [s for s in store_list if s.get('store_id') not in completed_ids]

        if resume and completed_ids:
            logging.info(f"[{retailer_name}] Skipping {len(store_list) - len(remaining_stores)} already-processed stores from checkpoint")

        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} stores")
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_stores = remaining_stores[:total_needed]
            else:
                remaining_stores = []

        total_to_process = len(remaining_stores)
        if total_to_process > 0:
            logging.info(f"[{retailer_name}] Extracting details for {total_to_process} stores")
        else:
            logging.info(f"[{retailer_name}] No new stores to process")

        # Track failed store IDs for logging
        failed_store_ids = []

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
                    executor.submit(_extract_single_store, store_info, session_factory, retailer_name, config): store_info
                    for store_info in remaining_stores
                }

                for future in as_completed(futures):
                    store_id, store_data = future.result()

                    with processed_lock:
                        processed_count[0] += 1
                        current_count = processed_count[0]

                        if store_data:
                            stores.append(store_data)
                            completed_ids.add(store_id)
                            successful_count[0] += 1
                        else:
                            failed_store_ids.append(store_id)

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
                                'completed_ids': list(completed_ids),
                                'stores': stores,
                                'last_updated': datetime.now().isoformat()
                            }, checkpoint_path)
                            logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores processed")
        else:
            # Sequential extraction (original behavior for direct mode)
            for i, store_info in enumerate(remaining_stores, 1):
                store_id = store_info.get('store_id')
                store_obj = get_store_details(session, store_id, retailer_name)
                if store_obj:
                    stores.append(store_obj.to_dict())
                    completed_ids.add(store_id)

                    # Log successful extraction every 10 stores for more frequent updates
                    if i % 10 == 0:
                        logging.info(f"[{retailer_name}] Extracted {len(stores)} stores so far ({i}/{total_to_process})")
                else:
                    failed_store_ids.append(store_id)

                # Progress logging every 100 stores
                if i % 100 == 0:
                    logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")

                if i % checkpoint_interval == 0:
                    utils.save_checkpoint({
                        'completed_count': len(stores),
                        'completed_ids': list(completed_ids),
                        'stores': stores,
                        'last_updated': datetime.now().isoformat()
                    }, checkpoint_path)
                    logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores processed")

        # Log failed extractions
        if failed_store_ids:
            logging.warning(f"[{retailer_name}] Failed to extract {len(failed_store_ids)} stores:")
            for failed_id in failed_store_ids[:10]:  # Log first 10
                logging.warning(f"[{retailer_name}]   - store_id={failed_id}")
            if len(failed_store_ids) > 10:
                logging.warning(f"[{retailer_name}]   ... and {len(failed_store_ids) - 10} more")

            # Save failed store IDs to file for followup
            _save_failed_extractions(retailer_name, failed_store_ids)

        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_ids': list(completed_ids),
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
