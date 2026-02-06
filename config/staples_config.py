"""Configuration constants for Staples Store Scraper.

Staples operates ~500-600 retail stores across the US. Two APIs provide store data:
1. StaplesConnect REST API (primary) - rich detail, scannable by store number
2. Staples Store Locator (secondary) - geographic search, features/status data

The scraper uses a 3-phase approach:
  Phase 1: Bulk store number scan via StaplesConnect API
  Phase 2: ZIP code gap-fill via store locator for missed stores
  Phase 3: Service enrichment via StaplesConnect services API
"""

import random
from typing import Dict, List, Optional, Tuple

# ===========================================================================
# API Endpoints
# ===========================================================================

# StaplesConnect REST API (primary - richer data, no auth needed)
STAPLESCONNECT_BASE_URL = "https://www.staplesconnect.com"
STAPLESCONNECT_STORE_URL = f"{STAPLESCONNECT_BASE_URL}/api/store"
STAPLESCONNECT_SERVICES_URL = (
    f"{STAPLESCONNECT_BASE_URL}/api/store/service/getStoreServicesByStoreNumber"
)

# Store Locator Proxy (secondary - geographic search, session-dependent)
STORE_LOCATOR_URL = "https://www.staples.com/ele-lpd/api/sparxProxy/storeLocator"

# Staples store page (for establishing session context)
STORES_PAGE_URL = "https://www.staples.com/stores"

# ===========================================================================
# Store Number Ranges
# ===========================================================================
# Non-sequential: not all numbers in range are valid stores
# Majority: 0001-1967, outliers up to 5311

STORE_NUMBER_RANGES = [
    (1, 2001),      # Main range: 0001-2000
    (5001, 5500),   # Outlier range: 5001-5499
]

# ===========================================================================
# ZIP Codes for Geographic Gap-Fill (Phase 2)
# ===========================================================================
# Covers all US states and major metro areas to catch stores
# missed by store number scanning

GAP_FILL_ZIP_CODES = [
    "01001", "02101", "03101", "04101", "05401", "06101", "07101",
    "10001", "11201", "12201", "13201", "14201", "15201", "17101",
    "19101", "20001", "21201", "22201", "23219", "24001", "25301",
    "27001", "28001", "29201", "30301", "32201", "33101", "35201",
    "37201", "40201", "43201", "44101", "45201", "46201", "48201",
    "50301", "53201", "55101", "60601", "63101", "64101", "66101",
    "68101", "70112", "72201", "73101", "75201", "77001", "78201",
    "80201", "83701", "84101", "85001", "87101", "89101", "90001",
    "92101", "94101", "97201", "98101", "99201",
]

# Store locator search radius (miles) - max 10 results per query
LOCATOR_SEARCH_RADIUS = 200

# ===========================================================================
# Feature and Service Mappings
# ===========================================================================

# ===========================================================================
# User Agents
# ===========================================================================

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


def get_headers(user_agent: Optional[str] = None) -> Dict[str, str]:
    """Get request headers with optional user agent rotation.

    Args:
        user_agent: Specific user agent string. If None, randomly selects one.

    Returns:
        Dict of HTTP headers for StaplesConnect API requests.
    """
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


def get_locator_headers(user_agent: Optional[str] = None) -> Dict[str, str]:
    """Get request headers for the store locator API.

    Args:
        user_agent: Specific user agent string. If None, randomly selects one.

    Returns:
        Dict of HTTP headers for store locator POST requests.
    """
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.staples.com/stores",
        "Origin": "https://www.staples.com",
    }


def build_store_detail_url(store_number: str) -> str:
    """Build StaplesConnect store detail URL.

    Args:
        store_number: Store number (e.g., "1571" or "0001").

    Returns:
        Full API URL for the store detail endpoint.
    """
    return f"{STAPLESCONNECT_STORE_URL}/{store_number}"


def build_services_url(store_number: str) -> str:
    """Build StaplesConnect services URL.

    Args:
        store_number: Store number (e.g., "1571").

    Returns:
        Full API URL for the store services endpoint.
    """
    return f"{STAPLESCONNECT_SERVICES_URL}/{store_number}"


# ===========================================================================
# Rate Limiting
# ===========================================================================

TIMEOUT = 60  # Higher timeout for Web Scraper API
