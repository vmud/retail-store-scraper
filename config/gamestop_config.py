"""Configuration constants for GameStop Store Scraper.

GameStop runs on Salesforce Commerce Cloud (SFCC/Demandware) with
Cloudflare WAF. Two-phase scraping approach:

Phase 1 - Geographic Grid Discovery (~90 API calls):
    Query Stores-FindStores API at grid points covering the US
    with 200-mile radius to discover all ~4,000+ stores.

Phase 2 - Detail Page Enrichment (~4,000 page fetches):
    Fetch each store's detail page for JSON-LD structured data
    (description, knowsAbout, paymentAccepted, image).

API: POST/GET Stores-FindStores (no auth required, Cloudflare challenge)
Bot Protection: Cloudflare JS challenge + residential proxy recommended.
"""

import random
import re
from typing import List, Optional, Tuple


# Base URLs
BASE_URL = "https://www.gamestop.com"
FIND_STORES_URL = (
    f"{BASE_URL}/on/demandware.store/"
    "Sites-gamestop-us-Site/default/Stores-FindStores"
)
STORE_DETAIL_BASE = f"{BASE_URL}/store/us"

# Geographic grid configuration
# US bounding box (contiguous 48 states)
US_BOUNDS = {
    "lat_min": 24.5,    # Southern tip of Florida
    "lat_max": 49.5,    # Northern border with Canada
    "lng_min": -125.0,  # Western coast
    "lng_max": -66.5,   # Eastern coast (Maine)
}

# Grid spacing: ~4 degrees latitude (~280 miles), ~5 degrees longitude
# With 200-mile search radius, circles overlap to ensure full coverage
LAT_STEP = 4.0
LNG_STEP = 5.0

# API search radius in miles (safe maximum per design doc)
SEARCH_RADIUS_MILES = 200

# Additional geographic points beyond CONUS grid
EXTRA_GRID_POINTS: List[Tuple[float, float]] = [
    (61.2, -150.0),   # Anchorage, Alaska
    (64.8, -147.7),   # Fairbanks, Alaska
    (21.3, -157.8),   # Honolulu, Hawaii
    (19.7, -155.1),   # Hilo, Hawaii
    (18.2, -66.5),    # San Juan, Puerto Rico
    (13.4, 144.7),    # Hagatna, Guam
]

# Store detail URL pattern (from storesResultsHtml)
# Format: /store/us/{state}/{city_slug}/{store_id}/{name_slug}-gamestop
STORE_DETAIL_URL_PATTERN = (
    "{base}/{{state}}/{{city_slug}}/{{store_id}}/{{name_slug}}-gamestop"
).format(base=STORE_DETAIL_BASE)

# Regex to extract store detail URLs from storesResultsHtml
STORE_URL_REGEX = re.compile(
    r'href="(/store/us/[^"]+)"'
)

# JSON-LD extraction pattern for store detail pages
JSONLD_REGEX = re.compile(
    r'<script\s+type="application/ld\+json">\s*(.*?)\s*</script>',
    re.DOTALL,
)

# Store operation hours are double-encoded JSON strings
# (JSON string embedded in JSON response)
HOURS_FIELD = "storeOperationHours"

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

# Rate limiting
MIN_DELAY = 1.5
MAX_DELAY = 3.0

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30


def generate_us_grid() -> List[Tuple[float, float]]:
    """Generate lat/long grid covering US territory for store discovery.

    Creates a grid of coordinates covering the contiguous US plus
    additional points for Alaska, Hawaii, Puerto Rico, and Guam.

    Returns:
        List of (latitude, longitude) tuples covering all US territories.
    """
    points: List[Tuple[float, float]] = []

    lat = US_BOUNDS["lat_min"]
    while lat <= US_BOUNDS["lat_max"]:
        lng = US_BOUNDS["lng_min"]
        while lng <= US_BOUNDS["lng_max"]:
            points.append((round(lat, 1), round(lng, 1)))
            lng += LNG_STEP
        lat += LAT_STEP

    # Add non-CONUS territories
    points.extend(EXTRA_GRID_POINTS)

    return points


def get_headers(user_agent: Optional[str] = None) -> dict:
    """Get request headers for GameStop API/page requests.

    Args:
        user_agent: Optional specific user agent string.

    Returns:
        Headers dict suitable for GameStop requests.
    """
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": f"{BASE_URL}/stores/",
    }


def get_page_headers(user_agent: Optional[str] = None) -> dict:
    """Get request headers for GameStop store detail page requests.

    Args:
        user_agent: Optional specific user agent string.

    Returns:
        Headers dict suitable for HTML page requests.
    """
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": f"{BASE_URL}/stores/",
    }


def build_api_url(lat: float, lng: float, radius: int = SEARCH_RADIUS_MILES) -> str:
    """Build FindStores API URL with lat/long parameters.

    Args:
        lat: Latitude of search center.
        lng: Longitude of search center.
        radius: Search radius in miles.

    Returns:
        Full API URL with query parameters.
    """
    return f"{FIND_STORES_URL}?lat={lat}&long={lng}&radius={radius}"


def build_store_detail_url(
    state: str,
    city: str,
    store_id: str,
    name: str,
) -> str:
    """Build a store detail page URL from store data.

    Args:
        state: Two-letter state code (e.g., 'NY').
        city: City name.
        store_id: Numeric store ID.
        name: Store name for URL slug.

    Returns:
        Full URL to the store detail page.
    """
    state_slug = state.lower()
    city_slug = _slugify(city)
    name_slug = _slugify(name)

    return STORE_DETAIL_URL_PATTERN.format(
        state=state_slug,
        city_slug=city_slug,
        store_id=store_id,
        name_slug=name_slug,
    )


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug.

    Args:
        text: Raw text to slugify.

    Returns:
        Lowercase, hyphenated slug with only alphanumeric chars and hyphens.
    """
    slug = text.strip().lower()
    slug = slug.replace("\u2013", "-").replace("\u2014", "-")
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")
