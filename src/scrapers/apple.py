"""Core scraping functions for Apple Retail Store Locator.

Apple's retail data is built on a Next.js application with a public
GraphQL API (Apollo Server). The scraper uses a two-phase approach:

Phase 1 - Directory Snapshot (1 request):
    Fetch /retail/_next/data/{buildId}/storelist.json to get all stores
    worldwide with IDs, names, slugs, phones, and addresses.

Phase 2 - Detail Enrichment (272 requests for US):
    Fetch /retail/{slug}/ for each store and parse __NEXT_DATA__ JSON
    for hours, coordinates, timezone, services, and images.

No authentication or JS rendering required.
Expected results: ~272 US stores.
"""

import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import apple_config as config
from src.shared import utils
from src.shared.cache import URLCache
from src.shared.request_counter import RequestCounter, check_pause_logic


# Global request counter
_request_counter = RequestCounter()


@dataclass
class AppleStore:
    """Data model for Apple retail store information."""

    store_id: str               # R001, R720
    name: str                   # "Glendale Galleria"
    slug: str                   # "glendalegalleria"
    street_address: str         # "2148 Glendale Galleria"
    address2: str               # Optional second address line
    city: str                   # "Glendale"
    state: str                  # "CA" (2-letter code)
    state_name: str             # "California"
    zip_code: str               # "91210"
    country: str                # "US"
    phone: str                  # "(818) 507-6338"
    email: str                  # store email if available
    latitude: Optional[float]   # From detail page
    longitude: Optional[float]  # From detail page
    timezone: str               # "America/Los_Angeles"
    hours: Optional[str]        # JSON string of weekly hours
    current_status: str         # "Open until 9:00 p.m."
    services: Optional[str]     # JSON string of services by category
    operating_model: str        # "BAU01"
    hero_image_url: str         # Store hero image URL
    programs: Optional[str]     # JSON string of store programs
    url: str                    # Full store detail page URL
    scraped_at: str             # ISO timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary for export.

        Returns:
            Dict with all store fields, coordinates as strings for CSV.
        """
        result = asdict(self)
        for key in ("latitude", "longitude"):
            value = result.get(key)
            result[key] = str(value) if value is not None else ""
        return result


def reset_request_counter() -> None:
    """Reset the global request counter."""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count.

    Returns:
        Number of requests made since last reset.
    """
    return _request_counter.count


def get_build_id(session, retailer: str = "apple", yaml_config: dict = None) -> Optional[str]:
    """Fetch current Next.js buildId from the Apple retail storelist page.

    The buildId changes with each Apple deployment. It is extracted from
    the __NEXT_DATA__ JSON embedded in the HTML of any retail page.

    Args:
        session: Configured requests session
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        Build ID string, or None if extraction fails
    """
    url = f"{config.RETAIL_BASE_URL}/storelist/"
    logging.info(f"[{retailer}] Fetching buildId from {url}")

    response = utils.get_with_retry(
        session,
        url,
        max_retries=config.MAX_RETRIES,
        timeout=config.TIMEOUT,
        headers_func=config.get_headers,
    )

    if not response:
        logging.error(f"[{retailer}] Failed to fetch retail page for buildId")
        return None

    _request_counter.increment()
    if yaml_config:
        check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    match = re.search(r'"buildId"\s*:\s*"([^"]+)"', response.text)
    if match:
        build_id = match.group(1)
        logging.info(f"[{retailer}] Extracted buildId: {build_id}")
        return build_id

    logging.error(f"[{retailer}] Could not find buildId in retail page HTML")
    return None


def get_store_directory(
    session,
    build_id: str,
    retailer: str = "apple",
    yaml_config: dict = None,
) -> List[Dict[str, Any]]:
    """Fetch the complete worldwide store directory from Next.js SSR endpoint.

    Phase 1 of the scraping pipeline. Returns basic store info for all
    stores worldwide, grouped by country and state.

    Args:
        session: Configured requests session
        build_id: Current Next.js build ID
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        List of raw store dicts from the US locale, each containing
        id, name, slug, telephone, and address fields.
    """
    url = config.build_storelist_url(build_id)
    logging.info(f"[{retailer}] Fetching store directory from {url}")

    response = utils.get_with_retry(
        session,
        url,
        max_retries=config.MAX_RETRIES,
        timeout=config.TIMEOUT,
        headers_func=config.get_json_headers,
    )

    if not response:
        logging.error(f"[{retailer}] Failed to fetch store directory")
        return []

    _request_counter.increment()
    if yaml_config:
        check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    try:
        data = response.json()
        store_list = data.get("pageProps", {}).get("storeList", [])

        # Find US locale entry
        us_entry = next(
            (entry for entry in store_list if entry.get("locale") == config.US_LOCALE),
            None,
        )

        if not us_entry:
            logging.warning(f"[{retailer}] US locale not found in store directory")
            return []

        # Flatten: extract all stores from all states
        us_stores = []
        for state in us_entry.get("state", []):
            for store in state.get("store", []):
                us_stores.append(store)

        logging.info(f"[{retailer}] Found {len(us_stores)} US stores in directory")
        return us_stores

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logging.error(f"[{retailer}] Failed to parse store directory: {e}")
        return []


