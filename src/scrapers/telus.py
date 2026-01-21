"""Core scraping functions for Telus Store Locator

Telus uses Uberall as their store locator platform. The Uberall API provides
a single endpoint that returns all store locations in one JSON response,
making this the simplest scraper in the project.

API: https://uberall.com/api/storefinders/{token}/locations/all
Returns: ~857 stores (TELUS corporate, Koodo, and authorized dealers)
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import telus_config
from src.shared import utils


# Day of week mapping for hours formatting (Uberall uses 1=Monday, 7=Sunday)
DAY_NAMES = {
    1: 'Monday',
    2: 'Tuesday',
    3: 'Wednesday',
    4: 'Thursday',
    5: 'Friday',
    6: 'Saturday',
    7: 'Sunday'
}


@dataclass
class TelusStore:
    """Data model for Telus store information"""
    store_id: str           # Uberall location ID
    telus_id: str           # Telus identifier
    name: str               # Store name (TELUS, Koodo, dealer name)
    street_address: str     # Full street address with unit
    city: str
    state: str              # Province abbreviation (ON, QC, BC, etc.)
    postal_code: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    phone: str
    hours: Optional[str]    # JSON-formatted opening hours
    url: str                # Store page URL
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
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
        # Hours is already a JSON string or empty
        if result.get('hours') is None:
            result['hours'] = ''
        return result


def _format_opening_hours(hours_data: List[Dict[str, Any]]) -> Optional[str]:
    """Format Uberall opening hours to JSON string.

    Args:
        hours_data: List of hour dicts from Uberall API
            Example: [{"dayOfWeek": 1, "from1": "10:00", "to1": "20:00"}, ...]

    Returns:
        JSON string of formatted hours or None if no hours
    """
    if not hours_data:
        return None

    formatted = []
    for day_hours in sorted(hours_data, key=lambda x: x.get('dayOfWeek', 0)):
        day_num = day_hours.get('dayOfWeek')
        if day_num and day_num in DAY_NAMES:
            day_name = DAY_NAMES[day_num]
            from_time = day_hours.get('from1', '')
            to_time = day_hours.get('to1', '')
            if from_time and to_time:
                formatted.append({
                    'day': day_name,
                    'open': from_time,
                    'close': to_time
                })

    return json.dumps(formatted) if formatted else None


def _get_province_abbreviation(province_name: str) -> str:
    """Convert full province name to 2-letter abbreviation.

    Args:
        province_name: Full province name (e.g., 'Ontario', 'Québec')

    Returns:
        2-letter abbreviation (e.g., 'ON', 'QC') or original if not found
    """
    return telus_config.PROVINCE_ABBREVIATIONS.get(province_name, province_name)


def _build_store_url(location: Dict[str, Any]) -> str:
    """Build store page URL from location data.

    Telus store URLs follow pattern: /en/{slug} where slug is derived from
    the store identifier or city name.
    """
    # Use identifier if available, otherwise construct from city
    identifier = location.get('identifier', '')
    city = location.get('city', '').lower().replace(' ', '-')

    if identifier:
        return f"{telus_config.STORE_PAGE_BASE}/{identifier}"
    elif city:
        return f"{telus_config.STORE_PAGE_BASE}/{city}"
    else:
        return telus_config.BASE_URL


def _parse_store(location: Dict[str, Any]) -> TelusStore:
    """Parse Uberall location data into TelusStore object.

    Args:
        location: Single location dict from Uberall API response

    Returns:
        TelusStore object with normalized data
    """
    # Build full street address (include unit/suite if present)
    street = location.get('streetAndNumber', '')
    address_extra = location.get('addressExtra', '')
    if address_extra:
        street_address = f"{street}, {address_extra}"
    else:
        street_address = street

    # Get province abbreviation
    province_full = location.get('province', '')
    province_abbr = _get_province_abbreviation(province_full)

    # Format opening hours
    hours = _format_opening_hours(location.get('openingHours', []))

    return TelusStore(
        store_id=str(location.get('id', '')),
        telus_id=location.get('identifier', ''),
        name=location.get('name', ''),
        street_address=street_address,
        city=location.get('city', ''),
        state=province_abbr,
        postal_code=location.get('zip', ''),
        country=location.get('country', 'CA'),
        latitude=location.get('lat'),
        longitude=location.get('lng'),
        phone=location.get('phone', ''),
        hours=hours,
        url=_build_store_url(location),
        scraped_at=datetime.now().isoformat()
    )


def fetch_all_stores(session, retailer: str = 'telus') -> List[TelusStore]:
    """Fetch all Telus stores from Uberall API.

    This is a single API call that returns all ~857 stores at once.
    No pagination or iteration required.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        retailer: Retailer name for logging

    Returns:
        List of TelusStore objects
    """
    logging.info(f"[{retailer}] Fetching all stores from Uberall API")

    response = utils.get_with_retry(
        session,
        telus_config.API_URL,
        max_retries=telus_config.MAX_RETRIES,
        timeout=telus_config.TIMEOUT,
        headers_func=telus_config.get_headers
    )

    if not response:
        logging.error(f"[{retailer}] Failed to fetch stores from API")
        return []

    try:
        data = response.json()

        if data.get('status') != 'SUCCESS':
            logging.error(f"[{retailer}] API returned error status: {data.get('status')}")
            return []

        locations = data.get('response', {}).get('locations', [])
        logging.info(f"[{retailer}] API returned {len(locations)} locations")

        stores = []
        for location in locations:
            try:
                store = _parse_store(location)
                stores.append(store)
            except Exception as e:
                store_id = location.get('id', 'unknown')
                logging.warning(f"[{retailer}] Failed to parse store {store_id}: {e}")

        logging.info(f"[{retailer}] Successfully parsed {len(stores)} stores")
        return stores

    except json.JSONDecodeError as e:
        logging.error(f"[{retailer}] Failed to parse API response: {e}")
        return []
    except Exception as e:
        logging.error(f"[{retailer}] Unexpected error processing API response: {e}")
        return []


def run(session, config: dict, **kwargs) -> dict:
    """Standard scraper entry point.

    Telus scraper is simple - single API call returns all stores.
    No pagination, no checkpointing needed for this fast operation.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - retailer: str - Retailer name for logging
            - limit: int - Max stores to return (for testing)

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Always False (no checkpointing needed)
    """
    retailer_name = kwargs.get('retailer', 'telus')
    limit = kwargs.get('limit')

    logging.info(f"[{retailer_name}] Starting scrape run")

    # Log proxy mode for visibility
    proxy_mode = config.get('proxy', {}).get('mode', 'direct')
    logging.info(f"[{retailer_name}] Using proxy mode: {proxy_mode}")

    try:
        # Fetch all stores in single API call
        stores = fetch_all_stores(session, retailer_name)

        if not stores:
            logging.warning(f"[{retailer_name}] No stores found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        # Apply limit if specified (for testing)
        if limit and limit < len(stores):
            logging.info(f"[{retailer_name}] Limiting to {limit} stores (from {len(stores)})")
            stores = stores[:limit]

        # Convert to dicts for export
        store_dicts = [store.to_dict() for store in stores]

        # Validate store data
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
