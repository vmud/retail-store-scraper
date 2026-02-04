"""Core scraping functions for Target Store Locator"""

import gzip
import json
import logging
import re
import threading
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
from src.shared.cache import RichURLCache
from src.shared.constants import WORKERS
from src.shared.request_counter import RequestCounter, check_pause_logic
from src.shared.session_factory import create_session_factory
from src.shared.scraper_utils import (
    initialize_run_context,
    load_urls_with_cache,
    filter_remaining_items,
    save_checkpoint_if_needed,
    log_progress,
    finalize_scraper_run
)


# Global request counter (deprecated - kept for backwards compatibility)
# Use instance-based counter passed to functions instead
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


# =============================================================================
# PARALLEL EXTRACTION - Speed up store detail extraction
# =============================================================================


def _extract_single_store(
    store_info: Dict[str, Any],
    session_factory,
    retailer_name: str,
    yaml_config: dict = None,
    min_delay: float = None,
    max_delay: float = None,
    request_counter: RequestCounter = None
) -> Tuple[int, Optional[Dict[str, Any]]]:
    """Worker function for parallel store extraction.

    Creates its own session for thread safety and extracts store details.

    Args:
        store_info: Store info dict with store_id, slug, url
        session_factory: Callable that creates session instances
        retailer_name: Name of retailer for logging
        yaml_config: Retailer configuration from retailers.yaml
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests
        request_counter: Optional RequestCounter instance for tracking requests

    Returns:
        Tuple of (store_id, store_data_dict) where store_data_dict is None on failure
    """
    session = session_factory()
    store_id = store_info.get('store_id')
    try:
        store_obj = get_store_details(
            session,
            store_id,
            retailer_name,
            min_delay=min_delay,
            max_delay=max_delay,
            yaml_config=yaml_config,
            request_counter=request_counter
        )
        if store_obj:
            return (store_id, store_obj.to_dict())
        return (store_id, None)
    except requests.RequestException as e:
        logging.warning(f"[{retailer_name}] Network error extracting store {store_id}: {e}")
        return (store_id, None)
    except (KeyError, TypeError, AttributeError) as e:
        logging.warning(f"[{retailer_name}] Data extraction error for store {store_id}: {e}", exc_info=True)
        return (store_id, None)
    except Exception as e:
        # Catch-all for worker threads to prevent crashes
        logging.warning(f"[{retailer_name}] Unexpected error extracting store {store_id}: {e}")
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


def get_all_store_ids(
    session: requests.Session,
    retailer: str = 'target',
    min_delay: float = None,
    max_delay: float = None,
    yaml_config: dict = None,
    request_counter: RequestCounter = None
) -> List[Dict[str, Any]]:
    """Extract all store IDs from Target's sitemap.

    Args:
        session: Requests session object
        retailer: Retailer name for logging
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests
        yaml_config: Retailer config dict (for pause settings)
        request_counter: Optional RequestCounter instance for tracking requests

    Returns:
        List of store dictionaries with store_id, slug, and url
    """
    logging.info(f"[{retailer}] Fetching sitemap: {target_config.SITEMAP_URL}")

    response = utils.get_with_retry(
        session,
        target_config.SITEMAP_URL,
        min_delay=min_delay,
        max_delay=max_delay
    )
    if not response:
        logging.error(f"[{retailer}] Failed to fetch sitemap: {target_config.SITEMAP_URL}")
        return []

    if request_counter:
        request_counter.increment()
        check_pause_logic(request_counter, retailer=retailer, config=yaml_config)

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
    except (UnicodeDecodeError, re.error) as e:
        logging.error(f"[{retailer}] Error processing sitemap content: {e}")
        return []


