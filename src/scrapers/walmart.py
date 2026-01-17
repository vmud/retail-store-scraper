"""Core scraping functions for Walmart Store Locator"""

import gzip
import json
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional
import requests

from config import walmart_config
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
class WalmartStore:
    """Data model for Walmart store information"""
    store_id: str
    store_type: str
    name: str
    phone_number: str
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: float
    longitude: float
    capabilities: Optional[List[str]]
    is_glass_eligible: bool
    url: str
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        result = asdict(self)
        # Convert capabilities list to JSON string for CSV compatibility
        if result.get('capabilities'):
            result['capabilities'] = json.dumps(result['capabilities'])
        elif result.get('capabilities') is None:
            result['capabilities'] = ''  # Empty string for CSV when None
        # Convert numeric types to appropriate format
        if result.get('latitude') is None:
            result['latitude'] = ''
        else:
            result['latitude'] = str(result['latitude'])
        if result.get('longitude') is None:
            result['longitude'] = ''
        else:
            result['longitude'] = str(result['longitude'])
        if result.get('is_glass_eligible') is None:
            result['is_glass_eligible'] = False
        return result


def _check_pause_logic() -> None:
    """Check if we need to pause based on request count"""
    count = _request_counter.count

    if count % walmart_config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(walmart_config.PAUSE_200_MIN, walmart_config.PAUSE_200_MAX)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % walmart_config.PAUSE_50_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(walmart_config.PAUSE_50_MIN, walmart_config.PAUSE_50_MAX)
        logging.info(f"Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)


def get_store_urls_from_sitemap(session: requests.Session) -> List[str]:
    """Fetch all store URLs from the Walmart gzipped sitemaps.

    Returns:
        List of store URLs from all sitemap types
    """
    all_store_urls = []

    for sitemap_url in walmart_config.SITEMAP_URLS:
        logging.info(f"Fetching sitemap: {sitemap_url}")

        response = utils.get_with_retry(session, sitemap_url)
        if not response:
            logging.error(f"Failed to fetch sitemap: {sitemap_url}")
            continue

        _request_counter.increment()
        _check_pause_logic()

        try:
            # Decompress gzipped content
            xml_content = gzip.decompress(response.content).decode('utf-8')

            # Parse XML
            root = ET.fromstring(xml_content)
            namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            # Extract all URLs
            sitemap_urls = []
            for loc in root.findall(".//sm:loc", namespace):
                url = loc.text
                if url:
                    sitemap_urls.append(url)

            all_store_urls.extend(sitemap_urls)
            logging.info(f"Found {len(sitemap_urls)} store URLs from {sitemap_url}")

        except gzip.BadGzipFile as e:
            logging.error(f"Failed to decompress gzip sitemap {sitemap_url}: {e}")
            continue
        except ET.ParseError as e:
            logging.error(f"Failed to parse XML sitemap {sitemap_url}: {e}")
            continue
        except Exception as e:
            logging.error(f"Unexpected error processing sitemap {sitemap_url}: {e}")
            continue

    logging.info(f"Total store URLs collected: {len(all_store_urls)}")
    return all_store_urls


def extract_store_details(session: requests.Session, url: str) -> Optional[WalmartStore]:
    """Extract store data from a single Walmart store page.

    Args:
        session: Requests session object
        url: Store page URL

    Returns:
        WalmartStore object if successful, None otherwise
    """
    logging.debug(f"Extracting details from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"Failed to fetch store details: {url}")
        return None

    _request_counter.increment()
    _check_pause_logic()

    try:
        # Find __NEXT_DATA__ script tag using regex
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            response.text,
            re.DOTALL
        )

        if not match:
            logging.warning(f"No __NEXT_DATA__ script tag found for {url}")
            return None

        # Parse JSON from script tag
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logging.warning(f"Failed to parse JSON from __NEXT_DATA__ for {url}: {e}")
            return None

        # Navigate to store data in Next.js structure: props.pageProps.store
        page_props = data.get('props', {})
        if not page_props:
            logging.warning(f"No 'props' found in __NEXT_DATA__ for {url}")
            return None

        store_data = page_props.get('pageProps', {}).get('store', {})
        if not store_data:
            logging.warning(f"No 'store' found in props.pageProps for {url}")
            return None

        # Extract store ID (from store_data.id or URL pattern)
        store_id = store_data.get('id', '')
        if not store_id:
            # Fallback: extract from URL pattern /store/{storeId}-{city}-{state}
            url_match = re.search(r'/store/(\d+)-', url)
            if url_match:
                store_id = url_match.group(1)

        # Extract address components
        address = store_data.get('address', {})

        # Extract geoPoint
        geo_point = store_data.get('geoPoint', {})
        latitude = geo_point.get('latitude') if geo_point else None
        longitude = geo_point.get('longitude') if geo_point else None

        # Convert latitude/longitude to float if they're strings
        if latitude is not None:
            try:
                latitude = float(latitude)
            except (ValueError, TypeError):
                latitude = None
        if longitude is not None:
            try:
                longitude = float(longitude)
            except (ValueError, TypeError):
                longitude = None

        # Extract capabilities (array)
        capabilities = store_data.get('capabilities', [])
        if capabilities is None:
            capabilities = []

        # Extract isGlassEligible (boolean, default to False if missing)
        is_glass_eligible = store_data.get('isGlassEligible', False)
        if is_glass_eligible is None:
            is_glass_eligible = False

        # Extract store type (name field typically contains "Supercenter", "Neighborhood Market", etc.)
        store_type = store_data.get('name', '')  # e.g., "Walmart Supercenter"
        # If store_type contains "Supercenter", "Neighborhood Market", etc., extract it
        if 'Supercenter' in store_type:
            store_type_clean = 'Supercenter'
        elif 'Neighborhood Market' in store_type:
            store_type_clean = 'Neighborhood Market'
        elif 'Discount' in store_type:
            store_type_clean = 'Discount Store'
        else:
            store_type_clean = store_type or 'Other'

        # Extract displayName for the actual store name
        display_name = store_data.get('displayName', store_data.get('name', ''))

        # Create WalmartStore object
        store = WalmartStore(
            store_id=store_id,
            store_type=store_type_clean,
            name=display_name,
            phone_number=store_data.get('phoneNumber', ''),
            street_address=address.get('addressLineOne', ''),
            city=address.get('city', ''),
            state=address.get('state', ''),
            postal_code=address.get('postalCode', ''),
            country=address.get('country', 'US'),
            latitude=latitude or 0.0,
            longitude=longitude or 0.0,
            capabilities=capabilities if capabilities else None,
            is_glass_eligible=bool(is_glass_eligible),
            url=url,
            scraped_at=datetime.now().isoformat()
        )

        logging.debug(f"Extracted store: {store.name} ({store.store_type})")
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
