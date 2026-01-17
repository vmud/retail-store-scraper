"""Core scraping functions for Verizon Store Locator"""

import json
import logging
import random
import re
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
import requests

from config import verizon_config as config
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

# Valid US state slugs (lowercase, hyphenated format)
# Note: District of Columbia uses "washington-dc" slug
VALID_STATE_SLUGS = {
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new-hampshire', 'new-jersey', 'new-mexico', 'new-york',
    'north-carolina', 'north-dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode-island', 'south-carolina', 'south-dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west-virginia', 'wisconsin', 'wyoming', 'washington-dc'
}

# Mapping from state slugs to proper state names
STATE_SLUG_TO_NAME = {
    'alabama': 'Alabama',
    'alaska': 'Alaska',
    'arizona': 'Arizona',
    'arkansas': 'Arkansas',
    'california': 'California',
    'colorado': 'Colorado',
    'connecticut': 'Connecticut',
    'delaware': 'Delaware',
    'florida': 'Florida',
    'georgia': 'Georgia',
    'hawaii': 'Hawaii',
    'idaho': 'Idaho',
    'illinois': 'Illinois',
    'indiana': 'Indiana',
    'iowa': 'Iowa',
    'kansas': 'Kansas',
    'kentucky': 'Kentucky',
    'louisiana': 'Louisiana',
    'maine': 'Maine',
    'maryland': 'Maryland',
    'massachusetts': 'Massachusetts',
    'michigan': 'Michigan',
    'minnesota': 'Minnesota',
    'mississippi': 'Mississippi',
    'missouri': 'Missouri',
    'montana': 'Montana',
    'nebraska': 'Nebraska',
    'nevada': 'Nevada',
    'new-hampshire': 'New Hampshire',
    'new-jersey': 'New Jersey',
    'new-mexico': 'New Mexico',
    'new-york': 'New York',
    'north-carolina': 'North Carolina',
    'north-dakota': 'North Dakota',
    'ohio': 'Ohio',
    'oklahoma': 'Oklahoma',
    'oregon': 'Oregon',
    'pennsylvania': 'Pennsylvania',
    'rhode-island': 'Rhode Island',
    'south-carolina': 'South Carolina',
    'south-dakota': 'South Dakota',
    'tennessee': 'Tennessee',
    'texas': 'Texas',
    'utah': 'Utah',
    'vermont': 'Vermont',
    'virginia': 'Virginia',
    'washington': 'Washington',
    'west-virginia': 'West Virginia',
    'wisconsin': 'Wisconsin',
    'wyoming': 'Wyoming',
    'washington-dc': 'District Of Columbia'
}

# Special URL patterns for states that don't follow the standard pattern
# North Carolina: /stores/north-carolina/ (missing "state" in path)
STATE_URL_PATTERNS = {
    'north-carolina': '/stores/north-carolina/',
    'washington-dc': '/stores/state/washington-dc/'
}


