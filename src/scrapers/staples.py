"""Staples Store Scraper.

Extracts store location data from Staples using a 3-phase approach:
  Phase 1: Bulk store number scan via StaplesConnect REST API
  Phase 2: ZIP code gap-fill via store locator for missed stores
  Phase 3: Service enrichment via StaplesConnect services endpoint

StaplesConnect API is the primary data source (richer data, scannable by
store number). The store locator provides geographic search and features
data not available from StaplesConnect.

Supports:
  - Parallel store number scanning with ThreadPoolExecutor
  - Checkpoint/resume for long-running scans
  - Proxy integration via Oxylabs Web Scraper API
  - Test mode with configurable store limits
  - Deduplication by store number
"""

import base64
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests as req_lib

from config import staples_config as config
from src.shared import utils
from src.shared.proxy_client import ProxyClient, ProxyConfig, ProxyMode

logger = logging.getLogger(__name__)

# Days of the week for hours parsing
DAYS_OF_WEEK = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]

DAY_SHORT_TO_FULL = {
    "MON": "monday", "TUE": "tuesday", "WED": "wednesday",
    "THU": "thursday", "FRI": "friday", "SAT": "saturday", "SUN": "sunday",
}


@dataclass
class StaplesStore:
    """Represents a single Staples store location.

    Fields are sourced from both StaplesConnect and Store Locator APIs,
    merged by store number as the unique key.
    """

    store_id: str
    name: str
    street_address: str
    address_line2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = "US"
    latitude: str = ""
    longitude: str = ""
    phone: str = ""
    fax: str = ""
    timezone: str = ""
    store_url: str = ""
    plaza_mall: str = ""
    store_region: str = ""
    store_district: str = ""
    store_division: str = ""
    published_status: str = ""
    hours_monday: str = ""
    hours_tuesday: str = ""
    hours_wednesday: str = ""
    hours_thursday: str = ""
    hours_friday: str = ""
    hours_saturday: str = ""
    hours_sunday: str = ""
    features: str = ""
    services: str = ""
    google_place_id: str = ""
    scraped_at: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Convert store to dictionary for export.

        Returns:
            Dictionary with all store fields as string values.
        """
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()

        return {
            "store_id": self.store_id,
            "name": self.name,
            "street_address": self.street_address,
            "address_line2": self.address_line2,
            "city": self.city,
            "state": self.state,
            "zip": self.zip,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "phone": self.phone,
            "fax": self.fax,
            "timezone": self.timezone,
            "url": self.store_url,
            "plaza_mall": self.plaza_mall,
            "store_region": self.store_region,
            "store_district": self.store_district,
            "store_division": self.store_division,
            "published_status": self.published_status,
            "hours_monday": self.hours_monday,
            "hours_tuesday": self.hours_tuesday,
            "hours_wednesday": self.hours_wednesday,
            "hours_thursday": self.hours_thursday,
            "hours_friday": self.hours_friday,
            "hours_saturday": self.hours_saturday,
            "hours_sunday": self.hours_sunday,
            "features": self.features,
            "services": self.services,
            "google_place_id": self.google_place_id,
            "scraped_at": self.scraped_at,
        }


def _format_phone(raw_phone: str) -> str:
    """Format a raw phone number string into (XXX) XXX-XXXX.

    Args:
        raw_phone: Phone digits without formatting (e.g., "7329189446").

    Returns:
        Formatted phone string, or original if not 10 digits.
    """
    digits = "".join(c for c in raw_phone if c.isdigit())
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw_phone


def _format_hours_staplesconnect(store_hours: List[Dict[str, Any]]) -> Dict[str, str]:
    """Parse StaplesConnect storeHours array into per-day strings.

    Args:
        store_hours: List of hour objects with 'day', 'open', 'close' fields.

    Returns:
        Dict mapping lowercase day names to formatted hour strings.
        Example: {"monday": "8:00 AM - 9:00 PM"}
    """
    hours_map: Dict[str, str] = {}
    for entry in store_hours:
        day_short = entry.get("dayShort", "")
        day_name = DAY_SHORT_TO_FULL.get(day_short, "")
        if not day_name:
            continue

        if entry.get("close24Hr", False):
            hours_map[day_name] = "Closed"
        elif entry.get("open24Hr", False):
            hours_map[day_name] = "Open 24 Hours"
        else:
            formatted = entry.get("formattedStoreHours", "")
            if formatted:
                hours_map[day_name] = formatted
            else:
                open_time = entry.get("open", "")
                close_time = entry.get("close", "")
                if open_time and close_time:
                    hours_map[day_name] = f"{open_time} - {close_time}"

    return hours_map


def _format_hours_locator(working_hours: List[Dict[str, Any]]) -> Dict[str, str]:
    """Parse store locator workingHours array into per-day strings.

    Args:
        working_hours: List of hour objects with 'day', 'openTime', 'closeTime'.

    Returns:
        Dict mapping lowercase day names to formatted hour strings.
        Example: {"monday": "8am - 9pm"}
    """
    hours_map: Dict[str, str] = {}
    for entry in working_hours:
        day = entry.get("day", "").lower()
        if day not in DAYS_OF_WEEK:
            continue
        open_time = entry.get("openTime", "")
        close_time = entry.get("closeTime", "")
        if open_time and close_time:
            hours_map[day] = f"{open_time} - {close_time}"
    return hours_map


def _format_features(features_list: List[Dict[str, str]]) -> str:
    """Convert features array to comma-separated label string.

    Args:
        features_list: List of feature objects with 'featureLabel' field.

    Returns:
        Comma-separated string of feature labels.
    """
    labels = [f.get("featureLabel", "") for f in features_list if f.get("featureLabel")]
    return ", ".join(labels)


def _format_services(services_data: Any) -> str:
    """Convert services data to comma-separated string.

    Handles both the locator's string array format and StaplesConnect's
    object array format.

    Args:
        services_data: Either a list of strings or list of dicts with
            'serviceName' field.

    Returns:
        Comma-separated string of service names.
    """
    if not services_data:
        return ""

    if isinstance(services_data, list):
        names = []
        for item in services_data:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("serviceName", "")
                if name and item.get("active", True):
                    names.append(name)
        return ", ".join(names)

    return str(services_data)


def _parse_staplesconnect_store(data: Dict[str, Any]) -> Optional[StaplesStore]:
    """Parse a StaplesConnect API response into a StaplesStore.

    Args:
        data: JSON response from GET /api/store/{number}.

    Returns:
        StaplesStore instance, or None if data is invalid.
    """
    store_number = str(data.get("storeNumber", ""))
    if not store_number:
        return None

    address = data.get("address", {})

    # Parse hours
    store_hours = data.get("storeHours", [])
    hours_map = _format_hours_staplesconnect(store_hours)

    # Parse services
    services = _format_services(data.get("storeServices", []))

    # Build store URL from slugs
    url_state = address.get("urlState", "")
    url_city = address.get("urlCity", "")
    url_address = address.get("urlAddress", "")
    store_url = ""
    if url_state and url_city and url_address:
        store_url = (
            f"https://www.staplesconnect.com/{url_state}/{url_city}/{url_address}"
        )

    return StaplesStore(
        store_id=store_number,
        name=data.get("name", data.get("storeTitle", "")),
        street_address=address.get("address_1", ""),
        address_line2=address.get("address_2", ""),
        city=address.get("city", ""),
        state=address.get("region", ""),
        zip=address.get("postal_code", ""),
        country=address.get("country", "US"),
        latitude=str(data.get("latitude", "")),
        longitude=str(data.get("longitude", "")),
        phone=_format_phone(data.get("phoneNumber", "")),
        fax=_format_phone(data.get("faxNumber", "")),
        timezone=data.get("timezone", ""),
        store_url=store_url,
        plaza_mall=data.get("plazaMall", ""),
        store_region=data.get("storeRegion", ""),
        store_district=data.get("storeDistrict", ""),
        store_division=data.get("storeDivision", ""),
        published_status=data.get("publishedStatus", ""),
        hours_monday=hours_map.get("monday", ""),
        hours_tuesday=hours_map.get("tuesday", ""),
        hours_wednesday=hours_map.get("wednesday", ""),
        hours_thursday=hours_map.get("thursday", ""),
        hours_friday=hours_map.get("friday", ""),
        hours_saturday=hours_map.get("saturday", ""),
        hours_sunday=hours_map.get("sunday", ""),
        services=services,
    )


def _parse_locator_store(data: Dict[str, Any]) -> Optional[StaplesStore]:
    """Parse a store locator API response into a StaplesStore.

    Args:
        data: Single store object from the locator's results.stores array.

    Returns:
        StaplesStore instance, or None if data is invalid.
    """
    store_number = str(data.get("storeNumber", ""))
    if not store_number:
        return None

    address = data.get("address", {})

    # Parse hours
    working_hours = data.get("workingHours", [])
    hours_map = _format_hours_locator(working_hours)

    # Parse features and services
    features = _format_features(data.get("features", []))
    services = _format_services(data.get("instoreServices", []))

    return StaplesStore(
        store_id=store_number,
        name=f"Staples Store {store_number}",
        street_address=address.get("addressLine1", ""),
        city=address.get("city", ""),
        state=address.get("state", ""),
        zip=address.get("zipcode", ""),
        country=address.get("country", "US"),
        latitude=str(data.get("latitude", "")),
        longitude=str(data.get("longitude", "")),
        phone=_format_phone(address.get("phoneNumber", "")),
        fax=_format_phone(address.get("faxNumber", "")),
        hours_monday=hours_map.get("monday", ""),
        hours_tuesday=hours_map.get("tuesday", ""),
        hours_wednesday=hours_map.get("wednesday", ""),
        hours_thursday=hours_map.get("thursday", ""),
        hours_friday=hours_map.get("friday", ""),
        hours_saturday=hours_map.get("saturday", ""),
        hours_sunday=hours_map.get("sunday", ""),
        features=features,
        services=services,
        google_place_id=data.get("placeId", ""),
    )


def _merge_store_data(
    primary: StaplesStore,
    secondary: StaplesStore,
) -> StaplesStore:
    """Merge two StaplesStore objects, preferring primary for shared fields.

    Fields unique to secondary (features, google_place_id) are added
    to the primary store if missing.

    Args:
        primary: Main store data (typically from StaplesConnect).
        secondary: Supplemental data (typically from store locator).

    Returns:
        Merged StaplesStore with combined data.
    """
    # Enrich primary with fields only secondary has
    if not primary.features and secondary.features:
        primary.features = secondary.features
    if not primary.google_place_id and secondary.google_place_id:
        primary.google_place_id = secondary.google_place_id

    # Fill empty fields from secondary
    if not primary.latitude and secondary.latitude:
        primary.latitude = secondary.latitude
    if not primary.longitude and secondary.longitude:
        primary.longitude = secondary.longitude
    if not primary.phone and secondary.phone:
        primary.phone = secondary.phone

    # Merge services: combine unique services from both sources
    if secondary.services and not primary.services:
        primary.services = secondary.services
    elif secondary.services and primary.services:
        primary_set = set(s.strip() for s in primary.services.split(","))
        secondary_set = set(s.strip() for s in secondary.services.split(","))
        combined = primary_set | secondary_set
        primary.services = ", ".join(sorted(combined))

    return primary


def _fetch_store_detail(
    store_number: str,
    proxy_client: ProxyClient,
) -> Optional[Dict[str, Any]]:
    """Fetch store detail from StaplesConnect API.

    Args:
        store_number: Store number to fetch (e.g., "1571").
        proxy_client: Configured ProxyClient instance.

    Returns:
        Parsed JSON dict if store exists, None if 404 or error.
    """
    url = config.build_store_detail_url(store_number)
    response = proxy_client.get(url, headers=config.get_headers())

    if response is None:
        return None

    if response.status_code == 404:
        return None

    if response.ok:
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            logger.warning("Invalid JSON for store %s", store_number)
            return None

    return None


def _fetch_store_services(
    store_number: str,
    proxy_client: ProxyClient,
) -> Optional[List[Dict[str, Any]]]:
    """Fetch store services from StaplesConnect services API.

    Args:
        store_number: Store number to fetch services for.
        proxy_client: Configured ProxyClient instance.

    Returns:
        List of service dicts, or None on error.
    """
    url = config.build_services_url(store_number)
    response = proxy_client.get(url, headers=config.get_headers())

    if response is None or not response.ok:
        return None

    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        return None


def _scan_worker(
    store_number: str,
    proxy_client: ProxyClient,
) -> Tuple[str, Optional[StaplesStore]]:
    """Worker function for parallel store number scanning.

    Args:
        store_number: Store number to scan.
        proxy_client: ProxyClient instance (thread-safe for Web Scraper API).

    Returns:
        Tuple of (store_number, StaplesStore or None).
    """
    data = _fetch_store_detail(store_number, proxy_client)
    if data is None:
        return store_number, None

    store = _parse_staplesconnect_store(data)
    return store_number, store


def _generate_store_numbers() -> List[str]:
    """Generate all store numbers to scan from configured ranges.

    Returns:
        List of zero-padded store number strings.
    """
    numbers = []
    for start, end in config.STORE_NUMBER_RANGES:
        for i in range(start, end):
            numbers.append(str(i).zfill(4))
    return numbers


def _scan_store_numbers(
    proxy_client: ProxyClient,
    retailer_config: Dict[str, Any],
    resume: bool = False,
    limit: int = 0,
    test: bool = False,
) -> Tuple[Dict[str, StaplesStore], bool]:
    """Phase 1: Scan store numbers via StaplesConnect API.

    Args:
        proxy_client: Configured ProxyClient.
        retailer_config: YAML configuration for staples.
        resume: Whether to resume from checkpoint.
        limit: Maximum stores to collect (0 = unlimited).
        test: If True, scan only first 20 store numbers.

    Returns:
        Tuple of (stores dict keyed by store_number, checkpoints_used bool).
    """
    stores: Dict[str, StaplesStore] = {}
    store_lock = threading.Lock()
    checkpoints_used = False

    # Determine store numbers to scan
    all_numbers = _generate_store_numbers()
    if test:
        all_numbers = all_numbers[:20]

    # Checkpoint support
    checkpoint_dir = Path("data/staples/checkpoints")
    checkpoint_path = checkpoint_dir / "scan_checkpoint.json"
    scanned_numbers: Set[str] = set()

    if resume and checkpoint_path.exists():
        checkpoint = utils.load_checkpoint(str(checkpoint_path))
        if checkpoint:
            scanned_numbers = set(checkpoint.get("scanned", []))
            for store_data in checkpoint.get("stores", []):
                store = _parse_staplesconnect_store(store_data)
                if store:
                    stores[store.store_id] = store
            checkpoints_used = True
            logger.info(
                "Resumed from checkpoint: %d scanned, %d stores found",
                len(scanned_numbers), len(stores),
            )

    # Filter out already-scanned numbers
    remaining = [n for n in all_numbers if n not in scanned_numbers]
    logger.info(
        "Phase 1: Scanning %d store numbers (%d already scanned)",
        len(remaining), len(scanned_numbers),
    )

    # Parallel scanning
    max_workers = retailer_config.get("parallel_workers", 5)
    checkpoint_interval = retailer_config.get("checkpoint_interval", 100)
    processed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_scan_worker, num, proxy_client): num
            for num in remaining
        }

        for future in as_completed(futures):
            store_number = futures[future]
            try:
                _, store = future.result()
                with store_lock:
                    scanned_numbers.add(store_number)
                    if store:
                        stores[store.store_id] = store
                    processed_count += 1

                    # Progress logging
                    if processed_count % 100 == 0:
                        logger.info(
                            "Phase 1 progress: %d/%d scanned, %d stores found",
                            processed_count, len(remaining), len(stores),
                        )

                    # Checkpoint (inside lock to prevent race condition)
                    if processed_count % checkpoint_interval == 0:
                        checkpoint_dir.mkdir(parents=True, exist_ok=True)
                        checkpoint_data = {
                            "scanned": list(scanned_numbers),
                            "stores": [
                                {"storeNumber": s.store_id, "name": s.name}
                                for s in stores.values()
                            ],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        utils.save_checkpoint(checkpoint_data, str(checkpoint_path))

                    # Limit check
                    store_count = len(stores)

                if limit and store_count >= limit:
                    logger.info("Reached store limit of %d", limit)
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

            except Exception as e:
                logger.warning("Error scanning store %s: %s", store_number, e)

    logger.info("Phase 1 complete: %d stores found from %d numbers", len(stores), len(scanned_numbers))
    return stores, checkpoints_used


def _zip_code_gap_fill(
    proxy_client: ProxyClient,
    known_store_ids: Set[str],
    test: bool = False,
) -> Dict[str, StaplesStore]:
    """Phase 2: Geographic gap-fill using store locator ZIP code sweep.

    Args:
        proxy_client: Configured ProxyClient.
        known_store_ids: Set of store IDs already found in Phase 1.
        test: If True, only sweep 5 ZIP codes.

    Returns:
        Dict of newly discovered stores keyed by store number.
    """
    new_stores: Dict[str, StaplesStore] = {}
    zip_codes = config.GAP_FILL_ZIP_CODES[:5] if test else config.GAP_FILL_ZIP_CODES

    logger.info("Phase 2: Sweeping %d ZIP codes for gap-fill", len(zip_codes))

    for i, zip_code in enumerate(zip_codes, 1):
        stores = _search_stores_by_zip(proxy_client, zip_code)
        for store in stores:
            if store.store_id not in known_store_ids and store.store_id not in new_stores:
                new_stores[store.store_id] = store
                logger.debug("Gap-fill found new store: %s", store.store_id)

        if i % 10 == 0:
            logger.info("Phase 2 progress: %d/%d ZIPs, %d new stores", i, len(zip_codes), len(new_stores))

    logger.info("Phase 2 complete: %d new stores found", len(new_stores))
    return new_stores


def _search_stores_by_zip(
    proxy_client: ProxyClient,
    zip_code: str,
) -> List[StaplesStore]:
    """Search for stores near a ZIP code via the store locator API.

    Uses Oxylabs Web Scraper API with POST method to call the
    store locator endpoint.

    Args:
        proxy_client: Configured ProxyClient.
        zip_code: 5-digit US ZIP code.

    Returns:
        List of StaplesStore objects found near the ZIP code.
    """
    post_body = json.dumps({
        "address": zip_code,
        "radius": config.LOCATOR_SEARCH_RADIUS,
    })

    # For Web Scraper API, we need to construct a POST request
    # through the proxy's universal source
    if proxy_client.config.mode == ProxyMode.WEB_SCRAPER_API:
        encoded_body = base64.b64encode(post_body.encode()).decode()
        payload = {
            "source": "universal",
            "url": config.STORE_LOCATOR_URL,
            "context": [
                {"key": "http_method", "value": "post"},
                {"key": "content", "value": encoded_body},
                {"key": "force_headers", "value": True},
                {"key": "headers", "value": {
                    "Content-Type": "application/json",
                }},
            ],
        }

        response = req_lib.post(
            proxy_client.config.scraper_api_endpoint,
            auth=(proxy_client.config.username, proxy_client.config.password),
            json=payload,
            timeout=proxy_client.config.timeout,
        )

        if response.status_code == 200:
            api_data = response.json()
            content = api_data.get("results", [{}])[0].get("content", "")
            try:
                store_data = json.loads(content)
                raw_stores = store_data.get("results", {}).get("stores", [])
                return [s for s in (_parse_locator_store(r) for r in raw_stores) if s]
            except (json.JSONDecodeError, ValueError):
                return []
    else:
        # Direct mode: POST directly (may fail without session cookies)
        import requests as req_lib  # noqa: E402 - conditional import
        try:
            response = req_lib.post(
                config.STORE_LOCATOR_URL,
                json={"address": zip_code, "radius": config.LOCATOR_SEARCH_RADIUS},
                headers=config.get_locator_headers(),
                timeout=config.TIMEOUT,
            )
            if response.status_code == 200:
                data = response.json()
                raw_stores = data.get("results", {}).get("stores", [])
                return [s for s in (_parse_locator_store(r) for r in raw_stores) if s]
        except (req_lib.RequestException, json.JSONDecodeError, ValueError):
            pass

    return []


def _enrich_services(
    stores: Dict[str, StaplesStore],
    proxy_client: ProxyClient,
    max_workers: int = 3,
    test: bool = False,
) -> None:
    """Phase 3: Enrich stores with service details from StaplesConnect.

    Modifies stores dict in-place by fetching and adding service data.

    Args:
        stores: Dict of stores to enrich.
        proxy_client: Configured ProxyClient.
        max_workers: Number of parallel workers for service fetching.
        test: If True, only enrich first 5 stores.
    """
    store_ids = list(stores.keys())
    if test:
        store_ids = store_ids[:5]

    logger.info("Phase 3: Enriching %d stores with service data", len(store_ids))

    enriched = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_store_services, sid, proxy_client): sid
            for sid in store_ids
        }

        for future in as_completed(futures):
            sid = futures[future]
            try:
                services = future.result()
                if services:
                    stores[sid].services = _format_services(services)
                    enriched += 1
            except Exception as e:
                logger.warning("Error enriching store %s: %s", sid, e)

    logger.info("Phase 3 complete: %d/%d stores enriched", enriched, len(store_ids))


def run(
    session: req_lib.Session,
    retailer_config: Dict[str, Any],
    retailer: str = "staples",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Main entry point for the Staples scraper.

    Orchestrates 3-phase scraping:
      1. Store number scan via StaplesConnect API
      2. ZIP code gap-fill via store locator
      3. Service enrichment

    Args:
        session: Requests session (may be proxied).
        retailer_config: YAML config dict for staples.
        retailer: Retailer name string.
        **kwargs: Additional options:
            - test (bool): Run in test mode with reduced scope.
            - limit (int): Maximum number of stores to collect.
            - resume (bool): Resume from checkpoint.
            - refresh_urls (bool): Ignored (no URL caching).

    Returns:
        Dict with keys:
            - stores: List of store dicts
            - count: Number of stores
            - checkpoints_used: Whether checkpoints were used
    """
    test = kwargs.get("test", False)
    limit = kwargs.get("limit", 0)
    resume = kwargs.get("resume", False)

    logger.info("Starting Staples scraper (test=%s, limit=%s, resume=%s)", test, limit, resume)

    # Create proxy client from retailer config
    proxy_config_dict = retailer_config.get("proxy", {})
    proxy_client = ProxyClient(ProxyConfig.from_dict(proxy_config_dict))

    # Phase 1: Store number scan
    stores, checkpoints_used = _scan_store_numbers(
        proxy_client=proxy_client,
        retailer_config=retailer_config,
        resume=resume,
        limit=limit,
        test=test,
    )

    # Phase 2: ZIP code gap-fill (skip if we hit the limit already)
    if not limit or len(stores) < limit:
        gap_fill_stores = _zip_code_gap_fill(
            proxy_client=proxy_client,
            known_store_ids=set(stores.keys()),
            test=test,
        )
        # Merge gap-fill stores (add new, merge existing)
        for sid, store in gap_fill_stores.items():
            if sid in stores:
                stores[sid] = _merge_store_data(stores[sid], store)
            else:
                stores[sid] = store

    # Phase 3: Service enrichment
    max_workers = retailer_config.get("parallel_workers", 3)
    _enrich_services(stores, proxy_client, max_workers=max_workers, test=test)

    # Convert to list of dicts
    store_dicts = [store.to_dict() for store in stores.values()]

    # Validate
    if store_dicts:
        validation_summary = utils.validate_stores_batch(store_dicts)
        logger.info(
            "Validation: %d valid, %d with warnings, %d with errors",
            validation_summary.get("valid", 0),
            validation_summary.get("warnings", 0),
            validation_summary.get("errors", 0),
        )

    # Clean up
    proxy_client.close()

    logger.info("Staples scraper complete: %d stores", len(store_dicts))

    return {
        "stores": store_dicts,
        "count": len(store_dicts),
        "checkpoints_used": checkpoints_used,
    }
