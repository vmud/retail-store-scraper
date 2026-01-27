"""Configuration constants for Cricket Wireless Store Scraper

Cricket uses a Yext-powered store locator with a publicly accessible API.
The scraper uses geographic grid-based discovery to find all stores.
"""

import random

# Yext API configuration
YEXT_API_URL = "https://prod-cdn.us.yextapis.com/v2/accounts/me/search/query"
API_KEY = "7f7c4d30a6fc41f51d425ed2ed177b02"
EXPERIENCE_KEY = "cricket-locator"
API_VERSION = "20220511"
LOCALE = "en"

# Geographic bounds (continental US)
# These bounds cover the lower 48 states, excluding Alaska and Hawaii
US_BOUNDS = {
    'lat_min': 24.5,   # Southern tip of Florida
    'lat_max': 49.4,   # Northern border with Canada
    'lng_min': -125.0,  # Western coast
    'lng_max': -66.9    # Eastern coast (Maine)
}

# Grid spacing for geographic search
# At 50-mile spacing, generates ~1,200 grid points
DEFAULT_GRID_SPACING_MILES = 50

# Yext API returns stores within a radius (in miles)
# Using 50-mile radius ensures overlap with 50-mile grid spacing
DEFAULT_SEARCH_RADIUS_MILES = 50

# Maximum results per API call (Yext limit)
MAX_RESULTS_PER_CALL = 50

# Store type mapping from c_locatorFilters to friendly names
STORE_TYPES = {
    'Cricket Wireless Authorized Retailer': 'authorized_retailer',
    'Cricket Wireless Dealer': 'dealer',
    'Best Buy': 'bestbuy',
    'Target': 'target',
    'Walmart': 'walmart',
    'Meijer': 'meijer',
    'Kroger': 'kroger',
    'Big Lots': 'big_lots',
    'Dollar General': 'dollar_general',
    'Family Dollar': 'family_dollar',
}

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


def get_headers(user_agent=None):
    """Get headers dict with optional user agent rotation."""
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.cricketwireless.com/",
        "Origin": "https://www.cricketwireless.com",
    }


def build_api_url(lat: float, lng: float, radius_miles: int = DEFAULT_SEARCH_RADIUS_MILES) -> str:
    """Build Yext API URL for a geographic search.

    Args:
        lat: Latitude of search center
        lng: Longitude of search center
        radius_miles: Search radius in miles

    Returns:
        Complete API URL with query parameters
    """
    # Convert miles to meters (1 mile = 1609.34 meters)
    radius_meters = int(radius_miles * 1609.34)

    # Note: Yext API doesn't support 'limit' parameter - it returns all results
    # within the radius up to an internal maximum
    return (
        f"{YEXT_API_URL}"
        f"?api_key={API_KEY}"
        f"&experienceKey={EXPERIENCE_KEY}"
        f"&v={API_VERSION}"
        f"&locale={LOCALE}"
        f"&input="
        f"&location={lat},{lng}"
        f"&locationRadius={radius_meters}"
    )


# Rate limiting (API is lightweight, can be aggressive with proxies)
MIN_DELAY = 0.3
MAX_DELAY = 0.5

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30
