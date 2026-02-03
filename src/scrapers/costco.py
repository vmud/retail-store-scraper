"""Core scraping functions for Costco Warehouse Locator

Costco uses Akamai bot protection, requiring Web Scraper API with JS rendering.
The scraper extracts warehouse data from the store locator page.

Discovery method: Page scraping with geographic search
Data source: costco.com/w/-/locations
Expected results: ~600 US warehouses

Approach:
1. Fetch the main locations page with JS rendering
2. Extract embedded warehouse data from the page
3. Optionally fetch individual warehouse pages for detailed info
4. Return normalized store data
"""

import json
import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
from bs4 import BeautifulSoup

from config import costco_config as config
from src.shared import utils
from src.shared.proxy_client import ProxyClient, ProxyConfig, ProxyMode
from src.shared.session_factory import create_session_factory


logger = logging.getLogger(__name__)


@dataclass
class CostcoWarehouse:
    """Data model for Costco warehouse information."""
    store_id: str           # Warehouse number (e.g., "148")
    name: str               # Warehouse name (e.g., "Marina Del Rey")
    store_type: str         # warehouse or business_center
    street_address: str
    city: str
    state: str              # 2-letter state code
    zip: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    phone: str
    url: str
    services: List[str]     # gas_station, tire_center, etc.
    hours_weekday: str      # Mon-Fri hours
    hours_saturday: str
    hours_sunday: str
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
        # Convert services list to JSON string
        if result.get('services'):
            result['services'] = json.dumps(result['services'])
        else:
            result['services'] = ''
        return result


def _extract_warehouse_from_html(soup: BeautifulSoup, warehouse_element) -> Optional[Dict[str, Any]]:
    """Extract warehouse data from a warehouse list item element.

    Args:
        soup: BeautifulSoup object for the page
        warehouse_element: HTML element containing warehouse info

    Returns:
        Dictionary with warehouse data or None if extraction fails
    """
    try:
        # Look for warehouse name and details
        name_elem = warehouse_element.find(['h2', 'h3', 'a'], class_=re.compile(r'warehouse|location|name', re.I))
        if not name_elem:
            name_elem = warehouse_element.find(['h2', 'h3', 'a'])

        name = name_elem.get_text(strip=True) if name_elem else None
        if not name:
            return None

        # Extract address components
        address_elem = warehouse_element.find(['address', 'div'], class_=re.compile(r'address', re.I))
        address_text = address_elem.get_text(separator='\n', strip=True) if address_elem else ''

        # Extract URL (warehouse detail page link)
        link = warehouse_element.find('a', href=re.compile(r'/w/-/'))
        url = link['href'] if link and link.get('href') else ''
        if url and not url.startswith('http'):
            url = f"{config.BASE_URL}{url}"

        # Extract warehouse ID from URL
        store_id = ''
        if url:
            match = re.search(r'/(\d+)(?:\?|$|#)', url)
            if match:
                store_id = match.group(1)

        # Extract phone
        phone_elem = warehouse_element.find(['a', 'span'], href=re.compile(r'tel:'))
        phone = ''
        if phone_elem:
            phone = phone_elem.get_text(strip=True)
        else:
            phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', address_text)
            if phone_match:
                phone = phone_match.group(0)

        return {
            'name': name,
            'store_id': store_id,
            'url': url,
            'phone': phone,
            'address_text': address_text,
        }
    except Exception as e:
        logger.debug(f"Error extracting warehouse: {e}")
        return None


def _parse_address(address_text: str) -> Dict[str, str]:
    """Parse address text into components.

    Args:
        address_text: Raw address text (may have newlines)

    Returns:
        Dictionary with street_address, city, state, zip
    """
    lines = [line.strip() for line in address_text.split('\n') if line.strip()]

    result = {
        'street_address': '',
        'city': '',
        'state': '',
        'zip': '',
    }

    if not lines:
        return result

    # First line is usually street address
    result['street_address'] = lines[0] if lines else ''

    # Look for city, state ZIP pattern in remaining lines
    for line in lines[1:]:
        # Pattern: City, ST 12345 or City, ST 12345-6789
        match = re.match(r'^(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$', line)
        if match:
            result['city'] = match.group(1).strip()
            result['state'] = match.group(2)
            result['zip'] = match.group(3)
            break

    return result


