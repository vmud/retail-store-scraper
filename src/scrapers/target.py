"""Core scraping functions for Target Store Locator"""

import gzip
import json
import logging
import random
import re
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from io import BytesIO
import requests

from config import target_config
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
class TargetStore:
    """Data model for Target store information"""
    store_id: str
    name: str
    status: str
    street_address: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: float
    longitude: float
    phone: str
    capabilities: Optional[List[str]]
    format: Optional[str]
    building_area: Optional[int]
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
        if result.get('building_area') is None:
            result['building_area'] = ''
        else:
            result['building_area'] = str(result['building_area'])
        return result


def _check_pause_logic() -> None:
    """Check if we need to pause based on request count"""
    count = _request_counter.count

    if count % target_config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(target_config.PAUSE_200_MIN, target_config.PAUSE_200_MAX)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % target_config.PAUSE_50_THRESHOLD == 0 and count > 0:
        logging.info(f"Pause after {count} requests: {target_config.PAUSE_50_DELAY} seconds")
        time.sleep(target_config.PAUSE_50_DELAY)


def get_all_store_ids(session: requests.Session) -> List[Dict[str, Any]]:
    """Extract all store IDs from Target's sitemap.

    Args:
        session: Requests session object

    Returns:
        List of store dictionaries with store_id, slug, and url
    """
    logging.info(f"Fetching sitemap: {target_config.SITEMAP_URL}")

    response = utils.get_with_retry(session, target_config.SITEMAP_URL)
    if not response:
        logging.error(f"Failed to fetch sitemap: {target_config.SITEMAP_URL}")
        return []

    _request_counter.increment()
    _check_pause_logic()

    try:
        # Check if content is already decompressed (starts with XML) or gzipped
        content_bytes = response.content
        if content_bytes.startswith(b'<?xml') or content_bytes.startswith(b'<urlset'):
            # Already decompressed XML
            content = content_bytes.decode('utf-8')
        else:
            # Try to decompress gzipped content
            try:
                with gzip.GzipFile(fileobj=BytesIO(content_bytes)) as f:
                    content = f.read().decode('utf-8')
            except (gzip.BadGzipFile, OSError):
                # If decompression fails, try as plain text
                content = content_bytes.decode('utf-8')

        # Extract store URLs with regex
        pattern = r'https://www\.target\.com/sl/([a-zA-Z0-9-]+)/(\d+)'
        matches = re.findall(pattern, content)

        stores = []
        seen_ids = set()
        for slug, store_id in matches:
            store_id_int = int(store_id)
            if store_id_int not in seen_ids:
                seen_ids.add(store_id_int)
                stores.append({
                    "store_id": store_id_int,
                    "slug": slug,
                    "url": f"https://www.target.com/sl/{slug}/{store_id}"
                })

        logging.info(f"Found {len(stores)} stores in sitemap")
        return stores

    except gzip.BadGzipFile as e:
        logging.error(f"Failed to decompress gzip sitemap: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error processing sitemap: {e}")
        return []


def get_store_details(session: requests.Session, store_id: int) -> Optional[TargetStore]:
    """Fetch detailed store info from Redsky API.

    Args:
        session: Requests session object
        store_id: Numeric store ID

    Returns:
        TargetStore object if successful, None otherwise
    """
    params = {
        "store_id": store_id,
        "key": target_config.API_KEY,
        "channel": target_config.API_CHANNEL
    }

    headers = target_config.get_headers()

    # Build URL with params for get_with_retry
    import urllib.parse
    url_with_params = f"{target_config.REDSKY_API_URL}?{urllib.parse.urlencode(params)}"
    response = utils.get_with_retry(session, url_with_params, max_retries=target_config.MAX_RETRIES)
    if not response:
        logging.warning(f"Failed to fetch store details for store_id={store_id}")
        return None

    _request_counter.increment()
    _check_pause_logic()

    try:
        if response.status_code == 200:
            data = response.json()
            store = data.get("data", {}).get("store", {})

            if not store:
                logging.warning(f"No store data found for store_id={store_id}")
                return None

            # Extract address
            mailing_address = store.get("mailing_address", {})

            # Extract geographic specifications
            geo_specs = store.get("geographic_specifications", {})

            # Extract physical specifications
            physical_specs = store.get("physical_specifications", {})

            # Extract capabilities
            capabilities = [c.get("capability_name", "") for c in store.get("capabilities", [])]

            # Build store URL from slug if available, otherwise construct from store_id
            store_url = f"https://www.target.com/sl/store/{store_id}"
            # Try to get slug from original store data if available
            if 'slug' in store:
                store_url = f"https://www.target.com/sl/{store['slug']}/{store_id}"

            target_store = TargetStore(
                store_id=str(store.get("store_id", store_id)),
                name=store.get("location_name", ""),
                status=store.get("status", ""),
                street_address=mailing_address.get("address_line1", ""),
                city=mailing_address.get("city", ""),
                state=mailing_address.get("region", ""),  # State abbreviation
                postal_code=mailing_address.get("postal_code", ""),
                country=mailing_address.get("country", "United States of America"),
                latitude=geo_specs.get("latitude"),
                longitude=geo_specs.get("longitude"),
                phone=store.get("main_voice_phone_number", ""),
                capabilities=capabilities if capabilities else None,
                format=physical_specs.get("format"),
                building_area=physical_specs.get("total_building_area"),
                url=store_url,
                scraped_at=datetime.now().isoformat()
            )

            return target_store
        else:
            logging.warning(f"API returned status {response.status_code} for store_id={store_id}")
            return None

    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse JSON response for store_id={store_id}: {e}")
        return None
    except Exception as e:
        logging.warning(f"Unexpected error processing store_id={store_id}: {e}")
        return None


