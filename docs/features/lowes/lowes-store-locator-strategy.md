# Lowe's Store Locator - Data Extraction Strategy

## Overview

This document describes how to programmatically extract structured store data from Lowe's store locator system. Lowe's operates approximately **1,761 stores** across 50 US states and the District of Columbia.

Unlike Home Depot (which exposes a public GraphQL API), Lowe's store data is primarily accessed through **server-rendered HTML pages** with embedded JSON data. There is no public unauthenticated REST or GraphQL API for store data. The recommended approach is a two-phase HTML scraping strategy.

## Architecture

Lowe's store locator is a React application with a Redux state store, served from:
- **Web App**: `https://www.lowes.com/store`
- **Store Detail Pages**: `https://www.lowes.com/store/{State}-{City}/{StoreNumber}`
- **Store Directory**: `https://www.lowes.com/Lowes-Stores`
- **State Directory**: `https://www.lowes.com/Lowes-Stores/{StateName}/{StateCode}`
- **CDN Assets**: `https://www.lowescdn.com/store-locator/`
- **Internal API** (not publicly accessible): `storedataservice.storelocator.svc.cluster.local:8080`

The store locator client bundle references an internal `/store/api/search` endpoint, but this is proxied through the server-side rendering layer and is **not directly accessible** as a public API.

---

## Data Access Methods

### Method 1: Store Detail Pages (Primary - Recommended)

Each store has a detail page at:
```
https://www.lowes.com/store/{anything}/{storeNumber}
```

**Key finding:** Only the store number in the URL path matters. The state/city portion is ignored by the server. For example, `/store/XX-Test/1548` returns the same data as `/store/NJ-Eatontown/1548`.

The store detail page HTML contains an embedded JSON object with the full store data. This JSON is part of the server-side rendered Redux initial state.

**Extraction Pattern:**
```python
import requests
import json
import re

def extract_store_data(store_number):
    """Extract store data from the Lowe's store detail page."""
    url = f"https://www.lowes.com/store/X-X/{store_number}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible)",
        "Accept": "text/html"
    }
    resp = requests.get(url, headers=headers)

    if resp.status_code == 404:
        return None

    html = resp.text

    # Find the embedded JSON store data
    # The data starts with {"_id":" and is a complete JSON object
    idx = html.find('"_id":"')
    if idx == -1:
        return None

    # Walk backwards to find the opening brace
    start = idx
    for i in range(idx, max(0, idx - 100), -1):
        if html[i] == '{':
            start = i
            break

    # Find the matching closing brace
    depth = 0
    end = start
    for i in range(start, min(len(html), start + 10000)):
        if html[i] == '{':
            depth += 1
        elif html[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    try:
        return json.loads(html[start:end])
    except json.JSONDecodeError:
        return None
```

**Response Data Schema:**
```json
{
  "_id": "63994ee18b168758f99b3af1",
  "zip": "07724",
  "address": "118 Highway 35",
  "storeHours": [
    {
      "day": {
        "day": "Thursday",
        "open": "06.00.00",
        "close": "21.00.00"
      },
      "label": "Thursday",
      "open": "6:00 am",
      "close": "9:00 pm",
      "isCurrentDay": true,
      "isHoliday": false,
      "is24Open": false
    }
  ],
  "city": "Eatontown",
  "bisName": "LOWE'S OF EATONTOWN, NJ",
  "phone": "(732) 544-5820",
  "storeName": "Eatontown Lowe's",
  "fax": "(732) 544-5821",
  "proServicesDesk": "(732) 544-5849",
  "proFax": "(732) 544-5823",
  "toolPhone": "",
  "lat": "40.296715",
  "long": "-74.056353",
  "timeZone": "America/New_York",
  "storeDescription": "Working on a project? ...",
  "storeFeature": "Garden Center,Key Copy,Dog-Friendly,Pickup Lockers,Truck Delivery",
  "corpNumber": "29",
  "areaNumber": "1243",
  "regionNumber": "30",
  "storeType": "1",
  "storeStatusCd": "1",
  "openDate": "2005-10-12",
  "country": "US",
  "id": "1548",
  "state": "NJ",
  "stateFullName": "New Jersey",
  "pageUrl": "https://www.lowes.com/store/NJ-Eatontown/1548",
  "store_name": "Eatontown Lowe's",
  "bis_name": "LOWE'S OF EATONTOWN, NJ"
}
```

