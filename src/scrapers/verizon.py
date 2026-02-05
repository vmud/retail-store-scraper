# pylint: disable=too-many-lines
"""Core scraping functions for Verizon Store Locator"""

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Set, Tuple
from bs4 import BeautifulSoup
import requests

from config import verizon_config as config
from src.shared import utils
from src.shared.cache import URLCache
from src.shared.constants import WORKERS
from src.shared.request_counter import RequestCounter, check_pause_logic
from src.shared.session_factory import create_session_factory


# Global request counter
_request_counter = RequestCounter()


# =============================================================================
# STATE CONFIGURATION - Single Source of Truth (#101)
# =============================================================================

@dataclass(frozen=True)
class StateConfig:
    """Configuration for a US state in the Verizon store locator."""
    slug: str
    name: str
    url_pattern: Optional[str] = None  # Custom URL pattern if different from standard


# Single source of truth for all US states
# States with custom URL patterns have them specified here
_STATES: Dict[str, StateConfig] = {
    'alabama': StateConfig('alabama', 'Alabama'),
    'alaska': StateConfig('alaska', 'Alaska'),
    'arizona': StateConfig('arizona', 'Arizona'),
    'arkansas': StateConfig('arkansas', 'Arkansas'),
    'california': StateConfig('california', 'California'),
    'colorado': StateConfig('colorado', 'Colorado'),
    'connecticut': StateConfig('connecticut', 'Connecticut'),
    'delaware': StateConfig('delaware', 'Delaware'),
    'florida': StateConfig('florida', 'Florida'),
    'georgia': StateConfig('georgia', 'Georgia'),
    'hawaii': StateConfig('hawaii', 'Hawaii'),
    'idaho': StateConfig('idaho', 'Idaho'),
    'illinois': StateConfig('illinois', 'Illinois'),
    'indiana': StateConfig('indiana', 'Indiana'),
    'iowa': StateConfig('iowa', 'Iowa'),
    'kansas': StateConfig('kansas', 'Kansas'),
    'kentucky': StateConfig('kentucky', 'Kentucky'),
    'louisiana': StateConfig('louisiana', 'Louisiana'),
    'maine': StateConfig('maine', 'Maine'),
    'maryland': StateConfig('maryland', 'Maryland'),
    'massachusetts': StateConfig('massachusetts', 'Massachusetts'),
    'michigan': StateConfig('michigan', 'Michigan'),
    'minnesota': StateConfig('minnesota', 'Minnesota'),
    'mississippi': StateConfig('mississippi', 'Mississippi'),
    'missouri': StateConfig('missouri', 'Missouri'),
    'montana': StateConfig('montana', 'Montana'),
    'nebraska': StateConfig('nebraska', 'Nebraska'),
    'nevada': StateConfig('nevada', 'Nevada'),
    'new-hampshire': StateConfig('new-hampshire', 'New Hampshire'),
    'new-jersey': StateConfig('new-jersey', 'New Jersey'),
    'new-mexico': StateConfig('new-mexico', 'New Mexico'),
    'new-york': StateConfig('new-york', 'New York'),
    # North Carolina: /stores/north-carolina/ (missing "state" in path)
    'north-carolina': StateConfig('north-carolina', 'North Carolina', '/stores/north-carolina/'),
    'north-dakota': StateConfig('north-dakota', 'North Dakota'),
    'ohio': StateConfig('ohio', 'Ohio'),
    'oklahoma': StateConfig('oklahoma', 'Oklahoma'),
    'oregon': StateConfig('oregon', 'Oregon'),
    'pennsylvania': StateConfig('pennsylvania', 'Pennsylvania'),
    'rhode-island': StateConfig('rhode-island', 'Rhode Island'),
    'south-carolina': StateConfig('south-carolina', 'South Carolina'),
    'south-dakota': StateConfig('south-dakota', 'South Dakota'),
    'tennessee': StateConfig('tennessee', 'Tennessee'),
    'texas': StateConfig('texas', 'Texas'),
    'utah': StateConfig('utah', 'Utah'),
    'vermont': StateConfig('vermont', 'Vermont'),
    'virginia': StateConfig('virginia', 'Virginia'),
    'washington': StateConfig('washington', 'Washington'),
    # Washington DC: uses "washington-dc" slug
    'washington-dc': StateConfig('washington-dc', 'District Of Columbia', '/stores/state/washington-dc/'),
    'west-virginia': StateConfig('west-virginia', 'West Virginia'),
    'wisconsin': StateConfig('wisconsin', 'Wisconsin'),
    'wyoming': StateConfig('wyoming', 'Wyoming'),
}

