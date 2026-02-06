"""Configuration constants for Lowe's Store Scraper

Lowe's uses server-rendered HTML with embedded JSON (Redux initial state).
Two-phase discovery:
1. State directory pages list all store IDs per state (51 pages)
2. Store detail pages contain full embedded JSON data (~1,761 stores)

Architecture: React/Redux SSR with PerimeterX bot protection.
Store detail URLs only require the store number; the path prefix is cosmetic.
"""


# Base URLs
BASE_URL = "https://www.lowes.com"
STORE_DIRECTORY_URL = f"{BASE_URL}/Lowes-Stores"
STORE_DETAIL_URL_TEMPLATE = f"{BASE_URL}/store/X-X/{{store_id}}"

# State directory URL template
# Format: /Lowes-Stores/{StateName}/{StateCode}
STATE_DIRECTORY_URL_TEMPLATE = f"{BASE_URL}/Lowes-Stores/{{state_name}}/{{state_code}}"

# All 50 US states + DC with URL-safe names
# Format: (state_name_for_url, state_code)
STATES = [
    ("Alabama", "AL"), ("Alaska", "AK"), ("Arizona", "AZ"), ("Arkansas", "AR"),
    ("California", "CA"), ("Colorado", "CO"), ("Connecticut", "CT"), ("Delaware", "DE"),
    ("District-Of-Columbia", "DC"), ("Florida", "FL"), ("Georgia", "GA"), ("Hawaii", "HI"),
    ("Idaho", "ID"), ("Illinois", "IL"), ("Indiana", "IN"), ("Iowa", "IA"),
    ("Kansas", "KS"), ("Kentucky", "KY"), ("Louisiana", "LA"), ("Maine", "ME"),
    ("Maryland", "MD"), ("Massachusetts", "MA"), ("Michigan", "MI"), ("Minnesota", "MN"),
    ("Mississippi", "MS"), ("Missouri", "MO"), ("Montana", "MT"), ("Nebraska", "NE"),
    ("Nevada", "NV"), ("New-Hampshire", "NH"), ("New-Jersey", "NJ"), ("New-Mexico", "NM"),
    ("New-York", "NY"), ("North-Carolina", "NC"), ("North-Dakota", "ND"), ("Ohio", "OH"),
    ("Oklahoma", "OK"), ("Oregon", "OR"), ("Pennsylvania", "PA"), ("Rhode-Island", "RI"),
    ("South-Carolina", "SC"), ("South-Dakota", "SD"), ("Tennessee", "TN"), ("Texas", "TX"),
    ("Utah", "UT"), ("Vermont", "VT"), ("Virginia", "VA"), ("Washington", "WA"),
    ("West-Virginia", "WV"), ("Wisconsin", "WI"), ("Wyoming", "WY"),
]

# Regex patterns for extracting store data from HTML
# Store links in state directory pages: href="/store/{State-City}/{StoreNumber}"
STORE_LINK_PATTERN = r'href="/store/[^"]*/(\d+)"'

# Embedded store IDs in state directory JSON data
EMBEDDED_STORE_ID_PATTERN = r'"id"\s*:\s*"(\d+)"'

# Store names in embedded data
STORE_NAME_PATTERN = r'"storeName"\s*:\s*"([^"]+)"'

# Marker for finding embedded JSON in store detail pages
# Uses '"_id":' (without trailing quote) to match both minified and
# pretty-printed JSON: '"_id":"abc"' and '"_id": "abc"'
EMBEDDED_JSON_MARKER = '"_id":'

# Maximum search distance from marker to find opening brace
JSON_SEARCH_LOOKBACK = 100

# Maximum JSON object size to parse (prevents runaway on malformed HTML)
JSON_MAX_SIZE = 50000


def build_state_directory_url(state_name: str, state_code: str) -> str:
    """Build URL for a state's store directory page.

    Args:
        state_name: URL-safe state name (e.g., 'New-Jersey').
        state_code: Two-letter state code (e.g., 'NJ').

    Returns:
        Full URL for the state directory page.
    """
    return STATE_DIRECTORY_URL_TEMPLATE.format(
        state_name=state_name, state_code=state_code
    )


def build_store_detail_url(store_id: str) -> str:
    """Build URL for a store's detail page.

    Only the store number matters in the URL path. The state-city portion
    is cosmetic and ignored by the server.

    Args:
        store_id: Numeric store ID (e.g., '1548').

    Returns:
        Full URL for the store detail page.
    """
    return STORE_DETAIL_URL_TEMPLATE.format(store_id=store_id)


# Rate limiting (conservative for HTML scraping with PerimeterX)
MIN_DELAY = 1.0
MAX_DELAY = 2.0

# Retry settings
MAX_RETRIES = 3
TIMEOUT = 30

# Rate limit handling
RATE_LIMIT_BASE_WAIT = 30
