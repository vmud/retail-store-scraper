"""Configuration constants for Apple Retail Store Scraper.

Apple uses a Next.js-powered retail site with two data access patterns:
1. Store directory via Next.js SSR data endpoint (storelist.json)
2. Store detail pages with __NEXT_DATA__ JSON blobs

No authentication or JS rendering required. Minimal bot protection.
"""

import json
import logging
import random
import re
import urllib.parse

# Base URLs
BASE_URL = "https://www.apple.com"
RETAIL_BASE_URL = f"{BASE_URL}/retail"
STORELIST_PATH = "/retail/_next/data/{build_id}/storelist.json"
STORE_DETAIL_PATH = "/retail/{slug}/"
GRAPHQL_URL = f"{BASE_URL}/api-www/graphql"
RETAIL_SITEMAP_URL = f"{BASE_URL}/retail/sitemap/sitemap.xml"

# GraphQL persisted query hash for StoreSearchByLocation (public, not a secret)
PERSISTED_QUERY_HASH = (
    "95310df81b3cd55c84fda50c49580bff1761ce5ff9acfdb9763b97915d18f7d9"  # pragma: allowlist secret
)

# Locale for US stores
US_LOCALE = "en_US"

# Validation patterns for external data
STORE_ID_PATTERN = re.compile(r"^R\d+$")  # R001, R720
SLUG_PATTERN = re.compile(r"^[a-z0-9]+$")  # Apple slugs are lowercase alphanumeric
BUILD_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")  # Next.js build IDs

logger = logging.getLogger(__name__)

# Known in-store service categories and their IDs
SERVICE_CATEGORIES = {
    "Shopping": ["SHOP", "SWS", "TradeIn", "CarrierDeals", "SelfCheckout", "LimitedSHOP"],
    "Pickup/Delivery": ["APU"],
    "Support": ["GBDI", "GB", "LimitedGB"],
    "Learning": ["TodayApple", "PS"],
    "Other": ["SignLanguage", "Curbside"],
}

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

# Rate limiting
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30


def get_headers(user_agent: str = None) -> dict:
    """Get headers dict for Apple retail page requests.

    Args:
        user_agent: Optional specific user agent string

    Returns:
        Headers dict suitable for Apple retail requests
    """
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": RETAIL_BASE_URL,
    }


def get_json_headers(user_agent: str = None) -> dict:
    """Get headers dict for Apple JSON/API requests.

    Args:
        user_agent: Optional specific user agent string

    Returns:
        Headers dict suitable for JSON API requests
    """
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": RETAIL_BASE_URL,
    }


def get_graphql_headers(user_agent: str = None) -> dict:
    """Get headers dict for Apple GraphQL API requests.

    The GraphQL API requires specific CSRF headers to avoid 400 errors.

    Args:
        user_agent: Optional specific user agent string

    Returns:
        Headers dict with required GraphQL CSRF headers
    """
    headers = get_json_headers(user_agent)
    headers["x-apollo-operation-name"] = "StoreSearchByLocation"
    headers["apollo-require-preflight"] = "true"
    return headers


def build_storelist_url(build_id: str) -> str:
    """Build URL for the Next.js store directory endpoint.

    Args:
        build_id: Current Next.js build ID

    Returns:
        Full URL to the storelist.json endpoint

    Raises:
        ValueError: If build_id contains unexpected characters
    """
    if not BUILD_ID_PATTERN.match(build_id):
        raise ValueError(f"Invalid build ID format: {build_id!r}")
    return BASE_URL + STORELIST_PATH.format(build_id=build_id)


def build_store_detail_url(slug: str) -> str:
    """Build URL for a store detail page.

    Args:
        slug: Store URL slug (e.g., 'glendalegalleria')

    Returns:
        Full URL to the store detail page
    """
    if not SLUG_PATTERN.match(slug):
        logger.warning("Unexpected slug format: %r, sanitizing", slug)
        slug = re.sub(r"[^a-z0-9]", "", slug.lower())
    return BASE_URL + STORE_DETAIL_PATH.format(slug=slug)


def build_graphql_url(latitude: float, longitude: float, locale: str = US_LOCALE) -> str:
    """Build URL for the GraphQL store search endpoint.

    Args:
        latitude: Search center latitude
        longitude: Search center longitude
        locale: Locale identifier (default: en_US)

    Returns:
        Full GraphQL URL with encoded query parameters
    """
    params = urllib.parse.urlencode({
        "operationName": "StoreSearchByLocation",
        "variables": json.dumps({
            "localeId": locale,
            "latitude": latitude,
            "longitude": longitude,
        }),
        "extensions": json.dumps({
            "persistedQuery": {
                "version": 1,
                "sha256Hash": PERSISTED_QUERY_HASH,
            }
        }),
    })
    return f"{GRAPHQL_URL}?{params}"
