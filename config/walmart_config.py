"""Configuration constants for Walmart Store Scraper"""

import random

BASE_URL = "https://www.walmart.com"
SITEMAP_INDEX_URL = "https://www.walmart.com/sitemap_store_main.xml"

# Gzipped sitemap URLs for different store types
SITEMAP_URLS = [
    "https://www.walmart.com/sitemap_store_main_supercenter.xml.gz",
    "https://www.walmart.com/sitemap_store_main_discount.xml.gz",
    "https://www.walmart.com/sitemap_store_main_neighborhood.xml.gz",
    "https://www.walmart.com/sitemap_store_main_other.xml.gz",
]

# User agents for rotation
USER_AGENTS = [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
     "(KHTML, like Gecko) Version/17.1 Safari/605.1.15"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"),
]

# Default headers template
def get_headers(user_agent=None):
    """Get headers dict with optional user agent rotation"""
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": BASE_URL,
    }

# Delay constants (per specs: 1-2 seconds recommended)
MIN_DELAY = 1.0  # Minimum delay between requests (seconds)
MAX_DELAY = 2.0  # Maximum delay between requests (seconds)

# Pause thresholds
PAUSE_50_REQUESTS = 50  # Pause after this many requests
PAUSE_50_MIN = 30  # Minimum pause duration (seconds)
PAUSE_50_MAX = 60  # Maximum pause duration (seconds)

PAUSE_200_REQUESTS = 200  # Longer pause after this many requests
PAUSE_200_MIN = 120  # Minimum pause duration (seconds) - 2 minutes
PAUSE_200_MAX = 180  # Maximum pause duration (seconds) - 3 minutes

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30  # Request timeout in seconds

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30  # Base wait time for 429 errors (seconds)

# Checkpoint settings
CHECKPOINT_STORES_INTERVAL = 100  # Save checkpoint every N stores