# Derived views for backwards compatibility and fast lookups
VALID_STATE_SLUGS: Set[str] = set(_STATES.keys())
STATE_SLUG_TO_NAME: Dict[str, str] = {s.slug: s.name for s in _STATES.values()}
STATE_URL_PATTERNS: Dict[str, str] = {
    s.slug: s.url_pattern for s in _STATES.values() if s.url_pattern
}

# State abbreviation to slug mapping for --states CLI flag
STATE_ABBREV_TO_SLUG: Dict[str, str] = {
    'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas',
    'CA': 'california', 'CO': 'colorado', 'CT': 'connecticut', 'DE': 'delaware',
    'DC': 'washington-dc', 'FL': 'florida', 'GA': 'georgia', 'HI': 'hawaii',
    'ID': 'idaho', 'IL': 'illinois', 'IN': 'indiana', 'IA': 'iowa',
    'KS': 'kansas', 'KY': 'kentucky', 'LA': 'louisiana', 'ME': 'maine',
    'MD': 'maryland', 'MA': 'massachusetts', 'MI': 'michigan', 'MN': 'minnesota',
    'MS': 'mississippi', 'MO': 'missouri', 'MT': 'montana', 'NE': 'nebraska',
    'NV': 'nevada', 'NH': 'new-hampshire', 'NJ': 'new-jersey', 'NM': 'new-mexico',
    'NY': 'new-york', 'NC': 'north-carolina', 'ND': 'north-dakota', 'OH': 'ohio',
    'OK': 'oklahoma', 'OR': 'oregon', 'PA': 'pennsylvania', 'RI': 'rhode-island',
    'SC': 'south-carolina', 'SD': 'south-dakota', 'TN': 'tennessee', 'TX': 'texas',
    'UT': 'utah', 'VT': 'vermont', 'VA': 'virginia', 'WA': 'washington',
    'WV': 'west-virginia', 'WI': 'wisconsin', 'WY': 'wyoming'
}


def get_state_url(slug: str) -> str:
    """Get URL path for a state.

    Args:
        slug: State slug (lowercase, hyphenated)

    Returns:
        URL path for the state (e.g., '/stores/state/california/')
    """
    state = _STATES.get(slug)
    if state and state.url_pattern:
        return state.url_pattern
    return f"/stores/state/{slug}/"