---

### Method 2: State Directory Pages (For Building Store Inventory)

State directory pages list all stores per state with basic info and store IDs.

**URL Pattern:**
```
https://www.lowes.com/Lowes-Stores/{StateName}/{StateCode}
```

**Example:** `https://www.lowes.com/Lowes-Stores/Texas/TX`

**Extraction:** Parse `storeName` fields from the embedded JSON:
```python
def get_store_ids_for_state(state_name, state_code):
    """Get all store IDs and names for a state from the directory page."""
    url = f"https://www.lowes.com/Lowes-Stores/{state_name}/{state_code}"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible)"})
    html = resp.text

    # Extract store names from embedded data
    name_pattern = r'"storeName"\s*:\s*"([^"]+)"'
    names = list(set(re.findall(name_pattern, html)))

    # Extract store URLs/IDs from links
    store_pattern = r'href="/store/[^"]*/(\d+)"'
    store_ids = list(set(re.findall(store_pattern, html)))

    # Also extract from the embedded city data (catches collapsed cities)
    id_pattern = r'"id"\s*:\s*"(\d{4})"'
    embedded_ids = list(set(re.findall(id_pattern, html)))

    all_ids = list(set(store_ids + embedded_ids))
    return all_ids, names
```

### Method 3: Main Store Directory (List All States)

**URL:** `https://www.lowes.com/Lowes-Stores`

Returns a page listing all 51 state/territory entries with links.

---

## Complete Data Schema Per Store

| Category | Field | Type | Example |
|----------|-------|------|---------|
| **Identity** | id | String | "1548" |
| | _id | String | "63994ee18b168758f99b3af1" (MongoDB ObjectId) |
| | storeName | String | "Eatontown Lowe's" |
| | store_name | String | "Eatontown Lowe's" (alias) |
| | bisName / bis_name | String | "LOWE'S OF EATONTOWN, NJ" |
| | storeType | String | "1" (retail) |
| | storeStatusCd | String | "1" (active) |
| | openDate | String | "2005-10-12" |
| | pageUrl | String | "https://www.lowes.com/store/NJ-Eatontown/1548" |
| **Address** | address | String | "118 Highway 35" |
| | city | String | "Eatontown" |
| | state | String | "NJ" |
| | stateFullName | String | "New Jersey" |
| | zip | String | "07724" |
| | country | String | "US" |
| **Geolocation** | lat | String | "40.296715" |
| | long | String | "-74.056353" |
| | timeZone | String | "America/New_York" |
| **Phone Numbers** | phone | String | "(732) 544-5820" |
| | fax | String | "(732) 544-5821" |
| | proServicesDesk | String | "(732) 544-5849" |
| | proFax | String | "(732) 544-5823" |
| | toolPhone | String | "" |
| **Organization** | corpNumber | String | "29" |
| | areaNumber | String | "1243" |
| | regionNumber | String | "30" |
| **Services/Features** | storeFeature | String (CSV) | "Garden Center,Key Copy,Dog-Friendly,Pickup Lockers,Truck Delivery" |
| **Description** | storeDescription | String | "Working on a project? ..." |
| **Hours** | storeHours | Array | See hours schema below |

**Hours Schema (per day):**
```json
{
  "day": {
    "day": "Monday",
    "open": "06.00.00",
    "close": "21.00.00"
  },
  "label": "Monday",
  "open": "6:00 am",
  "close": "9:00 pm",
  "isCurrentDay": false,
  "isHoliday": false,
  "is24Open": false
}
```

**Known storeFeature values (comma-separated):**
- Garden Center
- Key Copy
- Dog-Friendly
- Pickup Lockers
- Truck Delivery
- Truck Rental

---

## Recommended Extraction Strategy

### Phase 1: Build Complete Store Inventory (51 HTTP requests)

Fetch all 51 state directory pages and extract store IDs and names.

