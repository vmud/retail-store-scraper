"""Core scraping functions for AT&T Store Locator"""

import json
import logging
import random
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional
from bs4 import BeautifulSoup
import requests

from config import att_config
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
class ATTStore:
    """Data model for AT&T store information"""
    store_id: str
    name: str
    telephone: str
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    rating_value: Optional[float]
    rating_count: Optional[int]
    url: str
    scraped_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        return asdict(self)


def _check_pause_logic() -> None:
    """Check if we need to pause based on request count"""
    count = _request_counter.count

    if count % att_config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(att_config.PAUSE_200_MIN, att_config.PAUSE_200_MAX)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % att_config.PAUSE_50_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(att_config.PAUSE_50_MIN, att_config.PAUSE_50_MAX)
        logging.info(f"Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)


def get_store_urls_from_sitemap(session: requests.Session) -> List[str]:
    """Fetch all store URLs from the AT&T sitemap.

    Returns:
        List of store URLs (filtered to only those ending in numeric IDs)
    """
    logging.info(f"Fetching sitemap from {att_config.SITEMAP_URL}")

    response = utils.get_with_retry(session, att_config.SITEMAP_URL)
    if not response:
        logging.error("Failed to fetch sitemap")
        return []

    _request_counter.increment()
    _check_pause_logic()

    try:
        # Parse XML
        root = ET.fromstring(response.content)
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Extract all URLs
        all_urls = []
        for loc in root.findall(".//ns:loc", namespace):
            url = loc.text
            if url:
                all_urls.append(url)

        logging.info(f"Found {len(all_urls)} total URLs in sitemap")

        # Filter to only store URLs (ending in numeric ID)
        store_urls = []
        for url in all_urls:
            # Extract the last segment of the URL path
            url_parts = url.rstrip('/').split('/')
            if url_parts:
                last_segment = url_parts[-1]
                # Check if it's a numeric ID (store page)
                if last_segment.isdigit():
                    store_urls.append(url)

        logging.info(f"Filtered to {len(store_urls)} store URLs (ending in numeric IDs)")

        return store_urls

    except ET.ParseError as e:
        logging.error(f"Failed to parse XML sitemap: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error parsing sitemap: {e}")
        return []


def extract_store_details(session: requests.Session, url: str) -> Optional[ATTStore]:
    """Extract store data from a single AT&T store page.

    Args:
        session: Requests session object
        url: Store page URL

    Returns:
        ATTStore object if successful, None otherwise
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

        # Find all JSON-LD script tags (there may be multiple)
        scripts = soup.find_all('script', type='application/ld+json')
        if not scripts:
            logging.warning(f"No JSON-LD found for {url}")
            return None

        # Try each script until we find a MobilePhoneStore
        data = None
        for script in scripts:
            try:
                script_data = json.loads(script.string)
                if script_data.get('@type') == 'MobilePhoneStore':
                    data = script_data
                    break
            except json.JSONDecodeError as e:
                logging.debug(f"Failed to parse JSON-LD script for {url}: {e}")
                continue

        # If no MobilePhoneStore found, log and return None
        if not data:
            if scripts:
                first_type = json.loads(scripts[0].string).get('@type', 'Unknown') if scripts[0].string else 'Unknown'
                logging.debug(f"Skipping {url}: No MobilePhoneStore found (first @type: '{first_type}')")
            return None

        # Extract store ID from URL
        url_parts = url.rstrip('/').split('/')
        store_id = url_parts[-1] if url_parts else ''

        # Extract address components
        address = data.get('address', {})

        # Handle nested addressCountry structure
        address_country = address.get('addressCountry', {})
        if isinstance(address_country, dict):
            country = address_country.get('name', 'US')
        else:
            country = address_country if address_country else 'US'

        # Extract rating if available
        rating = data.get('aggregateRating', {})
        rating_value = None
        rating_count = None

        if rating:
            rating_val = rating.get('ratingValue')
            if rating_val:
                try:
                    rating_value = float(rating_val)
                except (ValueError, TypeError):
                    rating_value = None

            rating_cnt = rating.get('ratingCount')
            if rating_cnt:
                try:
                    rating_count = int(rating_cnt)
                except (ValueError, TypeError):
                    rating_count = None

        # Create ATTStore object
        store = ATTStore(
            store_id=store_id,
            name=data.get('name', ''),
            telephone=data.get('telephone', ''),
            street_address=address.get('streetAddress', ''),
            city=address.get('addressLocality', ''),
            state=address.get('addressRegion', ''),
            postal_code=address.get('postalCode', ''),
            country=country,
            rating_value=rating_value,
            rating_count=rating_count,
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
