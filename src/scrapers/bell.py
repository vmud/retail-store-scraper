"""Core scraping functions for Bell Store Locator

Bell uses storelocator.bell.ca with:
- Sitemap at /sitemap.xml (~251 store URLs)
- LocalBusiness JSON-LD schema on each store page
- Store IDs in format BE### (e.g., BE516)
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup

from config import bell_config
from src.shared import utils
from src.shared.cache import URLCache
from src.shared.request_counter import RequestCounter, check_pause_logic


# Global request counter
_request_counter = RequestCounter()


@dataclass
class BellStore:
    """Data model for Bell store information"""
    store_id: str           # BE516
    name: str               # Bell - Queen St W
    street_address: str     # 316 Queen St W
    city: str               # Toronto
    state: str              # ON (province abbreviation)
    postal_code: str        # M5V2A2
    country: str            # CA
    phone: str              # 416 977-6969
    hours: Optional[str]    # JSON string of formatted hours
    services: Optional[str] # JSON string of services list
    store_type: str         # corporate, authorized_dealer
    has_curbside: bool      # Curbside pickup available
    url: str                # Full store page URL
    scraped_at: str         # ISO timestamp

    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        return asdict(self)


def _format_schema_hours(opening_hours: List[str]) -> Optional[str]:
    """Format schema.org openingHours to JSON string.

    Args:
        opening_hours: List of hours in schema.org format
            Example: ["Su 1200-1700", "Mo 1100-1800", ...]

    Returns:
        JSON string of formatted hours or None if no hours
    """
    if not opening_hours:
        return None

    day_map = {
        'Su': 'Sunday', 'Mo': 'Monday', 'Tu': 'Tuesday',
        'We': 'Wednesday', 'Th': 'Thursday', 'Fr': 'Friday', 'Sa': 'Saturday'
    }

    formatted = []
    for entry in opening_hours:
        # Parse format: "Mo 1100-1800"
        match = re.match(r'(\w{2})\s+(\d{4})-(\d{4})', entry)
        if match:
            day_abbr, open_time, close_time = match.groups()
            day_name = day_map.get(day_abbr, day_abbr)
            # Convert 1100 to 11:00
            open_fmt = f"{open_time[:2]}:{open_time[2:]}"
            close_fmt = f"{close_time[:2]}:{close_time[2:]}"
            formatted.append({
                'day': day_name,
                'open': open_fmt,
                'close': close_fmt
            })

    return json.dumps(formatted) if formatted else None


def _extract_store_type(store_name: str) -> str:
    """Determine store type from store name.

    Bell corporate stores typically have "Bell" as the primary name.
    Authorized dealers have different business names.

    Args:
        store_name: Store name from JSON-LD schema

    Returns:
        'corporate' or 'authorized_dealer'
    """
    # Corporate stores are simply named "Bell" or "Bell - Location"
    if store_name.lower().strip() == 'bell':
        return 'corporate'
    return 'authorized_dealer'


def _extract_services(soup: BeautifulSoup) -> Optional[str]:
    """Extract services list from HTML.

    Args:
        soup: BeautifulSoup object of store page

    Returns:
        JSON string of services list or None
    """
    services = []

    # Look for services in the rsx-list under "Products and services"
    service_list = soup.find('ul', class_='rsx-list')
    if service_list:
        for li in service_list.find_all('li'):
            text = li.get_text(strip=True)
            if text:
                services.append(text)

    return json.dumps(services) if services else None


def _has_curbside_pickup(soup: BeautifulSoup) -> bool:
    """Check if store offers curbside pickup.

    Args:
        soup: BeautifulSoup object of store page

    Returns:
        True if curbside pickup is available
    """
    # Look for curbside pickup indicator
    curbside_img = soup.find('img', src=lambda x: x and 'curbside' in x.lower() if x else False)
    curbside_text = soup.find(string=lambda x: x and 'curbside' in x.lower() if x else False)
    return bool(curbside_img or curbside_text)


def reset_request_counter() -> None:
    """Reset the global request counter"""
    _request_counter.reset()


def get_request_count() -> int:
    """Get current request count"""
    return _request_counter.count
