"""Core scraping functions for AT&T Store Locator"""

import json
import logging
import re
import threading
import defusedxml.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
import requests

from config import att_config
from src.shared import utils
from src.shared.cache import URLCache
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


# =============================================================================
# PARALLEL EXTRACTION - Speed up store detail extraction
# =============================================================================


def _extract_single_store(
    url: str,
    session_factory,
    retailer_name: str,
    yaml_config: dict = None,
    request_counter: RequestCounter = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Worker function for parallel store extraction.

    Creates its own session for thread safety and extracts store details.

    Args:
        url: Store URL to extract
        session_factory: Callable that creates session instances
        retailer_name: Name of retailer for logging
        yaml_config: Retailer configuration from retailers.yaml
        request_counter: Optional RequestCounter instance for tracking requests

    Returns:
        Tuple of (url, store_data_dict) where store_data_dict is None on failure
    """
    session = session_factory()
    try:
        store_obj = extract_store_details(session, url, retailer_name, yaml_config, request_counter)
        if store_obj:
            return (url, store_obj.to_dict())
        return (url, None)
    except requests.RequestException as e:
        logging.warning(f"[{retailer_name}] Network error extracting {url}: {e}")
        return (url, None)
    except Exception as e:
        # Catch-all for worker threads to prevent crashes
        logging.warning(f"[{retailer_name}] Unexpected error extracting {url}: {e}")
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
    yaml_config: dict = None,
    request_counter: RequestCounter = None
) -> List[str]:
    """Fetch all store URLs from the AT&T sitemap.

    Args:
        session: Requests session object
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml
        request_counter: Optional RequestCounter instance for tracking requests

    Returns:
        List of store URLs (filtered to only those ending in numeric IDs)
    """
    logging.info(f"[{retailer}] Fetching sitemap from {att_config.SITEMAP_URL}")

    response = utils.get_with_retry(session, att_config.SITEMAP_URL)
    if not response:
        logging.error(f"[{retailer}] Failed to fetch sitemap")
        return []

    if request_counter:
        request_counter.increment()
        check_pause_logic(request_counter, retailer=retailer, config=yaml_config)

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

    except (ET.ParseError, UnicodeDecodeError) as e:
        logging.error(f"[{retailer}] Failed to parse XML sitemap: {e}")
        return []


def extract_store_details(
    session: requests.Session,
    url: str,
    retailer: str = 'att',
    yaml_config: dict = None,
    request_counter: RequestCounter = None
) -> Optional[ATTStore]:
    """Extract store data from a single AT&T store page.

    Args:
        session: Requests session object
        url: Store page URL
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml
        request_counter: Optional RequestCounter instance for tracking requests

    Returns:
        ATTStore object if successful, None otherwise
    """
    logging.debug(f"[{retailer}] Extracting details from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store details: {url}")
        return None

    if request_counter:
        request_counter.increment()
        check_pause_logic(request_counter, retailer=retailer, config=yaml_config)

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

        if rating and isinstance(rating, dict):
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

    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as e:
        logging.warning(f"[{retailer}] Error extracting store data from {url}: {e}", exc_info=True)
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
    retailer_name = kwargs.get('retailer', 'att')
    limit = kwargs.get('limit')
    resume = kwargs.get('resume', False)
    refresh_urls = kwargs.get('refresh_urls', False)

    try:
        # Initialize common run context (handles delays, workers, checkpoints, resume)
        context = initialize_run_context(retailer_name, config, resume)
        reset_request_counter()  # Reset global counter for backwards compatibility

        # Load store URLs with cache support
        url_cache = URLCache(retailer_name)
        store_urls = load_urls_with_cache(
            url_cache,
            lambda: get_store_urls_from_sitemap(session, retailer_name, yaml_config=config, request_counter=context.request_counter),
            refresh_urls
        )

        if not store_urls:
            logging.warning(f"[{retailer_name}] No store URLs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        # Filter remaining URLs based on checkpoint and limit
        remaining_urls = filter_remaining_items(
            store_urls,
            context.completed_ids,
            limit,
            len(context.stores),
            retailer_name
        )

        total_to_process = len(remaining_urls)

        # Use parallel extraction if workers > 1
        if context.parallel_workers > 1 and total_to_process > 0:
            logging.info(f"[{retailer_name}] Using parallel extraction with {context.parallel_workers} workers")

            # Create session factory for parallel workers (each worker needs its own session)
            session_factory = create_session_factory(config)

            # Thread-safe counter for progress
            processed_count = [0]  # Use list for mutable closure
            processed_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=context.parallel_workers) as executor:
                # Submit all extraction tasks
                futures = {
                    executor.submit(_extract_single_store, url, session_factory, retailer_name, config, context.request_counter): url
                    for url in remaining_urls
                }

                for future in as_completed(futures):
                    url, store_data = future.result()

                    with processed_lock:
                        processed_count[0] += 1
                        current_count = processed_count[0]

                        if store_data:
                            context.stores.append(store_data)
                            context.completed_ids.add(url)

                        # Progress logging every 50 stores
                        log_progress(retailer_name, current_count, total_to_process, len(context.stores))

                        # Checkpoint at intervals
                        save_checkpoint_if_needed(context, current_count)
        else:
            # Sequential extraction (original behavior for direct mode)
            for i, url in enumerate(remaining_urls, 1):
                store_obj = extract_store_details(session, url, retailer_name, yaml_config=config, request_counter=context.request_counter)
                if store_obj:
                    context.stores.append(store_obj.to_dict())
                    context.completed_ids.add(url)

                    # Log successful extraction every 10 stores for more frequent updates
                    if i % 10 == 0:
                        logging.info(f"[{retailer_name}] Extracted {len(context.stores)} stores so far ({i}/{total_to_process})")

                # Progress logging every 100 stores
                if i % 100 == 0:
                    logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")

                save_checkpoint_if_needed(context, i)

        # Finalize run with validation and cleanup
        return finalize_scraper_run(context)

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