def _scrape_states_from_html(session: requests.Session, yaml_config: dict = None, retailer: str = 'verizon') -> List[Dict[str, str]]:
    """Scrape state URLs from the main stores page HTML.
    Returns empty list if scraping fails.

    Args:
        session: Requests session object
        yaml_config: Retailer configuration dict from retailers.yaml (optional)
        retailer: Retailer name for logging
    """
    url = f"{config.BASE_URL}/stores/"
    logging.info(f"[{retailer}] Fetching states from {url}")

    response = utils.get_with_retry(session, url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch stores page for state scraping")
        return []

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

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
                            logging.info(f"[{retailer}] Extracted {len(states)} states from statesJSON")
                            break
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logging.debug(f"[{retailer}] Failed to parse statesJSON: {e}")
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
        logging.info(f"[{retailer}] Scraped {len(result)} states from HTML")
    return result


def _generate_states_programmatically(retailer: str = 'verizon') -> List[Dict[str, str]]:
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

    logging.info(f"[{retailer}] Generated {len(states)} states programmatically")
    return states


def get_all_states(session: requests.Session, yaml_config: dict = None, retailer: str = 'verizon') -> List[Dict[str, str]]:
    """Get all US state URLs by scraping from the main stores page.
    Falls back to programmatic generation if scraping fails.

    Args:
        session: Requests session object
        yaml_config: Retailer configuration dict from retailers.yaml (optional)
        retailer: Retailer name for logging
    """

    # Try HTML scraping first
    states = _scrape_states_from_html(session, yaml_config, retailer)

    # Fallback to programmatic generation if scraping failed or found insufficient states
    if not states or len(states) < 50:
        if states:
            logging.warning(f"[{retailer}] HTML scraping found only {len(states)} states, using programmatic generation")
        else:
            logging.warning(f"[{retailer}] HTML scraping found no states, using programmatic generation")
        states = _generate_states_programmatically(retailer)

    return states


def get_cities_for_state(session: requests.Session, state_url: str, state_name: str, yaml_config: dict = None, retailer: str = 'verizon') -> List[Dict[str, str]]:
    """Get all city URLs for a given state

    Args:
        session: Requests session object
        state_url: URL of the state page
        state_name: Name of the state
        yaml_config: Retailer configuration dict from retailers.yaml (optional)
        retailer: Retailer name for logging
    """
    logging.info(f"[{retailer}] Fetching cities for state: {state_name}")

    response = utils.get_with_retry(session, state_url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch cities for state: {state_name}")
        return []

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

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

                    # Validate that returned data matches expected state (prevents race condition)
                    json_state_name = state_data.get('state', {}).get('name', '')
                    if json_state_name and json_state_name.lower() != state_name.lower():
                        logging.warning(
                            f"[{retailer}] State mismatch for {state_name}: "
                            f"page returned '{json_state_name}' data. Skipping."
                        )
                        continue

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
                        logging.info(f"[{retailer}] Extracted {len(cities)} cities from stateJSON")
                        break
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logging.debug(f"[{retailer}] Failed to parse stateJSON: {e}")
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
    logging.info(f"[{retailer}] Found {len(result)} cities for {state_name}")
    return result


def get_stores_for_city(session: requests.Session, city_url: str, city_name: str, state_name: str, yaml_config: dict = None, retailer: str = 'verizon') -> List[Dict[str, str]]:
    """Get all store URLs for a given city

    Args:
        session: Requests session object
        city_url: URL of the city page
        city_name: Name of the city
        state_name: Name of the state
        yaml_config: Retailer configuration dict from retailers.yaml (optional)
        retailer: Retailer name for logging
    """
    logging.info(f"[{retailer}] Fetching stores for {city_name}, {state_name}")

    response = utils.get_with_retry(session, city_url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch stores for {city_name}, {state_name}")
        return []

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

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
                        logging.info(f"[{retailer}] Extracted {len(stores)} stores from cityJSON")
                        break
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logging.debug(f"[{retailer}] Failed to parse cityJSON: {e}")
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
    logging.info(f"[{retailer}] Found {len(result)} stores for {city_name}, {state_name}")
    return result


def parse_url_components(url: str) -> Dict[str, Optional[str]]:
    """
    Parse all components from Verizon store URL slug into discrete fields.

    Args:
        url: Store URL (e.g., 'https://www.verizon.com/stores/alabama/victra-arab-1402922/')

    Returns:
        Dictionary with keys:
            - sub_channel: "COR", "Dealer", or "Retail"
            - dealer_name: Dealer name or None
            - store_location: Location name from slug
            - retailer_store_number: Store number (Best Buy) or None
            - verizon_uid: Verizon unique identifier

    Examples:
        'cellular-sales-albertville-1407222' →
            {'sub_channel': 'Dealer', 'dealer_name': 'Cellular Sales',
             'store_location': 'albertville', 'retailer_store_number': None,
             'verizon_uid': '1407222'}

        'best-buy-0793-dothan-n00000360018' →
            {'sub_channel': 'Retail', 'dealer_name': 'Best Buy',
             'store_location': 'dothan', 'retailer_store_number': '0793',
             'verizon_uid': 'n00000360018'}

        'alabaster-1135614' →
            {'sub_channel': 'COR', 'dealer_name': None,
             'store_location': 'alabaster', 'retailer_store_number': None,
             'verizon_uid': '1135614'}
    """
    # Extract slug from URL (last path component)
    slug = url.rstrip('/').split('/')[-1]
    parts = slug.split('-')

    # Dealer patterns: (prefix_parts, display_name, sub_channel)
    # Order matters - check multi-word prefixes first
    dealer_patterns = [
        (['best', 'buy'], 'Best Buy', 'Retail'),
        (['cellular', 'sales'], 'Cellular Sales', 'Dealer'),
        (['russell', 'cellular'], 'Russell Cellular', 'Dealer'),
        (['wireless', 'zone'], 'Wireless Zone', 'Dealer'),
        (['wireless', 'world'], 'Wireless World', 'Dealer'),
        (['wireless', 'vision'], 'Wireless Vision', 'Dealer'),
        (['diamond', 'wireless'], 'Diamond Wireless', 'Dealer'),
        (['cellular', 'connection'], 'Cellular Connection', 'Dealer'),
        (['arch', 'telecom'], 'Arch Telecom', 'Dealer'),
        (['a', 'wireless'], 'A Wireless', 'Dealer'),
        (['victra'], 'Victra', 'Dealer'),
        (['tcc'], 'TCC', 'Dealer'),
        (['gowireless'], 'GoWireless', 'Dealer'),
    ]

    # Check each dealer pattern
    for prefix_parts, dealer_name, sub_channel in dealer_patterns:
        if parts[:len(prefix_parts)] == prefix_parts:
            # Dealer pattern matched
            remaining = parts[len(prefix_parts):]

            # Special handling for Best Buy (has store number as first element after prefix)
            if dealer_name == 'Best Buy':
                if len(remaining) >= 3:
                    store_number = remaining[0]
                    verizon_uid = remaining[-1]
                    location = '-'.join(remaining[1:-1])
                    return {
                        'sub_channel': sub_channel,
                        'dealer_name': dealer_name,
                        'store_location': location,
                        'retailer_store_number': store_number,
                        'verizon_uid': verizon_uid
                    }
                else:
                    # Best Buy URL with insufficient parts - malformed
                    logging.warning(f"[verizon] Best Buy URL has insufficient parts: {url}")
                    return {
                        'sub_channel': sub_channel,
                        'dealer_name': dealer_name,
                        'store_location': '-'.join(remaining) if remaining else slug,
                        'retailer_store_number': None,
                        'verizon_uid': remaining[-1] if remaining else ''
                    }

            # Other dealers: no store number, format is {dealer}-{location}-{uid}
            if len(remaining) >= 2:
                verizon_uid = remaining[-1]
                location = '-'.join(remaining[:-1])
                return {
                    'sub_channel': sub_channel,
                    'dealer_name': dealer_name,
                    'store_location': location,
                    'retailer_store_number': None,
                    'verizon_uid': verizon_uid
                }
            else:
                # Dealer URL with insufficient parts - malformed
                logging.warning(f"[verizon] Dealer URL has insufficient parts: {url}")
                return {
                    'sub_channel': sub_channel,
                    'dealer_name': dealer_name,
                    'store_location': '-'.join(remaining) if remaining else slug,
                    'retailer_store_number': None,
                    'verizon_uid': remaining[0] if len(remaining) == 1 else ''
                }

    # No dealer prefix found - COR store
    # Format: {location}-{uid}
    if len(parts) >= 2:
        verizon_uid = parts[-1]
        location = '-'.join(parts[:-1])
        return {
            'sub_channel': 'COR',
            'dealer_name': None,
            'store_location': location,
            'retailer_store_number': None,
            'verizon_uid': verizon_uid
        }

    # Fallback for unexpected format (shouldn't happen with real data)
    logging.warning(f"[verizon] Unexpected URL format, cannot parse components: {url}")
    return {
        'sub_channel': 'COR',
        'dealer_name': None,
        'store_location': slug,
        'retailer_store_number': None,
        'verizon_uid': ''
    }


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
        logging.warning(f"[verizon] Store data validation failed for {store_url}: {', '.join(issues)}")
        return False

    return True


def extract_store_details(session: requests.Session, store_url: str, yaml_config: dict = None, retailer: str = 'verizon') -> Optional[Dict[str, Any]]:
    """Extract structured store data from JSON-LD on store detail page

    Args:
        session: Requests session object
        store_url: URL of the store page
        yaml_config: Retailer configuration dict from retailers.yaml (optional)
        retailer: Retailer name for logging
    """
    logging.debug(f"[{retailer}] Extracting details from {store_url}")

    response = utils.get_with_retry(session, store_url)
    if not response:
        logging.warning(f"[{retailer}] Failed to fetch store details: {store_url}")
        return None

    _request_counter.increment()
    check_pause_logic(_request_counter, retailer=retailer, config=yaml_config)

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

                # Parse URL components (sub-channel, dealer name, location, store number, UID)
                url_components = parse_url_components(store_url)
                result.update(url_components)

                # Validate the extracted data
                if _validate_store_data(result, store_url):
                    logging.debug(f"[{retailer}] Extracted store: {result.get('name', 'Unknown')}")
                    return result
                else:
                    logging.warning(f"[{retailer}] Skipping store due to validation failure: {store_url}")
                    return None

        except json.JSONDecodeError as e:
            logging.warning(f"[{retailer}] JSON decode error for {store_url}: {e}")
            continue
        except Exception as e:
            logging.warning(f"[{retailer}] Error parsing JSON-LD for {store_url}: {e}")
            continue

    logging.warning(f"[{retailer}] No JSON-LD Store data found for {store_url}")
    return None


def reset_request_counter() -> None:
    """Reset the global request counter"""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count


# =============================================================================
# PARALLEL DISCOVERY - Speed up city and store URL discovery (Phases 2-3)
# =============================================================================


def _fetch_cities_for_state_worker(
    state: Dict[str, str],
    session_factory,
    yaml_config: dict,
    retailer_name: str
) -> Tuple[str, List[Dict[str, str]]]:
    """Worker function for parallel city discovery.

    Fetches all cities for a single state. Each worker creates its own
    session instance for thread safety.

    Args:
        state: Dict with 'name' and 'url' keys
        session_factory: Callable that creates session instances
        yaml_config: Retailer configuration
        retailer_name: Name of retailer for logging

    Returns:
        Tuple of (state_name, list_of_cities)
    """
    session = session_factory()
    try:
        cities = get_cities_for_state(
            session,
            state['url'],
            state['name'],
            yaml_config,
            retailer_name
        )
        return (state['name'], cities)
    except Exception as e:
        logging.warning(f"[{retailer_name}] Error fetching cities for {state['name']}: {e}")
        return (state['name'], [])
    finally:
        # Clean up session resources
        if hasattr(session, 'close'):
            session.close()


def _fetch_stores_for_city_worker(
    city: Dict[str, str],
    session_factory,
    yaml_config: dict,
    retailer_name: str
) -> Tuple[str, str, List[str]]:
    """Worker function for parallel store URL discovery.

    Fetches all store URLs for a single city. Each worker creates its own
    session instance for thread safety.

    Args:
        city: Dict with 'city', 'state', and 'url' keys
        session_factory: Callable that creates session instances
        yaml_config: Retailer configuration
        retailer_name: Name of retailer for logging

    Returns:
        Tuple of (city_name, state_name, list_of_store_urls)
    """
    session = session_factory()
    try:
        store_infos = get_stores_for_city(
            session,
            city['url'],
            city['city'],
            city['state'],
            yaml_config,
            retailer_name
        )
        store_urls = [s['url'] for s in store_infos]
        return (city['city'], city['state'], store_urls)
    except Exception as e:
        logging.warning(f"[{retailer_name}] Error fetching stores for {city['city']}, {city['state']}: {e}")
        return (city['city'], city['state'], [])
    finally:
        # Clean up session resources
        if hasattr(session, 'close'):
            session.close()


# =============================================================================
# =============================================================================
# PARALLEL EXTRACTION - Speed up store detail extraction
# =============================================================================


def _extract_single_store(
    url: str,
    session,
    yaml_config: dict,
    retailer_name: str
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Worker function for parallel store extraction.

    Args:
        url: Store URL to extract
        session: Session to use for requests
        yaml_config: Retailer configuration
        retailer_name: Name of retailer for logging

    Returns:
        Tuple of (url, store_data) where store_data is None on failure
    """
    try:
        store_data = extract_store_details(session, url, yaml_config, retailer_name)
        return (url, store_data)
    except Exception as e:
        logging.warning(f"[{retailer_name}] Error extracting {url}: {e}")
        return (url, None)


# Discovery checkpoint filename (centralized to avoid duplication)
_DISCOVERY_CHECKPOINT_FILENAME = "discovery_checkpoint.json"


def _get_discovery_checkpoint_path(retailer: str) -> str:
    """Get the path to the discovery checkpoint file.

    Args:
        retailer: Retailer name (used for path)

    Returns:
        Path string to the discovery checkpoint file
    """
    return f"data/{retailer}/checkpoints/{_DISCOVERY_CHECKPOINT_FILENAME}"


def save_discovery_checkpoint(retailer: str, checkpoint_data: dict) -> None:
    """Save discovery phase progress.

    Args:
        retailer: Retailer name (used for path)
        checkpoint_data: Dictionary with discovery progress data
    """
    checkpoint_path = _get_discovery_checkpoint_path(retailer)
    utils.save_checkpoint(checkpoint_data, checkpoint_path)


def load_discovery_checkpoint(retailer: str) -> Optional[dict]:
    """Load discovery phase progress if resuming.

    Args:
        retailer: Retailer name (used for path)

    Returns:
        Dictionary with discovery progress, or None if no checkpoint exists
    """
    checkpoint_path = _get_discovery_checkpoint_path(retailer)
    return utils.load_checkpoint(checkpoint_path)


def clear_discovery_checkpoint(retailer: str) -> None:
    """Clear discovery checkpoint after successful completion.

    Args:
        retailer: Retailer name (used for path)
    """
    checkpoint_path = Path(_get_discovery_checkpoint_path(retailer))
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        logging.info(f"[{retailer}] Cleared discovery checkpoint")


def run(session, config: dict, **kwargs) -> dict:
    """Standard scraper entry point with parallel extraction and URL caching.

    Args:
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - resume: bool - Resume from checkpoint
            - limit: int - Max stores to process
            - incremental: bool - Only process changes
            - refresh_urls: bool - Force URL re-discovery (ignore cache)
            - target_states: List[str] - State abbreviations to scrape (e.g., ['MD', 'PA', 'RI'])

    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
    retailer_name = kwargs.get('retailer', 'verizon')
    logging.info(f"[{retailer_name}] Starting scrape run")

    try:
        limit = kwargs.get('limit')
        resume = kwargs.get('resume', False)
        refresh_urls = kwargs.get('refresh_urls', False)
        target_states = kwargs.get('target_states')  # List of state abbreviations like ['MD', 'PA']

        # Targeted states mode: load existing stores for merge
        existing_stores = []
        existing_urls = set()
        if target_states:
            # Convert abbreviations to slugs and validate
            target_slugs = []
            for abbrev in target_states:
                slug = STATE_ABBREV_TO_SLUG.get(abbrev.upper())
                if slug:
                    target_slugs.append(slug)
                else:
                    logging.warning(f"[{retailer_name}] Unknown state abbreviation: {abbrev}")

            if not target_slugs:
                logging.error(f"[{retailer_name}] No valid state abbreviations provided")
                return {'stores': [], 'count': 0, 'checkpoints_used': False}

            logging.info(f"[{retailer_name}] Targeted states mode: {target_states} -> {target_slugs}")

            # Load existing stores for merge
            output_path = Path(f"data/{retailer_name}/output/stores_latest.json")
            if output_path.exists():
                with open(output_path, 'r') as f:
                    existing_stores = json.load(f)
                existing_urls = {s.get('url') for s in existing_stores if s.get('url')}
                logging.info(f"[{retailer_name}] Loaded {len(existing_stores)} existing stores for merge")

            # Store target slugs for later filtering
            kwargs['_target_slugs'] = target_slugs

        reset_request_counter()

        # Auto-select delays based on proxy mode for optimal performance
        proxy_mode = config.get('proxy', {}).get('mode', 'direct')
        min_delay, max_delay = utils.select_delays(config, proxy_mode)
        logging.info(f"[{retailer_name}] Using delays: {min_delay:.1f}-{max_delay:.1f}s (mode: {proxy_mode})")

        # Get parallel workers count (default: WORKERS.PROXIED_WORKERS for residential proxy, WORKERS.DIRECT_WORKERS for direct)
        default_workers = WORKERS.PROXIED_WORKERS if proxy_mode in ('residential', 'web_scraper_api') else WORKERS.DIRECT_WORKERS
        parallel_workers = config.get('parallel_workers', default_workers)

        # Get discovery workers (separate from extraction workers for Phases 2-3)
        # Default: WORKERS.DISCOVERY_WORKERS_PROXIED for proxy modes, WORKERS.DISCOVERY_WORKERS_DIRECT for direct mode
        default_discovery_workers = WORKERS.DISCOVERY_WORKERS_PROXIED if proxy_mode in ('residential', 'web_scraper_api') else WORKERS.DISCOVERY_WORKERS_DIRECT
        discovery_workers = config.get('discovery_workers', default_discovery_workers)

        logging.info(f"[{retailer_name}] Discovery workers: {discovery_workers}, Extraction workers: {parallel_workers}")

        checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
        # Increase checkpoint interval when using parallel workers (less frequent saves)
        base_checkpoint_interval = config.get('checkpoint_interval', 10)
        checkpoint_interval = base_checkpoint_interval * max(1, parallel_workers) if parallel_workers > 1 else base_checkpoint_interval

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

        # Try to load cached URLs (skip discovery phases if cache is valid)
        # Note: Skip cache when targeting specific states
        target_slugs = kwargs.get('_target_slugs')
        url_cache = URLCache(retailer_name)
        all_store_urls = None
        if not refresh_urls and not target_slugs:
            all_store_urls = url_cache.get()

        # Load discovery checkpoint if resuming
        # Skip checkpoint if refresh_urls is requested (user wants fresh discovery)
        discovery_checkpoint = None
        if resume and all_store_urls is None and not refresh_urls:
            discovery_checkpoint = load_discovery_checkpoint(retailer_name)
            if discovery_checkpoint:
                logging.info(f"[{retailer_name}] Loaded discovery checkpoint from phase {discovery_checkpoint.get('phase', 0)}")
        elif resume and refresh_urls:
            # Clear any existing discovery checkpoint when refresh_urls is requested
            clear_discovery_checkpoint(retailer_name)
            logging.info(f"[{retailer_name}] Cleared discovery checkpoint due to --refresh-urls")

        if all_store_urls is None:
            # Cache miss or refresh requested - run full discovery
            # Phase 1: Discover states
            if discovery_checkpoint and discovery_checkpoint.get('phase', 0) >= 1:
                # Resume from checkpoint
                all_states = discovery_checkpoint.get('all_states', [])
                logging.info(f"[{retailer_name}] Phase 1: Resumed with {len(all_states)} states from checkpoint")
            else:
                logging.info(f"[{retailer_name}] Phase 1: Discovering states")
                all_states = get_all_states(session, config, retailer_name)

                # Save Phase 1 checkpoint
                if resume:
                    save_discovery_checkpoint(retailer_name, {
                        'phase': 1,
                        'all_states': all_states,
                        'timestamp': datetime.now().isoformat()
                    })

            # Filter to target states if specified
            if target_slugs:
                all_states = [s for s in all_states if s['url'].rstrip('/').split('/')[-1] in target_slugs]
                logging.info(f"[{retailer_name}] Filtered to {len(all_states)} target states: {[s['name'] for s in all_states]}")
            else:
                logging.info(f"[{retailer_name}] Found {len(all_states)} states")

            # Create session factory for parallel workers (each worker needs its own session)
            session_factory = create_session_factory(config)

            # Phase 2: Parallel city discovery
            if discovery_checkpoint and discovery_checkpoint.get('phase', 0) >= 2:
                # Resume from Phase 2 checkpoint
                all_cities = discovery_checkpoint.get('all_cities', [])
                logging.info(f"[{retailer_name}] Phase 2: Resumed with {len(all_cities)} cities from checkpoint")
                # Filter cities to target states if specified
                if target_slugs:
                    # Get state names for target slugs
                    target_state_names = {STATE_SLUG_TO_NAME.get(slug, '').lower() for slug in target_slugs}
                    all_cities = [c for c in all_cities if c.get('state', '').lower() in target_state_names]
                    logging.info(f"[{retailer_name}] Filtered to {len(all_cities)} cities in target states")
            else:
                all_cities = []
                if discovery_workers > 1 and len(all_states) > 1:
                    logging.info(f"[{retailer_name}] Phase 2: Discovering cities (parallel, {discovery_workers} workers)")
                    states_completed = [0]
                    states_lock = threading.Lock()

                    with ThreadPoolExecutor(max_workers=discovery_workers) as executor:
                        futures = {
                            executor.submit(
                                _fetch_cities_for_state_worker,
                                state,
                                session_factory,
                                config,
                                retailer_name
                            ): state
                            for state in all_states
                        }

                        for future in as_completed(futures):
                            state_name, cities = future.result()
                            all_cities.extend(cities)

                            with states_lock:
                                states_completed[0] += 1
                                if states_completed[0] % 10 == 0 or states_completed[0] == len(all_states):
                                    logging.info(
                                        f"[{retailer_name}] Phase 2 progress: "
                                        f"{states_completed[0]}/{len(all_states)} states, "
                                        f"{len(all_cities)} cities found"
                                    )
                else:
                    # Sequential fallback for direct mode or single state
                    logging.info(f"[{retailer_name}] Phase 2: Discovering cities (sequential)")
                    for state in all_states:
                        cities = get_cities_for_state(session, state['url'], state['name'], config, retailer_name)
                        all_cities.extend(cities)

                logging.info(f"[{retailer_name}] Found {len(all_cities)} cities total")

                # Save Phase 2 checkpoint
                if resume:
                    save_discovery_checkpoint(retailer_name, {
                        'phase': 2,
                        'all_states': all_states,
                        'all_cities': all_cities,
                        'timestamp': datetime.now().isoformat()
                    })

            # Phase 3: Parallel store URL discovery
            if discovery_checkpoint and discovery_checkpoint.get('phase', 0) >= 3:
                # Resume from Phase 3 checkpoint
                all_store_urls = discovery_checkpoint.get('all_store_urls', [])
                logging.info(f"[{retailer_name}] Phase 3: Resumed with {len(all_store_urls)} store URLs from checkpoint")
                # Filter store URLs to target states if specified
                if target_slugs:
                    # Store URLs contain state slug: /stores/{state-slug}/{city}/...
                    all_store_urls = [
                        url for url in all_store_urls
                        if any(f'/stores/{slug}/' in url.lower() for slug in target_slugs)
                    ]
                    logging.info(f"[{retailer_name}] Filtered to {len(all_store_urls)} store URLs in target states")
            else:
                all_store_urls = []
                if discovery_workers > 1 and len(all_cities) > 1:
                    logging.info(f"[{retailer_name}] Phase 3: Discovering store URLs (parallel, {discovery_workers} workers)")
                    cities_completed = [0]
                    cities_lock = threading.Lock()

                    with ThreadPoolExecutor(max_workers=discovery_workers) as executor:
                        futures = {
                            executor.submit(
                                _fetch_stores_for_city_worker,
                                city,
                                session_factory,
                                config,
                                retailer_name
                            ): city
                            for city in all_cities
                        }

                        for future in as_completed(futures):
                            city_name, state_name, store_urls = future.result()
                            all_store_urls.extend(store_urls)

                            with cities_lock:
                                cities_completed[0] += 1
                                if cities_completed[0] % 100 == 0 or cities_completed[0] == len(all_cities):
                                    logging.info(
                                        f"[{retailer_name}] Phase 3 progress: "
                                        f"{cities_completed[0]}/{len(all_cities)} cities, "
                                        f"{len(all_store_urls)} store URLs found"
                                    )
                else:
                    # Sequential fallback for direct mode or few cities
                    logging.info(f"[{retailer_name}] Phase 3: Discovering store URLs (sequential)")
                    for city in all_cities:
                        store_infos = get_stores_for_city(session, city['url'], city['city'], city['state'], config, retailer_name)
                        all_store_urls.extend([s['url'] for s in store_infos])

                logging.info(f"[{retailer_name}] Found {len(all_store_urls)} store URLs total")

                # Save Phase 3 checkpoint
                if resume:
                    save_discovery_checkpoint(retailer_name, {
                        'phase': 3,
                        'all_states': all_states,
                        'all_cities': all_cities,
                        'all_store_urls': all_store_urls,
                        'timestamp': datetime.now().isoformat()
                    })

            # Cache the discovered URLs for future runs
            if all_store_urls:
                url_cache.set(all_store_urls)

            # Clear discovery checkpoint after successful discovery
            # Clear regardless of whether we loaded from checkpoint - checkpoints may have been
            # saved during this run even on a fresh start with resume=True
            if resume:
                clear_discovery_checkpoint(retailer_name)
        else:
            logging.info(f"[{retailer_name}] Skipped discovery phases (using cached URLs)")

        if not all_store_urls:
            logging.warning(f"[{retailer_name}] No store URLs found")
            return {'stores': [], 'count': 0, 'checkpoints_used': False}

        remaining_urls = [url for url in all_store_urls if url not in completed_urls]

        if limit:
            logging.info(f"[{retailer_name}] Limited to {limit} stores")
            total_needed = limit - len(stores)
            if total_needed > 0:
                remaining_urls = remaining_urls[:total_needed]
            else:
                remaining_urls = []

        total_to_process = len(remaining_urls)
        logging.info(f"[{retailer_name}] Phase 4: Extracting store details ({total_to_process} URLs)")

        # Use parallel extraction if workers > 1
        if parallel_workers > 1 and total_to_process > 0:
            logging.info(f"[{retailer_name}] Using parallel extraction with {parallel_workers} workers")

            # Thread-safe counter for progress
            processed_count = [0]  # Use list for mutable closure
            processed_lock = threading.Lock()

            with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
                # Process in batches to limit memory usage
                batch_size = config.get('extraction_batch_size', 500)

                for batch_start in range(0, len(remaining_urls), batch_size):
                    batch_urls = remaining_urls[batch_start:batch_start + batch_size]
                    futures = {
                        executor.submit(_extract_single_store, url, session, config, retailer_name): url
                        for url in batch_urls
                    }

                    for future in as_completed(futures):
                        url, store_data = future.result()

                        with processed_lock:
                            processed_count[0] += 1
                            current_count = processed_count[0]

                            if store_data:
                                stores.append(store_data)
                                completed_urls.add(url)

                            # Progress logging every 100 stores
                            if current_count % 100 == 0:
                                logging.info(f"[{retailer_name}] Progress: {current_count}/{total_to_process} ({current_count/total_to_process*100:.1f}%)")

                            # Checkpoint at intervals
                            if current_count % checkpoint_interval == 0:
                                utils.save_checkpoint({
                                    'completed_count': len(stores),
                                    'completed_urls': list(completed_urls),
                                    'stores': stores,
                                    'last_updated': datetime.now().isoformat()
                                }, checkpoint_path)
                                logging.info(f"[{retailer_name}] Checkpoint saved: {len(stores)} stores processed")
        else:
            # Sequential extraction (original behavior)
            for i, url in enumerate(remaining_urls, 1):
                store_data = extract_store_details(session, url, config, retailer_name)
                if store_data:
                    stores.append(store_data)
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

        # Merge with existing stores if in targeted states mode
        if target_states and existing_stores:
            # Remove stores from target states from existing data (will be replaced)
            target_state_abbrevs = {a.upper() for a in target_states}
            filtered_existing = [
                s for s in existing_stores
                if s.get('state', '').upper() not in target_state_abbrevs
            ]
            # Add newly scraped stores
            merged_stores = filtered_existing + stores
            # Deduplicate by URL
            seen_urls = set()
            unique_stores = []
            for s in merged_stores:
                url = s.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_stores.append(s)

            logging.info(
                f"[{retailer_name}] Merged {len(stores)} new stores with "
                f"{len(filtered_existing)} existing stores = {len(unique_stores)} total"
            )
            stores = unique_stores

        return {
            'stores': stores,
            'count': len(stores),
            'checkpoints_used': checkpoints_used
        }

    except Exception as e:
        logging.error(f"[{retailer_name}] Fatal error: {e}", exc_info=True)
        raise