def scrape_all_stores(session: requests.Session, store_ids: List[Dict[str, Any]], resume: bool = False) -> List[TargetStore]:
    """Main scraping function with rate limiting.

    Args:
        session: Requests session object
        store_ids: List of store dictionaries from get_all_store_ids()
        resume: Whether to resume from checkpoint

    Returns:
        List of TargetStore objects
    """
    logging.info(f"Starting to scrape {len(store_ids)} stores")

    all_store_data = []

    for i, store in enumerate(store_ids, 1):
        store_id = store["store_id"]

        details = get_store_details(session, store_id)
        if details:
            all_store_data.append(details)

        # Progress logging and rate limiting
        if i % 50 == 0:
            logging.info(f"Processed {i}/{len(store_ids)} stores ({i*100/len(store_ids):.1f}%)...")
            time.sleep(target_config.PAUSE_50_DELAY)
        else:
            time.sleep(target_config.MIN_DELAY)

    logging.info(f"Completed scraping {len(all_store_data)} stores")
    return all_store_data


def scrape_state_stores(session: requests.Session, state: str) -> List[Dict[str, Any]]:
    """Scrape store IDs from a state's directory page (fallback method).

    Args:
        session: Requests session object
        state: State name (e.g., "california")

    Returns:
        List of store dictionaries with slug, store_id, and state
    """
    url = f"{target_config.STORE_DIRECTORY_BASE}/{state}"
    logging.info(f"Fetching state directory: {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"Failed to fetch state directory for {state}")
        return []

    _request_counter.increment()
    _check_pause_logic()

    try:
        # Extract /sl/{slug}/{id} links
        pattern = r'/sl/([a-zA-Z0-9-]+)/(\d+)'
        matches = re.findall(pattern, response.text)

        # Remove duplicates
        seen = set()
        stores = []
        for slug, store_id in matches:
            store_id_int = int(store_id)
            if store_id_int not in seen:
                seen.add(store_id_int)
                stores.append({
                    "slug": slug,
                    "store_id": store_id_int,
                    "state": state
                })

        logging.info(f"Found {len(stores)} stores for {state}")
        return stores

    except Exception as e:
        logging.warning(f"Error scraping state {state}: {e}")
        return []


def scrape_all_states(session: requests.Session) -> List[Dict[str, Any]]:
    """Scrape stores from all state pages (fallback method).

    Args:
        session: Requests session object

    Returns:
        List of store dictionaries from all states
    """
    all_stores = []

    for i, state in enumerate(target_config.STATES, 1):
        logging.info(f"[{i}/{len(target_config.STATES)}] Processing {state}...")
        stores = scrape_state_stores(session, state)
        all_stores.extend(stores)

        # Small delay between states
        if i < len(target_config.STATES):
            time.sleep(0.5)

    # Remove duplicates by store_id
    seen_ids = set()
    unique_stores = []
    for store in all_stores:
        if store["store_id"] not in seen_ids:
            seen_ids.add(store["store_id"])
            unique_stores.append(store)

    logging.info(f"Found {len(unique_stores)} unique stores from all states")
    return unique_stores


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count


def reset_request_counter() -> None:
    """Reset request counter"""
    _request_counter.reset()