def _parse_hours(hours_data: Dict[str, Any]) -> Optional[str]:
    """Parse store hours from detail page __NEXT_DATA__.

    Args:
        hours_data: Hours object from store detail data containing
            'days' list with formattedDate and formattedTime.

    Returns:
        JSON string of hours list, or None if no hours data
    """
    if not hours_data:
        return None

    days = hours_data.get("days", [])
    if not days:
        return None

    formatted = []
    for day in days:
        formatted.append({
            "name": day.get("name", ""),
            "date": day.get("formattedDate", ""),
            "hours": day.get("formattedTime", ""),
            "special": day.get("specialHours", False),
        })

    return json.dumps(formatted) if formatted else None


def _parse_services(operating_model: Dict[str, Any]) -> Optional[str]:
    """Parse in-store services from the operating model data.

    Args:
        operating_model: Operating model object from store detail data
            containing 'instore' dict with service categories.

    Returns:
        JSON string of services dict keyed by category, or None
    """
    if not operating_model:
        return None

    instore = operating_model.get("instore", {})
    if not instore:
        return None

    services = {}
    for category, details in instore.items():
        if isinstance(details, dict):
            services[category] = details.get("services", [])

    return json.dumps(services) if services else None


def _parse_programs(programs_data: List[Dict[str, Any]]) -> Optional[str]:
    """Parse store programs from detail page data.

    Args:
        programs_data: List of program dicts with 'id' and 'header' fields.

    Returns:
        JSON string of programs list, or None
    """
    if not programs_data:
        return None

    programs = []
    for prog in programs_data:
        programs.append({
            "id": prog.get("id", ""),
            "header": prog.get("header", ""),
        })

    return json.dumps(programs) if programs else None


def _get_hero_image_url(hero_image: Dict[str, Any]) -> str:
    """Extract the best quality hero image URL.

    Args:
        hero_image: Hero image object with size variants.

    Returns:
        URL string for the largest available image, or empty string
    """
    if not hero_image:
        return ""

    # Prefer large > medium > small
    for size in ("large", "medium", "small"):
        size_data = hero_image.get(size, {})
        if isinstance(size_data, dict):
            url = size_data.get("x2", "") or size_data.get("x1", "")
            if url:
                return url

    return ""


