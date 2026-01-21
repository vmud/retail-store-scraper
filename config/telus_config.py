"""Configuration constants for Telus Store Scraper"""

import random

# Uberall API configuration
# The storefinder token is embedded in stores.telus.com's __NEXT_DATA__
UBERALL_TOKEN = "WvKTSwsliw6eKvVJKXUpQ3vggaSxc9"
API_URL = f"https://uberall.com/api/storefinders/{UBERALL_TOKEN}/locations/all"

# Base URLs
BASE_URL = "https://stores.telus.com"
STORE_PAGE_BASE = "https://stores.telus.com/en"

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


def get_headers(user_agent=None):
    """Get headers dict with optional user agent rotation"""
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": BASE_URL,
    }


# Canadian province name to abbreviation mapping
PROVINCE_ABBREVIATIONS = {
    'Alberta': 'AB',
    'British Columbia': 'BC',
    'Manitoba': 'MB',
    'New Brunswick': 'NB',
    'Newfoundland and Labrador': 'NL',
    'Northwest Territories': 'NT',
    'Nova Scotia': 'NS',
    'Nunavut': 'NU',
    'Ontario': 'ON',
    'Prince Edward Island': 'PE',
    'Quebec': 'QC',
    'Québec': 'QC',  # Handle accented version
    'Saskatchewan': 'SK',
    'Yukon': 'YT',
}

# Rate limiting (minimal since it's a single API call)
MIN_DELAY = 0.5
MAX_DELAY = 1.0

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 60  # Longer timeout for bulk API response

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30