def _extract_warehouses_from_page(html: str) -> List[Dict[str, Any]]:
    """Extract all warehouse data from the locations page HTML.

    Args:
        html: Raw HTML content from the locations page

    Returns:
        List of warehouse dictionaries
    """
    warehouses = []
    soup = BeautifulSoup(html, 'html.parser')

    # Try to find embedded JSON data first (React apps often embed state)
    scripts = soup.find_all('script')
    for script in scripts:
        script_text = script.string or ''
        # Look for warehouse data in script tags
        if 'warehouse' in script_text.lower() and 'locationId' in script_text:
            try:
                # Try to extract JSON from script
                json_match = re.search(r'(\{.*"warehouses?".*\})', script_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                    if isinstance(data, dict):
                        warehouses_data = None
                        if 'warehouses' in data:
                            warehouses_data = data['warehouses']
                        elif 'warehouse' in data:
                            warehouses_data = data['warehouse']
                        if isinstance(warehouses_data, dict):
                            warehouses_data = [warehouses_data]
                        if isinstance(warehouses_data, list):
                            for w in warehouses_data:
                                warehouses.append(_normalize_warehouse_json(w))
            except (json.JSONDecodeError, KeyError) as e:
                logger.debug(f"Could not parse embedded JSON: {e}")

    # If no JSON found, fall back to HTML parsing
    if not warehouses:
        # Look for warehouse list items
        warehouse_containers = soup.find_all(
            ['div', 'li', 'article'],
            class_=re.compile(r'warehouse|location|store', re.I)
        )

        for container in warehouse_containers:
            warehouse_data = _extract_warehouse_from_html(soup, container)
            if warehouse_data and warehouse_data.get('store_id'):
                warehouses.append(warehouse_data)

    logger.info(f"Extracted {len(warehouses)} warehouses from page")
    return warehouses


def _normalize_warehouse_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize warehouse data from JSON format.

    Args:
        data: Raw warehouse JSON data

    Returns:
        Normalized warehouse dictionary

    Note:
        Uses None-coalescing for fields like coordinates to preserve valid
        falsy values (e.g., 0.0) while still falling back on null JSON values.
    """
    def _coalesce_none(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None
    name = data.get('name') or data.get('displayName') or ''
    return {
        'store_id': str(data.get('storeNumber') or data.get('locationId') or data.get('id') or ''),
        'name': name,
        'street_address': data.get('address') or data.get('streetAddress') or data.get('address1') or '',
        'city': data.get('city') or '',
        'state': data.get('state') or data.get('stateCode') or '',
        'zip': data.get('zip') or data.get('zipCode') or data.get('postalCode') or '',
        'country': data.get('country') or data.get('countryCode') or 'US',
        'latitude': _coalesce_none(data.get('latitude'), data.get('lat')),
        'longitude': _coalesce_none(data.get('longitude'), data.get('lng'), data.get('lon')),
        'phone': data.get('phone') or data.get('phoneNumber') or '',
        'url': data.get('url') or data.get('detailsUrl') or '',
        'services': data.get('services') or [],
        'store_type': 'business_center' if 'business' in name.lower() else 'warehouse',
    }


def _fetch_by_zip_codes(
    proxy_client: ProxyClient,
    retailer_config: Dict[str, Any],
    limit: Optional[int] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """Fetch warehouses by searching zip codes across the US.

    Uses a grid of zip codes to discover all warehouses.

    Args:
        proxy_client: ProxyClient instance
        retailer_config: Configuration dictionary
        limit: Maximum number of warehouses to fetch
        **kwargs: Additional arguments

    Returns:
        List of warehouse dictionaries
    """
    # Sample zip codes covering major US regions
    sample_zips = [
        # Northeast
        '10001', '02101', '19103', '20001',
        # Southeast
        '30301', '33101', '28201', '37201',
        # Midwest
        '60601', '48201', '55401', '63101',
        # Southwest
        '85001', '87501', '73301', '75201',
        # West
        '90001', '94101', '98101', '80201',
        # Other
        '96801',  # Hawaii
    ]

    all_warehouses = {}

    def search_zip(zip_code: str) -> List[Dict[str, Any]]:
        """Search for warehouses near a zip code."""
        try:
            search_url = f"{config.LOCATIONS_URL}?input={zip_code}"

            response = proxy_client.get(
                search_url,
                headers=config.get_headers(),
                render_js=True,
                timeout=config.TIMEOUT
            )

            if response.status_code == 200:
                return _extract_warehouses_from_page(response.text)
        except Exception as e:
            logger.debug(f"Error searching zip {zip_code}: {e}")
        return []

    # Search each zip code
    for zip_code in sample_zips:
        if limit and len(all_warehouses) >= limit:
            break

        warehouses = search_zip(zip_code)
        for w in warehouses:
            store_id = w.get('store_id')
            if store_id and store_id not in all_warehouses:
                all_warehouses[store_id] = w

        min_delay, max_delay = utils.select_delays(retailer_config, kwargs.get('proxy_mode'))
        utils.random_delay(min_delay, max_delay)

    return list(all_warehouses.values())


def run(session, retailer_config: Dict[str, Any], retailer: str, **kwargs) -> dict:
    """Main entry point for Costco warehouse scraper.

    Args:
        session: requests.Session (may be unused if using ProxyClient)
        retailer_config: Configuration from retailers.yaml
        retailer: Retailer name string ("costco")
        **kwargs: Additional arguments:
            - limit: Max warehouses to scrape
            - test_mode: If True, scrape only 10 warehouses
            - proxy_mode: Proxy mode to use
            - checkpoints: Enable checkpoint saves

    Returns:
        dict with keys:
            - stores: list of warehouse dictionaries
            - count: number of warehouses scraped
            - checkpoints_used: bool indicating if resumed from checkpoint
    """
    stores = []
    checkpoints_used = False
    completed_store_ids = set()

    limit = kwargs.get('limit')
    test_mode = kwargs.get('test_mode', False)
    proxy_mode = kwargs.get('proxy_mode', 'web_scraper_api')  # Default to web_scraper_api for Costco
    resume = kwargs.get('resume', False)

    if test_mode:
        limit = 10

    # Checkpoint setup
    retailer_name = retailer.lower()
    checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
    checkpoint_interval = retailer_config.get('checkpoint_interval', config.CHECKPOINT_INTERVAL)

    # Load checkpoint if resuming
    if resume:
        checkpoint = utils.load_checkpoint(checkpoint_path)
        if checkpoint:
            stores = checkpoint.get('stores', [])
            completed_store_ids = set(checkpoint.get('completed_store_ids', []))
            logger.info(f"[{retailer_name}] Resuming from checkpoint: {len(stores)} warehouses already collected")
            checkpoints_used = True

    logger.info(f"Starting Costco scraper (limit={limit}, proxy_mode={proxy_mode})")

    # Initialize proxy client
    proxy_config = ProxyConfig.from_env()
    if proxy_mode == 'web_scraper_api':
        proxy_config.mode = ProxyMode.WEB_SCRAPER_API
        proxy_config.render_js = True
    elif proxy_mode == 'residential':
        proxy_config.mode = ProxyMode.RESIDENTIAL
    else:
        proxy_config.mode = ProxyMode.DIRECT

    proxy_client = ProxyClient(proxy_config)

    try:
        # Step 1: Fetch main locations page to discover warehouses
        logger.info("Fetching Costco warehouse locations page...")
        try:
            response = proxy_client.get(
                config.LOCATIONS_URL,
                headers=config.get_headers(),
                render_js=True,
                timeout=config.TIMEOUT
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch locations page: {response.status_code}")
                # Fall back to zip code search
                warehouses = _fetch_by_zip_codes(proxy_client, retailer_config, limit, **kwargs)
            else:
                try:
                    warehouses = _extract_warehouses_from_page(response.text)
                except Exception as e:
                    logger.error(f"Error extracting warehouses from locations page: {e}")
                    logger.info("Falling back to zip code search after extraction error")
                    warehouses = _fetch_by_zip_codes(proxy_client, retailer_config, limit, **kwargs)

        except Exception as e:
            logger.error(f"Error fetching locations page: {e}")
            logger.info("Falling back to zip code search after fetch error")
            warehouses = _fetch_by_zip_codes(proxy_client, retailer_config, limit, **kwargs)

        # Step 2: Deduplicate and limit
        unique_warehouses = {}
        for w in warehouses:
            store_id = w.get('store_id')
            if store_id and store_id not in unique_warehouses:
                unique_warehouses[store_id] = w
                if limit and len(unique_warehouses) >= limit:
                    break

        logger.info(f"Found {len(unique_warehouses)} unique warehouses")

        # Step 3: Optionally fetch detailed info for each warehouse
        # For now, use the data we have from the list page
        scraped_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Filter out already completed store IDs (for resume support)
        pending_warehouses = {
            sid: data for sid, data in unique_warehouses.items()
            if sid not in completed_store_ids
        }
        logger.info(f"Processing {len(pending_warehouses)} pending warehouses (skipping {len(completed_store_ids)} already completed)")

        for i, (store_id, data) in enumerate(pending_warehouses.items(), 1):
            # Create CostcoWarehouse object
            try:
                # Parse address if we only have address_text
                if 'address_text' in data and not data.get('city'):
                    address_parts = _parse_address(data.get('address_text', ''))
                    data.update(address_parts)

                warehouse = CostcoWarehouse(
                    store_id=data.get('store_id', ''),
                    name=data.get('name', ''),
                    store_type=data.get('store_type', 'warehouse'),
                    street_address=data.get('street_address', ''),
                    city=data.get('city', ''),
                    state=data.get('state', ''),
                    zip=data.get('zip', ''),
                    country=data.get('country', 'US'),
                    latitude=data.get('latitude'),
                    longitude=data.get('longitude'),
                    phone=data.get('phone', ''),
                    url=data.get('url', ''),
                    services=data.get('services', []),
                    hours_weekday=data.get('hours_weekday', ''),
                    hours_saturday=data.get('hours_saturday', ''),
                    hours_sunday=data.get('hours_sunday', ''),
                    scraped_at=scraped_at,
                )

                # Validate before adding
                store_dict = warehouse.to_dict()
                validation = utils.validate_store_data(store_dict)
                if validation.is_valid:
                    stores.append(store_dict)
                    completed_store_ids.add(store_id)
                else:
                    logger.debug(f"Invalid warehouse {store_id}: {validation.errors}")

                # Checkpoint at intervals
                if i % checkpoint_interval == 0:
                    utils.save_checkpoint({
                        'completed_count': len(stores),
                        'completed_store_ids': list(completed_store_ids),
                        'stores': stores,
                        'last_updated': datetime.now(timezone.utc).isoformat()
                    }, checkpoint_path)
                    logger.debug(f"Checkpoint saved: {len(stores)} warehouses")

            except Exception as e:
                logger.warning(f"Error creating warehouse object for {store_id}: {e}")

        logger.info(f"Costco scraper complete: {len(stores)} valid warehouses")

        # Save final checkpoint
        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_store_ids': list(completed_store_ids),
                'stores': stores,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }, checkpoint_path)
            logger.debug(f"Final checkpoint saved: {len(stores)} warehouses")

        return {
            'stores': stores,
            'count': len(stores),
            'checkpoints_used': checkpoints_used,
        }

    finally:
        # Clean up proxy client session to prevent resource leak
        proxy_client.close()
        logger.debug("Closed proxy client session")
