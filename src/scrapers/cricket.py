"""Core scraping functions for Cricket Wireless Store Locator

Cricket uses a Yext-powered store locator with a publicly accessible API.
The scraper uses geographic grid-based discovery to query stores across
the continental US.

Approach:
1. Generate a geographic grid covering the continental US (~1,200 points at 50-mile spacing)
2. Query the Yext API for stores near each grid point (parallel execution)
3. Deduplicate stores by store_id (thread-safe)
4. Return normalized store data

API: https://prod-cdn.us.yextapis.com/v2/accounts/me/search/query
Expected results: ~13,588 stores (Cricket standalone + in-store retail partners)
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

from config import cricket_config as config
from src.shared import utils
from src.shared.constants import TEST_MODE
from src.shared.session_factory import create_session_factory


@dataclass
class CricketStore:
    """Data model for Cricket Wireless store information."""
    store_id: str           # Yext entity ID
    name: str               # Store name
    store_type: str         # standalone, bestbuy, walmart, etc.
    street_address: str
    city: str
    state: str              # 2-letter state code
    zip: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    phone: str
    url: Optional[str]
    hours_monday: str
    hours_tuesday: str
    hours_wednesday: str
    hours_thursday: str
    hours_friday: str
    hours_saturday: str
    hours_sunday: str
    closed: bool
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export."""
        result = asdict(self)
        # Convert coordinates to strings for CSV compatibility
        if result.get('latitude') is None:
            result['latitude'] = ''
        else:
            result['latitude'] = str(result['latitude'])
        if result.get('longitude') is None:
            result['longitude'] = ''
        else:
            result['longitude'] = str(result['longitude'])
        return result


def _generate_us_grid(spacing_miles: float = 50) -> List[Tuple[float, float]]:
    """Generate a grid of coordinates covering the continental US.

    The grid ensures complete coverage by using overlapping search radii.
    At 50-mile spacing with 50-mile search radius, each point's search
    area overlaps with neighbors, preventing gaps.

    Args:
        spacing_miles: Distance between grid points in miles

    Returns:
        List of (latitude, longitude) tuples covering the US
    """
    bounds = config.US_BOUNDS

    # Approximate degrees per mile at mid-US latitudes (~37°N)
    # 1 degree latitude ≈ 69 miles (constant)
    # 1 degree longitude ≈ 54.6 miles at 37°N (varies with latitude)
    lat_spacing = spacing_miles / 69.0
    lng_spacing = spacing_miles / 54.6

    grid_points = []
    lat = bounds['lat_min']

    while lat <= bounds['lat_max']:
        lng = bounds['lng_min']
        while lng <= bounds['lng_max']:
            grid_points.append((round(lat, 4), round(lng, 4)))
            lng += lng_spacing
        lat += lat_spacing

    logging.debug(f"Generated {len(grid_points)} grid points at {spacing_miles}-mile spacing")
    return grid_points


def _format_hours(hours_data: Dict[str, Any], day_key: str) -> str:
    """Format hours for a specific day from Yext hours data.

    Args:
        hours_data: Yext hours object with day keys
        day_key: Day name in lowercase (e.g., 'monday')

    Returns:
        Formatted hours string like "10:00-19:00" or "" if closed/unavailable
    """
    if not hours_data:
        return ""

    day_hours = hours_data.get(day_key, {})
    if not day_hours:
        return ""

    # Yext format: {"openIntervals": [{"start": "10:00", "end": "19:00"}]}
    intervals = day_hours.get('openIntervals', [])
    if not intervals:
        return ""

    # Use first interval (most stores have single opening period)
    first_interval = intervals[0]
    start = first_interval.get('start', '')
    end = first_interval.get('end', '')

    if start and end:
        return f"{start}-{end}"
    return ""


def _categorize_store(locator_filters: List[str]) -> str:
    """Categorize store type based on c_locatorFilters.

    Args:
        locator_filters: List of filter tags from Yext data

    Returns:
        Store type string (e.g., 'authorized_retailer', 'bestbuy', 'walmart')
    """
    if not locator_filters:
        return 'unknown'

    # Check each filter against known store types
    for filter_tag in locator_filters:
        if filter_tag in config.STORE_TYPES:
            return config.STORE_TYPES[filter_tag]

    # Default to first filter as-is if no mapping found
    return locator_filters[0].lower().replace(' ', '_') if locator_filters else 'unknown'


