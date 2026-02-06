"""Core scraping functions for Lowe's Store Locator

Lowe's uses server-rendered HTML with embedded JSON (Redux initial state).
Two-phase discovery:
1. State directory pages list all store IDs per state (51 pages)
2. Store detail pages contain full embedded JSON data (~1,761 stores)

Architecture: React/Redux SSR with PerimeterX bot protection.
Store detail URLs require only the store number; the path prefix is cosmetic.
"""

import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from config import lowes_config as config
from src.shared import utils
from src.shared.cache import URLCache
from src.shared.request_counter import RequestCounter, check_pause_logic


# Global request counter
_request_counter = RequestCounter()


@dataclass
class LowesStore:
    """Data model for Lowe's store information."""

    store_id: str               # Numeric store ID (e.g., "1548")
    name: str                   # Store name (e.g., "Eatontown Lowe's")
    street_address: str         # Street address
    city: str                   # City name
    state: str                  # 2-letter state code
    state_full_name: str        # Full state name
    zip: str                    # ZIP code
    country: str                # Country code (US)
    latitude: Optional[str]     # Latitude as string
    longitude: Optional[str]    # Longitude as string
    phone: str                  # Phone number
    fax: str                    # Fax number
    timezone: str               # Timezone (e.g., "America/New_York")
    store_type: str             # Store type code
    store_status: str           # Store status code
    open_date: str              # Store opening date
    features: str               # Comma-separated feature list
    hours: Optional[str]        # JSON string of formatted hours
    url: str                    # Canonical store page URL
    corp_number: str = ""       # Corporate number
    area_number: str = ""       # Area number
    region_number: str = ""     # Region number
    scraped_at: str = ""        # ISO timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary for export."""
        return asdict(self)


def _extract_json_from_html(html: str) -> Optional[Dict[str, Any]]:
    """Extract embedded store JSON from a Lowe's store detail page.

    Lowe's embeds store data as a JSON object in the Redux initial state
    within the HTML. The object is identified by the presence of '"_id":"'
    and contains all store fields.

    The extraction uses brace-depth matching to find the complete JSON object.

    Args:
        html: Raw HTML content of the store detail page.

    Returns:
        Parsed JSON dict if found and valid, None otherwise.
    """
    marker = config.EMBEDDED_JSON_MARKER
    idx = html.find(marker)
    if idx == -1:
        return None

    # Walk backwards from marker to find the opening brace
    lookback = config.JSON_SEARCH_LOOKBACK
    start = idx
    for i in range(idx, max(0, idx - lookback), -1):
        if html[i] == '{':
            start = i
            break
    else:
        # No opening brace found within lookback distance
        return None

    if start == idx:
        # Didn't find an opening brace before the marker
        return None

    # Find the matching closing brace using string-aware depth tracking.
    # Skips braces inside quoted strings to avoid premature termination
    # from values like "address": "123 {Suite A} Rd".
    max_size = config.JSON_MAX_SIZE
    depth = 0
    end = start
    in_string = False
    for i in range(start, min(len(html), start + max_size)):
        ch = html[i]
        if ch == '"' and (i == 0 or html[i - 1] != '\\'):
            in_string = not in_string
        elif not in_string:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
    else:
        # Didn't find matching close brace within max size
        return None

    if end == start:
        return None

    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError:
        return None


def _format_hours(store_hours: List[Dict[str, Any]]) -> Optional[str]:
    """Format Lowe's storeHours array to a JSON string.

    Args:
        store_hours: List of hour objects from the embedded store JSON.
            Each object has 'day.day', 'open', 'close', 'is24Open', 'isHoliday'.

    Returns:
        JSON string of formatted hours or None if no hours available.
    """
    if not store_hours:
        return None

    formatted = []
    for entry in store_hours:
        day_info = entry.get('day', {})
        if not isinstance(day_info, dict):
            continue

        day_name = entry.get('label', day_info.get('day', ''))
        open_time = entry.get('open', '')
        close_time = entry.get('close', '')
        is_24_open = entry.get('is24Open', False)

        formatted.append({
            'day': day_name,
            'open': 'Open 24 hours' if is_24_open else open_time,
            'close': '' if is_24_open else close_time,
            'is24Open': is_24_open,
            'isHoliday': entry.get('isHoliday', False),
        })

    return json.dumps(formatted) if formatted else None