```python
import requests
import re
import time
import json

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
    ("West-Virginia", "WV"), ("Wisconsin", "WI"), ("Wyoming", "WY")
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible)", "Accept": "text/html"}

def get_all_store_ids():
    """Get all store IDs from all state directory pages."""
    all_stores = []
    for state_name, state_code in STATES:
        url = f"https://www.lowes.com/Lowes-Stores/{state_name}/{state_code}"
        resp = requests.get(url, headers=HEADERS)
        html = resp.text

        # Extract store links (href pattern)
        link_ids = set(re.findall(r'href="/store/[^"]*/(\d+)"', html))

        # Extract embedded store names and IDs
        name_matches = re.findall(r'"storeName"\s*:\s*"([^"]+)"', html)

        for sid in link_ids:
            all_stores.append({"store_id": sid, "state": state_code})

        time.sleep(1)  # Respect rate limits
        print(f"{state_code}: {len(link_ids)} stores")

    return all_stores
```

### Phase 2: Fetch Detailed Store Data (~1,761 HTTP requests)

For each store ID, fetch the store detail page and extract the embedded JSON.

```python
def get_store_details(store_id):
    """Fetch full store details from the store page."""
    # The URL path doesn't matter - only the store number
    url = f"https://www.lowes.com/store/X-X/{store_id}"
    resp = requests.get(url, headers=HEADERS)

    if resp.status_code == 404:
        return None

    html = resp.text
    idx = html.find('"_id":"')
    if idx == -1:
        return None

    start = idx
    for i in range(idx, max(0, idx - 100), -1):
        if html[i] == '{':
            start = i
            break

    depth = 0
    end = start
    for i in range(start, min(len(html), start + 10000)):
        if html[i] == '{':
            depth += 1
        elif html[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    try:
        data = json.loads(html[start:end])
        return data
    except json.JSONDecodeError:
        return None


def get_all_stores():
    """Main function: get all store IDs, then fetch details."""
    store_ids = get_all_store_ids()

    all_data = []
    for i, store in enumerate(store_ids):
        details = get_store_details(store["store_id"])
        if details:
            all_data.append(details)

        if i % 50 == 0:
            print(f"Processed {i}/{len(store_ids)}")

        time.sleep(1)  # Respect rate limits

    return all_data
```

### Phase 3: Export

```python
import csv

def export_to_csv(stores, filename="lowes_stores.csv"):
    fieldnames = [
        "id", "storeName", "bisName", "storeType", "storeStatusCd",
        "address", "city", "state", "stateFullName", "zip", "country",
        "lat", "long", "timeZone",
        "phone", "fax", "proServicesDesk", "proFax", "toolPhone",
        "storeFeature", "corpNumber", "areaNumber", "regionNumber",
        "openDate", "storeDescription"
    ]

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for store in stores:
            # Flatten storeHours into separate columns if needed
            row = {k: store.get(k, "") for k in fieldnames}
            writer.writerow(row)

    # Also export hours separately
    with open("lowes_store_hours.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["store_id", "day", "open_raw", "close_raw", "open", "close", "is24Open", "isHoliday"])
        for store in stores:
            for h in store.get("storeHours", []):
                writer.writerow([
                    store["id"],
                    h["day"]["day"],
                    h["day"]["open"],
                    h["day"]["close"],
                    h.get("open", ""),
                    h.get("close", ""),
                    h.get("is24Open", False),
                    h.get("isHoliday", False)
                ])
```

---

## URL Patterns

| Resource | URL Pattern | Example |
|----------|-------------|---------|
| Store Locator | `/store` | `https://www.lowes.com/store` |
| Store Directory | `/Lowes-Stores` | `https://www.lowes.com/Lowes-Stores` |
| State Directory | `/Lowes-Stores/{StateName}/{StateCode}` | `/Lowes-Stores/Texas/TX` |
| Store Detail | `/store/{State}-{City}/{StoreNumber}` | `/store/NJ-Eatontown/1548` |
| Canonical Store | `/store/{State}-{City}/{StoreNumber}` | (from `canonicalStoreUrl` field) |

**Important:** The store detail URL only requires the store number. The state-city path segment is cosmetic and ignored by the server. `/store/X-X/1548` works identically to `/store/NJ-Eatontown/1548`.

---

## Rate Limiting & Bot Protection

