# pylint: disable=too-many-lines
"""Core scraping functions for Best Buy Store Locator"""

import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, Tuple
from bs4 import BeautifulSoup
import requests

from config import bestbuy_config
from src.shared import utils
from src.shared.cache import URLCache, DEFAULT_CACHE_EXPIRY_DAYS
from src.shared.constants import WORKERS
from src.shared.request_counter import RequestCounter, check_pause_logic
from src.shared.session_factory import create_session_factory


# Global request counter
_request_counter = RequestCounter()


@dataclass
class BestBuyStore:
    """Data model for Best Buy store information"""
    store_id: str
    name: str
    status: str
    store_type: str
    display_name: str
    street_address: str
    city: str
    state: str
    zip: str
    country: str
    latitude: str
    longitude: str
    phone: str
    services: Optional[List[str]]
    service_codes: Optional[List[Dict[str, str]]]
    hours: Optional[List[Dict[str, str]]]
    has_pickup: bool
    curbside_enabled: bool
    url: str
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        result = asdict(self)
        # Convert services list to JSON string for CSV compatibility
        if result.get('services'):
            result['services'] = json.dumps(result['services'])
        elif result.get('services') is None:
            result['services'] = ''  # Empty string for CSV when None

        # Convert service_codes list to JSON string for CSV compatibility
        if result.get('service_codes'):
            result['service_codes'] = json.dumps(result['service_codes'])
        elif result.get('service_codes') is None:
            result['service_codes'] = ''  # Empty string for CSV when None

        # Convert hours list to JSON string for CSV compatibility
        if result.get('hours'):
            result['hours'] = json.dumps(result['hours'])
        elif result.get('hours') is None:
            result['hours'] = ''  # Empty string for CSV when None

        # Convert boolean fields to strings for CSV
        if result.get('has_pickup') is None:
            result['has_pickup'] = False
        result['has_pickup'] = 'True' if result['has_pickup'] else 'False'

        if result.get('curbside_enabled') is None:
            result['curbside_enabled'] = False
        result['curbside_enabled'] = 'True' if result['curbside_enabled'] else 'False'

        # Convert latitude/longitude to strings if needed
        if result.get('latitude') is None:
            result['latitude'] = ''
        else:
            result['latitude'] = str(result['latitude'])

        if result.get('longitude') is None:
            result['longitude'] = ''
        else:
            result['longitude'] = str(result['longitude'])

        return result


def _extract_services_from_html(soup: BeautifulSoup) -> Optional[List[str]]:
    """Extract services offered from store page HTML.

    Uses flexible pattern matching to capture common services and rare services.

    Args:
        soup: BeautifulSoup object of the store page

    Returns:
        List of service names if found, None otherwise
    """
    page_text = soup.get_text().lower()
    services = []
    seen_services = set()

    # Common Best Buy services (known services to look for)
    common_services = [
        'geek squad',
        'apple',
        'trade-in',
        'trade in',
        'curbside',
        'pickup',
        'alexa',
        'google home',
        'hearing solutions',
        'car and gps install',
        'windows store',
        'yardbird',
        'amazon alexa',
        'apple shop',
        'apple authorized service',
        'geek squad services',
        'apple service provider',
        'trade-in program',
    ]

    # Check for common services in page text
    for service in common_services:
        service_lower = service.lower()
        # Look for service in page (exact match or with context)
        if service_lower in page_text:
            # Normalize service name (use canonical form)
            normalized = _normalize_service_name(service_lower)
            if normalized and normalized not in seen_services:
                services.append(normalized)
                seen_services.add(normalized)

    # Look for services in structured HTML elements
    # Check for services sections, lists, or feature lists
    service_sections = soup.find_all(['section', 'div', 'ul'],
                                     class_=re.compile(r'service|feature|offer', re.I))

    for section in service_sections:
        _section_text = section.get_text().lower()
        # Look for service names in structured sections
        # Try to extract service names from list items or links
        list_items = section.find_all(['li', 'a', 'span', 'div'])
        for item in list_items:
            item_text = item.get_text().strip().lower()
            if item_text and len(item_text) > 3 and len(item_text) < 50:
                # Check if it looks like a service name
                if _looks_like_service_name(item_text):
                    normalized = _normalize_service_name(item_text)
                    if normalized and normalized not in seen_services:
                        services.append(normalized)
                        seen_services.add(normalized)

    # Look for services in headings or prominent text
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
    for heading in headings:
        heading_text = heading.get_text().strip().lower()
        if heading_text and len(heading_text) > 3 and len(heading_text) < 50:
            if _looks_like_service_name(heading_text):
                normalized = _normalize_service_name(heading_text)
                if normalized and normalized not in seen_services:
                    services.append(normalized)
                    seen_services.add(normalized)

    return services if services else None


