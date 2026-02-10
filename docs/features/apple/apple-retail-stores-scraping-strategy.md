# Apple Retail Store Locator - Data Extraction Strategy

## Executive Summary

Apple operates **536 retail stores worldwide** across 27 countries, with **272 stores in the United States**. Apple's retail data infrastructure is exceptionally clean and well-structured, built on a **Next.js** application backed by a **public GraphQL API** (Apollo Server). The entire worldwide store directory — including addresses, phone numbers, coordinates, hours, services, and store images — is available through two primary data sources, neither of which requires authentication.

This is the most straightforward retailer of those analyzed. A complete extraction of all 272 US stores with full detail can be accomplished in **under 300 API calls** with no bot protection concerns.

**Last Updated:** February 2026
**Target URL:** `https://www.apple.com/retail/`

---

## Architecture Overview

Apple's retail pages are built with **Next.js** (SSR) using **Apollo GraphQL** for data fetching. Two primary data access patterns exist:

1. **Next.js SSR Data Endpoint** (`/retail/_next/data/{buildId}/storelist.json`) — Returns the complete worldwide store directory in a single request. Contains basic info: store ID, name, slug, phone, address.
2. **GraphQL API** (`/api-www/graphql`) — Powers the store finder map. Supports geographic search and returns rich store data. Uses **persisted queries** with SHA256 hashes.

Both endpoints are publicly accessible with minimal header requirements.

---

## OxyLabs Integration Recommendations

### Service Selection

| Use Case | Recommended Service | Rationale |
|----------|-------------------|-----------|
| Full store directory (storelist.json) | **Web Scraper API** (universal, no rendering) | Single GET request returns all 536 stores worldwide. Cheapest option. |
| Individual store detail pages | **Web Scraper API** (universal, no rendering) | Clean server-rendered HTML with `__NEXT_DATA__` JSON. No JS rendering needed. |
| GraphQL store search by location | **Web Scraper API** (universal, no rendering) | GET request with custom headers. No rendering needed. |
| Bulk store detail enrichment | **Web Scraper API** (Push-Pull batch) | Submit all 272 US store detail URLs in one batch request. |

### Key Insight: No JS Rendering Needed

Apple's retail site does **not** require JavaScript rendering for data extraction. All store data is either available via direct API calls or embedded in server-rendered HTML as `__NEXT_DATA__` JSON. This makes extraction significantly cheaper and faster than retailers like Staples or Lowe's.

### Recommended Execution Plan

```
Phase 1: Directory Snapshot (1 request)
  - GET /retail/_next/data/{buildId}/storelist.json
  - Yields: all 536 stores worldwide with IDs, names, slugs, phones, addresses
  - Cost: 1 non-rendered Web Scraper API call

Phase 2: Detail Enrichment (272 requests for US, or 536 for worldwide)
  - GET /retail/{slug}/ for each store
  - Parse __NEXT_DATA__ from HTML for: hours, services, geolocation,
    timezone, operating model, images, programs
  - Cost: 272 non-rendered Web Scraper API calls (use Push-Pull batch)

Phase 3 (Optional): Geographic Search Validation
  - GraphQL StoreSearchByLocation queries to verify coverage
  - Cost: ~50 calls with different coordinates

Total estimated: ~275-325 API calls (all non-rendered)
```

---

## Data Source #1: Next.js Store List Endpoint

### Endpoint

```
GET https://www.apple.com/retail/_next/data/{buildId}/storelist.json
```

The `buildId` changes with each deployment. Current value: `WvJEhhQSiVnNziWwWdN-K`. To obtain the current buildId, fetch any Apple retail page and extract `window.__NEXT_DATA__.buildId` from the HTML.

### Response Schema

Returns the complete worldwide store directory grouped by country and state.

