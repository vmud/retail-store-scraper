"""Configuration constants for Bell Store Scraper

Bell uses storelocator.bell.ca with:
- Sitemap at /sitemap.xml (~251 store URLs)
- LocalBusiness JSON-LD schema on each store page
- Store IDs in format BE### (e.g., BE516)
"""

import random

# Base URLs
BASE_URL = "https://storelocator.bell.ca"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

# Store page URL pattern
# Example: https://storelocator.bell.ca/en/on/toronto/316-queen-st-w
STORE_URL_PATTERN = r'/en/[a-z]{2}/[^/]+/[^/]+'

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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": BASE_URL,
    }


# Rate limiting (conservative for HTML scraping)
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30