def _normalize_service_name(service: str, strict: bool = False) -> Optional[str]:
    """Normalize service name to canonical form.

    Args:
        service: Raw service name from HTML
        strict: If True, reject unknown services. If False, accept and normalize them.

    Returns:
        Normalized service name or None if not a valid service
    """
    original = service
    service = service.strip().lower()

    # Skip if empty or too generic
    if not service or len(service) < 3:
        return None

    # Remove common prefixes/suffixes
    service = re.sub(r'^(the|a|an|our|all|view|see)\s+', '', service)
    service = re.sub(r'\s+(services?|center|program|experience|only|and|or|&)$', '', service)
    service = re.sub(r'^(services?|specialty)\s+', '', service)
    service = re.sub(r'\s+', ' ', service).strip()

    # Skip if it became too short or generic
    generic_terms = {'and', 'or', 'the', 'a', 'an', 'all', 'offered', 'available',
                     'services', 'specialty', 'shops'}
    if len(service) < 3 or service in generic_terms:
        logging.debug(f"Dropping generic service: '{original}'")
        return None

    # Map variations to canonical names
    service_mapping = {
        'geek squad': 'Geek Squad',
        'apple shop': 'Apple Shop',
        'apple service': 'Apple Authorized Service Provider',
        'apple authorized': 'Apple Authorized Service Provider',
        'apple authorized service provider': 'Apple Authorized Service Provider',
        'trade-in': 'Trade-In',
        'trade in': 'Trade-In',
        'amazon alexa': 'Amazon Alexa Experience',
        'alexa': 'Amazon Alexa Experience',
        'google home': 'Google Home Experience',
        'hearing solutions': 'Hearing Solutions Center',
        'hearing solutions center': 'Hearing Solutions Center',
        'car and gps': 'Car and GPS Install Services',
        'car install': 'Car and GPS Install Services',
        'gps install': 'Car and GPS Install Services',
        'car and gps install': 'Car and GPS Install Services',
        'windows store': 'Microsoft Windows Store',
        'microsoft windows': 'Microsoft Windows Store',
        'microsoft': 'Microsoft Windows Store',
        'yardbird': 'Yardbird',
        'curbside': 'Curbside Pickup',
        'curbside pickup': 'Curbside Pickup',
        'pickup': 'Store Pickup',
        'store pickup': 'Store Pickup',
        'in-store pickup': 'Store Pickup',
        'samsung experience': 'Samsung Experience',
        'samsung experience only': 'Samsung Experience',
    }

    # Check for exact or partial matches
    for key, canonical in service_mapping.items():
        if key == service or key in service:
            return canonical
        # Also check reverse (service is subset of key)
        if len(key) > len(service) and service in key:
            return canonical

    # For unmapped services: normalize and keep in non-strict mode
    if service and len(service) > 2:
        normalized = ' '.join(word.capitalize() for word in service.split())
        # Filter out if it still looks too generic
        if normalized.lower() in {'services', 'offered', 'available', 'specialty', 'shops'}:
            logging.debug(f"Dropping generic service: '{original}'")
            return None

        if not strict:
            # Accept unknown services with normalized capitalization
            logging.debug(f"Unknown service accepted: '{original}' -> '{normalized}'")
            return normalized

        # In strict mode, log and drop unmapped services
        logging.debug(f"Dropping unmapped service (strict mode): '{original}'")
        return None

    logging.debug(f"Dropping invalid service: '{original}'")
    return None