def extract_store_detail(
    session,
    slug: str,
    directory_data: Dict[str, Any],
    retailer: str = "apple",
    yaml_config: dict = None,
) -> Optional[AppleStore]:
    """Fetch and parse a store detail page for rich data enrichment.

    Phase 2 of the scraping pipeline. Fetches the store's detail page
    and extracts comprehensive data from the __NEXT_DATA__ JSON blob.

    Args:
        session: Configured requests session
        slug: Store URL slug (e.g., 'glendalegalleria')
        directory_data: Basic store data from Phase 1 directory
        retailer: Retailer name for logging
        yaml_config: Retailer configuration from retailers.yaml

    Returns:
        AppleStore object with enriched data, or None on failure
    """
    url = config.build_store_detail_url(slug)
    logging.debug(f"[{retailer}] Fetching detail page for {slug}")

    response = utils.get_with_retry(
        session,
        url,
        max_retries=config.MAX_RETRIES,
        timeout=config.TIMEOUT,
        headers_func=config.get_headers,
    )

    if not response:
        logging.warning(f"[{retailer}] Failed to fetch detail page: {url}")
        return _build_store_from_directory(directory_data, slug, url)

    _request_counter.increment()
    if yaml_config:
        check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    try:
        # Extract __NEXT_DATA__ JSON from HTML
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            response.text,
            re.DOTALL,
        )

        if not match:
            logging.warning(f"[{retailer}] No __NEXT_DATA__ found for {slug}")
            return _build_store_from_directory(directory_data, slug, url)

        next_data = json.loads(match.group(1))
        store_data = (
            next_data.get("props", {})
            .get("pageProps", {})
            .get("storeDetails", {})
        )

        if not store_data:
            logging.warning(f"[{retailer}] No storeDetails in __NEXT_DATA__ for {slug}")
            return _build_store_from_directory(directory_data, slug, url)

        # Extract address
        address = store_data.get("address", {})
        geolocation = store_data.get("geolocation", {})
        hours_data = store_data.get("hours", {})
        operating_model = store_data.get("operatingModel", {})
        hero_image = store_data.get("heroImage", {})
        programs_data = store_data.get("programs", [])

        return AppleStore(
            store_id=store_data.get("storeNumber", directory_data.get("id", "")),
            name=store_data.get("name", directory_data.get("name", "")),
            slug=store_data.get("slug", slug),
            street_address=address.get("address1", ""),
            address2=address.get("address2", ""),
            city=address.get("city", ""),
            state=address.get("stateCode", ""),
            state_name=address.get("stateName", ""),
            zip_code=address.get("postal", ""),
            country="US",
            phone=store_data.get("telephone", directory_data.get("telephone", "")),
            email=store_data.get("email", ""),
            latitude=geolocation.get("latitude"),
            longitude=geolocation.get("longitude"),
            timezone=store_data.get("timezone", ""),
            hours=_parse_hours(hours_data),
            current_status=hours_data.get("currentStatus", ""),
            services=_parse_services(operating_model),
            operating_model=operating_model.get("operatingModelId", ""),
            hero_image_url=_get_hero_image_url(hero_image),
            programs=_parse_programs(programs_data),
            url=url,
            scraped_at=datetime.now().isoformat(),
        )

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logging.warning(f"[{retailer}] Error parsing detail page for {slug}: {e}")
        return _build_store_from_directory(directory_data, slug, url)


def _build_store_from_directory(
    directory_data: Dict[str, Any],
    slug: str,
    url: str,
) -> AppleStore:
    """Build an AppleStore from directory data only (fallback when detail page fails).

    Args:
        directory_data: Basic store data from Phase 1 directory
        slug: Store URL slug
        url: Full store detail URL

    Returns:
        AppleStore with directory-level data, missing detail enrichment fields
    """
    address = directory_data.get("address", {})

    return AppleStore(
        store_id=directory_data.get("id", ""),
        name=directory_data.get("name", ""),
        slug=slug,
        street_address=address.get("address1", ""),
        address2=address.get("address2", ""),
        city=address.get("city", ""),
        state=address.get("stateCode", ""),
        state_name=address.get("stateName", ""),
        zip_code=address.get("postalCode", ""),
        country="US",
        phone=directory_data.get("telephone", ""),
        email="",
        latitude=None,
        longitude=None,
        timezone="",
        hours=None,
        current_status="",
        services=None,
        operating_model="",
        hero_image_url="",
        programs=None,
        url=url,
        scraped_at=datetime.now().isoformat(),
    )


