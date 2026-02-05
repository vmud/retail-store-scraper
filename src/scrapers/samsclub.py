"""Core scraping functions for Sam's Club Store Locator

Sam's Club uses a Next.js site with bot protection (Akamai).
The scraper uses a hybrid approach:
1. Fetch club URLs from sitemap (no bot protection)
2. Extract club details from __NEXT_DATA__ on each page (requires Web Scraper API)

API: Sitemap at https://www.samsclub.com/sitemap_locators.xml
Expected results: ~600 clubs nationwide
"""

import json
import logging
import re
import threading
import defusedxml.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

from config import samsclub_config as config
from src.shared import utils
from src.shared.cache import URLCache
from src.shared.proxy_client import ProxyClient, ProxyConfig, ProxyMode
from src.shared.request_counter import RequestCounter, check_pause_logic
from src.shared.session_factory import create_session_factory


# Global request counter (deprecated - kept for backwards compatibility)
# Use instance-based counter passed to functions instead
_request_counter = RequestCounter()


@dataclass
class SamsClubStore:
    """Data model for Sam's Club store information."""
    store_id: str               # Club ID (numeric)
    name: str                   # Club name
    street_address: str
    city: str
    state: str                  # 2-letter state code
    zip: str
    county: str
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    phone: str
    url: str
    time_zone: str
    # Services offered at this club
    services: List[str] = field(default_factory=list)
    has_pharmacy: bool = False
    has_optical: bool = False
    has_hearing_aid: bool = False
    has_wireless: bool = False
    has_cafe: bool = False
    has_bakery: bool = False
    has_gas: bool = False
    has_liquor: bool = False
    has_tires_batteries: bool = False
    # Club attributes
    is_curbside: bool = False
    is_scan_and_go: bool = False
    is_same_day_pickup: bool = False
    # Operating hours
    hours_mon_fri: str = ""
    hours_saturday: str = ""
    hours_sunday: str = ""
    # Plus member early hours
    plus_hours_mon_fri: str = ""
    plus_hours_saturday: str = ""
    plus_hours_sunday: str = ""
    scraped_at: str = ""

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
        # Convert services list to comma-separated string for CSV
        result['services'] = ','.join(result.get('services', []))
        return result


def get_club_urls_from_sitemap(session: requests.Session, retailer: str = 'samsclub') -> List[str]:
    """Fetch all club URLs from Sam's Club sitemap.

    The sitemap is publicly accessible but requires curl-like headers to avoid bot detection.

    Args:
        session: Requests session (plain session works fine)
        retailer: Retailer name for logging

    Returns:
        List of unique club URLs
    """
    sitemap_url = config.SITEMAP_URL
    logging.info(f"[{retailer}] Fetching sitemap: {sitemap_url}")

    # Use minimal headers to avoid bot detection (browser-like headers trigger 412)
    headers = {
        'User-Agent': 'curl/8.4.0',
        'Accept': '*/*',
    }
    response = session.get(sitemap_url, headers=headers, timeout=30)

    if response.status_code != 200:
        logging.error(f"[{retailer}] Failed to fetch sitemap: {response.status_code}")
        return []

    try:
        # Parse XML sitemap
        root = ET.fromstring(response.content)

        # Extract club URLs - handle both namespaced and non-namespaced elements
        club_urls = set()

        # Try with namespace (standard sitemap format)
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_elem in root.findall(".//ns:loc", namespace):
            url = url_elem.text
            if url and '/club/' in url:
                club_urls.add(url)

        # Also try without namespace (Sam's Club uses mixed format)
        for url_elem in root.findall(".//loc"):
            url = url_elem.text
            if url and '/club/' in url:
                club_urls.add(url)

        logging.info(f"[{retailer}] Found {len(club_urls)} unique club URLs in sitemap")
        return list(club_urls)

    except ET.ParseError as e:
        logging.error(f"[{retailer}] Failed to parse sitemap XML: {e}")
        return []
    except Exception as e:
        logging.error(f"[{retailer}] Unexpected error processing sitemap: {e}")
        return []


def _format_hours(hours_data: Dict[str, Any], key: str) -> str:
    """Format operating hours from API response.

    Args:
        hours_data: Hours object from API (e.g., operationalHours)
        key: Key for the time period (e.g., 'monToFriHrs')

    Returns:
        Formatted hours string like "09:00-20:00" or "" if unavailable
    """
    if not hours_data:
        return ""

    period = hours_data.get(key, {})
    if not period:
        return ""

    start = period.get('startHrs', '')
    end = period.get('endHrs', '')

    if start and end:
        return f"{start}-{end}"
    return ""


