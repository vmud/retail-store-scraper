"""Core scraping functions for Home Depot Store Locator.

Home Depot uses a GraphQL Federation Gateway API (Apollo) with two phases:
1. storeDirectoryByState — discover all ~2,021 stores (54 API calls)
2. storeSearch — enrich each store with coordinates, services, hours, flags

Uses the ScrapeRunner orchestration pattern for cache, checkpoints,
and parallel extraction.
"""

import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests

from config import homedepot_config as config
from src.shared.constants import HTTP
from src.shared.delays import random_delay
from src.shared.http import log_safe
from src.shared.request_counter import RequestCounter, check_pause_logic
from src.shared.scrape_runner import ScrapeRunner, ScraperContext


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class HomeDepotStore:
    """Data model for Home Depot store information.

    Fields are grouped by category:
    - Identity: store_id, name, store_type
    - Address: street_address, city, state, zip, county, country
    - Geo: latitude, longitude, timezone
    - Contact: phone, pro_desk_phone, tool_rental_phone, services_phone
    - Hours: 7 day columns as "HH:MM-HH:MM" strings
    - Services: 11 boolean fields
    - Flags: 3 boolean fields (BOPIS, BODFS, curbside)
    - Specialty hours: JSON strings for pro desk, tool rental, curbside
    """

    # Required (validation)
    store_id: str
    name: str
    street_address: str
    city: str
    state: str

    # Address
    zip: str
    county: str
    country: str

    # Geo
    latitude: Optional[float]
    longitude: Optional[float]
    timezone: str

    # Contact
    phone: str
    pro_desk_phone: str
    tool_rental_phone: str
    services_phone: str

    # Metadata
    url: str
    store_type: str
    scraped_at: str

    # Hours — 7 columns as "HH:MM-HH:MM" strings
    hours_mon: str
    hours_tue: str
    hours_wed: str
    hours_thu: str
    hours_fri: str
    hours_sat: str
    hours_sun: str

    # Services — 11 boolean fields
    service_load_n_go: bool
    service_propane: bool
    service_tool_rental: bool
    service_penske: bool
    service_key_cutting: bool
    service_wifi: bool
    service_appliance_showroom: bool
    service_flooring_showroom: bool
    service_large_equipment: bool
    service_kitchen_showroom: bool
    service_hd_moving: bool

    # Flags — 3 boolean fields
    flag_bopis: bool
    flag_bodfs: bool
    flag_curbside: bool

    # Specialty hours — JSON strings
    pro_desk_hours: str
    tool_rental_hours: str
    curbside_hours: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export.

        Coordinates are converted to strings for CSV compatibility.
        None coordinates become empty strings.

        Returns:
            Dictionary of all store fields
        """
        result = asdict(self)
        # Convert coordinates to strings for CSV compatibility
        if result.get("latitude") is None:
            result["latitude"] = ""
        else:
            result["latitude"] = str(result["latitude"])
        if result.get("longitude") is None:
            result["longitude"] = ""
        else:
            result["longitude"] = str(result["longitude"])
        return result


# ---------------------------------------------------------------------------
# Hour formatting helpers
# ---------------------------------------------------------------------------

def _format_day_hours(day_data: Optional[Dict[str, str]]) -> str:
    """Convert a single day's hours to "HH:MM-HH:MM" string.

    Args:
        day_data: Dict with 'open' and 'close' keys, or None

    Returns:
        Formatted hours string, or empty string if data is missing
    """
    if not day_data:
        return ""
    open_time = day_data.get("open")
    close_time = day_data.get("close")
    if not open_time or not close_time:
        return ""
    return f"{open_time}-{close_time}"


def _format_hours_json(hours_dict: Optional[Dict]) -> str:
    """Serialize a full week of specialty hours to a JSON string.

    Converts each day's {open, close} dict to a "HH:MM-HH:MM" string,
    then serializes the result as JSON.

    Args:
        hours_dict: Dict with day keys (monday, tuesday, ...) mapping
            to {open, close} dicts, or None

    Returns:
        JSON string of formatted hours, or empty string if data is missing
    """
    if not hours_dict:
        return ""
    formatted = {}
    for day, times in hours_dict.items():
        formatted[day] = _format_day_hours(times)
    return json.dumps(formatted)


# ---------------------------------------------------------------------------
# GraphQL POST with retry
# ---------------------------------------------------------------------------

def _post_graphql(
    session: requests.Session,
    operation_name: str,
    query: str,
    variables: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = None,
    timeout: int = None,
    min_delay: float = None,
    max_delay: float = None,
) -> Optional[Dict]:
    """POST a GraphQL query with retry logic.

    Mirrors the retry semantics of get_with_retry in src/shared/http.py:
    - Exponential backoff on 429/403/5xx
    - Fail-fast on other 4xx
    - Checks for GraphQL-level errors in the response

    Args:
        session: Requests session object
        operation_name: GraphQL operation name (used in URL param)
        query: GraphQL query string
        variables: GraphQL variables dict
        headers: Optional headers override (uses config defaults if None)
        max_retries: Maximum retry attempts
        timeout: Request timeout in seconds
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests

    Returns:
        Parsed JSON response dict, or None on failure
    """
    max_retries = max_retries if max_retries is not None else HTTP.MAX_RETRIES
    timeout = timeout if timeout is not None else HTTP.TIMEOUT

    if headers is None:
        headers = config.get_headers()

    url = f"{config.GRAPHQL_URL}?opname={operation_name}"
    payload = {
        "operationName": operation_name,
        "variables": variables,
        "query": query,
    }

    for attempt in range(max_retries):
        try:
            random_delay(min_delay, max_delay)
            response = session.post(
                url, json=payload, headers=headers, timeout=timeout
            )

            if response.status_code == 200:
                data = response.json()
                # Check for GraphQL-level errors
                if data.get("errors"):
                    error_msgs = [e.get("message", "") for e in data["errors"]]
                    log_safe(
                        f"[homedepot] GraphQL errors for {operation_name}: {error_msgs}",
                        level=logging.WARNING,
                    )
                    return None
                return data

            if response.status_code in (429, 403):
                wait_time = (2 ** attempt) * HTTP.RATE_LIMIT_BASE_WAIT
                log_safe(
                    f"[homedepot] {response.status_code} for {operation_name}. "
                    f"Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})",
                    level=logging.WARNING,
                )
                time.sleep(wait_time)

            elif response.status_code >= 500:
                wait_time = HTTP.SERVER_ERROR_WAIT
                log_safe(
                    f"[homedepot] Server error ({response.status_code}) for "
                    f"{operation_name}. Waiting {wait_time}s "
                    f"(attempt {attempt + 1}/{max_retries})",
                    level=logging.WARNING,
                )
                time.sleep(wait_time)

            else:
                # 4xx (not 429/403) — fail fast
                log_safe(
                    f"[homedepot] Client error ({response.status_code}) for "
                    f"{operation_name}. Failing immediately.",
                    level=logging.ERROR,
                )
                return None

        except requests.exceptions.RequestException as exc:
            wait_time = HTTP.SERVER_ERROR_WAIT
            log_safe(
                f"[homedepot] Request error for {operation_name}: {exc}. "
                f"Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})",
                level=logging.WARNING,
            )
            time.sleep(wait_time)

    log_safe(
        f"[homedepot] Failed {operation_name} after {max_retries} attempts",
        level=logging.ERROR,
    )
    return None


# ---------------------------------------------------------------------------
# Phase 1: Discovery
# ---------------------------------------------------------------------------

def discover_stores(
    session: requests.Session,
    retailer: str = "homedepot",
    yaml_config: dict = None,
    request_counter: RequestCounter = None,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Discover all Home Depot stores by querying each state directory.

    Phase 1: Loops through 54 US states/territories, calling the
    storeDirectoryByState GraphQL operation for each. Returns a flat
    list of store info dicts containing basic data + county.

    Args:
        session: Requests session object
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml
        request_counter: RequestCounter instance for tracking requests
        **kwargs: Additional keyword arguments (unused)

    Returns:
        List of dicts with keys: store_id, name, phone, street_address,
        city, state, zip, county, url
    """
    all_stores: List[Dict[str, Any]] = []

    for state_code in config.US_STATES:
        data = _post_graphql(
            session,
            operation_name="storeDirectoryByState",
            query=config.QUERY_STATE_DIRECTORY,
            variables={"state": state_code},
        )

        if request_counter:
            current_count = request_counter.increment()
            check_pause_logic(
                request_counter, retailer=retailer,
                config=yaml_config, current_count=current_count
            )

        if not data:
            logging.warning(f"[{retailer}] Failed to fetch state: {state_code}")
            continue

        state_data = data.get("data", {}).get("storeDirectoryByState")
        if not state_data:
            continue

        stores_info = state_data.get("storesInfo") or []
        for store in stores_info:
            # Extract store_id from URL last path segment
            url = store.get("url", "")
            store_id = url.rstrip("/").split("/")[-1] if url else ""

            address = store.get("address") or {}
            all_stores.append({
                "store_id": store_id,
                "name": store.get("storeName", ""),
                "phone": store.get("phone", ""),
                "street_address": address.get("street", ""),
                "city": address.get("city", ""),
                "state": address.get("state", ""),
                "zip": address.get("postalCode", ""),
                "county": address.get("county", ""),
                "url": url,
            })

        if stores_info:
            logging.info(
                f"[{retailer}] {state_code}: {len(stores_info)} stores"
            )

    logging.info(f"[{retailer}] Total stores discovered: {len(all_stores)}")
    return all_stores