def get_store_details(
    session: requests.Session,
    store_id: int,
    retailer: str = 'target',
    min_delay: float = None,
    max_delay: float = None,
    yaml_config: dict = None,
    request_counter: RequestCounter = None
) -> Optional[TargetStore]:
    """Fetch detailed store info from Redsky API.

    Args:
        session: Requests session object
        store_id: Numeric store ID
        retailer: Retailer name for logging
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests
        yaml_config: Retailer config dict (for pause settings)
        request_counter: Optional RequestCounter instance for tracking requests

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
    response = utils.get_with_retry(
        session,
        url_with_params,
        max_retries=target_config.MAX_RETRIES,
        min_delay=min_delay,
        max_delay=max_delay
    )
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store details for store_id={store_id}")
        return None

    if request_counter:
        request_counter.increment()
        check_pause_logic(request_counter, retailer=retailer, config=yaml_config)

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
    except (KeyError, TypeError, AttributeError) as e:
        logging.warning(f"[{retailer}] Data extraction error for store_id={store_id}: {e}", exc_info=True)
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
    limit = kwargs.get('limit')
    resume = kwargs.get('resume', False)
    refresh_urls = kwargs.get('refresh_urls', False)

    try:
        # Initialize common run context (handles delays, workers, checkpoints, resume)
        context = initialize_run_context(retailer_name, config, resume)
        reset_request_counter()  # Reset global counter for backwards compatibility

        # Load store URLs with cache support
        # Target uses RichURLCache since it stores extra data (store_id, slug) alongside URLs
        url_cache = RichURLCache(retailer_name)
        store_list = load_urls_with_cache(
            url_cache,
            lambda: get_all_store_ids(
                session,
                retailer_name,
                min_delay=context.min_delay,
                max_delay=context.max_delay,
                yaml_config=config,
                request_counter=context.request_counter
            ),
            refresh_urls
        )

        if not store_list:
            logging.warning(f"[{retailer_name}] No store IDs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        # Filter remaining stores based on checkpoint and limit
        remaining_stores = filter_remaining_items(
            store_list,
            context.completed_ids,
            limit,
            len(context.stores),
            retailer_name,
            id_extractor=lambda s: s.get('store_id')
        )

        total_to_process = len(remaining_stores)

        # Track failed store IDs for logging
        failed_store_ids = []

        # Use parallel extraction if workers > 1
        if context.parallel_workers > 1 and total_to_process > 0:
            logging.info(f"[{retailer_name}] Using parallel extraction with {context.parallel_workers} workers")

            # Create session factory for parallel workers (each worker needs its own session)
            session_factory = create_session_factory(config)

            # Thread-safe counters for progress
            processed_count = [0]  # Use list for mutable closure
            successful_count = [0]
            processed_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=context.parallel_workers) as executor:
                # Submit all extraction tasks
                futures = {
                    executor.submit(
                        _extract_single_store,
                        store_info,
                        session_factory,
                        retailer_name,
                        config,
                        context.min_delay,
                        context.max_delay,
                        context.request_counter
                    ): store_info
                    for store_info in remaining_stores
                }

                for future in as_completed(futures):
                    store_id, store_data = future.result()

                    with processed_lock:
                        processed_count[0] += 1
                        current_count = processed_count[0]

                        if store_data:
                            context.stores.append(store_data)
                            context.completed_ids.add(store_id)
                            successful_count[0] += 1
                        else:
                            failed_store_ids.append(store_id)

                        # Progress logging every 50 stores
                        log_progress(retailer_name, current_count, total_to_process, successful_count[0])

                        # Checkpoint at intervals
                        save_checkpoint_if_needed(context, current_count)
        else:
            # Sequential extraction (original behavior for direct mode)
            for i, store_info in enumerate(remaining_stores, 1):
                store_id = store_info.get('store_id')
                store_obj = get_store_details(
                    session,
                    store_id,
                    retailer_name,
                    min_delay=context.min_delay,
                    max_delay=context.max_delay,
                    yaml_config=config,
                    request_counter=context.request_counter
                )
                if store_obj:
                    context.stores.append(store_obj.to_dict())
                    context.completed_ids.add(store_id)

                    # Log successful extraction every 10 stores for more frequent updates
                    if i % 10 == 0:
                        logging.info(f"[{retailer_name}] Extracted {len(context.stores)} stores so far ({i}/{total_to_process})")
                else:
                    failed_store_ids.append(store_id)

                # Progress logging every 100 stores
                if i % 100 == 0:
                    logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")

                save_checkpoint_if_needed(context, i)

        # Save failed store IDs to file for followup
        if failed_store_ids:
            _save_failed_extractions(retailer_name, failed_store_ids)

        # Finalize run with validation and cleanup
        return finalize_scraper_run(context, failed_items=failed_store_ids, item_key="failed_store_ids")

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