def _looks_like_service_name(text: str) -> bool:
    """Check if text looks like a service name.

    Args:
        text: Text to check

    Returns:
        True if text looks like a service name
    """
    text = text.strip().lower()

    # Skip if too short or too long
    if len(text) < 3 or len(text) > 50:
        return False

    # Skip generic/non-service phrases
    generic_phrases = {
        'click', 'here', 'more', 'learn', 'about', 'view', 'all', 'store',
        'location', 'hours', 'contact', 'phone', 'address', 'directions',
        'map', 'find', 'search', 'menu', 'home', 'back', 'next', 'previous',
        'services offered', 'service', 'offered', 'available', 'see all',
        'specialty shops', 'shops and', 'and more', 'experience only',
        'and', 'or', '&', 'services and', 'experience and'
    }

    # Skip if it's a generic phrase
    if text in generic_phrases:
        return False

    # Skip if it starts with generic words
    words = text.split()
    if words and words[0] in {'the', 'a', 'an', 'our', 'all', 'view', 'see'}:
        return False

    # Skip if it's just a single common word (likely not a service)
    if len(words) == 1 and text in {'service', 'shop', 'store', 'center'}:
        return False

    # Skip URLs, phone numbers, addresses
    if re.search(r'http|www|@|\d{3}-\d{3}-\d{4}|\d{5}', text):
        return False

    # Skip incomplete phrases (ending with "and", "or", "&", etc.)
    if text.endswith((' and', ' or', ' &', 'and ', 'or ', '& ')):
        return False

    # Likely a service if it contains service-related keywords
    service_keywords = [
        'squad', 'shop', 'experience', 'center', 'install',
        'trade', 'pickup', 'curbside', 'solutions', 'support',
        'alexa', 'google', 'apple', 'windows', 'samsung', 'hearing',
        'gps', 'yardbird', 'authorized', 'provider'
    ]

    if any(keyword in text for keyword in service_keywords):
        return True

    # Or if it's a proper noun/name (starts with capital, multiple words)
    # But only if it doesn't look generic
    if len(words) >= 2 and not text.startswith(('services', 'specialty', 'all ')):
        # Check if it looks like a brand name or service name
        capitalized_words = [w for w in words if w and w[0].isupper()]
        if len(capitalized_words) >= 1:
            return True

    return False


def get_all_store_ids(
    session: requests.Session,
    min_delay: float = None,
    max_delay: float = None
) -> List[Dict[str, Any]]:
    """Extract all store URLs from Best Buy's sitemap.

    Args:
        session: Requests session object
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests

    Returns:
        List of store dictionaries with store_id and url
    """
    logging.info(f"Fetching sitemap: {bestbuy_config.SITEMAP_URL}")

    response = utils.get_with_retry(
        session,
        bestbuy_config.SITEMAP_URL,
        min_delay=min_delay,
        max_delay=max_delay
    )
    if not response:
        logging.error(f"Failed to fetch sitemap: {bestbuy_config.SITEMAP_URL}")
        return []

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer='bestbuy', config=None)

    try:
        content = response.text

        # Extract actual store URLs from sitemap XML
        # Pattern: <loc>https://stores.bestbuy.com/...</loc>
        url_pattern = r'<loc>(https://stores\.bestbuy\.com/[^<]+)</loc>'
        urls = re.findall(url_pattern, content)

        # Extract store IDs from URLs and create store dictionaries
        stores = []
        seen_urls = set()

        for url in urls:
            # Skip state directory pages (pattern: /[state-code].html)
            if re.match(r'https://stores\.bestbuy\.com/[a-z]{2}\.html$', url):
                logging.debug(f"Skipping state directory: {url}")
                continue

            # Skip city index pages (pattern: /xx/city-name.html with no numbers)
            # City pages have only letters and dashes, store pages have numbers (store ID)
            if re.match(r'https://stores\.bestbuy\.com/[a-z]{2}/[a-z-]+\.html$', url):
                logging.debug(f"Skipping city index: {url}")
                continue

            # Skip subpages (geeksquad, services, etc.)
            if '/geeksquad.html' in url or '/services' in url:
                logging.debug(f"Skipping subpage: {url}")
                continue

            # Skip non-store URLs (404 pages, etc.)
            if '/404.html' in url or not url.endswith('.html'):
                continue

            # Only include URLs with numbers (indicating a store ID in the address)
            # Store URLs look like: /ut/farmington/360-n-station-pkwy-1887.html
            if not re.search(r'\d', url):
                logging.debug(f"Skipping URL without store ID: {url}")
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract store ID from URL - typically the last number sequence
            # URLs are like: https://stores.bestbuy.com/ut/farmington/360-n-station-pkwy-1887.html
            store_id = None

            # Try to extract the store ID (last number in URL, usually 3-4 digits)
            store_id_match = re.search(r'-(\d{3,4})\.html$', url)
            if store_id_match:
                store_id = store_id_match.group(1)
            else:
                # Fallback: extract any numeric ID from URL
                store_id_match = re.search(r'/(\d+)', url)
                if store_id_match:
                    store_id = store_id_match.group(1)
                else:
                    # Generate a stable hash-based ID from URL for tracking
                    store_id = hashlib.sha256(url.encode()).hexdigest()[:6]

            stores.append({
                "store_id": store_id,
                "url": url
            })

        logging.info(f"Found {len(stores)} store URLs in sitemap")
        return stores

    except Exception as e:
        logging.error(f"Unexpected error processing sitemap: {e}")
        return []