```json
{
  "pageProps": {
    "storeList": [
      {
        "locale": "en_US",
        "calledLocale": "en_US",
        "hasStates": true,
        "state": [
          {
            "__typename": "RgdsState",
            "name": "California",
            "store": [
              {
                "id": "R001",
                "name": "Glendale Galleria",
                "slug": "glendalegalleria",
                "telephone": "(818) 507-6338",
                "address": {
                  "address1": "2148 Glendale Galleria",
                  "address2": "",
                  "city": "Glendale",
                  "postalCode": "91210",
                  "__typename": "PostalAddress",
                  "stateName": "California",
                  "stateCode": "CA"
                },
                "__typename": "RgdsStore"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### Store List Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Store ID (e.g., "R001", "R720") |
| `name` | string | Store display name (e.g., "Glendale Galleria") |
| `slug` | string | URL slug for store detail page |
| `telephone` | string | Formatted phone number |
| `address.address1` | string | Street address line 1 |
| `address.address2` | string | Street address line 2 |
| `address.city` | string | City |
| `address.postalCode` | string | ZIP/postal code |
| `address.stateName` | string | Full state name |
| `address.stateCode` | string | 2-letter state code |

### Store Count by Country

| Country | Locale | Store Count |
|---------|--------|-------------|
| United States | en_US | 272 |
| China | zh_CN | 50 |
| United Kingdom | en_GB | 39 |
| Canada | en_CA | 28 |
| Australia | en_AU | 22 |
| France | fr_FR | 20 |
| Italy | it_IT | 17 |
| Germany | de_DE | 16 |
| Spain | es_ES | 12 |
| Japan | ja_JP | 11 |
| South Korea | ko_KR | 7 |
| Hong Kong | en_HK | 6 |
| India | en_IN | 5 |
| UAE | en_AE | 5 |
| **Total Worldwide** | | **536** |

---

## Data Source #2: GraphQL API (Store Search)

### Endpoint

```
GET https://www.apple.com/api-www/graphql
```

### Required Headers

```
x-apollo-operation-name: StoreSearchByLocation
apollo-require-preflight: true
```

Without these headers, the API returns a 400 CSRF error.

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `operationName` | string | `StoreSearchByLocation` |
| `variables` | JSON string | `{"localeId":"en_US","latitude":34.10252,"longitude":-118.41679}` |
| `extensions` | JSON string | Persisted query hash (see below) |

### Persisted Query Hash

```json
{
  "persistedQuery": {
    "version": 1,
    "sha256Hash": "95310df81b3cd55c84fda50c49580bff1761ce5ff9acfdb9763b97915d18f7d9"  # pragma: allowlist secret
  }
}
```

### Search Result Store Schema

```json
{
  "storeNumber": "R250",
  "storeName": "West 14th Street",
  "storeSlug": "west14thstreet",
  "_locale": { "localeId": "en_US" },
  "geolocation": {
    "latitude": 40.7412,
    "longitude": -74.00542
  },
  "_address": {
    "line1": "401 W 14th Street",
    "line2": "",
    "zip": "10014",
    "city": "New York",
    "state": { "code": "NY", "name": "New York" }
  },
  "_storeHours": {
    "formattedSearchStatus": "Open until 9:00 p.m.",
    "alwaysOpen": false,
    "closed": false
  },
  "distance": {
    "formatted": "0.7 miles",
    "meters": 1059.15
  },
  "_imageData": {
    "cardImage": {
      "large": { "x2": "https://rtlimages.apple.com/cmc/dieter/store/16_9/R250.png" }
    }
  },
  "telephone": "(212) 444-3400",
  "email": "west14thstreet@apple.com"
}
```

### Search API Limitations

- Returns **up to 12 stores** per query (sorted by distance)
- Requires lat/lng coordinates (not ZIP codes directly)
- Persisted query hash may change with deployments

---

## Data Source #3: Store Detail Pages (Richest Data)

### URL Pattern

```
https://www.apple.com/retail/{slug}/
```

Each page contains a `__NEXT_DATA__` JSON blob with comprehensive store details accessible by parsing the HTML.

### Store Detail Schema

```json
{
  "storeNumber": "R225",
  "locale": "en_US",
  "name": "The Summit",
  "slug": "thesummit",
  "timezone": "America/Chicago",
  "telephone": "(205) 909-2570",
  "geolocation": {
    "latitude": 33.44726,
    "longitude": -86.7285
  },
  "address": {
    "address1": "211 Summit Boulevard",
    "address2": "",
    "city": "Birmingham",
    "stateCode": "AL",
    "stateName": "Alabama",
    "postal": "35243"
  },
  "hours": {
    "alwaysOpen": false,
    "closed": false,
    "isNSO": null,
    "currentStatus": "Open until 9:00 p.m.",
    "days": [
      {
        "name": "Today",
        "formattedDate": "Feb 5",
        "formattedTime": "10:00 a.m. - 9:00 p.m.",
        "specialHours": false
      }
    ],
    "hoursData": { /* 7 days of hours */ },
    "specialHoursData": []
  },
  "operatingModel": {
    "operatingModelId": "BAU01",
    "instore": {
      "Shopping": { "services": ["SHOP", "SWS", "TradeIn", "CarrierDeals", "SelfCheckout"] },
      "Pickup/Delivery": { "services": ["APU"] },
      "Support": { "services": ["GBDI", "GB"] },
      "Learning": { "services": ["TodayApple", "PS"] },
      "Other services": { "services": ["SignLanguage", "Curbside"] }
    }
  },
  "heroImage": {
    "large": { "x2": "https://rtlimages.apple.com/..." },
    "medium": { "x2": "https://rtlimages.apple.com/..." },
    "small": { "x2": "https://rtlimages.apple.com/..." }
  },
  "programs": [
    { "id": "Shop", "header": "Come see the best of Apple at our stores." },
    { "id": "Support", "header": "We'll help you get started. And keep going." },
    { "id": "WHA", "header": "What's happening at Apple." }
  ]
}
```

### Known In-Store Services

| Category | Service ID | Label |
|----------|-----------|-------|
| Shopping | SHOP | Drop-in shopping |
| Shopping | SWS | Experience Apple Vision Pro |
| Shopping | TradeIn | Apple Trade In |
| Shopping | CarrierDeals | Carrier deals and activation |
| Shopping | SelfCheckout | Self-Checkout |
| Shopping | LimitedSHOP | Limited drop-in shopping |
| Pickup/Delivery | APU | Pick up an online order in store |
| Support | GBDI | Drop-in Genius Bar support |
| Support | GB | Genius Bar by appointment |
| Support | LimitedGB | Limited drop-in Genius Bar support |
| Learning | TodayApple | Today at Apple |
| Learning | PS | Personal Setup |
| Other | SignLanguage | Sign language interpretation |
| Other | Curbside | Pick up an online order curbside |

---

## OxyLabs Implementation Code

### Approach A: Full Directory in One Call (Web Scraper API)

```python
import requests
import json
import re

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret  # pragma: allowlist secret

