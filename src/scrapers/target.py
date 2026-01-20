"""Core scraping functions for Target Store Locator"""

import gzip
import json
import logging
import random
import re
import time
import urllib.parse
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from io import BytesIO
import requests

from config import target_config
from src.shared import utils
from src.shared.request_counter import RequestCounter


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
    latitude: Optional[float]
    longitude: Optional[float]
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
    """Check if we need to pause based on request count (#71).

    Uses standardized random delay ranges for consistency with other scrapers.
    """
    count = _request_counter.count

    if count % target_config.PAUSE_200_REQUESTS == 0 and count > 0:
        # Use random delay range for 200-request pause (#71)
        pause_time = random.uniform(target_config.PAUSE_200_MIN, target_config.PAUSE_200_MAX)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % target_config.PAUSE_50_REQUESTS == 0 and count > 0:
        # Use random delay range for 50-request pause (#71)
        pause_time = random.uniform(target_config.PAUSE_50_MIN, target_config.PAUSE_50_MAX)
        logging.info(f"Pause after {count} requests: {pause_time:.1f} seconds")
        time.sleep(pause_time)


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

    # Build URL with params for get_with_retry
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


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count


def reset_request_counter() -> None:
    """Reset request counter"""
    _request_counter.reset()


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
    retailer_name = kwargs.get('retailer', 'target')
    logging.info(f"[{retailer_name}] Starting scrape run")
    
    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        
        reset_request_counter()
        
        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        checkpoint_interval = config.get('checkpoint_interval', 100)
        
        stores = []
        completed_ids = set()
        checkpoints_used = False
        
        if resume:
            checkpoint = utils.load_checkpoint(checkpoint_path)
            if checkpoint:
                stores = checkpoint.get('stores', [])
                completed_ids = set(checkpoint.get('completed_ids', []))
                logging.info(f"[{retailer_name}] Resuming from checkpoint: {len(stores)} stores already collected")
                checkpoints_used = True
        
        store_list = get_all_store_ids(session)
        logging.info(f"[{retailer_name}] Found {len(store_list)} store IDs")
        
        if not store_list:
            logging.warning(f"[{retailer_name}] No store IDs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}
        
        remaining_stores = [s for s in store_list if s.get('store_id') not in completed_ids]
        
        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} stores")
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_stores = remaining_stores[:total_needed]
            else:
                remaining_stores = []
        
        total_to_process = len(remaining_stores)
        for i, store_info in enumerate(remaining_stores, 1):
            store_id = store_info.get('store_id')
            store_obj = get_store_details(session, store_id)
            if store_obj:
                stores.append(store_obj.to_dict())
                completed_ids.add(store_id)
            
            # Progress logging every 100 stores
            if i % 100 == 0:
                logging.info(f"[{retailer_name}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")
            
            if i % checkpoint_interval == 0:
                utils.save_checkpoint({
                    'completed_count': len(stores),
                    'completed_ids': list(completed_ids),
                    'stores': stores,
                    'last_updated': datetime.now().isoformat()
                }, checkpoint_path)
                logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores processed")
        
        if stores:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_ids': list(completed_ids),
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