### Observed Protections
- **PerimeterX**: Lowe's uses PerimeterX bot detection (observed endpoint: `/CU1pC1/NNZ/y1w/...`). This system fingerprints browsers and monitors request patterns.
- **No Public API**: Unlike Home Depot, there is no public GraphQL or REST API. All store data is served through server-rendered HTML pages.
- **No Authentication Required**: Store detail and directory pages are publicly accessible without login.

### Recommended Practices
- Use realistic User-Agent headers
- Add 1-2 second delays between requests
- For Phase 1 (51 state pages): ~1-2 minutes total
- For Phase 2 (1,761 detail pages): ~30-60 minutes with 1s delays
- Monitor for 403/429 responses and implement exponential backoff
- Consider running in batches over multiple sessions
- Rotate delays randomly (0.5-2s) to appear more natural

---

## Terms of Use Considerations

Lowe's Terms & Conditions contain relevant restrictions:

1. **No robots/spiders**: Explicitly prohibits "Use any robot, spider, site search/retrieval application or other manual or automatic device or process to retrieve, index, data mine or in any way reproduce or circumvent the navigational structure or presentation of the Site or its contents."
2. **No infrastructure overload**: Prohibits "taking any action that imposes an unreasonable or disproportionately large load on Lowe's infrastructure."
3. **Anti-scraping in reseller context**: Prohibits "extracting, scraping, mining, copying or otherwise gathering information from the Site in connection with your sale or another party's sale of products."

### robots.txt Analysis
- `/store/` pages are **NOT disallowed** (only stacked pages like `/store/*/pl/*` are blocked)
- `/Lowes-Stores` directory pages are **NOT disallowed**
- `/search` pages ARE disallowed
- Sitemap is at: `https://www.lowes.com/sitemap.xml`

---

## Store Count Summary (as of February 2026)

Total: **~1,761 stores**

Largest states: TX (151), FL (132), NC (117), CA (112), OH (84), PA (83), NY (70), VA (69), GA (65), TN (60)

---

## Key Differences from Home Depot

| Feature | Lowe's | Home Depot |
|---------|--------|------------|
| **API Access** | No public API | Public GraphQL API |
| **Data Source** | Server-rendered HTML with embedded JSON | Apollo GraphQL endpoint |
| **Authentication** | None required for pages | None required for API |
| **Store Count** | ~1,761 | ~2,021 |
| **Data Format** | JSON embedded in HTML (Redux state) | Direct JSON API responses |
| **Features Field** | Comma-separated string | Individual boolean fields |
| **Hours Format** | Array of day objects with raw/formatted times | Nested object per day |
| **Coordinates** | Strings ("40.296715") | Floats (40.296715) |
| **Store ID Range** | 4-digit numbers (0001-3068+) | 4-digit (0100-8999) |
| **Extraction Method** | HTML parsing + JSON extraction | Direct API calls |
| **Requests for Full Scrape** | ~1,812 (51 state + 1,761 detail) | ~2,075 (54 state + 2,021 detail) |

---

## Quick Reference: Minimal Working Example

```bash
# Get store detail for store #1548 (returns full HTML page with embedded JSON)
curl -s 'https://www.lowes.com/store/X-X/1548' \
  -H 'User-Agent: Mozilla/5.0 (compatible)' | \
  grep -oP '"_id":"[^}]*' | head -1

# Get all store links for Texas
curl -s 'https://www.lowes.com/Lowes-Stores/Texas/TX' \
  -H 'User-Agent: Mozilla/5.0 (compatible)' | \
  grep -oP 'href="/store/[^"]*/(\d+)"' | sort -u
```

```python
# Quick test: fetch one store
import requests, json

resp = requests.get(
    "https://www.lowes.com/store/X-X/1548",
    headers={"User-Agent": "Mozilla/5.0 (compatible)"}
)
html = resp.text
idx = html.find('"_id":"')
start = html.rfind('{', max(0, idx - 100), idx)
depth, end = 0, start
for i in range(start, start + 10000):
    if html[i] == '{': depth += 1
    if html[i] == '}':
        depth -= 1
        if depth == 0: end = i + 1; break
store = json.loads(html[start:end])
print(f"{store['id']} - {store['storeName']}, {store['city']}, {store['state']}")
print(f"Features: {store['storeFeature']}")
print(f"Phone: {store['phone']}")
```