def get_build_id():
    """Fetch current Next.js buildId from any Apple retail page."""
    payload = {
        "source": "universal",
        "url": "https://www.apple.com/retail/storelist/"
    }
    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )
    html = response.json()["results"][0]["content"]
    match = re.search(r'"buildId":"([^"]+)"', html)
    return match.group(1) if match else None


def get_full_store_directory(build_id):
    """Fetch the complete worldwide store directory in a single request."""
    payload = {
        "source": "universal",
        "url": f"https://www.apple.com/retail/_next/data/{build_id}/storelist.json"
    }
    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )
    content = response.json()["results"][0]["content"]
    data = json.loads(content)
    return data["pageProps"]["storeList"]


# Execute
build_id = get_build_id()
store_list = get_full_store_directory(build_id)

# Extract all US stores
us_entry = next(c for c in store_list if c["locale"] == "en_US")
us_stores = []
for state in us_entry["state"]:
    for store in state["store"]:
        us_stores.append({
            "id": store["id"],
            "name": store["name"],
            "slug": store["slug"],
            "phone": store["telephone"],
            "address1": store["address"]["address1"],
            "city": store["address"]["city"],
            "state": store["address"]["stateCode"],
            "zip": store["address"]["postalCode"]
        })

print(f"Total US stores: {len(us_stores)}")
# Save
with open("apple_stores_directory.json", "w") as f:
    json.dump(us_stores, f, indent=2)
```

### Approach B: Batch Store Detail Enrichment (Push-Pull)

```python
import requests
import json
import re
import time

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret  # pragma: allowlist secret