def run(session, retailer_config: dict, retailer: str = "apple", **kwargs) -> dict:
    """Standard scraper entry point for Apple retail stores.

    Two-phase pipeline:
    1. Fetch global store directory (1 request) to discover all US stores
    2. Enrich each store by fetching its detail page (272 requests)

    Args:
        session: Configured session (requests.Session or ProxyClient)
        retailer_config: Retailer configuration dict from retailers.yaml
        retailer: Retailer name for logging
        **kwargs: Additional options
            - limit: int - Max stores to return
            - resume: bool - Resume from checkpoint
            - refresh_urls: bool - Force re-discovery (ignore cache)
            - test: bool - Test mode (limits stores)

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = retailer
    logging.info(f"[{retailer_name}] Starting scrape run")

    try:
        limit = kwargs.get("limit")
        resume = kwargs.get("resume", False)
        refresh_urls = kwargs.get("refresh_urls", False)
        test_mode = kwargs.get("test", False)

        reset_request_counter()

        # Auto-select delays based on proxy mode
        proxy_mode = retailer_config.get("proxy", {}).get("mode", "direct")
        min_delay, max_delay = utils.select_delays(retailer_config, proxy_mode)
        logging.info(
            f"[{retailer_name}] Using delays: {min_delay:.1f}-{max_delay:.1f}s "
            f"(mode: {proxy_mode})"
        )

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = retailer_config.get("checkpoint_interval", 25)

        stores: List[dict] = []
        completed_slugs: set = set()
        checkpoints_used = False

        # Resume from checkpoint if requested
        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores = checkpoint.get("stores", [])
                completed_slugs = set(checkpoint.get("completed_slugs", []))
                logging.info(
                    f"[{retailer_name}] Resuming from checkpoint: "
                    f"{len(stores)} stores already collected"
                )
                checkpoints_used = True

        # Phase 1: Get store directory
        # Try URL cache first (stores slugs from previous directory fetch)
        url_cache = URLCache(retailer_name)
        cached_slugs = None
        if not refresh_urls:
            cached_slugs = url_cache.get()

        if cached_slugs is not None:
            logging.info(f"[{retailer_name}] Using {len(cached_slugs)} cached store slugs")
            directory_stores = [
                {"slug": slug_str, "id": "", "name": "", "telephone": "", "address": {}}
                for slug_str in cached_slugs
            ]
        else:
            # Fetch buildId and directory
            build_id = get_build_id(session, retailer_name, yaml_config=retailer_config)
            if not build_id:
                logging.error(f"[{retailer_name}] Cannot proceed without buildId")
                return {"stores": [], "count": 0, "checkpoints_used": False}

            directory_stores = get_store_directory(
                session, build_id, retailer_name, yaml_config=retailer_config
            )

            if not directory_stores:
                logging.warning(f"[{retailer_name}] No stores found in directory")
                return {"stores": [], "count": 0, "checkpoints_used": False}

            # Cache the slugs for future runs
            slugs_to_cache = [s.get("slug", "") for s in directory_stores if s.get("slug")]
            if slugs_to_cache:
                url_cache.set(slugs_to_cache)

        # Apply test mode limit
        if test_mode and not limit:
            from src.shared.constants import TEST_MODE
            limit = TEST_MODE.STORE_LIMIT
            logging.info(f"[{retailer_name}] Test mode: limiting to {limit} stores")

        # Filter out already-completed slugs
        remaining_stores = [
            s for s in directory_stores
            if s.get("slug", "") not in completed_slugs
        ]

        if resume and completed_slugs:
            logging.info(
                f"[{retailer_name}] Skipping {len(directory_stores) - len(remaining_stores)} "
                f"already-processed stores"
            )

        # Apply limit
        if limit:
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_stores = remaining_stores[:total_needed]
            else:
                remaining_stores = []

        total_to_process = len(remaining_stores)
        if total_to_process > 0:
            logging.info(f"[{retailer_name}] Enriching details for {total_to_process} stores")
        else:
            logging.info(f"[{retailer_name}] No new stores to process")

        # Phase 2: Sequential detail enrichment
        for i, dir_store in enumerate(remaining_stores, 1):
            slug = dir_store.get("slug", "")
            if not slug:
                continue

            store_obj = extract_store_detail(
                session, slug, dir_store, retailer_name, yaml_config=retailer_config
            )

            if store_obj:
                stores.append(store_obj.to_dict())
                completed_slugs.add(slug)

            # Progress logging every 25 stores
            if i % 25 == 0:
                logging.info(
                    f"[{retailer_name}] Progress: {i}/{total_to_process} "
                    f"({i / total_to_process * 100:.1f}%)"
                )

            # Checkpoint at intervals
            if i % checkpoint_interval == 0:
                utils.save_checkpoint(
                    {
                        "completed_count": len(stores),
                        "completed_slugs": list(completed_slugs),
                        "stores": stores,
                        "last_updated": datetime.now().isoformat(),
                    },
                    checkpoint_path,
                )
                logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores")

            # Respect rate limiting
            utils.random_delay(min_delay, max_delay)

        # Final checkpoint
        if stores:
            utils.save_checkpoint(
                {
                    "completed_count": len(stores),
                    "completed_slugs": list(completed_slugs),
                    "stores": stores,
                    "last_updated": datetime.now().isoformat(),
                },
                checkpoint_path,
            )

        # Validate store data
        if stores:
            validation_summary = utils.validate_stores_batch(stores)
            logging.info(
                f"[{retailer_name}] Validation: {validation_summary['valid']}/"
                f"{validation_summary['total']} valid, "
                f"{validation_summary['warning_count']} warnings"
            )

        logging.info(f"[{retailer_name}] Completed: {len(stores)} stores scraped")

        return {
            "stores": stores,
            "count": len(stores),
            "checkpoints_used": checkpoints_used,
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