def _parse_services(services_list: List[Any]) -> Tuple[List[str], Dict[str, bool]]:
    """Parse services list into service names and boolean flags.

    Args:
        services_list: List of service objects with 'name' field, or strings

    Returns:
        Tuple of (service_names, service_flags_dict)
    """
    if not services_list:
        return [], {
            'has_pharmacy': False,
            'has_optical': False,
            'has_hearing_aid': False,
            'has_wireless': False,
            'has_cafe': False,
            'has_bakery': False,
            'has_gas': False,
            'has_liquor': False,
            'has_tires_batteries': False,
        }

    # Extract service names (handle both object and string formats)
    service_names = []
    for s in services_list:
        if isinstance(s, dict):
            name = s.get('name', '')
        else:
            name = str(s)
        if name:
            service_names.append(name)

    # Normalize to uppercase for matching
    services = set(s.upper() for s in service_names)

    flags = {
        'has_pharmacy': 'PHARMACY' in services,
        'has_optical': 'VISION_CENTER' in services or 'OPTICAL' in services,
        'has_hearing_aid': 'HEARING_AID_CENTER' in services,
        'has_wireless': 'WIRELESS_MOBILE' in services or 'MOBILE_WIRELESS' in services,
        'has_cafe': 'CAFE' in services,
        'has_bakery': 'BAKERY' in services,
        'has_gas': 'GAS_SAMS' in services or 'GAS' in services,
        'has_liquor': 'LIQUOR' in services,
        'has_tires_batteries': 'TIRE_AND_LUBE' in services or 'TIRES_&_BATTERIES' in services,
    }

    return service_names, flags


