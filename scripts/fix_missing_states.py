#!/usr/bin/env python3
"""
Script to re-discover and scrape stores for missing states (MD, PA, RI).

The parallel discovery phase had issues where some state pages returned
wrong state data or failed silently. This script runs targeted discovery
for the affected states and merges with existing data.

Usage:
    python scripts/fix_missing_states.py [--proxy residential]

Note: DC is intentionally excluded because the /stores/state/washington-dc/
page incorrectly returns Washington state data. DC needs special handling.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from bs4 import BeautifulSoup
import requests

from config import verizon_config as config
from src.shared import utils

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.verizon.com"

# States that need re-scraping
MISSING_STATES = [
    ('maryland', 'Maryland', 'MD'),
    ('pennsylvania', 'Pennsylvania', 'PA'),
    ('rhode-island', 'Rhode Island', 'RI'),
]


def create_session(use_proxy: bool = False) -> requests.Session:
    """Create a requests session, optionally with proxy."""
    if use_proxy:
        import yaml
        with open('config/retailers.yaml', 'r') as f:
            yaml_config = yaml.safe_load(f)
        retailer_config = yaml_config['retailers']['verizon']
        os.environ['PROXY_MODE'] = 'residential'
        return utils.create_proxied_session(retailer_config)
    else:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return session


def discover_cities(session: requests.Session, state_slug: str, state_name: str) -> list:
    """Discover all cities for a state."""
    state_url = f"{BASE_URL}/stores/state/{state_slug}/"
    logger.info(f"Fetching cities for {state_name} from {state_url}")

    response = utils.get_with_retry(session, state_url)
    if not response:
        logger.error(f"Failed to fetch state page for {state_name}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    cities = []

    # Extract from stateJSON
    for script in soup.find_all('script'):
        script_content = script.string or ""
        if 'stateJSON' in script_content:
            json_match = re.search(r'stateJSON\s*=\s*({.+?});', script_content, re.DOTALL)
            if json_match:
                try:
                    state_data = json.loads(json_match.group(1))
                    json_state_name = state_data.get('state', {}).get('name', '')

                    # Verify correct state data
                    if json_state_name.lower() != state_name.lower():
                        logger.warning(f"State mismatch: expected {state_name}, got {json_state_name}")
                        continue

                    for city_data in state_data.get('cities', []):
                        city_name = city_data.get('name', '')
                        city_url_path = city_data.get('url', '')
                        if city_name and city_url_path:
                            city_url = f"{BASE_URL}{city_url_path}" if city_url_path.startswith('/') else city_url_path
                            cities.append({
                                'city': city_name,
                                'state': state_name,
                                'url': city_url
                            })
                    logger.info(f"Found {len(cities)} cities for {state_name}")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")

    return cities


def discover_stores_for_city(session: requests.Session, city: dict, delay: float = 0.3) -> list:
    """Discover all store URLs for a city."""
    store_urls = []

    response = utils.get_with_retry(session, city['url'])
    if not response:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract from cityJSON
    for script in soup.find_all('script'):
        script_content = script.string or ""
        if 'cityJSON' in script_content:
            json_match = re.search(r'cityJSON\s*=\s*({.+?});', script_content, re.DOTALL)
            if json_match:
                try:
                    city_data = json.loads(json_match.group(1))
                    for store_data in city_data.get('stores', []):
                        store_url_path = store_data.get('storeUrl', '')
                        if store_url_path:
                            store_url = f"{BASE_URL}{store_url_path}" if store_url_path.startswith('/') else store_url_path
                            store_urls.append(store_url)
                    break
                except json.JSONDecodeError:
                    pass

    time.sleep(delay)
    return store_urls


def extract_store_details(session: requests.Session, url: str) -> dict:
    """Extract store details from a store page."""
    from src.scrapers.verizon import extract_store_details as verizon_extract
    import yaml

    with open('config/retailers.yaml', 'r') as f:
        yaml_config = yaml.safe_load(f)
    retailer_config = yaml_config['retailers']['verizon']

    return verizon_extract(session, url, retailer_config, 'verizon')


def main():
    parser = argparse.ArgumentParser(description='Fix missing states in Verizon data')
    parser.add_argument('--proxy', choices=['residential', 'direct'], default='direct',
                       help='Proxy mode to use')
    parser.add_argument('--discovery-only', action='store_true',
                       help='Only discover URLs, do not scrape store details')
    args = parser.parse_args()

    use_proxy = args.proxy == 'residential'
    logger.info(f"Using proxy: {use_proxy}")

    session = create_session(use_proxy)

    all_store_urls = []

    # Phase 1: Discover cities and store URLs for missing states
    logger.info("=" * 60)
    logger.info("PHASE 1: DISCOVERING STORE URLs")
    logger.info("=" * 60)

    for state_slug, state_name, state_abbr in MISSING_STATES:
        cities = discover_cities(session, state_slug, state_name)

        if not cities:
            logger.warning(f"No cities found for {state_name}")
            continue

        state_store_urls = []
        for i, city in enumerate(cities):
            store_urls = discover_stores_for_city(session, city)
            state_store_urls.extend(store_urls)

            if (i + 1) % 20 == 0:
                logger.info(f"  {state_name}: {i+1}/{len(cities)} cities, {len(state_store_urls)} stores")

        logger.info(f"{state_name}: {len(state_store_urls)} store URLs discovered")
        all_store_urls.extend(state_store_urls)

    # Save discovered URLs
    urls_file = Path('data/verizon/missing_state_urls.txt')
    urls_file.parent.mkdir(parents=True, exist_ok=True)
    with open(urls_file, 'w') as f:
        for url in all_store_urls:
            f.write(url + '\n')
    logger.info(f"Saved {len(all_store_urls)} URLs to {urls_file}")

    if args.discovery_only:
        logger.info("Discovery only mode - skipping store extraction")
        return

    # Phase 2: Extract store details
    logger.info("=" * 60)
    logger.info("PHASE 2: EXTRACTING STORE DETAILS")
    logger.info("=" * 60)

    new_stores = []
    for i, url in enumerate(all_store_urls):
        store = extract_store_details(session, url)
        if store:
            new_stores.append(store)

        if (i + 1) % 50 == 0:
            logger.info(f"Progress: {i+1}/{len(all_store_urls)} ({len(new_stores)} extracted)")

    logger.info(f"Extracted {len(new_stores)} stores")

    # Phase 3: Merge with existing data
    logger.info("=" * 60)
    logger.info("PHASE 3: MERGING WITH EXISTING DATA")
    logger.info("=" * 60)

    existing_file = Path('data/verizon/output/stores_latest.json')
    if not existing_file.exists():
        logger.error(f"Existing stores file not found: {existing_file}")
        return
    
    with open(existing_file, 'r') as f:
        existing_stores = json.load(f)

    logger.info(f"Existing stores: {len(existing_stores)}")

    # Deduplicate by URL
    existing_urls = {s.get('url') for s in existing_stores}
    added_count = 0
    for store in new_stores:
        if store.get('url') not in existing_urls:
            existing_stores.append(store)
            existing_urls.add(store.get('url'))
            added_count += 1

    logger.info(f"Added {added_count} new stores")
    logger.info(f"Total stores: {len(existing_stores)}")

    # Save merged data
    backup_file = existing_file.with_suffix('.json.bak')
    existing_file.rename(backup_file)
    logger.info(f"Backed up existing data to {backup_file}")

    with open(existing_file, 'w') as f:
        json.dump(existing_stores, f, indent=2)
    logger.info(f"Saved merged data to {existing_file}")

    # Summary
    from collections import Counter
    state_counts = Counter(s.get('state', '').upper() for s in existing_stores)
    logger.info("\nFinal state counts for previously missing states:")
    for state_slug, state_name, state_abbr in MISSING_STATES:
        count = state_counts.get(state_abbr, 0)
        logger.info(f"  {state_abbr}: {count}")

    session.close()


if __name__ == '__main__':
    main()