def _parse_store(raw_store: Dict[str, Any]) -> Optional[CricketStore]:
    """Parse Yext store data into CricketStore object.

    Args:
        raw_store: Raw store data from Yext API response

    Returns:
        CricketStore object or None if parsing fails
    """
    try:
        # Extract nested data structures
        data = raw_store.get('data', raw_store)  # Handle both wrapped and unwrapped
        address = data.get('address', {})

        # Coordinates can be in multiple places - prefer geocodedCoordinate or yextDisplayCoordinate
        coords = (
            data.get('geocodedCoordinate') or
            data.get('yextDisplayCoordinate') or
            address.get('coordinate') or
            {}
        )
        hours = data.get('hours', {})

        # Get store type from locator filters
        locator_filters = data.get('c_locatorFilters', [])
        store_type = _categorize_store(locator_filters)

        # Build website URL if available
        website_url = data.get('websiteUrl', {})
        url = website_url.get('url') if isinstance(website_url, dict) else (website_url or None)

        return CricketStore(
            store_id=str(data.get('id', '')),
            name=data.get('name', ''),
            store_type=store_type,
            street_address=address.get('line1', ''),
            city=address.get('city', ''),
            state=address.get('region', ''),
            zip=address.get('postalCode', ''),
            country=address.get('countryCode', 'US'),
            latitude=coords.get('latitude'),
            longitude=coords.get('longitude'),
            phone=data.get('mainPhone', ''),
            url=url,
            hours_monday=_format_hours(hours, 'monday'),
            hours_tuesday=_format_hours(hours, 'tuesday'),
            hours_wednesday=_format_hours(hours, 'wednesday'),
            hours_thursday=_format_hours(hours, 'thursday'),
            hours_friday=_format_hours(hours, 'friday'),
            hours_saturday=_format_hours(hours, 'saturday'),
            hours_sunday=_format_hours(hours, 'sunday'),
            closed=data.get('closed', False),
            scraped_at=datetime.now().isoformat()
        )

    except Exception as e:
        store_id = raw_store.get('data', {}).get('id', raw_store.get('id', 'unknown'))
        logging.warning(f"[cricket] Failed to parse store {store_id}: {e}")
        return None


def _fetch_stores_at_point(
    session,
    lat: float,
    lng: float,
    retailer: str = 'cricket'
) -> List[Dict[str, Any]]:
    """Fetch stores near a geographic point using Yext API.

    Args:
        session: Configured requests session
        lat: Latitude of search center
        lng: Longitude of search center
        retailer: Retailer name for logging

    Returns:
        List of raw store data from API response
    """
    url = config.build_api_url(lat, lng)

    response = utils.get_with_retry(
        session,
        url,
        max_retries=config.MAX_RETRIES,
        timeout=config.TIMEOUT,
        headers_func=config.get_headers
    )

    if not response:
        logging.debug(f"[{retailer}] No response for point ({lat}, {lng})")
        return []

    try:
        data = response.json()

        # Extract stores from Yext response structure
        # Response format: {"response": {"modules": [{"results": [{"data": {...}}, ...]}]}}
        modules = data.get('response', {}).get('modules', [])
        results = modules[0].get('results', []) if modules else []

        if results:
            logging.debug(f"[{retailer}] Found {len(results)} stores at ({lat}, {lng})")

        return results

    except Exception as e:
        logging.warning(f"[{retailer}] Failed to parse response for ({lat}, {lng}): {e}")
        return []


def _fetch_stores_worker(
    point: Tuple[float, float],
    session_factory,
    retailer: str
) -> Tuple[Tuple[float, float], List[CricketStore]]:
    """Worker function for parallel grid scanning.

    Each worker creates its own session for thread safety and fetches
    stores at a single grid point.

    Args:
        point: (latitude, longitude) tuple
        session_factory: Callable that creates session instances
        retailer: Retailer name for logging

    Returns:
        Tuple of (point, list_of_parsed_stores)
    """
    lat, lng = point
    session = session_factory()

    try:
        raw_stores = _fetch_stores_at_point(session, lat, lng, retailer)
        parsed_stores = []

        for raw_store in raw_stores:
            store = _parse_store(raw_store)
            if store:
                parsed_stores.append(store)

        return (point, parsed_stores)

    except Exception as e:
        logging.warning(f"[{retailer}] Error at point ({lat}, {lng}): {e}")
        return (point, [])

    finally:
        if hasattr(session, 'close'):
            session.close()