def _extract_club_data_from_page(html: str, url: str, retailer: str = 'samsclub') -> Optional[SamsClubStore]:
    """Extract club data from page HTML using __NEXT_DATA__ JSON.

    Args:
        html: Page HTML content
        url: Club page URL
        retailer: Retailer name for logging

    Returns:
        SamsClubStore object or None if extraction fails
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__', type='application/json')

        if not script_tag or not script_tag.string:
            logging.warning(f"[{retailer}] No __NEXT_DATA__ found for {url}")
            return None

        data = json.loads(script_tag.string)

        # Navigate to club data in Next.js structure
        page_props = data.get('props', {}).get('pageProps', {})

        # Primary path: initialNodeDetail.data.nodeDetail
        club_data = None
        if 'initialNodeDetail' in page_props:
            initial_node = page_props.get('initialNodeDetail', {})
            club_data = initial_node.get('data', {}).get('nodeDetail', {})

        if not club_data:
            logging.debug(f"[{retailer}] pageProps keys: {list(page_props.keys())[:10]}")
            logging.warning(f"[{retailer}] Could not find club data structure for {url}")
            return None

        # Extract fields
        address = club_data.get('address', {})
        geo_point = club_data.get('geoPoint', {})
        services_list = club_data.get('services', [])

        # Parse services (returns both names list and flags dict)
        service_names, service_flags = _parse_services(services_list)

        club_id = str(club_data.get('id', ''))
        if not club_id:
            # Extract from URL
            match = re.search(r'/club/(\d+)-', url)
            if match:
                club_id = match.group(1)

        # Parse operating hours from array format
        op_hours = club_data.get('operationalHours', [])
        hours_by_day = {}
        for h in op_hours:
            if isinstance(h, dict):
                day = h.get('day', '').lower()
                if not h.get('closed', False) and h.get('start') and h.get('end'):
                    hours_by_day[day] = f"{h['start']}-{h['end']}"

        # Check for capabilities (scan-and-go, pickup, etc.)
        has_scan_go = any(
            s.get('name') == 'SCAN_AND_GO'
            for s in services_list if isinstance(s, dict)
        )
        has_pickup = any(
            s.get('name') in ('PICKUP_PLUS_MEMBERS', 'PICKUP_REGULAR_MEMBERS')
            for s in services_list if isinstance(s, dict)
        )

        return SamsClubStore(
            store_id=club_id,
            name=club_data.get('displayName', '') or club_data.get('name', ''),
            street_address=address.get('addressLineOne', '') or '',
            city=address.get('city', ''),
            state=address.get('state', ''),
            zip=address.get('postalCode', ''),
            county='',  # Not available in this format
            country=address.get('country', 'US'),
            latitude=geo_point.get('latitude'),
            longitude=geo_point.get('longitude'),
            phone=club_data.get('phoneNumber', ''),
            url=url,
            time_zone='',  # Not available in this format
            services=service_names,
            **service_flags,
            is_curbside=has_pickup,
            is_scan_and_go=has_scan_go,
            is_same_day_pickup=has_pickup,
            hours_mon_fri=hours_by_day.get('monday', ''),
            hours_saturday=hours_by_day.get('saturday', ''),
            hours_sunday=hours_by_day.get('sunday', ''),
            plus_hours_mon_fri='',  # Not easily available in this format
            plus_hours_saturday='',
            plus_hours_sunday='',
            scraped_at=datetime.now().isoformat()
        )

    except json.JSONDecodeError as e:
        logging.warning(f"[{retailer}] Failed to parse JSON for {url}: {e}")
        return None
    except Exception as e:
        logging.warning(f"[{retailer}] Error extracting club data from {url}: {e}")
        return None


def extract_club_details(client, url: str, retailer: str = 'samsclub', request_counter: RequestCounter = None) -> Optional[SamsClubStore]:
    """Extract club data from a club page.

    Args:
        client: ProxyClient (for Web Scraper API with JS rendering) or requests.Session
        url: Club page URL
        retailer: Retailer name for logging
        request_counter: Optional RequestCounter instance for tracking requests

    Returns:
        SamsClubStore object if successful, None otherwise
    """
    logging.debug(f"[{retailer}] Extracting details from {url}")

    # Curl-like headers work better than browser headers for Sam's Club
    curl_headers = {
        'User-Agent': 'curl/8.4.0',
        'Accept': '*/*',
    }

    try:
        # Check if client is a ProxyClient (has mode attribute)
        if hasattr(client, 'mode'):
            response = client.get(url)
            if not response or response.status_code != 200:
                status = response.status_code if response else 'None'
                logging.warning(f"[{retailer}] Failed to fetch {url} (status={status})")
                return None
            html = response.text
        else:
            # Direct session - use curl-like headers to avoid bot detection
            response = client.get(url, headers=curl_headers, timeout=30)
            if response.status_code != 200:
                logging.warning(f"[{retailer}] Failed to fetch {url}: {response.status_code}")
                return None
            html = response.text

        # Track request if counter is provided
        if request_counter:
            request_counter.increment()

        return _extract_club_data_from_page(html, url, retailer)

    except Exception as e:
        logging.warning(f"[{retailer}] Error fetching {url}: {e}")
        return None


def run(session, yaml_config: dict, **kwargs) -> dict:
    """Standard scraper entry point with sitemap-based discovery.

    HYBRID PROXY MODE:
    - Uses passed-in session for sitemap fetching (no bot protection)
    - Creates web_scraper_api session for club pages (JS rendering for Akamai bypass)

    Args:
        session: Configured session for sitemaps (requests.Session)
        yaml_config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - resume: bool - Resume from checkpoint
            - limit: int - Max clubs to process
            - refresh_urls: bool - Force URL re-discovery (ignore cache)

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped club data
            - count: int - Number of clubs processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = kwargs.get('retailer', 'samsclub')
    logging.info(f"[{retailer_name}] Starting scrape run")

    club_client = None

    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        refresh_urls = kwargs.get('refresh_urls', False)

        # Create fresh RequestCounter instance for this run
        request_counter = RequestCounter()
        reset_request_counter()  # Reset global counter for backwards compatibility

        # Log proxy mode
        proxy_mode = yaml_config.get('proxy', {}).get('mode', 'direct')
        logging.info(f"[{retailer_name}] HYBRID MODE: sitemap via direct, clubs via web_scraper_api")

        # Create web_scraper_api client for club extraction (Akamai bypass)
        logging.info(f"[{retailer_name}] Creating web_scraper_api client for club extraction")
        proxy_config = ProxyConfig.from_env()
        proxy_config.mode = ProxyMode.WEB_SCRAPER_API
        proxy_config.render_js = True
        club_client = ProxyClient(proxy_config)
        logging.info(f"[{retailer_name}] Web Scraper API client ready (render_js=true)")

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = yaml_config.get('checkpoint_interval', 50)

        clubs = []
        completed_urls = set()
        checkpoints_used = False

        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                clubs = checkpoint.get('stores', [])
                completed_urls = set(checkpoint.get('completed_urls', []))
                logging.info(f"[{retailer_name}] Resuming from checkpoint: {len(clubs)} clubs already collected")
                checkpoints_used = True

        # Try to load cached URLs
        url_cache = URLCache(retailer_name)
        club_urls = None
        if not refresh_urls:
            club_urls = url_cache.get()

        if club_urls is None:
            # Fetch from sitemap
            club_urls = get_club_urls_from_sitemap(session, retailer_name)
            logging.info(f"[{retailer_name}] Found {len(club_urls)} club URLs from sitemap")

            # Save to cache
            if club_urls:
                url_cache.set(club_urls)
        else:
            logging.info(f"[{retailer_name}] Using {len(club_urls)} cached club URLs")

        if not club_urls:
            logging.warning(f"[{retailer_name}] No club URLs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        remaining_urls = [url for url in club_urls if url not in completed_urls]

        if resume and completed_urls:
            logging.info(f"[{retailer_name}] Skipping {len(club_urls) - len(remaining_urls)} already-processed clubs")

        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} clubs")
            total_needed = limit - len(clubs)
            if total_needed > 0:
                remaining_urls = remaining_urls[:total_needed]
            else:
                remaining_urls = []

        total_to_process = len(remaining_urls)
        if total_to_process > 0:
            logging.info(f"[{retailer_name}] Extracting details for {total_to_process} clubs")
        else:
            logging.info(f"[{retailer_name}] No new clubs to process")

        # Track failed URLs
        failed_urls = []

        for i, url in enumerate(remaining_urls, 1):
            club_obj = extract_club_details(club_client, url, retailer_name, request_counter=request_counter)

            # Apply pause logic for anti-blocking (counter incremented inside extract_club_details)
            if request_counter:
                check_pause_logic(request_counter, retailer=retailer_name, config=yaml_config)

            if club_obj:
                clubs.append(club_obj.to_dict())
                completed_urls.add(url)

                if i % 10 == 0:
                    logging.info(f"[{retailer_name}] Extracted {len(clubs)} clubs so far ({i}/{total_to_process})")
            else:
                failed_urls.append(url)

            # Progress logging
            if i % 50 == 0:
                logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")

            # Checkpoint
            if i % checkpoint_interval == 0:
                utils.save_checkpoint({
                    'completed_count': len(clubs),
                    'completed_urls': list(completed_urls),
                    'stores': clubs,
                    'last_updated': datetime.now().isoformat()
                }, checkpoint_path)
                logging.info(f"[{retailer_name}] Checkpoint saved: {len(clubs)} clubs processed")

        # Log failed extractions
        if failed_urls:
            logging.warning(f"[{retailer_name}] Failed to extract {len(failed_urls)} clubs:")
            for failed_url in failed_urls[:10]:
                logging.warning(f"[{retailer_name}]   - {failed_url}")
            if len(failed_urls) > 10:
                logging.warning(f"[{retailer_name}]   ... and {len(failed_urls) - 10} more")

        # Final checkpoint
        if clubs:
            utils.save_checkpoint({
                'completed_count': len(clubs),
                'completed_urls': list(completed_urls),
                'stores': clubs,
                'last_updated': datetime.now().isoformat()
            }, checkpoint_path)
            logging.info(f"[{retailer_name}] Final checkpoint saved: {len(clubs)} clubs total")

        # Validate store data
        validation_summary = utils.validate_stores_batch(clubs)
        logging.info(
            f"[{retailer_name}] Validation: {validation_summary['valid']}/{validation_summary['total']} valid, "
            f"{validation_summary['warning_count']} warnings"
        )

        # Log service statistics
        if clubs:
            service_counts = {
                'pharmacy': sum(1 for c in clubs if c.get('has_pharmacy')),
                'optical': sum(1 for c in clubs if c.get('has_optical')),
                'wireless': sum(1 for c in clubs if c.get('has_wireless')),
                'gas': sum(1 for c in clubs if c.get('has_gas')),
                'cafe': sum(1 for c in clubs if c.get('has_cafe')),
            }
            logging.info(f"[{retailer_name}] Services found: {service_counts}")

        logging.info(f"[{retailer_name}] Completed: {len(clubs)} clubs scraped")

        return {
            'stores': clubs,
            'count': len(clubs),
            'checkpoints_used': checkpoints_used
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
    finally:
        # Clean up
        if club_client and hasattr(club_client, 'close'):
            try:
                club_client.close()
                logging.debug(f"[{retailer_name}] Closed web_scraper_api session")
            except Exception as e:
                logging.warning(f"[{retailer_name}] Error closing club session: {e}")


def reset_request_counter() -> None:
    """Reset the global request counter."""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count."""
    return _request_counter.count