def submit_batch_detail_scrape(store_slugs):
    """Submit all store detail pages as a batch for async processing."""
    urls = [
        f"https://www.apple.com/retail/{slug}/"
        for slug in store_slugs
    ]

    payload = {
        "source": "universal",
        "url": urls,
        # No render needed - data is in server-rendered __NEXT_DATA__
    }

    response = requests.post(
        "https://data.oxylabs.io/v1/queries/batch",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )
    return response.json()


def parse_store_detail(html):
    """Extract __NEXT_DATA__ JSON from store detail page HTML."""
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL
    )
    if match:
        data = json.loads(match.group(1))
        return data.get("props", {}).get("pageProps", {}).get("storeDetails")
    return None


# Example: enrich all US stores
us_slugs = [s["slug"] for s in us_stores]  # From Approach A
batch = submit_batch_detail_scrape(us_slugs)

# Retrieve results (poll or use callback)
time.sleep(120)  # Wait for batch processing

enriched = []
for query in batch.get("queries", []):
    job_id = query["id"]
    result = requests.get(
        f"https://data.oxylabs.io/v1/queries/{job_id}/results",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD)
    ).json()

    for r in result.get("results", []):
        detail = parse_store_detail(r.get("content", ""))
        if detail:
            enriched.append(detail)

print(f"Enriched {len(enriched)} stores with full details")
```

### Approach C: GraphQL Store Search (Web Scraper API)

```python
import requests
import json
import urllib.parse

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret

PERSISTED_HASH = "95310df81b3cd55c84fda50c49580bff1761ce5ff9acfdb9763b97915d18f7d9"  # pragma: allowlist secret

def search_stores_by_location(lat, lng, locale="en_US"):
    """Search Apple Stores near a geographic coordinate."""
    params = urllib.parse.urlencode({
        "operationName": "StoreSearchByLocation",
        "variables": json.dumps({
            "localeId": locale,
            "latitude": lat,
            "longitude": lng
        }),
        "extensions": json.dumps({
            "persistedQuery": {
                "version": 1,
                "sha256Hash": PERSISTED_HASH
            }
        })
    })

    url = f"https://www.apple.com/api-www/graphql?{params}"

    payload = {
        "source": "universal",
        "url": url,
        "context": [
            {"key": "force_headers", "value": True},
            {"key": "headers", "value": {
                "x-apollo-operation-name": "StoreSearchByLocation",
                "apollo-require-preflight": "true"
            }}
        ]
    }

    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )

    content = response.json()["results"][0]["content"]
    data = json.loads(content)
    return data.get("data", {}).get("rmdLocale", {}).get("storesByLocation", [])


# Example: Find stores near NYC
stores = search_stores_by_location(40.7505, -74.0027)
for s in stores:
    print(f"{s['storeName']} ({s['storeNumber']}) - {s['distance']['formatted']}")
```

### curl Examples

**Full Store Directory:**
```bash
curl 'https://www.apple.com/retail/_next/data/WvJEhhQSiVnNziWwWdN-K/storelist.json'
```

**GraphQL Store Search:**
```bash
curl 'https://www.apple.com/api-www/graphql?operationName=StoreSearchByLocation&variables=%7B%22localeId%22%3A%22en_US%22%2C%22latitude%22%3A40.7505%2C%22longitude%22%3A-74.0027%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%2295310df81b3cd55c84fda50c49580bff1761ce5ff9acfdb9763b97915d18f7d9%22%7D%7D' \
  -H 'x-apollo-operation-name: StoreSearchByLocation' \
  -H 'apollo-require-preflight: true'
