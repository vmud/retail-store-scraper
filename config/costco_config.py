"""Configuration constants for Costco Warehouse Scraper

Costco uses Akamai bot protection, requiring Web Scraper API with JS rendering.
The scraper extracts warehouse data from the store locator page and individual
warehouse detail pages.

Discovery method: Geographic grid-based search + page scraping
Data source: costco.com/w/-/locations
"""

import random

# Base URLs
BASE_URL = "https://www.costco.com"
LOCATIONS_URL = "https://www.costco.com/w/-/locations"
WAREHOUSE_URL_PATTERN = "https://www.costco.com/w/-/{state}/{city}/{warehouse_id}"

# Geographic bounds (continental US + Hawaii + Alaska)
US_BOUNDS = {
    'lat_min': 24.5,    # Southern tip of Florida
    'lat_max': 49.4,    # Northern border with Canada
    'lng_min': -125.0,  # Western coast
    'lng_max': -66.9    # Eastern coast (Maine)
}

# Additional regions (for complete US coverage)
HAWAII_CENTER = (21.3069, -157.8583)  # Honolulu area
ALASKA_CENTER = (61.2181, -149.9003)  # Anchorage area

# Grid spacing for geographic search (miles)
# Costco warehouses are spaced further apart than typical retail stores
DEFAULT_GRID_SPACING_MILES = 75

# Search radius for each grid point (miles)
DEFAULT_SEARCH_RADIUS_MILES = 75

# Costco has ~600 US warehouses, much fewer than Cricket's 13,000+ stores
EXPECTED_STORE_COUNT = 600

# State codes for state-by-state discovery fallback
US_STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC', 'PR'  # Include DC and Puerto Rico
]

# Store type categories
STORE_TYPES = {
    'warehouse': 'warehouse',
    'business_center': 'business_center',
}

# Services available at warehouses
WAREHOUSE_SERVICES = [
    'gas_station',
    'tire_center',
    'optical',
    'pharmacy',
    'hearing_aid',
    'food_court',
    'car_wash',
]

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def get_headers(user_agent=None):
    """Get headers dict with optional user agent rotation."""
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def build_warehouse_url(state: str, city: str, warehouse_id: str) -> str:
    """Build URL for a specific warehouse detail page.

    Args:
        state: 2-letter state code (lowercase)
        city: City name (lowercase, hyphenated)
        warehouse_id: Numeric warehouse ID

    Returns:
        Complete warehouse URL
    """
    # Normalize inputs
    state = state.lower()
    city = city.lower().replace(' ', '-').replace("'", "")

    return f"{BASE_URL}/w/-/{state}/{city}/{warehouse_id}"


# Rate limiting - more conservative due to bot protection
# Use with web_scraper_api proxy mode
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 60  # Longer timeout for JS rendering

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 60

# Checkpoint interval (save progress every N warehouses)
CHECKPOINT_INTERVAL = 25

# Parallelization settings
# Keep low due to bot protection
DISCOVERY_WORKERS = 3
PARALLEL_WORKERS = 5