def extract_store_details(
    session: requests.Session,
    url: str,
    min_delay: float = None,
    max_delay: float = None
) -> Optional[BestBuyStore]:
    """Extract store data from a single Best Buy store page.

    Args:
        session: Requests session object
        url: Store page URL
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests

    Returns:
        BestBuyStore object if successful, None otherwise
    """
    logging.debug(f"Extracting details from {url}")

    response = utils.get_with_retry(
        session,
        url,
        min_delay=min_delay,
        max_delay=max_delay
    )
    if not response:
        logging.warning(f"Failed to fetch store details: {url}")
        return None

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer='bestbuy', config=None)

    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find JSON-LD structured data (similar to T-Mobile scraper)
        scripts = soup.find_all('script', type='application/ld+json')
        if not scripts:
            logging.warning(f"No JSON-LD found for {url}")
            return None

        # Try each script until we find a Store
        data = None
        for script in scripts:
            try:
                script_content = script.string
                if not script_content:
                    continue

                script_data = json.loads(script_content)

                # Handle @graph structure (used by Best Buy)
                if '@graph' in script_data:
                    graph = script_data['@graph']
                    for item in graph:
                        if isinstance(item, dict):
                            item_type = item.get('@type')
                            # Best Buy uses ElectronicsStore instead of Store
                            if item_type in ('Store', 'ElectronicsStore', 'LocalBusiness'):
                                data = item
                                break
                # Handle both single objects and arrays
                elif isinstance(script_data, list):
                    for item in script_data:
                        item_type = item.get('@type')
                        if item_type in ('Store', 'ElectronicsStore', 'LocalBusiness'):
                            data = item
                            break
                else:
                    item_type = script_data.get('@type')
                    if item_type in ('Store', 'ElectronicsStore', 'LocalBusiness'):
                        data = script_data

                if data:
                    break

            except json.JSONDecodeError as e:
                logging.debug(f"Failed to parse JSON-LD script for {url}: {e}")
                continue

        # If no Store found, log and return None
        if not data:
            logging.debug(f"No Store found in JSON-LD for {url}")
            return None

        # Extract store ID from URL or data
        store_id = None
        store_id_match = re.search(r'/(\d+)', url)
        if store_id_match:
            store_id = store_id_match.group(1)
        else:
            # Try to extract from JSON-LD or use stable hash
            store_id = data.get('locationId') or data.get('branchCode') or hashlib.sha256(url.encode()).hexdigest()[:6]

        # Extract address components
        address = data.get('address', {})

        # Handle addressCountry (can be string or object)
        address_country = address.get('addressCountry', 'US')
        if isinstance(address_country, dict):
            country = address_country.get('name', 'US')
        else:
            country = address_country if address_country else 'US'

        # Extract geo coordinates
        geo = data.get('geo', {})
        latitude = geo.get('latitude')
        longitude = geo.get('longitude')

        # Convert coordinates to strings
        # Handle zero as a valid coordinate (e.g., equator at lat 0, prime meridian at lon 0)
        if latitude is not None:
            latitude = str(latitude)
        else:
            latitude = ''
        if longitude is not None:
            longitude = str(longitude)
        else:
            longitude = ''

        # Extract store type/name
        store_type = data.get('storeType', '')
        name = data.get('name', '')
        display_name = data.get('displayName', name)

        # Extract phone
        phone = data.get('telephone', '')

        # Extract status (if available)
        status = data.get('status', 'Open')

        # Extract services and service codes (may need to parse from page or structured data)
        services = None
        service_codes = None
        hours = None
        has_pickup = False
        curbside_enabled = False

        # Extract services from page HTML (flexible approach to capture all services)
        services_from_html = _extract_services_from_html(soup)
        if services_from_html:
            services = services_from_html

        # Try to extract additional data from page HTML if not in JSON-LD
        # Look for embedded JavaScript with store data
        page_scripts = soup.find_all('script')
        for script in page_scripts:
            script_content = script.string or ""
            # Look for store data in JavaScript variables
            if 'storeData' in script_content or 'store' in script_content.lower():
                # Try to extract JSON from JavaScript
                try:
                    # Look for JSON objects in script
                    json_match = re.search(r'(\{[^{}]*"store[^}]*\})', script_content)
                    if json_match:
                        store_js_data = json.loads(json_match.group(1))
                        # Extract services, hours, etc. if present
                        if 'services' in store_js_data:
                            js_services = store_js_data.get('services', [])
                            # Merge with HTML-extracted services
                            if services:
                                services = list(set(services + js_services))
                            else:
                                services = js_services
                        if 'serviceCodes' in store_js_data:
                            service_codes = store_js_data.get('serviceCodes', [])
                        if 'hours' in store_js_data:
                            hours = store_js_data.get('hours', [])
                except (json.JSONDecodeError, KeyError, AttributeError, ValueError, TypeError) as e:
                    logging.debug(f"JS extraction failed for {url}: {type(e).__name__}: {e}")

        # Check for pickup/curbside indicators in HTML
        page_text = soup.get_text().lower()
        if 'curbside' in page_text or 'curbside pickup' in page_text:
            curbside_enabled = True
        if 'pickup' in page_text and ('store pickup' in page_text or 'in-store pickup' in page_text):
            has_pickup = True

        # Extract opening hours from JSON-LD if available
        opening_hours = data.get('openingHours', [])
        if opening_hours and not hours:
            # Convert opening hours format if needed
            hours = opening_hours

        # Create BestBuyStore object
        store = BestBuyStore(
            store_id=str(store_id),
            name=name,
            status=status,
            store_type=store_type,
            display_name=display_name,
            street_address=address.get('streetAddress', ''),
            city=address.get('addressLocality', ''),
            state=address.get('addressRegion', ''),
            zip=address.get('postalCode', ''),
            country=country,
            latitude=latitude,
            longitude=longitude,
            phone=phone,
            services=services if services else None,
            service_codes=service_codes if service_codes else None,
            hours=hours if hours else None,
            has_pickup=bool(has_pickup),
            curbside_enabled=bool(curbside_enabled),
            url=url,
            scraped_at=datetime.now().isoformat()
        )

        logging.debug(f"Extracted store: {store.name}")
        return store

    except Exception as e:
        logging.warning(f"Error extracting store data from {url}: {e}")
        return None