def _check_pause_logic() -> None:
    """Check if we need to pause based on request count"""
    count = _request_counter.count

    if count % config.PAUSE_200_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(config.PAUSE_200_MIN, config.PAUSE_200_MAX)
        logging.info(f"Long pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)
    elif count % config.PAUSE_50_REQUESTS == 0 and count > 0:
        pause_time = random.uniform(config.PAUSE_50_MIN, config.PAUSE_50_MAX)
        logging.info(f"Pause after {count} requests: {pause_time:.0f} seconds")
        time.sleep(pause_time)


def _scrape_states_from_html(session: requests.Session) -> List[Dict[str, str]]:
    """Scrape state URLs from the main stores page HTML.
    Returns empty list if scraping fails."""
    url = f"{config.BASE_URL}/stores/"
    logging.info(f"Fetching states from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning("Failed to fetch stores page for state scraping")
        return []

    _request_counter.increment()
    _check_pause_logic()

    soup = BeautifulSoup(response.text, 'html.parser')
    states = []
    seen_slugs = set()

    # Try to extract states from JavaScript/JSON data first (similar to cities extraction)
    scripts = soup.find_all('script')
    for script in scripts:
        script_content = script.string or ""
        if 'var statesJSON' in script_content or 'statesJSON' in script_content:
            try:
                json_match = re.search(r'statesJSON\s*=\s*({.+?});', script_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    states_data = json.loads(json_str)
                    if 'states' in states_data:
                        for state_data in states_data['states']:
                            state_slug = state_data.get('slug', '').lower()
                            state_name = state_data.get('name', '')
                            if state_slug and state_slug in VALID_STATE_SLUGS and state_slug not in seen_slugs:
                                # Use provided name or fall back to mapping
                                proper_name = state_name if state_name else STATE_SLUG_TO_NAME.get(state_slug, state_slug.title())
                                # Use special URL pattern if available, otherwise standard pattern
                                url_path = STATE_URL_PATTERNS.get(state_slug, f'/stores/state/{state_slug}/')
                                states.append({
                                    'name': proper_name,
                                    'url': f"{config.BASE_URL}{url_path}"
                                })
                                seen_slugs.add(state_slug)
                        if states:
                            logging.info(f"Extracted {len(states)} states from statesJSON")
                            break
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logging.debug(f"Failed to parse statesJSON: {e}")
                continue

    # Fallback: Parse HTML links if JSON extraction didn't work
    if not states:
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            # Match patterns: /stores/state/{slug}/ or /stores/{slug}/ (for North Carolina)
            if '/stores/state/' in href.lower() or (href.lower().startswith('/stores/') and href.count('/') == 3):
                # Extract state slug from URL
                parts = href.rstrip('/').split('/')
                if len(parts) >= 3:
                    # Check if it's /stores/state/{slug}/ pattern
                    if parts[-2] == 'state':
                        state_slug = parts[-1].lower()
                    # Check if it's /stores/{slug}/ pattern (North Carolina special case)
                    elif len(parts) == 3 and parts[1] == 'stores':
                        state_slug = parts[-1].lower()
                    else:
                        continue

                    # Validate against whitelist
                    if state_slug in VALID_STATE_SLUGS and state_slug not in seen_slugs:
                        state_name = STATE_SLUG_TO_NAME.get(state_slug, state_slug.title())
                        # Use special URL pattern if available, otherwise standard pattern
                        url_path = STATE_URL_PATTERNS.get(state_slug, f'/stores/state/{state_slug}/')
                        states.append({
                            'name': state_name,
                            'url': f"{config.BASE_URL}{url_path}"
                        })
                        seen_slugs.add(state_slug)

    # Deduplicate by slug
    unique_states = {}
    for state in states:
        slug = state['url'].rstrip('/').split('/')[-1].lower()
        if slug not in unique_states:
            unique_states[slug] = state

    result = list(unique_states.values())
    if result:
        logging.info(f"Scraped {len(result)} states from HTML")
    return result


def _generate_states_programmatically() -> List[Dict[str, str]]:
    """Generate state URLs programmatically from the standard list of US states."""
    # Standard list of US states (50 states + DC)
    # Note: Using "District Of Columbia" (capital O) as per state-slugs.md
    US_STATES = [
        'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
        'Connecticut', 'Delaware', 'District Of Columbia', 'Florida', 'Georgia',
        'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky',
        'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
        'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
        'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
        'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
        'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
        'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
        'West Virginia', 'Wisconsin', 'Wyoming'
    ]

    def state_name_to_slug(state_name: str) -> str:
        """Convert state name to URL slug format (lowercase with hyphens)"""
        return state_name.lower().replace(' ', '-')

    states = []
    for state_name in US_STATES:
        # Handle special case: District Of Columbia uses "washington-dc" slug
        if state_name == 'District Of Columbia':
            state_slug = 'washington-dc'
        else:
            state_slug = state_name_to_slug(state_name)

        # Use special URL pattern if available, otherwise standard pattern
        url_path = STATE_URL_PATTERNS.get(state_slug, f'/stores/state/{state_slug}/')
        states.append({
            'name': state_name,
            'url': f"{config.BASE_URL}{url_path}"
        })

    logging.info(f"Generated {len(states)} states programmatically")
    return states


def get_all_states(session: requests.Session) -> List[Dict[str, str]]:
    """Get all US state URLs by scraping from the main stores page.
    Falls back to programmatic generation if scraping fails."""

    # Try HTML scraping first
    states = _scrape_states_from_html(session)

    # Fallback to programmatic generation if scraping failed or found insufficient states
    if not states or len(states) < 50:
        if states:
            logging.warning(f"HTML scraping found only {len(states)} states, using programmatic generation")
        else:
            logging.warning("HTML scraping found no states, using programmatic generation")
        states = _generate_states_programmatically()

    return states


def get_cities_for_state(session: requests.Session, state_url: str, state_name: str) -> List[Dict[str, str]]:
    """Get all city URLs for a given state"""
    logging.info(f"Fetching cities for state: {state_name}")

    response = utils.get_with_retry(session, state_url)
    if not response:
        logging.warning(f"Failed to fetch cities for state: {state_name}")
        return []

    _request_counter.increment()
    _check_pause_logic()

    # Extract state slug from URL (e.g., "new-jersey" from "/stores/state/new-jersey/")
    state_slug = state_url.rstrip('/').split('/')[-1].lower()

    soup = BeautifulSoup(response.text, 'html.parser')
    cities = []
    seen_cities = set()

    # Try to extract cities from stateJSON JavaScript variable first
    # The page embeds city data in: var stateJSON = {"state":{...},"cities":[...]}
    scripts = soup.find_all('script')
    for script in scripts:
        script_content = script.string or ""
        if 'var stateJSON' in script_content or 'stateJSON' in script_content:
            # Extract JSON from JavaScript variable
            try:
                # Find the JSON part (between = and ; or just the JSON object)
                # Match: var stateJSON = {...}; or stateJSON = {...};
                json_match = re.search(r'stateJSON\s*=\s*({.+?});', script_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    state_data = json.loads(json_str)
                    if 'cities' in state_data:
                        for city_data in state_data['cities']:
                            city_name = city_data.get('name', '')
                            city_url_path = city_data.get('url', '')
                            if city_name and city_url_path and city_name not in seen_cities:
                                city_url = f"{config.BASE_URL}{city_url_path}" if city_url_path.startswith('/') else city_url_path
                                cities.append({
                                    'city': city_name,
                                    'state': state_name,
                                    'url': city_url
                                })
                                seen_cities.add(city_name)
                        logging.info(f"Extracted {len(cities)} cities from stateJSON")
                        break
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logging.debug(f"Failed to parse stateJSON: {e}")
                continue

    # Fallback: if no cities found from stateJSON, try parsing HTML links
    if not cities:
        all_links = soup.find_all('a', href=True)
        state_slug = state_url.rstrip('/').split('/')[-1].lower()

        for link in all_links:
            href = link.get('href', '')
            # City URLs can be in format: /stores/{state-slug}/{city}/ or /stores/city/{city}/
            if f'/stores/{state_slug}/' in href.lower() or '/stores/city/' in href.lower():
                # Skip if it's a state page or detail page
                if '/stores/state/' in href.lower() or '/stores/details/' in href.lower():
                    continue

                city_name = href.rstrip('/').split('/')[-1]
                # Skip if empty or looks like a state slug
                if not city_name or city_name in ['stores', 'city', 'state', 'details', state_slug]:
                    continue

                if city_name not in seen_cities:
                    city_url = f"{config.BASE_URL}{href}" if href.startswith('/') else href
                    cities.append({
                        'city': city_name,
                        'state': state_name,
                        'url': city_url
                    })
                    seen_cities.add(city_name)

    # Deduplicate by city
    unique_cities = {}
    for city in cities:
        city_key = (city['city'], city['state'])
        if city_key not in unique_cities:
            unique_cities[city_key] = city

    result = list(unique_cities.values())
    logging.info(f"Found {len(result)} cities for {state_name}")
    return result


def get_stores_for_city(session: requests.Session, city_url: str, city_name: str, state_name: str) -> List[Dict[str, str]]:
    """Get all store URLs for a given city"""
    logging.info(f"Fetching stores for {city_name}, {state_name}")

    response = utils.get_with_retry(session, city_url)
    if not response:
        logging.warning(f"Failed to fetch stores for {city_name}, {state_name}")
        return []

    _request_counter.increment()
    _check_pause_logic()

    soup = BeautifulSoup(response.text, 'html.parser')
    stores = []
    seen_urls = set()

    # Try to extract stores from cityJSON JavaScript variable first
    # The page embeds store data in: var cityJSON = {"city":{...},"stores":[...]}
    scripts = soup.find_all('script')
    for script in scripts:
        script_content = script.string or ""
        if 'var cityJSON' in script_content or 'cityJSON' in script_content:
            # Extract JSON from JavaScript variable
            try:
                # Match: var cityJSON = {...}; or cityJSON = {...};
                json_match = re.search(r'cityJSON\s*=\s*({.+?});', script_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    city_data = json.loads(json_str)
                    if 'stores' in city_data:
                        for store_data in city_data['stores']:
                            store_url_path = store_data.get('storeUrl', '')
                            if store_url_path:
                                store_url = f"{config.BASE_URL}{store_url_path}" if store_url_path.startswith('/') else store_url_path
                                if store_url not in seen_urls:
                                    stores.append({
                                        'city': city_name,
                                        'state': state_name,
                                        'url': store_url
                                    })
                                    seen_urls.add(store_url)
                        logging.info(f"Extracted {len(stores)} stores from cityJSON")
                        break
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logging.debug(f"Failed to parse cityJSON: {e}")
                continue

    # Fallback: if no stores found from cityJSON, try parsing HTML links
    if not stores:
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            # Store detail URLs can be in format: /stores/{state}/{city}/{store-name}/ or /stores/details/...
            if '/stores/details/' in href or (href.startswith('/stores/') and '/stores/' in href[8:]):
                store_url = f"{config.BASE_URL}{href}" if href.startswith('/') else href
                if store_url not in seen_urls:
                    stores.append({
                        'city': city_name,
                        'state': state_name,
                        'url': store_url
                    })
                    seen_urls.add(store_url)

    # Deduplicate by URL
    unique_stores = {}
    for store in stores:
        if store['url'] not in unique_stores:
            unique_stores[store['url']] = store

    result = list(unique_stores.values())
    logging.info(f"Found {len(result)} stores for {city_name}, {state_name}")
    return result


def _validate_store_data(store_data: Dict[str, Any], store_url: str) -> bool:
    """Validate that store data has required fields and valid format"""
    issues = []

    # Required fields: name, city, state, and at least one of street_address or coordinates
    if not store_data.get('name') or not store_data.get('name').strip():
        issues.append("missing or empty name")

    if not store_data.get('city') or not store_data.get('city').strip():
        issues.append("missing or empty city")

    if not store_data.get('state') or not store_data.get('state').strip():
        issues.append("missing or empty state")

    # At least address or coordinates should be present
    has_address = store_data.get('street_address') and store_data.get('street_address').strip()
    has_coords = (store_data.get('latitude') and store_data.get('longitude'))

    if not has_address and not has_coords:
        issues.append("missing both street address and coordinates")

    # Validate coordinates if present
    lat = store_data.get('latitude')
    lon = store_data.get('longitude')

    if lat:
        try:
            lat_float = float(lat) if isinstance(lat, str) else lat
            if not (-90 <= lat_float <= 90):
                issues.append(f"latitude out of range: {lat_float}")
        except (ValueError, TypeError):
            issues.append(f"invalid latitude format: {lat}")

    if lon:
        try:
            lon_float = float(lon) if isinstance(lon, str) else lon
            if not (-180 <= lon_float <= 180):
                issues.append(f"longitude out of range: {lon_float}")
        except (ValueError, TypeError):
            issues.append(f"invalid longitude format: {lon}")

    if issues:
        logging.warning(f"Store data validation failed for {store_url}: {', '.join(issues)}")
        return False

    return True


def extract_store_details(session: requests.Session, store_url: str) -> Optional[Dict[str, Any]]:
    """Extract structured store data from JSON-LD on store detail page"""
    logging.debug(f"Extracting details from {store_url}")

    response = utils.get_with_retry(session, store_url)
    if not response:
        logging.warning(f"Failed to fetch store details: {store_url}")
        return None

    _request_counter.increment()
    _check_pause_logic()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find JSON-LD script tag
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if data.get('@type') == 'Store':
                # Extract address components
                address = data.get('address', {})
                geo = data.get('geo', {})

                result = {
                    'name': data.get('name', ''),
                    'street_address': address.get('streetAddress', ''),
                    'city': address.get('addressLocality', ''),
                    'state': address.get('addressRegion', ''),
                    'zip': address.get('postalCode', ''),
                    'country': address.get('addressCountry', 'US'),
                    'latitude': geo.get('latitude', ''),
                    'longitude': geo.get('longitude', ''),
                    'phone': data.get('telephone', ''),
                    'url': store_url,
                    'scraped_at': datetime.now().isoformat()
                }

                # Validate the extracted data
                if _validate_store_data(result, store_url):
                    logging.debug(f"Extracted store: {result.get('name', 'Unknown')}")
                    return result
                else:
                    logging.warning(f"Skipping store due to validation failure: {store_url}")
                    return None

        except json.JSONDecodeError as e:
            logging.warning(f"JSON decode error for {store_url}: {e}")
            continue
        except Exception as e:
            logging.warning(f"Error parsing JSON-LD for {store_url}: {e}")
            continue

    logging.warning(f"No JSON-LD Store data found for {store_url}")
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
    limit = kwargs.get('limit')
    resume = kwargs.get('resume', False)
    
    reset_request_counter()
    
    retailer_name = kwargs.get('retailer', 'verizon')
    checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
    # Verizon uses smaller interval (10) due to slower multi-phase crawl
    checkpoint_interval = config.get('checkpoint_interval', 10)
    
    stores = []
    completed_urls = set()
    checkpoints_used = False
    
    if resume:
        checkpoint = utils.load_checkpoint(checkpoint_path)
        if checkpoint:
            stores = checkpoint.get('stores', [])
            completed_urls = set(checkpoint.get('completed_urls', []))
            logging.info(f"Resuming from checkpoint: {len(stores)} stores already collected")
            checkpoints_used = True
    
    all_states = get_all_states(session)
    
    all_store_urls = []
    for state in all_states:
        cities = get_cities_for_state(session, state['url'], state['name'])
        for city in cities:
            store_infos = get_stores_for_city(session, city['url'], city['city'], city['state'])
            all_store_urls.extend([s['url'] for s in store_infos])
    
    remaining_urls = [url for url in all_store_urls if url not in completed_urls]
    
    if limit:
        total_needed = limit - len(stores)
        if total_needed > 0:
            remaining_urls = remaining_urls[:total_needed]
        else:
            remaining_urls = []
    
    for i, url in enumerate(remaining_urls):
        store_data = extract_store_details(session, url)
        if store_data:
            stores.append(store_data)
            completed_urls.add(url)
        
        if (i + 1) % checkpoint_interval == 0:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_urls': list(completed_urls),
                'stores': stores,
                'last_updated': datetime.now().isoformat()
            }, checkpoint_path)
            logging.info(f"Checkpoint saved: {len(stores)} stores processed")
    
    if stores:
        utils.save_checkpoint({
            'completed_count': len(stores),
            'completed_urls': list(completed_urls),
            'stores': stores,
            'last_updated': datetime.now().isoformat()
        }, checkpoint_path)
        logging.info(f"Final checkpoint saved: {len(stores)} stores total")
    
    return {
        'stores': stores,
        'count': len(stores),
        'checkpoints_used': checkpoints_used
    }
