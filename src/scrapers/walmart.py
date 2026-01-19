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
from bs4 import BeautifulSoup
import requests

from config import walmart_config
from src.shared import utils
from src.shared.request_counter import RequestCounter


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
    latitude: Optional[float]
    longitude: Optional[float]
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
        # Convert boolean fields to strings for CSV compatibility
        if result.get('is_glass_eligible') is None:
            result['is_glass_eligible'] = False
        result['is_glass_eligible'] = 'True' if result['is_glass_eligible'] else 'False'
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
            # Try to decompress gzipped content, fall back to plain text if not gzipped
            try:
                xml_content = gzip.decompress(response.content).decode('utf-8')
            except (gzip.BadGzipFile, OSError):
                # Content is not gzipped, try as plain text
                logging.debug(f"Content from {sitemap_url} is not gzipped, using plain text")
                xml_content = response.content.decode('utf-8')

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
        # Use BeautifulSoup to extract __NEXT_DATA__ script tag
        # This is more robust than regex as it properly handles embedded scripts
        # that might contain </script> within JSON string values
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__', type='application/json')

        if not script_tag or not script_tag.string:
            logging.warning(f"No __NEXT_DATA__ script tag found for {url}")
            logging.warning("Walmart requires JavaScript rendering. Enable proxy with render_js=true in config/retailers.yaml")
            return None

        # Parse JSON from script tag
        try:
            data = json.loads(script_tag.string)
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
            latitude=latitude,
            longitude=longitude,
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
    retailer_name = kwargs.get('retailer', 'walmart')
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