def _parse_store_data(raw_data: Dict[str, Any], store_id: str) -> Optional[LowesStore]:
    """Parse raw JSON data into a LowesStore dataclass.

    Args:
        raw_data: Parsed JSON dict from the store detail page.
        store_id: The store ID used in the request.

    Returns:
        LowesStore object if data is valid, None otherwise.
    """
    # Validate minimum required fields
    extracted_id = raw_data.get('id', store_id)
    name = raw_data.get('storeName', '') or raw_data.get('store_name', '')
    if not name:
        return None

    hours = _format_hours(raw_data.get('storeHours', []))

    return LowesStore(
        store_id=str(extracted_id),
        name=name,
        street_address=raw_data.get('address', ''),
        city=raw_data.get('city', ''),
        state=raw_data.get('state', ''),
        state_full_name=raw_data.get('stateFullName', ''),
        zip=raw_data.get('zip', ''),
        country=raw_data.get('country', 'US'),
        latitude=raw_data.get('lat'),
        longitude=raw_data.get('long'),
        phone=raw_data.get('phone', ''),
        fax=raw_data.get('fax', ''),
        timezone=raw_data.get('timeZone', ''),
        store_type=raw_data.get('storeType', ''),
        store_status=raw_data.get('storeStatusCd', ''),
        open_date=raw_data.get('openDate', ''),
        features=raw_data.get('storeFeature', ''),
        hours=hours,
        url=raw_data.get('pageUrl', ''),
        corp_number=raw_data.get('corpNumber', ''),
        area_number=raw_data.get('areaNumber', ''),
        region_number=raw_data.get('regionNumber', ''),
        scraped_at=datetime.now().isoformat(),
    )


def get_store_ids_from_state(
    session,
    state_name: str,
    state_code: str,
    retailer: str = 'lowes',
    yaml_config: Optional[dict] = None,
) -> List[str]:
    """Fetch all store IDs for a given state from the directory page.

    Parses both href links and embedded JSON data to find store IDs,
    then deduplicates the results.

    Args:
        session: Requests session object.
        state_name: URL-safe state name (e.g., 'New-Jersey').
        state_code: Two-letter state code (e.g., 'NJ').
        retailer: Retailer name for logging.
        yaml_config: Retailer configuration from retailers.yaml.

    Returns:
        List of unique store ID strings.
    """
    url = config.build_state_directory_url(state_name, state_code)
    logging.debug(f"[{retailer}] Fetching state directory: {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch state directory for {state_code}")
        return []

    _request_counter.increment()
    if yaml_config:
        check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    html = response.text

    # Extract store IDs from href links
    link_ids = set(re.findall(config.STORE_LINK_PATTERN, html))

    # Extract embedded store IDs from JSON data
    embedded_ids = set(re.findall(config.EMBEDDED_STORE_ID_PATTERN, html))

    all_ids = list(link_ids | embedded_ids)
    logging.debug(f"[{retailer}] {state_code}: {len(all_ids)} stores "
                  f"(links={len(link_ids)}, embedded={len(embedded_ids)})")

    return all_ids


def get_all_store_ids(
    session,
    retailer: str = 'lowes',
    yaml_config: Optional[dict] = None,
    states: Optional[List[str]] = None,
) -> List[str]:
    """Fetch store IDs from all state directory pages (Phase 1).

    Args:
        session: Requests session object.
        retailer: Retailer name for logging.
        yaml_config: Retailer configuration from retailers.yaml.
        states: Optional list of state codes to limit discovery to.

    Returns:
        List of unique store ID strings across all states.
    """
    all_ids: Set[str] = set()
    proxy_mode = 'direct'
    if yaml_config:
        proxy_mode = yaml_config.get('proxy', {}).get('mode', 'direct')

    states_to_process = config.STATES
    if states:
        state_set = {s.upper() for s in states}
        states_to_process = [
            (name, code) for name, code in config.STATES if code in state_set
        ]

    logging.info(f"[{retailer}] Phase 1: Discovering stores from "
                 f"{len(states_to_process)} state directories")

    for i, (state_name, state_code) in enumerate(states_to_process, 1):
        state_ids = get_store_ids_from_state(
            session, state_name, state_code, retailer, yaml_config
        )
        all_ids.update(state_ids)

        if i % 10 == 0:
            logging.info(f"[{retailer}] Phase 1 progress: {i}/{len(states_to_process)} "
                         f"states, {len(all_ids)} unique stores so far")

        # Respect rate limiting between state pages
        if yaml_config:
            utils.random_delay(yaml_config, proxy_mode)

    logging.info(f"[{retailer}] Phase 1 complete: {len(all_ids)} unique store IDs discovered")
    return sorted(all_ids)


def extract_store_details(
    session,
    store_id: str,
    retailer: str = 'lowes',
    yaml_config: Optional[dict] = None,
) -> Optional[LowesStore]:
    """Fetch and extract full store details from a detail page (Phase 2).

    Args:
        session: Requests session object.
        store_id: Numeric store ID.
        retailer: Retailer name for logging.
        yaml_config: Retailer configuration from retailers.yaml.

    Returns:
        LowesStore object if successful, None otherwise.
    """
    url = config.build_store_detail_url(store_id)
    logging.debug(f"[{retailer}] Extracting details for store {store_id}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store {store_id}")
        return None

    _request_counter.increment()
    if yaml_config:
        check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    # Note: 404s are already handled by get_with_retry returning None

    raw_data = _extract_json_from_html(response.text)
    if not raw_data:
        logging.warning(f"[{retailer}] No embedded JSON found for store {store_id}")
        return None

    store = _parse_store_data(raw_data, store_id)
    if store:
        logging.debug(f"[{retailer}] Extracted: {store.name} ({store.store_id})")
    return store