def run(session, retailer_config: dict, retailer: str, **kwargs) -> dict:
    """Standard scraper entry point.

    Cricket scraper uses geographic grid-based discovery with parallel
    execution. Stores are deduplicated by store_id across all grid points.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        retailer_config: Retailer configuration dict from retailers.yaml
        retailer: Retailer name for logging
        **kwargs: Additional options
            - limit: int - Max stores to return (for testing)
            - test: bool - Test mode (reduced grid for quick validation)

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Always False (no checkpointing for API-based scraper)

    Raises:
        None.

    Examples:
        >>> run(session, retailer_config, "cricket", test=True)

    Note:
        Defaults are sourced from src.shared.constants.TEST_MODE.
    """
    retailer_name = retailer
    limit = kwargs.get('limit')
    test_mode = kwargs.get('test', False)

    logging.info(f"[{retailer_name}] Starting scrape run")

    # Log proxy mode for visibility
    proxy_mode = retailer_config.get('proxy', {}).get('mode', 'direct')
    logging.info(f"[{retailer_name}] Using proxy mode: {proxy_mode}")

    try:
        # Get configuration values
        grid_spacing = retailer_config.get('grid_spacing_miles', config.DEFAULT_GRID_SPACING_MILES)
        parallel_workers = retailer_config.get('parallel_workers', 10)

        # Reduce grid for test mode (quick validation)
        if test_mode:
            grid_spacing = TEST_MODE.GRID_SPACING_MILES  # Fewer points for quick testing
            logging.info(f"[{retailer_name}] Test mode: using {grid_spacing}-mile grid spacing")

        # Generate grid points
        grid_points = _generate_us_grid(grid_spacing)
        total_points = len(grid_points)
        logging.info(f"[{retailer_name}] Generated {total_points} grid points at {grid_spacing}-mile spacing")

        # Thread-safe storage for deduplication
        seen_ids: Set[str] = set()
        all_stores: List[CricketStore] = []
        lock = threading.Lock()

        # Track progress
        points_completed = [0]
        progress_lock = threading.Lock()

        # Create session factory for parallel workers
        session_factory = create_session_factory(retailer_config)

        # Parallel grid scanning
        logging.info(f"[{retailer_name}] Scanning grid with {parallel_workers} parallel workers")

        with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
            # Submit all grid points
            futures = {
                executor.submit(_fetch_stores_worker, point, session_factory, retailer_name): point
                for point in grid_points
            }

            for future in as_completed(futures):
                point, stores = future.result()

                # Thread-safe deduplication and storage
                with lock:
                    for store in stores:
                        if store.store_id not in seen_ids:
                            seen_ids.add(store.store_id)
                            all_stores.append(store)

                            # Check limit
                            if limit and len(all_stores) >= limit:
                                logging.info(f"[{retailer_name}] Reached limit of {limit} stores")
                                # Cancel remaining futures
                                for f in futures:
                                    f.cancel()
                                break

                # Progress logging
                with progress_lock:
                    points_completed[0] += 1
                    if points_completed[0] % 100 == 0 or points_completed[0] == total_points:
                        logging.info(
                            f"[{retailer_name}] Progress: {points_completed[0]}/{total_points} points "
                            f"({points_completed[0]/total_points*100:.1f}%), "
                            f"{len(all_stores)} unique stores found"
                        )

                # Early exit if limit reached
                if limit and len(all_stores) >= limit:
                    break

        # Apply limit if specified
        if limit and len(all_stores) > limit:
            logging.info(f"[{retailer_name}] Trimming to {limit} stores (from {len(all_stores)})")
            all_stores = all_stores[:limit]

        # Convert to dicts for export
        store_dicts = [store.to_dict() for store in all_stores]

        # Validate store data
        if store_dicts:
            validation_summary = utils.validate_stores_batch(store_dicts)
            logging.info(
                f"[{retailer_name}] Validation: {validation_summary['valid']}/{validation_summary['total']} valid, "
                f"{validation_summary['warning_count']} warnings"
            )

        logging.info(f"[{retailer_name}] Completed: {len(store_dicts)} stores scraped")

        return {
            'stores': store_dicts,
            'count': len(store_dicts),
            'checkpoints_used': False
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
