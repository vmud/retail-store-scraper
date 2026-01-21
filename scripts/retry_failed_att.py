#!/usr/bin/env python3
"""
Retry extraction for failed AT&T store URLs using HTML fallback parsing.
These stores don't have JSON-LD structured data, so we parse HTML directly.
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shared.utils import create_proxied_session, random_delay
from src.shared.proxy_client import ProxyMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def extract_store_from_html(soup: BeautifulSoup, url: str) -> Optional[dict]:
    """Extract store data from HTML when JSON-LD is not available."""
    try:
        # Extract state and store ID from URL: /stores/{state}/{city}/{id}
        url_parts = url.rstrip('/').split('/')
        store_id = url_parts[-1]
        url_state = url_parts[-3] if len(url_parts) >= 3 else ''

        # State abbreviation mapping from URL state names
        state_map = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
            'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
            'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
            'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
            'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
            'new-hampshire': 'NH', 'new-jersey': 'NJ', 'new-mexico': 'NM', 'new-york': 'NY',
            'north-carolina': 'NC', 'north-dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode-island': 'RI', 'south-carolina': 'SC',
            'south-dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
            'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west-virginia': 'WV',
            'wisconsin': 'WI', 'wyoming': 'WY', 'district-of-columbia': 'DC',
            'puerto-rico': 'PR', 'guam': 'GU', 'virgin-islands': 'VI'
        }
        state = state_map.get(url_state.lower(), url_state.upper()[:2])

        # Store name from h1
        h1 = soup.find('h1')
        if not h1:
            logging.warning(f"No h1 found for {url}")
            return None

        name_text = h1.get_text(separator=' ', strip=True)
        # Clean up name - remove duplicate city names
        name = re.sub(r'\s+', ' ', name_text).strip()

        # Address from <address> tag
        addr_elem = soup.find('address')
        if not addr_elem:
            logging.warning(f"No address found for {url}")
            return None

        addr_lines = [l.strip() for l in addr_elem.get_text().split('\n') if l.strip()]

        # Parse address components
        street_address = addr_lines[0] if addr_lines else ''

        # Handle suite/unit on second line
        suite = ''
        city_line_idx = 1
        if len(addr_lines) > 1 and ('suite' in addr_lines[1].lower() or
                                     'ste' in addr_lines[1].lower() or
                                     'unit' in addr_lines[1].lower() or
                                     '#' in addr_lines[1]):
            suite = addr_lines[1]
            street_address = f"{street_address}, {suite}"
            city_line_idx = 2

        # Parse city and zip from remaining lines
        city = ''
        zip_code = ''

        # Look for pattern: "City," on one line, state and zip separate
        remaining = addr_lines[city_line_idx:] if len(addr_lines) > city_line_idx else []

        for i, line in enumerate(remaining):
            line = line.rstrip(',')
            # Skip country codes
            if line.upper() in ('US', 'USA'):
                continue
            # Skip state abbreviations (we got it from URL)
            if re.match(r'^[A-Z]{2}$', line) and line.upper() != 'US':
                continue
            # Check if it's a zip code
            if re.match(r'^\d{5}(-\d{4})?$', line):
                zip_code = line
            # Otherwise it's likely the city
            elif not city:
                city = line

        # Phone from tel: link
        phone_link = soup.find('a', href=lambda x: x and x.startswith('tel:') if x else False)
        phone = ''
        if phone_link:
            phone = phone_link['href'].replace('tel:', '').replace('+1', '').strip()
            # Format phone
            phone = re.sub(r'[^\d]', '', phone)
            if len(phone) == 10:
                phone = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"

        # Hours - extract from hours section
        hours = {}
        hours_container = soup.find(class_=lambda x: x and 'hour' in x.lower() if x else False)
        if hours_container:
            # Try to find day/time pairs
            day_pattern = r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)'
            time_pattern = r'(\d{1,2}:\d{2}\s*(?:AM|PM))\s*-\s*(\d{1,2}:\d{2}\s*(?:AM|PM))'

            text = hours_container.get_text()
            for day_match in re.finditer(day_pattern, text, re.IGNORECASE):
                day = day_match.group(1).capitalize()
                # Look for time after day
                remaining_text = text[day_match.end():]
                time_match = re.search(time_pattern, remaining_text, re.IGNORECASE)
                if time_match:
                    hours[day] = f"{time_match.group(1)} - {time_match.group(2)}"

        # Build store object
        store = {
            'store_id': store_id,
            'name': name,
            'street_address': street_address,
            'city': city,
            'state': state,
            'zip_code': zip_code,
            'country': 'US',
            'phone': phone,
            'url': url,
            'hours': hours if hours else None,
            'latitude': None,
            'longitude': None,
            'extraction_method': 'html_fallback'
        }

        return store

    except Exception as e:
        logging.error(f"Error extracting from HTML for {url}: {e}")
        return None


def geocode_address(address: str, api_key: str = None) -> tuple:
    """
    Geocode an address to get lat/lng coordinates.
    Uses Nominatim (free) by default, or Google if API key provided.
    """
    if not address:
        return None, None

    try:
        # Use Nominatim (OpenStreetMap) - free, no API key needed
        base_url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': address,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'us'
        }
        headers = {'User-Agent': 'ATT-Store-Scraper/1.0'}

        resp = requests.get(base_url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        logging.debug(f"Geocoding failed for {address}: {e}")

    return None, None


def retry_failed_stores(
    failed_urls_file: str,
    output_file: str,
    proxy_mode: str = 'residential',
    geocode: bool = False,
    delay: float = 0.5
):
    """Retry extraction for failed store URLs."""

    # Load failed URLs
    with open(failed_urls_file) as f:
        urls = [line.strip() for line in f if line.strip()]

    logging.info(f"Loaded {len(urls)} failed URLs to retry")

    # Create session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })

    # If proxy mode specified, try to create proxied session
    if proxy_mode != 'direct':
        try:
            import yaml
            with open('config/retailers.yaml') as f:
                config = yaml.safe_load(f)
            retailer_config = config['retailers']['att']
            retailer_config['proxy'] = {'mode': proxy_mode}
            session = create_proxied_session(retailer_config)
            logging.info(f"Using {proxy_mode} proxy")
        except Exception as e:
            logging.warning(f"Could not create proxied session: {e}, using direct")

    stores = []
    still_failed = []

    for i, url in enumerate(urls, 1):
        try:
            logging.info(f"[{i}/{len(urls)}] Fetching {url}")

            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                logging.warning(f"HTTP {resp.status_code} for {url}")
                still_failed.append(url)
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Try JSON-LD first (in case it's now available)
            scripts = soup.find_all('script', type='application/ld+json')
            store = None

            for script in scripts:
                if script.string:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'LocalBusiness':
                            # Found JSON-LD - use standard extraction
                            store = {
                                'store_id': url.rstrip('/').split('/')[-1],
                                'name': data.get('name', ''),
                                'street_address': data.get('address', {}).get('streetAddress', ''),
                                'city': data.get('address', {}).get('addressLocality', ''),
                                'state': data.get('address', {}).get('addressRegion', ''),
                                'zip_code': data.get('address', {}).get('postalCode', ''),
                                'country': 'US',
                                'phone': data.get('telephone', ''),
                                'url': url,
                                'latitude': data.get('geo', {}).get('latitude'),
                                'longitude': data.get('geo', {}).get('longitude'),
                                'extraction_method': 'json_ld'
                            }
                            break
                    except json.JSONDecodeError:
                        continue

            # Fall back to HTML extraction
            if not store:
                store = extract_store_from_html(soup, url)

            if store:
                # Geocode if requested and no coordinates
                if geocode and not store.get('latitude'):
                    full_address = f"{store['street_address']}, {store['city']}, {store['state']} {store['zip_code']}"
                    lat, lng = geocode_address(full_address)
                    if lat and lng:
                        store['latitude'] = lat
                        store['longitude'] = lng
                        logging.info(f"  Geocoded: {lat}, {lng}")
                    time.sleep(1)  # Rate limit for Nominatim

                stores.append(store)
                logging.info(f"  Extracted: {store['name']} - {store['city']}, {store['state']}")
            else:
                still_failed.append(url)
                logging.warning(f"  Failed to extract data")

            time.sleep(delay)

        except Exception as e:
            logging.error(f"Error processing {url}: {e}")
            still_failed.append(url)

    # Save results
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(stores, f, indent=2)

    logging.info(f"\nResults:")
    logging.info(f"  Successfully extracted: {len(stores)}")
    logging.info(f"  Still failed: {len(still_failed)}")
    logging.info(f"  Output saved to: {output_file}")

    # Save still-failed URLs
    if still_failed:
        failed_output = output_path.parent / 'still_failed_urls.txt'
        with open(failed_output, 'w') as f:
            f.write('\n'.join(still_failed))
        logging.info(f"  Still-failed URLs saved to: {failed_output}")

    return stores, still_failed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Retry failed AT&T store extractions')
    parser.add_argument('--input', '-i', default='data/att/failed_urls_2026-01-20.txt',
                       help='File containing failed URLs')
    parser.add_argument('--output', '-o', default='data/att/output/retry_stores.json',
                       help='Output file for extracted stores')
    parser.add_argument('--proxy', '-p', default='direct', choices=['direct', 'residential'],
                       help='Proxy mode')
    parser.add_argument('--geocode', '-g', action='store_true',
                       help='Geocode addresses to get coordinates')
    parser.add_argument('--delay', '-d', type=float, default=0.5,
                       help='Delay between requests in seconds')

    args = parser.parse_args()

    retry_failed_stores(
        failed_urls_file=args.input,
        output_file=args.output,
        proxy_mode=args.proxy,
        geocode=args.geocode,
        delay=args.delay
    )