def run(session, yaml_config: dict, **kwargs) -> dict:
    """Standard scraper entry point with two-phase discovery.

    Phase 1: Fetch store IDs from all 51 state directory pages.
    Phase 2: Fetch full store details from each store's detail page.

    Args:
        session: Configured session (requests.Session or ProxyClient).
        yaml_config: Retailer configuration dict from retailers.yaml.
        **kwargs: Additional options:
            - retailer: str - Retailer name for logging
            - resume: bool - Resume from checkpoint
            - limit: int - Max stores to process
            - refresh_urls: bool - Force URL re-discovery (ignore cache)
            - states: list - Limit to specific state codes

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = kwargs.get('retailer', 'lowes')
    logging.info(f"[{retailer_name}] Starting scrape run")

    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        refresh_urls = kwargs.get('refresh_urls', False)
        states_filter = kwargs.get('states')

        reset_request_counter()

        # Auto-select delays based on proxy mode
        proxy_mode = yaml_config.get('proxy', {}).get('mode', 'direct')
        min_delay, max_delay = utils.select_delays(yaml_config, proxy_mode)
        logging.info(f"[{retailer_name}] Using delays: {min_delay:.1f}-{max_delay:.1f}s "
                     f"(mode: {proxy_mode})")

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = yaml_config.get('checkpoint_interval', 50)

        stores: List[dict] = []
        completed_ids: Set[str] = set()
        checkpoints_used = False

        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores = checkpoint.get('stores', [])
                completed_ids = set(checkpoint.get('completed_ids', []))
                logging.info(f"[{retailer_name}] Resuming from checkpoint: "
                             f"{len(stores)} stores already collected")
                checkpoints_used = True

        # Phase 1: Discover store IDs (with caching)
        url_cache = URLCache(retailer_name)
        store_ids = None
        if not refresh_urls:
            cached = url_cache.get()
            if cached:
                store_ids = cached

        if store_ids is None:
            store_ids = get_all_store_ids(
                session, retailer_name, yaml_config, states=states_filter
            )
            logging.info(f"[{retailer_name}] Discovered {len(store_ids)} store IDs")
            if store_ids:
                url_cache.set(store_ids)
        else:
            logging.info(f"[{retailer_name}] Using {len(store_ids)} cached store IDs")

        if not store_ids:
            logging.warning(f"[{retailer_name}] No store IDs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        # Phase 2: Fetch store details
        remaining_ids = [sid for sid in store_ids if sid not in completed_ids]

        if resume and completed_ids:
            logging.info(f"[{retailer_name}] Skipping {len(store_ids) - len(remaining_ids)} "
                         f"already-processed stores")

        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} stores")
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_ids = remaining_ids[:total_needed]
            else:
                remaining_ids = []

        total_to_process = len(remaining_ids)
        if total_to_process > 0:
            logging.info(f"[{retailer_name}] Phase 2: Extracting details for "
                         f"{total_to_process} stores")
        else:
            logging.info(f"[{retailer_name}] No new stores to process")

        failed_ids: List[str] = []

        for i, store_id in enumerate(remaining_ids, 1):
            store_obj = extract_store_details(
                session, store_id, retailer_name, yaml_config
            )
            if store_obj:
                stores.append(store_obj.to_dict())
                completed_ids.add(store_id)
            else:
                failed_ids.append(store_id)

            # Progress logging
            if i % 25 == 0:
                logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} "
                             f"({i / total_to_process * 100:.1f}%)")

            # Checkpoint at intervals
            if i % checkpoint_interval == 0:
                utils.save_checkpoint({
                    'completed_count': len(stores),
                    'completed_ids': list(completed_ids),
                    'stores': stores,
                    'last_updated': datetime.now().isoformat(),
                }, checkpoint_path)
                logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores")

            # Respect rate limiting
            utils.random_delay(yaml_config, proxy_mode)

        # Log failed extractions
        if failed_ids:
            logging.warning(f"[{retailer_name}] Failed to extract {len(failed_ids)} stores:")
            for fid in failed_ids[:10]:
                logging.warning(f"[{retailer_name}]   - Store {fid}")
            if len(failed_ids) > 10:
                logging.warning(f"[{retailer_name}]   ... and {len(failed_ids) - 10} more")

        # Final checkpoint
        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_ids': list(completed_ids),
                'stores': stores,
                'last_updated': datetime.now().isoformat(),
            }, checkpoint_path)

        # Validate store data
        validation_summary = utils.validate_stores_batch(stores)
        logging.info(
            f"[{retailer_name}] Validation: {validation_summary['valid']}/"
            f"{validation_summary['total']} valid, "
            f"{validation_summary['warning_count']} warnings"
        )

        logging.info(f"[{retailer_name}] Completed: {len(stores)} stores scraped")

        return {
            'stores': stores,
            'count': len(stores),
            'checkpoints_used': checkpoints_used,
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise


def reset_request_counter() -> None:
    """Reset the global request counter."""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count."""
    return _request_counter.count
