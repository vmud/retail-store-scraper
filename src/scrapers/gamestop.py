"""Core scraping functions for GameStop Store Locator.

GameStop runs on Salesforce Commerce Cloud (SFCC/Demandware) with
Cloudflare WAF protection. Three-phase scraping approach:

Phase 1 - Geographic Grid Discovery (~90 API calls):
    Query the Stores-FindStores endpoint at grid points across the US
    with a 200-mile radius. Deduplicate by store ID.

Phase 2 - Detail Page Enrichment (~4,000 page fetches):
    Fetch each store's detail page and extract Schema.org JSON-LD
    for additional fields (description, knowsAbout, paymentAccepted).

Phase 3 - Deduplication & Export:
    Merge Phase 1 + 2 data, validate, and return normalized stores.

API: Stores-FindStores (no auth, Cloudflare JS challenge)
Bot Protection: Cloudflare - requires residential proxy for sustained access.
Expected results: ~4,000+ US stores.
"""

import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from config import gamestop_config as config
from src.shared import utils
from src.shared.request_counter import RequestCounter, check_pause_logic


# Global request counter
_request_counter = RequestCounter()


@dataclass
class GameStopStore:
    """Data model for GameStop store information."""

    store_id: str               # Numeric store ID (e.g., "6562")
    name: str                   # Store location name
    street_address: str         # Primary street address
    address2: str               # Suite/unit (nullable)
    city: str                   # City name
    state: str                  # Two-letter state code
    zip_code: str               # US zip code
    country: str                # Country code (default "US")
    latitude: Optional[float]   # Latitude coordinate
    longitude: Optional[float]  # Longitude coordinate
    phone: str                  # Phone number
    store_mode: str             # Status: "ACTIVE", etc.
    hours: Optional[str]        # JSON string of daily hours
    midday_closure: bool        # Whether store closes midday
    description: str            # From JSON-LD (templated SEO text)
    knows_about: str            # Pipe-separated product categories
    payment_accepted: str       # Pipe-separated payment methods
    currencies_accepted: str    # Supported currencies
    image_url: str              # Storefront image URL
    url: str                    # Canonical store detail page URL
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


def _parse_hours(hours_str: Optional[str]) -> Optional[str]:
    """Parse the double-encoded storeOperationHours field.

    The API returns hours as a JSON string embedded within the JSON
    response. This function parses the inner JSON and normalizes it.

    Args:
        hours_str: JSON string of hours array from API response.

    Returns:
        Normalized JSON string of hours, or None if parsing fails.
    """
    if not hours_str:
        return None

    try:
        hours_list = json.loads(hours_str)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(hours_list, list):
        return None

    formatted = []
    for entry in hours_list:
        if not isinstance(entry, dict):
            continue
        formatted.append({
            "day": entry.get("day", ""),
            "open": entry.get("open", ""),
            "close": entry.get("close", ""),
        })

    return json.dumps(formatted) if formatted else None


def _parse_store_from_api(raw: Dict[str, Any]) -> Optional[GameStopStore]:
    """Parse a single store from the FindStores API response.

    Args:
        raw: Raw store dict from the API 'stores' array.

    Returns:
        GameStopStore object if valid, None if missing required fields.
    """
    store_id = raw.get("ID", "")
    name = (raw.get("name") or "").strip()

    if not store_id or not name:
        return None

    hours_raw = raw.get(config.HOURS_FIELD, "")
    hours = _parse_hours(hours_raw) if hours_raw else None

    # Build detail URL from storesResultsHtml or from store data
    detail_url = ""
    state_code = raw.get("stateCode", "")
    city = raw.get("city", "")
    if state_code and city and name:
        detail_url = config.build_store_detail_url(
            state_code, city, store_id, name
        )

    return GameStopStore(
        store_id=str(store_id),
        name=name,
        street_address=raw.get("address1") or "",
        address2=raw.get("address2") or "",
        city=city,
        state=state_code,
        zip_code=raw.get("postalCode") or "",
        country="US",
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        phone=raw.get("phone") or "",
        store_mode=raw.get("storeMode") or "",
        hours=hours,
        midday_closure=raw.get("storeMiddleDayClosure", False),
        description="",
        knows_about="",
        payment_accepted="",
        currencies_accepted="",
        image_url="",
        url=detail_url,
        scraped_at=datetime.now().isoformat(),
    )