def reset_request_counter() -> None:
    """Reset the global request counter"""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count


# =============================================================================
# PARALLEL EXTRACTION - Speed up store detail extraction
# =============================================================================


def _extract_single_store_worker(
    url: str,
    session_factory: Callable[[], requests.Session],
    yaml_config: dict,
    retailer_name: str,
    min_delay: float = None,
    max_delay: float = None
) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """Worker function for parallel store extraction.

    Creates its own session for thread safety and extracts store details
    from a single URL.

    Args:
        url: Store URL to extract
        session_factory: Callable that creates session instances
        yaml_config: Retailer configuration
        retailer_name: Name of retailer for logging
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests

    Returns:
        Tuple of (url, store_data, error_reason) where store_data is None on failure
    """
    session = session_factory()
    try:
        store_obj = extract_store_details(
            session,
            url,
            min_delay=min_delay,
            max_delay=max_delay
        )
        if store_obj:
            return (url, store_obj.to_dict(), None)
        return (url, None, "No data extracted")
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logging.warning(f"[{retailer_name}] Error extracting {url}: {error_msg}")
        return (url, None, error_msg)
    finally:
        # Clean up session resources
        if hasattr(session, 'close'):
            session.close()


def _save_failed_extractions(
    retailer: str,
    failed_urls: List[str],
    failed_reasons: Dict[str, str]
) -> None:
    """Save failed extraction URLs for later retry.

    Args:
        retailer: Retailer name
        failed_urls: List of URLs that failed extraction
        failed_reasons: Dict mapping URL to failure reason
    """
    if not failed_urls:
        return

    failed_path = Path(f"data/{retailer}/failed_extractions.json")
    failed_path.parent.mkdir(parents=True, exist_ok=True)

    failed_data = {
        'saved_at': datetime.now().isoformat(),
        'count': len(failed_urls),
        'urls': failed_urls,
        'reasons': failed_reasons
    }

    try:
        with open(failed_path, 'w', encoding='utf-8') as f:
            json.dump(failed_data, f, indent=2)
        logging.info(f"[{retailer}] Saved {len(failed_urls)} failed URLs to {failed_path}")
    except IOError as e:
        logging.warning(f"[{retailer}] Failed to save failed extractions: {e}")