# ---------------------------------------------------------------------------
# Phase 2: Extraction
# ---------------------------------------------------------------------------

def extract_store_details(
    session: requests.Session,
    item: Dict[str, Any],
    retailer: str = "homedepot",
    yaml_config: dict = None,
    request_counter: RequestCounter = None,
    **kwargs,
) -> Optional[HomeDepotStore]:
    """Extract detailed store data using the storeSearch GraphQL operation.

    Phase 2: For a single store item from Phase 1, calls storeSearch with
    the store ID (zero-padded to 4 digits) and parses the full response
    into a HomeDepotStore dataclass.

    County is merged from the Phase 1 item since storeSearch does not
    return county information.

    Args:
        session: Requests session object
        item: Store info dict from Phase 1 (must contain store_id, county)
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml
        request_counter: RequestCounter instance for tracking requests
        **kwargs: Additional keyword arguments (unused)

    Returns:
        HomeDepotStore object if successful, None otherwise
    """
    store_id = item.get("store_id", "")
    padded_id = store_id.zfill(4)

    data = _post_graphql(
        session,
        operation_name="storeSearch",
        query=config.QUERY_STORE_SEARCH,
        variables={
            "lat": "",
            "lng": "",
            "pagesize": "1",
            "storeFeaturesFilter": config.DEFAULT_FEATURES_FILTER,
            "storeSearchInput": padded_id,
        },
    )

    if request_counter:
        current_count = request_counter.increment()
        check_pause_logic(
            request_counter, retailer=retailer,
            config=yaml_config, current_count=current_count
        )

    if not data:
        logging.warning(f"[{retailer}] Failed to fetch details for store {store_id}")
        return None

    stores = (
        data.get("data", {}).get("storeSearch", {}).get("stores") or []
    )

    if not stores:
        logging.warning(f"[{retailer}] No stores returned for ID {store_id}")
        return None

    # Find the matching store (first result when searching by ID)
    store = stores[0]

    # Parse address
    address = store.get("address") or {}

    # Parse coordinates
    coords = store.get("coordinates") or {}
    latitude = coords.get("lat")
    longitude = coords.get("lng")

    # Parse services (default all False if missing)
    services = store.get("services") or {}

    # Parse store hours
    hours = store.get("storeHours") or {}

    # Parse flags (default all False if missing)
    flags = store.get("flags") or {}

    # Build the URL from base + detail page link
    detail_link = store.get("storeDetailsPageLink", "")
    url = f"https://www.homedepot.com{detail_link}" if detail_link else ""

    return HomeDepotStore(
        store_id=store_id,
        name=store.get("name", ""),
        street_address=address.get("street", ""),
        city=address.get("city", ""),
        state=address.get("state", ""),
        zip=address.get("postalCode", ""),
        county=item.get("county", ""),  # Merged from Phase 1
        country=address.get("country", "US"),
        latitude=latitude,
        longitude=longitude,
        timezone=store.get("storeTimeZone") or "",
        phone=store.get("phone") or "",
        pro_desk_phone=store.get("proDeskPhone") or "",
        tool_rental_phone=store.get("toolRentalPhone") or "",
        services_phone=store.get("storeServicesPhone") or "",
        url=url,
        store_type=store.get("storeType") or "",
        scraped_at=datetime.now().isoformat(),
        # Main store hours
        hours_mon=_format_day_hours(hours.get("monday")),
        hours_tue=_format_day_hours(hours.get("tuesday")),
        hours_wed=_format_day_hours(hours.get("wednesday")),
        hours_thu=_format_day_hours(hours.get("thursday")),
        hours_fri=_format_day_hours(hours.get("friday")),
        hours_sat=_format_day_hours(hours.get("saturday")),
        hours_sun=_format_day_hours(hours.get("sunday")),
        # Services
        service_load_n_go=services.get("loadNGo", False),
        service_propane=services.get("propane", False),
        service_tool_rental=services.get("toolRental", False),
        service_penske=services.get("penske", False),
        service_key_cutting=services.get("keyCutting", False),
        service_wifi=services.get("wiFi", False),
        service_appliance_showroom=services.get("applianceShowroom", False),
        service_flooring_showroom=services.get("expandedFlooringShowroom", False),
        service_large_equipment=services.get("largeEquipment", False),
        service_kitchen_showroom=services.get("kitchenShowroom", False),
        service_hd_moving=services.get("hdMoving", False),
        # Flags
        flag_bopis=flags.get("bopisFlag", False),
        flag_bodfs=flags.get("bodfsFlag", False),
        flag_curbside=flags.get("curbsidePickupFlag", False),
        # Specialty hours (JSON strings)
        pro_desk_hours=_format_hours_json(store.get("proDeskHours")),
        tool_rental_hours=_format_hours_json(store.get("toolRentalHours")),
        curbside_hours=_format_hours_json(store.get("curbsidePickupHours")),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(session, config: dict, **kwargs) -> dict:
    """Standard scraper entry point with ScrapeRunner orchestration.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - retailer: str - Retailer name (default: 'homedepot')
            - resume: bool - Resume from checkpoint
            - limit: int - Max stores to process
            - refresh_urls: bool - Force URL re-discovery

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = kwargs.get("retailer", "homedepot")

    context = ScraperContext(
        retailer=retailer_name,
        session=session,
        config=config,
        resume=kwargs.get("resume", False),
        limit=kwargs.get("limit"),
        refresh_urls=kwargs.get("refresh_urls", False),
        use_rich_cache=True,  # Phase 1 returns dicts with county
    )

    runner = ScrapeRunner(context)

    return runner.run_with_checkpoints(
        url_discovery_func=discover_stores,
        extraction_func=extract_store_details,
        item_key_func=lambda x: x.get("store_id"),
    )