def _extract_store_urls_from_html(html_content: Optional[str]) -> Dict[str, str]:
    """Extract store detail URLs from storesResultsHtml.

    The API response includes rendered HTML with store detail page links.
    These are more reliable than constructing URLs from store data.

    Args:
        html_content: The storesResultsHtml string from API response.

    Returns:
        Dict mapping store_id to detail page URL path.
    """
    urls: Dict[str, str] = {}
    if not html_content:
        return urls

    for match in config.STORE_URL_REGEX.finditer(html_content):
        path = match.group(1)
        # Extract store ID from the URL path
        # Pattern: /store/us/{state}/{city}/{store_id}/{slug}
        parts = path.strip("/").split("/")
        if len(parts) >= 5:
            store_id = parts[4]
            if store_id.isdigit():
                urls[store_id] = f"{config.BASE_URL}{path}"

    return urls


def fetch_stores_at_point(
    session,
    lat: float,
    lng: float,
    retailer: str = "gamestop",
    yaml_config: Optional[dict] = None,
) -> List[Dict[str, Any]]:
    """Query the FindStores API for stores near a geographic point.

    Args:
        session: Configured requests session.
        lat: Latitude of search center.
        lng: Longitude of search center.
        retailer: Retailer name for logging.
        yaml_config: Retailer configuration from retailers.yaml.

    Returns:
        List of raw store dicts from the API response.
    """
    url = config.build_api_url(lat, lng)
    logging.debug(f"[{retailer}] Querying grid point ({lat}, {lng})")

    response = utils.get_with_retry(
        session,
        url,
        max_retries=config.MAX_RETRIES,
        timeout=config.TIMEOUT,
        headers_func=config.get_headers,
    )

    if not response:
        logging.warning(f"[{retailer}] No response for grid point ({lat}, {lng})")
        return []

    _request_counter.increment()
    if yaml_config:
        check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    # Verify we got JSON (Cloudflare may return HTML challenge page)
    content_type = response.headers.get("Content-Type", "")
    if "application/json" not in content_type and "text/json" not in content_type:
        logging.warning(
            f"[{retailer}] Non-JSON response at ({lat}, {lng}): {content_type}"
        )
        return []

    try:
        data = response.json()
        stores = data.get("stores", [])

        # Also extract reliable URLs from rendered HTML
        results_html = data.get("storesResultsHtml", "")
        url_map = _extract_store_urls_from_html(results_html)

        # Attach resolved URLs to stores (normalize ID to string)
        for store in stores:
            sid = str(store.get("ID", ""))
            if sid in url_map:
                store["_resolved_url"] = url_map[sid]

        return stores

    except (json.JSONDecodeError, AttributeError) as exc:
        logging.warning(f"[{retailer}] JSON parse error at ({lat}, {lng}): {exc}")
        return []


def discover_all_stores(
    session,
    retailer: str = "gamestop",
    yaml_config: Optional[dict] = None,
) -> Dict[str, GameStopStore]:
    """Phase 1: Discover all stores via geographic grid search.

    Queries the FindStores API at each grid point, deduplicates by
    store ID, and returns a dict of parsed GameStopStore objects.

    Args:
        session: Configured requests session.
        retailer: Retailer name for logging.
        yaml_config: Retailer configuration from retailers.yaml.

    Returns:
        Dict mapping store_id to GameStopStore object.
    """
    grid = config.generate_us_grid()
    logging.info(f"[{retailer}] Phase 1: Scanning {len(grid)} grid points")

    all_stores: Dict[str, GameStopStore] = {}
    proxy_mode = "direct"
    min_delay, max_delay = config.MIN_DELAY, config.MAX_DELAY
    if yaml_config:
        proxy_mode = yaml_config.get("proxy", {}).get("mode", "direct")
        min_delay, max_delay = utils.select_delays(yaml_config, proxy_mode)

    for i, (lat, lng) in enumerate(grid, 1):
        raw_stores = fetch_stores_at_point(
            session, lat, lng, retailer, yaml_config
        )

        for raw in raw_stores:
            sid = str(raw.get("ID", ""))
            if sid and sid not in all_stores:
                store = _parse_store_from_api(raw)
                if store:
                    # Use resolved URL from HTML if available
                    if raw.get("_resolved_url"):
                        store.url = raw["_resolved_url"]
                    all_stores[sid] = store

        if i % 10 == 0:
            logging.info(
                f"[{retailer}] Phase 1 progress: {i}/{len(grid)} points, "
                f"{len(all_stores)} unique stores"
            )

        utils.random_delay(min_delay, max_delay)

    logging.info(
        f"[{retailer}] Phase 1 complete: {len(all_stores)} unique stores "
        f"from {len(grid)} grid points"
    )
    return all_stores


