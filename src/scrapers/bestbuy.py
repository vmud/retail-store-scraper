"""Core scraping functions for Best Buy Store Locator"""

import json
import logging
import random
import re
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import requests

from config import bestbuy_config
from src.shared import utils


class RequestCounter:
    """Track request count for pause logic"""
    def __init__(self):
        self.count = 0

    def increment(self) -> int:
        """Increment counter and return current count"""
        self.count += 1
        return self.count

    def reset(self) -> None:
        """Reset counter"""
        self.count = 0


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
        section_text = section.get_text().lower()
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


def _normalize_service_name(service: str) -> str:
    """Normalize service name to canonical form.

    Args:
        service: Raw service name from HTML

    Returns:
        Normalized service name or None if not a valid service
    """
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
    if len(service) < 3 or service in {'and', 'or', 'the', 'a', 'an', 'all', 'offered', 'available'}:
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

    # If no mapping found, capitalize first letter of each word
    # This handles rare services we haven't seen before
    if service and len(service) > 2:
        normalized = ' '.join(word.capitalize() for word in service.split())
        # Filter out if it still looks too generic
        if normalized.lower() not in {'Services', 'Offered', 'Available', 'Specialty', 'Shops'}:
            return normalized

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
        'specialty shops', 'shops and', 'and more', 'experience only'
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


def _check_pause_logic() -> None:
    """Check if we need to pause based on request count"""
    count = _request_counter.count

    if count % bestbuy_config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(bestbuy_config.PAUSE_200_MIN, bestbuy_config.PAUSE_200_MAX)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % bestbuy_config.PAUSE_50_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(bestbuy_config.PAUSE_50_MIN, bestbuy_config.PAUSE_50_MAX)
        logging.info(f"Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)


def get_all_store_ids(session: requests.Session) -> List[Dict[str, Any]]:
    """Extract all store URLs from Best Buy's sitemap.

    Args:
        session: Requests session object

    Returns:
        List of store dictionaries with store_id and url
    """
    logging.info(f"Fetching sitemap: {bestbuy_config.SITEMAP_URL}")

    response = utils.get_with_retry(session, bestbuy_config.SITEMAP_URL)
    if not response:
        logging.error(f"Failed to fetch sitemap: {bestbuy_config.SITEMAP_URL}")
        return []

    _request_counter.increment()
    _check_pause_logic()

    try:
        content = response.text

        # Extract actual store URLs from sitemap XML
        # Pattern: <loc>https://stores.bestbuy.com/...</loc>
        import re
        url_pattern = r'<loc>(https://stores\.bestbuy\.com/[^<]+)</loc>'
        urls = re.findall(url_pattern, content)

        # Extract store IDs from URLs and create store dictionaries
        stores = []
        seen_urls = set()

        for url in urls:
            # Skip non-store URLs (404 pages, etc.)
            if '/404.html' in url or not url.endswith('.html'):
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Extract store ID from URL pattern (last segment before .html)
            # URLs are like: https://stores.bestbuy.com/ut/farmington/360-n-station-pkwy-1887.html
            # Store ID is typically in the URL path or can be extracted from page content
            # For now, use the full URL and extract store ID from page later
            url_parts = url.rstrip('/').split('/')
            store_id = None

            # Try to extract numeric ID from URL if present
            # Some URLs might have store ID in them
            store_id_match = re.search(r'/(\d+)', url)
            if store_id_match:
                store_id = store_id_match.group(1)
            else:
                # Generate a hash-based ID from URL for tracking
                store_id = str(abs(hash(url)) % 1000000)

            stores.append({
                "store_id": store_id,
                "url": url
            })

        logging.info(f"Found {len(stores)} store URLs in sitemap")
        return stores

    except Exception as e:
        logging.error(f"Unexpected error processing sitemap: {e}")
        return []


def extract_store_details(session: requests.Session, url: str) -> Optional[BestBuyStore]:
    """Extract store data from a single Best Buy store page.

    Args:
        session: Requests session object
        url: Store page URL

    Returns:
        BestBuyStore object if successful, None otherwise
    """
    logging.debug(f"Extracting details from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"Failed to fetch store details: {url}")
        return None

    _request_counter.increment()
    _check_pause_logic()

    try:
        from bs4 import BeautifulSoup
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
        url_parts = url.rstrip('/').split('/')
        store_id_match = re.search(r'/(\d+)', url)
        if store_id_match:
            store_id = store_id_match.group(1)
        else:
            # Try to extract from JSON-LD or use hash
            store_id = data.get('locationId') or data.get('branchCode') or str(abs(hash(url)) % 1000000)

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
        latitude = geo.get('latitude', '')
        longitude = geo.get('longitude', '')

        # Convert coordinates to strings
        if latitude:
            latitude = str(latitude)
        if longitude:
            longitude = str(longitude)

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
                except:
                    pass

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


def _parse_store_data_legacy(store_data: Dict[str, Any], store_id: str) -> Optional[BestBuyStore]:
    """Parse API response data to BestBuyStore object.

    Args:
        store_data: Store data dictionary from API response
        store_id: Store ID string

    Returns:
        BestBuyStore object if successful, None otherwise
    """
    try:
        # Extract address
        street_address = store_data.get('addr1', '')
        city = store_data.get('city', '')
        state = store_data.get('state', '')
        zip_code = store_data.get('zipCode', '')

        # Extract location
        latitude = store_data.get('latitude', '')
        longitude = store_data.get('longitude', '')

        # Convert coordinates to strings
        if latitude:
            latitude = str(latitude)
        if longitude:
            longitude = str(longitude)

        # Extract services and service codes
        services = store_data.get('services', [])
        service_codes = store_data.get('serviceCodes', [])

        # Extract hours
        hours = store_data.get('hours', [])

        # Extract boolean flags
        has_pickup = store_data.get('hasPickup', False)
        curbside_enabled = store_data.get('curbsideEnabled', False)

        # Build store URL
        store_url = f"https://stores.bestbuy.com/{store_id}.html"

        # Create BestBuyStore object
        store = BestBuyStore(
            store_id=store_id,
            name=store_data.get('name', ''),
            status=store_data.get('status', ''),
            store_type=store_data.get('storeType', ''),
            display_name=store_data.get('displayName', ''),
            street_address=street_address,
            city=city,
            state=state,
            zip=zip_code,
            country='US',  # Default to US as all Best Buy stores are in US
            latitude=latitude,
            longitude=longitude,
            phone=store_data.get('phone', ''),
            services=services if services else None,
            service_codes=service_codes if service_codes else None,
            hours=hours if hours else None,
            has_pickup=bool(has_pickup),
            curbside_enabled=bool(curbside_enabled),
            url=store_url,
            scraped_at=datetime.now().isoformat()
        )

        return store

    except Exception as e:
        logging.warning(f"Error parsing store data for store_id={store_id}: {e}")
        return None


def reset_request_counter() -> None:
    """Reset the global request counter"""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count
