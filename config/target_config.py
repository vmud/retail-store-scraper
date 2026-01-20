"""Configuration constants for Target Store Scraper"""

import os
import random

BASE_URL = "https://www.target.com"
SITEMAP_URL = "https://www.target.com/sl/sitemap_0001.xml.gz"
REDSKY_API_URL = ("https://redsky.target.com/redsky_aggregations/"
                  "v1/web/store_location_v1")
API_KEY = os.getenv("TARGET_API_KEY", "8df66ea1e1fc070a6ea99e942431c9cd67a80f02")
API_CHANNEL = "WEB"
STORE_DIRECTORY_BASE = "https://www.target.com/store-locator/store-directory"

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (compatible; StoreLocatorBot/1.0)",
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
]

# Default headers template
def get_headers(user_agent=None):
    """Get headers dict with optional user agent rotation"""
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": ("application/json, text/html,application/xhtml+xml,"
                   "application/xml;q=0.9,*/*;q=0.8"),
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": BASE_URL,
    }

# Rate limiting (from spec: 0.1s between requests, 1s pause every 50)
MIN_DELAY = 0.1  # 100ms between requests
MAX_DELAY = 0.5  # 500ms max delay for random variation

# Pause thresholds - standardized naming (#75)
PAUSE_50_REQUESTS = 50  # Renamed from PAUSE_50_THRESHOLD for consistency
PAUSE_50_MIN = 1.0  # Minimum pause duration (seconds) after 50 requests
PAUSE_50_MAX = 2.0  # Maximum pause duration (seconds) after 50 requests

# Longer pause after 200 requests (similar to other scrapers for consistency)
PAUSE_200_REQUESTS = 200
PAUSE_200_MIN = 120  # Minimum pause duration (seconds) - 2 minutes
PAUSE_200_MAX = 180  # Maximum pause duration (seconds) - 3 minutes

# Legacy alias for backwards compatibility (#75)
PAUSE_50_THRESHOLD = PAUSE_50_REQUESTS
PAUSE_50_DELAY = PAUSE_50_MIN  # Legacy single-value delay

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30  # Request timeout in seconds

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30  # Base wait time for 429 errors (seconds)

# Checkpoint settings
CHECKPOINT_STORES_INTERVAL = 100  # Save checkpoint every N stores

# All US states for HTML fallback scraping
STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new-hampshire", "new-jersey",
    "new-mexico", "new-york", "north-carolina", "north-dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode-island", "south-carolina",
    "south-dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west-virginia", "wisconsin", "wyoming"
]