def extract_jsonld_from_page(
    session,
    url: str,
    retailer: str = "gamestop",
    yaml_config: Optional[dict] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch a store detail page and extract Schema.org JSON-LD data.

    Args:
        session: Configured requests session.
        url: Full URL to the store detail page.
        retailer: Retailer name for logging.
        yaml_config: Retailer configuration from retailers.yaml.

    Returns:
        Parsed JSON-LD dict with @type "Store", or None on failure.
    """
    response = utils.get_with_retry(
        session,
        url,
        max_retries=config.MAX_RETRIES,
        timeout=config.TIMEOUT,
        headers_func=config.get_page_headers,
    )

    if not response:
        return None

    _request_counter.increment()
    if yaml_config:
        check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

    for match in config.JSONLD_REGEX.finditer(response.text):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and data.get("@type") == "Store":
                return data
        except json.JSONDecodeError:
            continue

    return None


def enrich_store(
    store: GameStopStore,
    jsonld: Dict[str, Any],
) -> GameStopStore:
    """Merge JSON-LD data into an existing GameStopStore.

    Args:
        store: Existing store from Phase 1 API discovery.
        jsonld: Parsed JSON-LD dict from the store detail page.

    Returns:
        Updated GameStopStore with enriched fields.
    """
    store.description = jsonld.get("description", "")
    store.image_url = jsonld.get("image", "")
    store.currencies_accepted = jsonld.get("currenciesAccepted", "")

    knows_about = jsonld.get("knowsAbout", [])
    if isinstance(knows_about, list):
        store.knows_about = "|".join(str(k) for k in knows_about)
    elif isinstance(knows_about, str):
        store.knows_about = knows_about

    payment = jsonld.get("paymentAccepted", [])
    if isinstance(payment, list):
        store.payment_accepted = "|".join(str(p) for p in payment)
    elif isinstance(payment, str):
        store.payment_accepted = payment

    # Use canonical URL from JSON-LD if available
    canonical_url = jsonld.get("url", "")
    if canonical_url:
        store.url = canonical_url

    return store


def enrich_all_stores(
    session,
    stores: Dict[str, GameStopStore],
    retailer: str = "gamestop",
    yaml_config: Optional[dict] = None,
    completed_ids: Optional[Set[str]] = None,
    limit: Optional[int] = None,
    checkpoint_path: Optional[str] = None,
    checkpoint_interval: int = 50,
    stores_list: Optional[List[dict]] = None,
) -> Dict[str, GameStopStore]:
    """Phase 2: Enrich stores with detail page JSON-LD data.

    Args:
        session: Configured requests session.
        stores: Dict mapping store_id to GameStopStore from Phase 1.
        retailer: Retailer name for logging.
        yaml_config: Retailer configuration from retailers.yaml.
        completed_ids: Set of already-enriched store IDs (for resume).
        limit: Maximum number of stores to enrich.
        checkpoint_path: Path to save periodic checkpoints.
        checkpoint_interval: Number of stores between checkpoint saves.
        stores_list: Running list of completed store dicts (for checkpoints).

    Returns:
        The same stores dict with enriched fields where available.
    """
    if completed_ids is None:
        completed_ids = set()

    remaining = [
        (sid, store) for sid, store in stores.items()
        if sid not in completed_ids and store.url
    ]

    if limit is not None:
        remaining = remaining[:limit]

    total = len(remaining)
    if total == 0:
        logging.info(f"[{retailer}] Phase 2: No stores to enrich")
        return stores

    logging.info(f"[{retailer}] Phase 2: Enriching {total} stores from detail pages")

    proxy_mode = "direct"
    min_delay, max_delay = config.MIN_DELAY, config.MAX_DELAY
    if yaml_config:
        proxy_mode = yaml_config.get("proxy", {}).get("mode", "direct")
        min_delay, max_delay = utils.select_delays(yaml_config, proxy_mode)

    enriched_count = 0
    for i, (sid, store) in enumerate(remaining, 1):
        jsonld = extract_jsonld_from_page(
            session, store.url, retailer, yaml_config
        )

        if jsonld:
            enrich_store(store, jsonld)
            enriched_count += 1

        if i % 50 == 0:
            logging.info(
                f"[{retailer}] Phase 2 progress: {i}/{total} "
                f"({enriched_count} enriched)"
            )

        # Periodic checkpoint during long enrichment phase
        if checkpoint_path and i % checkpoint_interval == 0 and stores_list is not None:
            utils.save_checkpoint(
                {
                    "completed_count": len(stores_list),
                    "completed_ids": list(completed_ids),
                    "stores": stores_list,
                    "last_updated": datetime.now().isoformat(),
                },
                checkpoint_path,
            )
            logging.info(f"[{retailer}] Checkpoint saved: {len(stores_list)} stores")

        utils.random_delay(min_delay, max_delay)

    logging.info(
        f"[{retailer}] Phase 2 complete: {enriched_count}/{total} stores enriched"
    )
    return stores


def run(session, retailer_config: dict, retailer: str = "gamestop", **kwargs) -> dict:
    """Standard scraper entry point for GameStop stores.

    Three-phase pipeline:
    1. Geographic grid discovery via FindStores API (~90 calls)
    2. Detail page enrichment via JSON-LD (~4,000 fetches)
    3. Deduplication, validation, and export

    Args:
        session: Configured session (requests.Session or ProxyClient).
        retailer_config: Retailer configuration dict from retailers.yaml.
        retailer: Retailer name for logging.
        **kwargs: Additional options:
            - limit: int - Max stores to process
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

        proxy_mode = retailer_config.get("proxy", {}).get("mode", "direct")
        min_delay, max_delay = utils.select_delays(retailer_config, proxy_mode)
        logging.info(
            f"[{retailer_name}] Using delays: {min_delay:.1f}-{max_delay:.1f}s "
            f"(mode: {proxy_mode})"
        )

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = retailer_config.get("checkpoint_interval", 50)

        stores_list: List[dict] = []
        completed_ids: Set[str] = set()
        checkpoints_used = False

        # Resume from checkpoint if requested
        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores_list = checkpoint.get("stores", [])
                completed_ids = set(checkpoint.get("completed_ids", []))
                logging.info(
                    f"[{retailer_name}] Resuming from checkpoint: "
                    f"{len(stores_list)} stores already collected"
                )
                checkpoints_used = True

        # Apply test mode limit
        if test_mode and not limit:
            from src.shared.constants import TEST_MODE
            limit = TEST_MODE.STORE_LIMIT
            logging.info(f"[{retailer_name}] Test mode: limiting to {limit} stores")

        # Phase 1: Discover stores via grid search
        # Note: No URL caching for GameStop. Phase 1 is only ~90 lightweight
        # API calls (grid search), so caching IDs without store data would
        # leave Phase 2 with no URLs to enrich. Unlike sitemap-based scrapers
        # where discovery is expensive, grid search is fast enough to re-run.
        all_stores: Dict[str, GameStopStore] = {}
        all_stores = discover_all_stores(
            session, retailer_name, retailer_config
        )

        if not all_stores:
            logging.warning(f"[{retailer_name}] No stores discovered")
            return {"stores": [], "count": 0, "checkpoints_used": False}

        # Phase 2: Enrich with detail page data
        enrichment_limit = None
        if limit:
            enrichment_limit = max(0, limit - len(stores_list))

        enrich_all_stores(
            session, all_stores, retailer_name, retailer_config,
            completed_ids=completed_ids,
            limit=enrichment_limit,
            checkpoint_path=checkpoint_path,
            checkpoint_interval=checkpoint_interval,
            stores_list=stores_list,
        )

        # Phase 3: Convert to dicts and merge with checkpoint data
        new_stores = []
        for sid, store_obj in all_stores.items():
            if sid not in completed_ids:
                store_obj.scraped_at = datetime.now().isoformat()
                new_stores.append(store_obj.to_dict())
                completed_ids.add(sid)

        stores_list.extend(new_stores)

        # Apply limit to final output
        if limit and len(stores_list) > limit:
            stores_list = stores_list[:limit]

        # Save checkpoint
        if stores_list:
            utils.save_checkpoint(
                {
                    "completed_count": len(stores_list),
                    "completed_ids": list(completed_ids),
                    "stores": stores_list,
                    "last_updated": datetime.now().isoformat(),
                },
                checkpoint_path,
            )

        # Validate store data
        if stores_list:
            validation_summary = utils.validate_stores_batch(stores_list)
            logging.info(
                f"[{retailer_name}] Validation: {validation_summary['valid']}/"
                f"{validation_summary['total']} valid, "
                f"{validation_summary['warning_count']} warnings"
            )

        logging.info(f"[{retailer_name}] Completed: {len(stores_list)} stores scraped")

        return {
            "stores": stores_list,
            "count": len(stores_list),
            "checkpoints_used": checkpoints_used,
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
