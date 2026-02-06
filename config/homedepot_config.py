"""Configuration constants for Home Depot Store Scraper.

Home Depot uses a GraphQL Federation Gateway API powered by Apollo Client.
Two operations are used:
1. storeDirectoryByState — lists all stores in a state (Phase 1: discovery)
2. storeSearch — returns detailed store data by store ID (Phase 2: enrichment)

No authentication tokens or API keys are required.
"""

import random
from typing import Dict, Optional

# GraphQL API endpoint
GRAPHQL_URL = "https://apionline.homedepot.com/federation-gateway/graphql"

# Required headers for GraphQL requests (per API spec)
REQUIRED_HEADERS = {
    "content-type": "application/json",
    "x-experience-name": "store-finder",
    "x-hd-dc": "origin",
}

# All 54 US states and territories with Home Depot stores
US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
    "WY", "GU", "PR", "VI",
]

# Phase 1: State directory query — returns store list with basic info + county
QUERY_STATE_DIRECTORY = """query storeDirectoryByState($state: String!) {
  storeDirectoryByState(state: $state) {
    stateName
    storesInfo {
      storeName
      url
      phone
      rentalsLink
      servicesLink
      address { street city state postalCode county }
    }
  }
}"""

# Phase 2: Store search query — returns full detail (services, hours, coordinates)
QUERY_STORE_SEARCH = """query storeSearch(
  $lat: String,
  $lng: String,
  $storeSearchInput: String,
  $pagesize: String,
  $storeFeaturesFilter: StoreFeaturesFilter
) {
  storeSearch(
    lat: $lat
    lng: $lng
    storeSearchInput: $storeSearchInput
    pagesize: $pagesize
    storeFeaturesFilter: $storeFeaturesFilter
  ) {
    stores {
      storeId
      name
      address {
        street
        city
        state
        postalCode
        country
      }
      coordinates {
        lat
        lng
      }
      services {
        loadNGo
        propane
        toolRental
        penske
        keyCutting
        wiFi
        applianceShowroom
        expandedFlooringShowroom
        largeEquipment
        kitchenShowroom
        hdMoving
      }
      storeHours {
        monday { open close }
        tuesday { open close }
        wednesday { open close }
        thursday { open close }
        friday { open close }
        saturday { open close }
        sunday { open close }
      }
      storeDetailsPageLink
      storeType
      proDeskPhone
      phone
      toolRentalPhone
      storeServicesPhone
      flags {
        bopisFlag
        bodfsFlag
        curbsidePickupFlag
      }
      storeTimeZone
      proDeskHours {
        monday { open close }
        tuesday { open close }
        wednesday { open close }
        thursday { open close }
        friday { open close }
        saturday { open close }
        sunday { open close }
      }
      toolRentalHours {
        monday { open close }
        tuesday { open close }
        wednesday { open close }
        thursday { open close }
        friday { open close }
        saturday { open close }
        sunday { open close }
      }
      curbsidePickupHours {
        monday { open close }
        tuesday { open close }
        wednesday { open close }
        thursday { open close }
        friday { open close }
        saturday { open close }
        sunday { open close }
      }
    }
  }
}"""

# Default features filter — all False means no filtering
DEFAULT_FEATURES_FILTER = {
    "applianceShowroom": False,
    "expandedFlooringShowroom": False,
    "keyCutting": False,
    "loadNGo": False,
    "penske": False,
    "propane": False,
    "toolRental": False,
    "wiFi": False,
}

# User agents for rotation (realistic browser strings)
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
    """Get merged headers for GraphQL requests.

    Combines the required GraphQL headers (content-type, x-experience-name,
    x-hd-dc) with browser-like headers for PerimeterX compatibility.

    Args:
        user_agent: Specific User-Agent string (random if not provided)

    Returns:
        Dictionary of HTTP headers
    """
    if user_agent is None:
        user_agent = random.choice(USER_AGENTS)

    return {
        **REQUIRED_HEADERS,
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://www.homedepot.com",
        "Referer": "https://www.homedepot.com/",
    }