def run(session, retailer_config: dict, retailer: str, **kwargs) -> dict:
    """Standard scraper entry point with parallel extraction and URL caching.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        retailer_config: Retailer configuration dict from retailers.yaml
        retailer: Retailer name for logging
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

    Raises:
        None.

    Examples:
        >>> run(session, retailer_config, "bestbuy", resume=True)

    Note:
        Defaults are sourced from src.shared.constants (WORKERS, etc).
    """
    retailer_name = retailer
    config = retailer_config
    logging.info(f"[{retailer_name}] Starting scrape run")

    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        refresh_urls = kwargs.get('refresh_urls', False)

        reset_request_counter()

        # Auto-select delays based on proxy mode for optimal performance
        proxy_mode = config.get('proxy', {}).get('mode', 'direct')
        min_delay, max_delay = utils.select_delays(config, proxy_mode)
        logging.info(f"[{retailer_name}] Using delays: {min_delay:.2f}-{max_delay:.2f}s (mode: {proxy_mode})")

        # Get parallel workers count (default: WORKERS.PROXIED_WORKERS for proxy modes, WORKERS.DIRECT_WORKERS for direct)
        default_workers = WORKERS.PROXIED_WORKERS if proxy_mode in ('residential', 'web_scraper_api') else WORKERS.DIRECT_WORKERS
        parallel_workers = config.get('parallel_workers', default_workers)
        logging.info(f"[{retailer_name}] Extraction workers: {parallel_workers}")

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        # Scale checkpoint interval with parallel workers (less frequent saves)
        base_checkpoint_interval = config.get('checkpoint_interval', 25)
        checkpoint_interval = base_checkpoint_interval * max(1, parallel_workers) if parallel_workers > 1 else base_checkpoint_interval

        stores = []
        completed_urls = set()
        failed_urls = []
        failed_reasons = {}
        checkpoints_used = False

        # Load checkpoint if resuming
        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores = checkpoint.get('stores', [])
                completed_urls = set(checkpoint.get('completed_urls', []))
                # Also load previously failed URLs for retry
                failed_urls = checkpoint.get('failed_urls', [])
                failed_reasons = checkpoint.get('failed_reasons', {})
                logging.info(f"[{retailer_name}] Resuming from checkpoint: {len(stores)} stores, "
                           f"{len(failed_urls)} failed URLs to retry")
                checkpoints_used = True

        # Try to load cached URLs (skip sitemap fetch if cache is valid)
        url_cache_days = config.get('url_cache_days', DEFAULT_CACHE_EXPIRY_DAYS)
        url_cache = URLCache(retailer_name, expiry_days=url_cache_days)
        all_store_urls = None
        if not refresh_urls:
            all_store_urls = url_cache.get()

        if all_store_urls is None:
            # Cache miss or refresh requested - fetch from sitemap
            logging.info(f"[{retailer_name}] Fetching store URLs from sitemap")
            store_list = get_all_store_ids(
                session,
                min_delay=min_delay,
                max_delay=max_delay
            )

            if not store_list:
                logging.warning(f"[{retailer_name}] No store URLs found in sitemap")
                return {'stores': [], 'count': 0, 'checkpoints_used': False}

            all_store_urls = [s.get('url') for s in store_list if s.get('url')]
            logging.info(f"[{retailer_name}] Found {len(all_store_urls)} store URLs in sitemap")

            # Cache the discovered URLs for future runs
            if all_store_urls:
                url_cache.set(all_store_urls)
        else:
            logging.info(f"[{retailer_name}] Using cached URLs (skipped sitemap fetch)")

        if not all_store_urls:
            logging.warning(f"[{retailer_name}] No store URLs available")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        # Filter to remaining URLs (exclude already completed)
        remaining_urls = [url for url in all_store_urls if url not in completed_urls]

        # Add previously failed URLs to the beginning for retry
        if failed_urls:
            # Remove from remaining to avoid duplicates, then prepend
            failed_set = set(failed_urls)
            remaining_urls = [url for url in remaining_urls if url not in failed_set]
            remaining_urls = failed_urls + remaining_urls
            failed_urls = []  # Clear for this run
            failed_reasons = {}

        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} stores")
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_urls = remaining_urls[:total_needed]
            else:
                remaining_urls = []

        total_to_process = len(remaining_urls)
        if total_to_process == 0:
            logging.info(f"[{retailer_name}] No stores to process (all completed or limit reached)")
            return {
                'stores': stores,
                'count': len(stores),
                'checkpoints_used': checkpoints_used
            }

        logging.info(f"[{retailer_name}] Extracting store details ({total_to_process} URLs)")

        # Track extraction statistics
        start_time = time.time()

        # Use parallel extraction if workers > 1
        if parallel_workers > 1 and total_to_process > 0:
            logging.info(f"[{retailer_name}] Using parallel extraction with {parallel_workers} workers")

            # Create session factory for thread-safe session creation
            session_factory = create_session_factory(config)

            # Thread-safe counters for progress
            processed_count = [0]
            successful_count = [0]
            processed_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                # Process in batches to limit memory usage
                batch_size = config.get('extraction_batch_size', 500)

                for batch_start in range(0, len(remaining_urls), batch_size):
                    batch_urls = remaining_urls[batch_start:batch_start + batch_size]
                    futures = {
                        executor.submit(
                            _extract_single_store_worker,
                            url,
                            session_factory,
                            config,
                            retailer_name,
                            min_delay,
                            max_delay
                        ): url
                        for url in batch_urls
                    }

                    for future in as_completed(futures):
                        url, store_data, error_reason = future.result()

                        with processed_lock:
                            processed_count[0] += 1
                            current_count = processed_count[0]

                            if store_data:
                                stores.append(store_data)
                                completed_urls.add(url)
                                successful_count[0] += 1
                            else:
                                failed_urls.append(url)
                                if error_reason:
                                    failed_reasons[url] = error_reason

                            # Progress logging every 50 stores
                            if current_count % 50 == 0:
                                success_rate = (successful_count[0] / current_count * 100) if current_count > 0 else 0
                                logging.info(
                                    f"[{retailer_name}] Progress: {current_count}/{total_to_process} "
                                    f"({current_count/total_to_process*100:.1f}%) - "
                                    f"{successful_count[0]} stores extracted ({success_rate:.1f}% success)"
                                )

                            # Checkpoint at intervals
                            if current_count % checkpoint_interval == 0:
                                elapsed = time.time() - start_time
                                avg_time = elapsed / current_count if current_count > 0 else 0
                                utils.save_checkpoint({
                                    'completed_count': len(stores),
                                    'completed_urls': list(completed_urls),
                                    'failed_urls': failed_urls,
                                    'failed_reasons': failed_reasons,
                                    'stores': stores,
                                    'extraction_stats': {
                                        'success_rate': successful_count[0] / current_count if current_count > 0 else 0,
                                        'avg_time_per_store': avg_time,
                                        'total_requests': get_request_count()
                                    },
                                    'last_updated': datetime.now().isoformat(),
                                    'scraper_version': '2.0'
                                }, checkpoint_path)
                                logging.debug(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores")
        else:
            # Sequential extraction (for direct mode or single store)
            logging.info(f"[{retailer_name}] Using sequential extraction")
            for i, store_url in enumerate(remaining_urls, 1):
                store_obj = extract_store_details(
                    session,
                    store_url,
                    min_delay=min_delay,
                    max_delay=max_delay
                )
                if store_obj:
                    stores.append(store_obj.to_dict())
                    completed_urls.add(store_url)
                else:
                    failed_urls.append(store_url)
                    failed_reasons[store_url] = "Extraction returned None"

                # Progress logging every 50 stores
                if i % 50 == 0:
                    success_rate = (len(stores) / i * 100) if i > 0 else 0
                    logging.info(
                        f"[{retailer_name}] Progress: {i}/{total_to_process} "
                        f"({i/total_to_process*100:.1f}%) - "
                        f"{len(stores)} stores extracted ({success_rate:.1f}% success)"
                    )

                # Checkpoint at intervals
                if i % checkpoint_interval == 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / i if i > 0 else 0
                    utils.save_checkpoint({
                        'completed_count': len(stores),
                        'completed_urls': list(completed_urls),
                        'failed_urls': failed_urls,
                        'failed_reasons': failed_reasons,
                        'stores': stores,
                        'extraction_stats': {
                            'success_rate': len(stores) / i if i > 0 else 0,
                            'avg_time_per_store': avg_time,
                            'total_requests': get_request_count()
                        },
                        'last_updated': datetime.now().isoformat(),
                        'scraper_version': '2.0'
                    }, checkpoint_path)
                    logging.debug(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores")

        # Final checkpoint and statistics
        elapsed = time.time() - start_time
        avg_time = elapsed / total_to_process if total_to_process > 0 else 0
        success_rate = (len(stores) / (len(stores) + len(failed_urls)) * 100) if (len(stores) + len(failed_urls)) > 0 else 0

        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_urls': list(completed_urls),
                'failed_urls': failed_urls,
                'failed_reasons': failed_reasons,
                'stores': stores,
                'extraction_stats': {
                    'success_rate': success_rate / 100,
                    'avg_time_per_store': avg_time,
                    'total_requests': get_request_count()
                },
                'last_updated': datetime.now().isoformat(),
                'scraper_version': '2.0'
            }, checkpoint_path)
            logging.info(f"[{retailer_name}] Final checkpoint saved: {len(stores)} stores")

        # Save failed extractions for later analysis
        if failed_urls:
            _save_failed_extractions(retailer_name, failed_urls, failed_reasons)

        # Validate store data
        validation_summary = utils.validate_stores_batch(stores)
        logging.info(
            f"[{retailer_name}] Validation: {validation_summary['valid']}/{validation_summary['total']} valid, "
            f"{validation_summary['warning_count']} warnings"
        )

        logging.info(
            f"[{retailer_name}] Completed: {len(stores)} stores scraped "
            f"({success_rate:.1f}% success rate), "
            f"{len(failed_urls)} failed, "
            f"{elapsed:.1f}s total ({avg_time:.2f}s/store)"
        )

        return {
            'stores': stores,
            'count': len(stores),
            'checkpoints_used': checkpoints_used
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