```

---

## Data Field Comparison: Directory vs. Detail vs. GraphQL Search

| Data Point | Store List | Store Detail Page | GraphQL Search |
|------------|:---------:|:-----------------:|:--------------:|
| Store ID/Number | ✅ | ✅ | ✅ |
| Name | ✅ | ✅ | ✅ |
| Slug | ✅ | ✅ | ✅ |
| Phone | ✅ | ✅ | ✅ |
| Email | ❌ | ❌ | ✅ |
| Address | ✅ | ✅ | ✅ |
| Coordinates | ❌ | ✅ | ✅ |
| Timezone | ❌ | ✅ | ❌ |
| Store Hours | ❌ | ✅ (full week) | ✅ (current status) |
| Special Hours | ❌ | ✅ | ❌ |
| In-Store Services | ❌ | ✅ (detailed) | ❌ |
| Operating Model | ❌ | ✅ | ❌ |
| Hero/Card Images | ❌ | ✅ | ✅ |
| Programs | ❌ | ✅ | ❌ |
| Distance | ❌ | ❌ | ✅ |
| Store Images URL | ❌ | ✅ | ✅ |

---

## Bot Protection & Rate Limiting

| Aspect | Details | OxyLabs Needed? |
|--------|---------|:--------------:|
| Bot Detection | Minimal — no observed JS challenges | Optional |
| Rate Limiting | No aggressive limiting observed | Optional |
| CSRF Protection | GraphQL requires `x-apollo-operation-name` header | Handled by custom headers |
| Authentication | None required | N/A |
| IP Blocking | Not observed during testing | Optional |

**Apple's retail site has the lightest bot protection of all retailers analyzed.** OxyLabs Web Scraper API is still recommended for reliability, automatic retries, and consistent IP rotation, but direct `requests`/`curl` calls may also work for small-scale extraction.

---

## robots.txt Analysis

**Source:** `https://www.apple.com/robots.txt`

- **User-agent: *** — All robots allowed
- `/retail/` is **NOT disallowed**
- `/api-www/` is **NOT disallowed**
- Only shop overlay pages and some China-specific paths are blocked
- **Retail sitemap exists:** `https://www.apple.com/retail/sitemap/sitemap.xml` — contains all store detail page URLs worldwide

### Sitemap Coverage

The retail sitemap at `/retail/sitemap/sitemap.xml` contains URLs for every store detail page worldwide, providing a complete enumeration of all stores without needing the storelist endpoint.

---

## Terms & Conditions

Apple's website Terms of Use (`https://www.apple.com/legal/internet-services/terms/site.html`) contain standard provisions about content ownership and restrictions on unauthorized use. No specific anti-scraping, anti-bot, or automated access clauses were identified that specifically target store locator data.

### Risk Assessment

| Factor | Risk Level | Notes |
|--------|-----------|-------|
| robots.txt compliance | **Very Low** | /retail/ and /api-www/ not disallowed; sitemap provided |
| Terms of Use | **Low** | No specific anti-scraping provisions |
| Bot detection | **Very Low** | No observed bot protection on retail pages |
| API access | **Very Low** | Public GraphQL API with only CSRF header requirement |
| Rate limiting | **Low** | No aggressive limiting; small store count (~272 US) |

---

## Store ID (storeNumber) Pattern

Apple store IDs follow the pattern `R{number}` where the number ranges from `R001` (Glendale Galleria, opened 2001) to approximately `R790` (newer stores). IDs are sequential based on opening order but have many gaps.

Examples: R001 (Glendale), R050 (The Grove), R108 (Century City), R225 (The Summit), R451 (The Americana), R720 (Tower Theatre), R790 (Hebbal, India).

---

## Quick Reference

| Item | Value |
|------|-------|
| Store Directory | `GET /retail/_next/data/{buildId}/storelist.json` |
| GraphQL API | `GET /api-www/graphql` |
| Store Detail | `GET /retail/{slug}/` (parse `__NEXT_DATA__`) |
| Retail Sitemap | `/retail/sitemap/sitemap.xml` |
| Required Headers (GraphQL) | `x-apollo-operation-name`, `apollo-require-preflight` |
| Persisted Query Hash | `95310df81b3cd55c84fda50c49580bff1761ce5ff9acfdb9763b97915d18f7d9` |
| Auth Required | None |
| US Store Count | 272 |
| Worldwide Store Count | 536 |
| Bot Protection | Minimal (CSRF header only) |
| robots.txt | /retail/ NOT disallowed |
| **OxyLabs Recommendation** | Web Scraper API (universal, no rendering) |
| **Estimated Total Calls** | ~275 (1 directory + 272 detail pages + validation) |
| **JS Rendering Needed** | No |
