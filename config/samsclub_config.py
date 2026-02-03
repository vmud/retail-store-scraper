"""Configuration constants for Sam's Club Store Scraper

Sam's Club uses a Next.js site with Akamai bot protection.
The scraper uses a hybrid approach:
1. Fetch club URLs from sitemap (no bot protection)
2. Extract club details using Web Scraper API (Akamai bypass)

Sitemap: https://www.samsclub.com/sitemap_locators.xml
Expected results: ~600 clubs nationwide
"""

import random

# Sitemap URL for club discovery
SITEMAP_URL = "https://www.samsclub.com/sitemap_locators.xml"

# Legacy API URL (blocked by bot protection, kept for reference)
API_URL = "https://www.samsclub.com/api/node/vivaldi/v2/clubfinder/list"

# Search radius for each API call
# Sam's Club API returns up to ~10 clubs per query
# Using 150-mile radius ensures overlap for complete coverage
DEFAULT_SEARCH_RADIUS_MILES = 150

# Maximum clubs returned per API call (observed limit)
MAX_RESULTS_PER_CALL = 10

# Grid of representative ZIP codes covering the continental US
# Approximately 200-mile spacing to ensure complete coverage with 150-mile radius
# Each ZIP code is positioned to cover a region of the country
US_ZIP_GRID = [
    # Northeast
    '04101', '03301', '05401', '02101', '06101', '12201', '08540', '19101',
    # Mid-Atlantic
    '21201', '20001', '23219', '25301', '27601', '29201',
    # Southeast
    '30301', '32301', '33101', '35201', '36601', '39201', '37201', '40601',
    # Midwest
    '43215', '48201', '46201', '60601', '53201', '55401', '50309', '63101',
    '66101', '68501', '57501', '58501', '59601',
    # Southwest
    '73101', '75201', '78201', '79901', '85001', '87501', '88001',
    # Mountain
    '80201', '82001', '83701', '84101', '89101', '59801',
    # West Coast
    '90001', '92101', '94102', '95814', '97201', '98101',
    # Alaska & Hawaii
    '99501', '96801',
    # Puerto Rico
    '00901',
    # Additional coverage points for dense areas
    '77001', '33401', '28201', '15201', '44101', '64101', '91001',
    '85281', '89501', '98201', '97401', '93301', '88901', '87101',
    '73301', '71101', '72201', '38103', '47201', '49501', '61801',
    '52001', '56001', '66201', '67201', '74101', '76101', '79101',
    # Fill gaps in coverage
    '17101', '18101', '13201', '14201', '16101', '26501', '24201',
    '31201', '32601', '34201', '34601', '35801', '36101', '37401',
    '38401', '39501', '41001', '42001', '45201', '54601', '55101',
]

# Service name mapping from API to friendly display names
SERVICE_DISPLAY_NAMES = {
    'pharmacy': 'Pharmacy',
    'optical': 'Optical Center',
    'hearing_aid_center': 'Hearing Aid Center',
    'mobile_wireless': 'Mobile/Wireless',
    'cafe': 'Cafe',
    'bakery': 'Bakery',
    'meat': 'Meat Department',
    'floral': 'Floral',
    'liquor': 'Liquor',
    'gas': 'Fuel Center',
    'tires_&_batteries': 'Tires & Batteries',
    'propane_exchange': 'Propane Exchange',
    'photo': 'Photo Center',
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
        "Referer": "https://www.samsclub.com/club-finder",
        "Origin": "https://www.samsclub.com",
    }


def build_api_url(zip_code: str, distance_miles: int = DEFAULT_SEARCH_RADIUS_MILES) -> str:
    """Build Sam's Club API URL for a geographic search.

    Args:
        zip_code: ZIP code or address for search center
        distance_miles: Search radius in miles

    Returns:
        Complete API URL with query parameters
    """
    return f"{API_URL}?singleLineAddr={zip_code}&distance={distance_miles}"


# Rate limiting (API is lightweight, can be aggressive with proxies)
MIN_DELAY = 0.2
MAX_DELAY = 0.4

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30
