"""Core scraping functions for T-Mobile Store Locator"""

import json
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from config import tmobile_config
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
class TMobileStore:
    """Data model for T-Mobile store information"""
    branch_code: str
    name: str
    store_type: Optional[str]
    phone: str
    street_address: str
    city: str
    state: str
    zip: str
    country: str
    latitude: str
    longitude: str
    opening_hours: Optional[List[str]]
    url: str
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        result = asdict(self)
        # Convert opening_hours list to JSON string for CSV compatibility
        if result.get('opening_hours'):
            result['opening_hours'] = json.dumps(result['opening_hours'])
        elif result.get('opening_hours') is None:
            result['opening_hours'] = ''  # Empty string for CSV when None
        # Handle store_type (Optional[str]) - convert None to empty string for CSV
        if result.get('store_type') is None:
            result['store_type'] = ''  # Empty string for CSV when None
        return result


def _check_pause_logic() -> None:
    """Check if we need to pause based on request count"""
    count = _request_counter.count

    if count % tmobile_config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(tmobile_config.PAUSE_200_MIN, tmobile_config.PAUSE_200_MAX)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % tmobile_config.PAUSE_50_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(tmobile_config.PAUSE_50_MIN, tmobile_config.PAUSE_50_MAX)
        logging.info(f"Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)


def _extract_state_from_url(url: str) -> Optional[str]:
    """Extract state code from T-Mobile URL pattern.

    URL pattern: /stores/bd/t-mobile-{city}-{state}-{zip}-{id}
    Note: City can contain hyphens (e.g., "new-york"), so we need to match carefully.
    We look for the two-letter state code followed by a hyphen and digits (zip code).

    Args:
        url: Store URL

    Returns:
        Lowercase state code (e.g., "ca", "ny", "tx") or None if pattern doesn't match
    """
    # Pattern: /stores/bd/t-mobile-{city}-{state}-{zip}-{id}
    # Match: /stores/bd/t-mobile- followed by city (may contain hyphens),
    # then -{state}-{zip}- where state is 2 letters and zip is digits
    # We look for -XX- followed by digits, where XX is the state code
    url_lower = url.lower()
    pattern = r'/stores/bd/t-mobile-.*-([a-z]{2})-\d+-'
    match = re.search(pattern, url_lower)
    if match:
        return match.group(1)
    return None


def _filter_urls_by_state(urls: List[str], state_code: str) -> List[str]:
    """Filter URLs by state code (case-insensitive).

    Args:
        urls: List of store URLs
        state_code: State code to filter by (e.g., "ca", "ny", "tx")

    Returns:
        List of URLs matching the specified state
    """
    state_code_lower = state_code.lower()
    filtered = []
    for url in urls:
        extracted_state = _extract_state_from_url(url)
        if extracted_state and extracted_state == state_code_lower:
            filtered.append(url)
    return filtered


def _extract_store_type_from_title(page_title: str) -> Optional[str]:
    """Extract store type from T-Mobile store page title.

    Args:
        page_title: The HTML <title> content from a store detail page

    Returns:
        Normalized store type string, or None if not found

    Examples:
        >>> _extract_store_type_from_title("T-Mobile Penn & I-494: Experience Store in Bloomington, MN")
        'T-Mobile Experience Store'

        >>> _extract_store_type_from_title("T-Mobile The Richfield Hub: Authorized Retailer in Richfield, MN")
        'T-Mobile Authorized Retailer'
    """
    patterns = [
        (r':\s*(Authorized Retailer)\s+in', 'T-Mobile Authorized Retailer'),
        (r':\s*(Experience Store)\s+in', 'T-Mobile Experience Store'),
        (r':\s*(Neighborhood Store)\s+in', 'T-Mobile Neighborhood Store'),
        (r':\s*(Store)\s+in', 'T-Mobile Store'),
    ]

    for pattern, store_type in patterns:
        if re.search(pattern, page_title, re.IGNORECASE):
            return store_type

    return None


def _extract_store_type_from_dom(soup: BeautifulSoup) -> Optional[str]:
    """Extract store type from page DOM as fallback.

    Args:
        soup: BeautifulSoup parsed HTML

    Returns:
        Normalized store type string, or None if not found
    """
    store_types = [
        'T-Mobile Experience Store',
        'T-Mobile Authorized Retailer',
        'T-Mobile Neighborhood Store',
        'T-Mobile Store'
    ]

    page_text = soup.get_text()
    for store_type in store_types:
        if store_type in page_text:
            return store_type

    return None


def get_store_urls_from_sitemap(session: requests.Session) -> List[str]:
    """Fetch all store URLs from the T-Mobile paginated sitemaps.

    Returns:
        List of store URLs (filtered to only those containing /stores/bd/)
    """
    all_store_urls = []

    for page in tmobile_config.SITEMAP_PAGES:
        if page == 1:
            sitemap_url = tmobile_config.SITEMAP_BASE_URL
        else:
            sitemap_url = f"{tmobile_config.SITEMAP_BASE_URL}?p={page}"

        logging.info(f"Fetching sitemap page {page} from {sitemap_url}")

        response = utils.get_with_retry(session, sitemap_url)
        if not response:
            logging.error(f"Failed to fetch sitemap page {page}")
            continue

        _request_counter.increment()
        _check_pause_logic()

        try:
            # Parse XML
            root = ET.fromstring(response.content)
            namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # Extract all URLs
            for loc in root.findall(".//sm:loc", namespace):
                url = loc.text
                if url and '/stores/bd/' in url:
                    all_store_urls.append(url)

            logging.info(f"Found {len(all_store_urls)} store URLs from page {page}")

        except ET.ParseError as e:
            logging.error(f"Failed to parse XML sitemap page {page}: {e}")
            continue
        except Exception as e:
            logging.error(f"Unexpected error parsing sitemap page {page}: {e}")
            continue

    logging.info(f"Total store URLs collected: {len(all_store_urls)}")
    return all_store_urls


def extract_store_details(session: requests.Session, url: str) -> Optional[TMobileStore]:
    """Extract store data from a single T-Mobile store page.

    Args:
        session: Requests session object
        url: Store page URL

    Returns:
        TMobileStore object if successful, None otherwise
    """
    logging.debug(f"Extracting details from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"Failed to fetch store details: {url}")
        return None

    _request_counter.increment()
    _check_pause_logic()

    try:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract store type from page title (with DOM fallback)
        store_type = None
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            store_type = _extract_store_type_from_title(title_tag.string)

        # Fallback to DOM extraction if title parsing fails
        if not store_type:
            store_type = _extract_store_type_from_dom(soup)

        # Find all JSON-LD script tags (there may be multiple)
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

                # Handle both single objects and arrays
                if isinstance(script_data, list):
                    for item in script_data:
                        if item.get('@type') == 'Store':
                            data = item
                            break
                elif script_data.get('@type') == 'Store':
                    data = script_data

                if data:
                    break

            except json.JSONDecodeError as e:
                logging.debug(f"Failed to parse JSON-LD script for {url}: {e}")
                continue

        # If no Store found, log and return None
        if not data:
            if scripts:
                try:
                    first_script = json.loads(scripts[0].string) if scripts[0].string else {}
                    first_type = first_script.get('@type', 'Unknown') if isinstance(first_script, dict) else 'Unknown'
                    if isinstance(first_script, list) and first_script:
                        first_type = first_script[0].get('@type', 'Unknown') if isinstance(first_script[0], dict) else 'Unknown'
                    logging.debug(f"Skipping {url}: No Store found (first @type: '{first_type}')")
                except Exception:
                    logging.debug(f"Skipping {url}: No Store found")
            return None

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

        # Extract openingHours (array)
        opening_hours = data.get('openingHours', [])
        if isinstance(opening_hours, str):
            # If it's a single string, convert to list
            opening_hours = [opening_hours]

        # Extract branchCode
        branch_code = data.get('branchCode', '')

        # Create TMobileStore object
        store = TMobileStore(
            branch_code=branch_code,
            name=data.get('name', ''),
            store_type=store_type,
            phone=data.get('telephone', ''),
            street_address=address.get('streetAddress', ''),
            city=address.get('addressLocality', ''),
            state=address.get('addressRegion', ''),
            zip=address.get('postalCode', ''),
            country=country,
            latitude=str(latitude) if latitude else '',
            longitude=str(longitude) if longitude else '',
            opening_hours=opening_hours if opening_hours else None,
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


def run(session, config: dict, **kwargs) -> dict:
    """Standard scraper entry point.
    
    Args:
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - resume: bool - Resume from checkpoint
            - limit: int - Max stores to process
            - incremental: bool - Only process changes
    
    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = kwargs.get('retailer', 'tmobile')
    logging.info(f"[{retailer_name}] Starting scrape run")
    
    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        
        reset_request_counter()
        
        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = config.get('checkpoint_interval', 100)
        
        stores = []
        completed_urls = set()
        checkpoints_used = False
        
        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores = checkpoint.get('stores', [])
                completed_urls = set(checkpoint.get('completed_urls', []))
                logging.info(f"[{retailer_name}] Resuming from checkpoint: {len(stores)} stores already collected")
                checkpoints_used = True
        
        store_urls = get_store_urls_from_sitemap(session)
        logging.info(f"[{retailer_name}] Found {len(store_urls)} store URLs")
        
        if not store_urls:
            logging.warning(f"[{retailer_name}] No store URLs found in sitemap")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}
        
        remaining_urls = [url for url in store_urls if url not in completed_urls]
        
        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} stores")
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_urls = remaining_urls[:total_needed]
            else:
                remaining_urls = []
        
        total_to_process = len(remaining_urls)
        for i, url in enumerate(remaining_urls, 1):
            store_obj = extract_store_details(session, url)
            if store_obj:
                stores.append(store_obj.to_dict())
                completed_urls.add(url)
            
            # Progress logging every 100 stores
            if i % 100 == 0:
                logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")
            
            if i % checkpoint_interval == 0:
                utils.save_checkpoint({
                    'completed_count': len(stores),
                    'completed_urls': list(completed_urls),
                    'stores': stores,
                    'last_updated': datetime.now().isoformat()
                }, checkpoint_path)
                logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores processed")
        
        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_urls': list(completed_urls),
                'stores': stores,
                'last_updated': datetime.now().isoformat()
            }, checkpoint_path)
            logging.info(f"[{retailer_name}] Final checkpoint saved: {len(stores)} stores total")
        
        logging.info(f"[{retailer_name}] Completed: {len(stores)} stores successfully scraped")
        
        return {
            'stores': stores,
            'count': len(stores),
            'checkpoints_used': checkpoints_used
        }
        
    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
