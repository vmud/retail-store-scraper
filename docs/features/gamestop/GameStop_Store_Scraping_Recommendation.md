# GameStop Store Data Scraping — Research & Recommendation

---

## 1. Executive Summary

GameStop's website runs on **Salesforce Commerce Cloud (SFCC/Demandware)**. Through live research, I discovered a **fully accessible JSON API endpoint** (`Stores-FindStores`) that returns structured store data without authentication. This is the primary recommended scraping vector. A supplementary approach using individual **store detail pages** (which contain Schema.org JSON-LD structured data) provides additional fields like payment methods, descriptions, and product categories. No store-specific sitemap exists, so a geographic grid strategy is required to enumerate all ~4,000+ US locations.

---

## 2. Platform & Anti-Bot Protections

**Platform:** Salesforce Commerce Cloud (SFCC), formerly Demandware. Confirmed by URL patterns (`/on/demandware.store/Sites-gamestop-us-Site/...`), the `robots.txt` referencing `*demandware.store*`, and the OCAPI returning `MissingClientIdException`.

**Bot Protection:** Cloudflare is deployed as the front-line WAF/CDN. Every initial request triggers a Cloudflare "Verify you are human" challenge. This typically resolves via JavaScript challenge (not CAPTCHA) in a normal browser session. For programmatic access:

- Cloudflare's JS challenge must be solved — standard `requests` will fail.
- **Recommended library:** `cloudscraper`, `curl_cffi`, or `playwright`/`selenium` with `undetected-chromedriver`.
- A **residential proxy** (as noted in scope) will be essential for sustained scraping. Rotate IPs per request batch.
- Session cookies from a successful Cloudflare challenge can be reused for subsequent API calls within the same session.

**OCAPI (Salesforce native API):** The endpoint exists at `/s/Sites-gamestop-us-Site/dw/shop/v24_5/stores` but requires a `client_id` parameter and returns `MissingClientIdException` without one. This is **not publicly accessible** and should not be relied upon.

---

## 3. Primary Data Source: Stores-FindStores API

### 3.1 Endpoint

```
POST/GET https://www.gamestop.com/on/demandware.store/Sites-gamestop-us-Site/default/Stores-FindStores
```

### 3.2 Parameters

| Parameter    | Type   | Required | Description                                    |
|-------------|--------|----------|------------------------------------------------|
| `postalCode` | string | Yes*     | US zip code to search around                   |
| `lat`        | float  | Yes*     | Latitude (alternative to postalCode)           |
| `long`       | float  | Yes*     | Longitude (alternative to postalCode)          |
| `radius`     | int    | Yes      | Search radius in miles. Tested up to 300.      |

\* Either `postalCode` OR `lat`+`long` is required. Both methods confirmed working.

### 3.3 Observed Constraints

- **Maximum usable radius:** ~250-300 miles. Radius values of 300 work for moderate-density areas but may error/timeout in dense regions (e.g., the NE corridor from NYC). Use 200 miles as a safe maximum.
- **Result cap:** No explicit pagination. Testing shows up to ~200+ stores returned per query. Dense urban corridors near the limit may cause server-side errors.
- **Radius dropdown values** offered by the UI: 15, 30, 50, 100. The API accepts arbitrary values beyond these.
- **Method:** Works with both GET and POST.

### 3.4 Response Schema (JSON)

```json
{
  "action": "Stores-FindStores",
  "queryString": "postalCode=10001&radius=15",
  "locale": "default",
  "preferredStore": {},
  "stores": [
    {
      "ID": "6562",
      "name": "East 14th Street New York",
      "address1": "32 E 14th ST",
      "address2": null,
      "city": "New York",
      "postalCode": "10003",
      "latitude": 40.73530294,
      "longitude": -73.99191706,
      "phone": "(212) 242-2567",
      "stateCode": "NY",
      "countryCode": {},
      "storeHours": "refer to custom attribute, storeOperationHours",
      "image": "",
      "storeOperationHours": "[{\"day\":\"Sun\",\"open\":\"1000\",\"close\":\"2000\"}, ...]",
      "storeBrand": {},
      "storeMode": "ACTIVE",
      "storeMiddleDayClosure": false,
      "isPreferredStore": false,
      "brandIcon": "store-detail-gamestop",
      "distance": "0.94"
    }
  ],
  "locations": "...",
  "searchKey": {},
  "radius": 15,
  "actionUrl": "...",
  "googleMapsApi": "...",
  "radiusOptions": [15, 30, 50, 100],
  "storesResultsHtml": "<!-- rendered HTML with additional data attributes -->"
}
```

### 3.5 Fields Available Per Store

**From the `stores` array (structured JSON):**

| Field                   | Type    | Description                                      |
|------------------------|---------|--------------------------------------------------|
| `ID`                   | string  | Unique store identifier (e.g., "6562")           |
| `name`                 | string  | Store name                                       |
| `address1`             | string  | Street address                                   |
| `address2`             | string  | Suite/unit (nullable)                            |
| `city`                 | string  | City                                             |
| `postalCode`           | string  | Zip code                                         |
| `latitude`             | float   | Latitude coordinate                              |
| `longitude`            | float   | Longitude coordinate                             |
| `phone`                | string  | Phone number                                     |
| `stateCode`            | string  | Two-letter state code                            |
| `countryCode`          | object  | Country code (typically empty `{}`)              |
| `storeOperationHours`  | string  | JSON string of daily open/close times (24h format)|
| `storeBrand`           | object  | Brand designation (typically `{}`)               |
| `storeMode`            | string  | Status: "ACTIVE"                                 |
| `storeMiddleDayClosure`| bool    | Whether store closes midday                      |
| `isPreferredStore`     | bool    | User-context preference flag                     |
| `brandIcon`            | string  | Brand icon CSS class                             |
| `distance`             | string  | Distance from search point in miles              |

**From `storesResultsHtml` (embedded data attributes):**

| Data Attribute         | Description                                      |
|-----------------------|--------------------------------------------------|
| `data-store-id`       | Store ID                                         |
| `data-store-hours`    | Full JSON hours schedule                         |
| `data-store-open-text`| Current open/closed status text                  |
| `data-storename`      | Store name                                       |
| `data-stateprovince`  | State code                                       |
| `data-postalcode`     | Zip code                                         |
| `data-city`           | City                                             |
| `data-gtmdata`        | Google Tag Manager analytics object              |

The HTML also contains the store detail page URL in the format:
```
/store/us/{state}/{city}/{storeID}/{slug-name}-gamestop
```

---

## 4. Secondary Data Source: Store Detail Pages

### 4.1 URL Pattern

```
https://www.gamestop.com/store/us/{state_code}/{city_slug}/{store_id}/{store_name_slug}-gamestop
```

Example: `https://www.gamestop.com/store/us/ny/new-york/6562/east-14th-street-new-york-gamestop`

### 4.2 Schema.org JSON-LD

Each store detail page contains a `@type: "Store"` structured data block with **additional fields not available from the API**:

```json
{
  "@context": "https://schema.org",
  "@type": "Store",
  "name": "East 14th Street New York",
  "alternateName": "GameStop",
  "description": "Visit East 14th Street New York in New York, NY to shop for Xbox Series X/S...",
  "url": "https://www.gamestop.com/store/us/ny/new-york/6562/east-14th-street-new-york-gamestop",
  "image": "https://media.gamestop.com/i/gamestop/aff_gme_storefront",
  "knowsAbout": [
    "Video Games", "Gaming Consoles", "Xbox Series X", "Xbox Series S",
    "PS5", "Nintendo Switch", "VR", "Pokemon Cards", "Sports Cards",
    "Trading Cards", "PSA Graded Cards", "Electronics"
  ],
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "32 E 14th ST",
    "addressLocality": "New York",
    "addressRegion": "NY",
    "postalCode": "10003"
  },
  "openingHours": ["Su 10:00-20:00", "Mo 10:00-21:00"],
  "telephone": "(212) 242-2567",
  "currenciesAccepted": "USD",
  "paymentAccepted": ["Cash", "Credit Card", "Personal Checks"]
}
```

**Unique fields from detail pages (not in API):**
- `description` — templated store description mentioning services
- `knowsAbout` — product/service categories the store handles
- `paymentAccepted` — accepted payment methods
- `currenciesAccepted` — supported currencies
- `image` — storefront image URL
- `openingHours` — Schema.org formatted hours strings

---

## 5. Other Data Sources Investigated

| Source | Finding |
|--------|---------|
| **Sitemap (`sitemap_index.xml`)** | No store-specific sitemap. Contains product (0-15), image (16-60), category (61), and misc (62) sitemaps only. |
| **robots.txt** | Does not disallow `/store/` paths. The `/stores/` directory page is accessible. |
| **OCAPI (SFCC native REST API)** | Exists at `/s/Sites-gamestop-us-Site/dw/shop/v24_5/stores` but requires `client_id` — not publicly usable. |
| **`storeLocator.js`** | Confirms `Stores-FindStores` is the only store search controller, reveals `lat`/`long` parameter support and `Stores-Find` / `Stores-NoResults` actions. |
| **Google Maps API key** | Embedded in the page for map rendering — not useful for scraping. |

---

## 6. Recommended Scraping Strategy

### Phase 1: Geographic Grid Enumeration via API

Since there is no "list all stores" endpoint, use a **geographic grid** approach:

1. **Generate a grid of coordinates** covering the contiguous US (and Alaska/Hawaii/Puerto Rico/Guam if needed).
2. **Query the `Stores-FindStores` API** at each grid point with `radius=200`.
3. **Deduplicate** results by store `ID`.

**Grid Design:**
- US bounding box: lat 24.5-49.5, long -125 to -66.5
- With 200-mile radius circles, space grid points ~280 miles apart (radius overlap ensures coverage)
- Latitude step: ~4.0 degrees (280mi / 69mi per degree)
- Longitude step: varies by latitude. At 37N: ~5.0 degrees (280mi / 55mi per degree)
- Estimated grid: ~7 lat x ~12 long = **~84 grid points** for CONUS
- Add a handful of points for Alaska, Hawaii, Puerto Rico/Guam
- **Total: ~90-100 API calls** to discover all US stores

### Phase 2: Detail Page Enrichment

For each unique store discovered in Phase 1:

1. **Construct the store detail URL** from the `storesResultsHtml` link or by building it from the store data.
2. **Fetch each store detail page** and extract the JSON-LD structured data.
3. Merge the enriched data (description, knowsAbout, paymentAccepted) with the API data.

**Estimated effort:** ~4,000+ page fetches (one per store). At a respectful rate of 1-2 req/sec with rotating residential proxies, this takes about 30-60 minutes.

### Phase 3: Deduplication & Export

Merge Phase 1 and Phase 2 data, deduplicate by store ID, and export to the desired format (CSV, JSON, database).

---

## 7. Python Implementation Architecture

```python
# Recommended libraries
# pip install curl_cffi pandas

import json
import time
import re
import pandas as pd
from curl_cffi import requests  # Best Cloudflare bypass library

# --- Configuration ---
PROXY = "http://user:pass@residential-proxy:port"  # pragma: allowlist secret
BASE_URL = ("https://www.gamestop.com/on/demandware.store/"
            "Sites-gamestop-us-Site/default/Stores-FindStores")
STORE_DETAIL_BASE = "https://www.gamestop.com"
RADIUS = 200
REQUEST_DELAY = 1.5  # seconds between requests


# --- Phase 1: Grid Search ---

def generate_grid():
    """Generate lat/long grid covering contiguous US."""
    points = []
    for lat in range(25, 50, 4):         # ~4 degree steps
        for lon in range(-124, -66, 5):   # ~5 degree steps
            points.append((lat, lon))
    # Add Alaska, Hawaii, PR
    points.extend([(61.2, -150.0), (64.8, -147.7)])   # Alaska
    points.extend([(21.3, -157.8), (19.7, -155.1)])    # Hawaii
    points.append((18.2, -66.5))                        # Puerto Rico
    return points


def fetch_stores_by_coords(session, lat, lon):
    """Query the FindStores API with lat/long."""
    params = {"radius": RADIUS, "lat": lat, "long": lon}
    resp = session.get(
        BASE_URL, params=params,
        impersonate="chrome",
        proxies={"https": PROXY}
    )
    if resp.status_code == 200:
        try:
            data = resp.json()
            return data.get("stores", [])
        except Exception:
            return []
    return []


def scrape_all_stores():
    """Phase 1: Discover all stores via grid search."""
    session = requests.Session()
    all_stores = {}
    grid = generate_grid()

    for i, (lat, lon) in enumerate(grid):
        stores = fetch_stores_by_coords(session, lat, lon)
        for store in stores:
            sid = store["ID"]
            if sid not in all_stores:
                all_stores[sid] = store
        print(f"[{i+1}/{len(grid)}] lat={lat}, lon={lon} -> "
              f"{len(stores)} stores (total unique: {len(all_stores)})")
        time.sleep(REQUEST_DELAY)

    return all_stores


# --- Phase 2: Detail Page Enrichment ---

def build_store_url(store):
    """Construct a store detail URL from store data."""
    state = store["stateCode"].lower()
    city = store["city"].lower().replace(" ", "-").replace(".", "")
    sid = store["ID"]
    name_slug = store["name"].strip().lower()
    name_slug = name_slug.replace(" ", "-").replace("\u2013", "-")
    name_slug = "".join(c for c in name_slug if c.isalnum() or c == "-")
    return (f"{STORE_DETAIL_BASE}/store/us/{state}/"
            f"{city}/{sid}/{name_slug}-gamestop")


def extract_jsonld(session, url):
    """Fetch a store detail page and extract JSON-LD structured data."""
    resp = session.get(url, impersonate="chrome", proxies={"https": PROXY})
    if resp.status_code == 200:
        matches = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            resp.text, re.DOTALL
        )
        for match in matches:
            try:
                data = json.loads(match)
                if data.get("@type") == "Store":
                    return data
            except json.JSONDecodeError:
                continue
    return None


def enrich_stores(all_stores):
    """Phase 2: Fetch detail pages for additional data."""
    session = requests.Session()
    for sid, store in all_stores.items():
        url = build_store_url(store)
        jsonld = extract_jsonld(session, url)
        if jsonld:
            store["description"] = jsonld.get("description", "")
            store["knowsAbout"] = jsonld.get("knowsAbout", [])
            store["paymentAccepted"] = jsonld.get("paymentAccepted", [])
            store["currenciesAccepted"] = jsonld.get("currenciesAccepted", "")
            store["schemaUrl"] = jsonld.get("url", "")
            store["imageUrl"] = jsonld.get("image", "")
        time.sleep(REQUEST_DELAY)
    return all_stores


# --- Phase 3: Export ---

def export_data(all_stores):
    """Export to CSV and JSON."""
    records = []
    for sid, store in all_stores.items():
        hours = {}
        try:
            ops = json.loads(store.get("storeOperationHours", "[]"))
            for entry in ops:
                hours[f"hours_{entry['day']}_open"] = entry.get("open", "")
                hours[f"hours_{entry['day']}_close"] = entry.get("close", "")
        except (json.JSONDecodeError, TypeError):
            pass

        record = {
            "store_id": store["ID"],
            "name": store["name"].strip(),
            "address1": store.get("address1", ""),
            "address2": store.get("address2", ""),
            "city": store.get("city", ""),
            "state": store.get("stateCode", ""),
            "zip": store.get("postalCode", ""),
            "latitude": store.get("latitude"),
            "longitude": store.get("longitude"),
            "phone": store.get("phone", ""),
            "store_mode": store.get("storeMode", ""),
            "brand_icon": store.get("brandIcon", ""),
            "midday_closure": store.get("storeMiddleDayClosure", False),
            "description": store.get("description", ""),
            "knows_about": "|".join(store.get("knowsAbout", [])),
            "payment_accepted": "|".join(store.get("paymentAccepted", [])),
            "currencies_accepted": store.get("currenciesAccepted", ""),
            "image_url": store.get("imageUrl", ""),
            "detail_url": store.get("schemaUrl", ""),
            **hours
        }
        records.append(record)

    df = pd.DataFrame(records)
    df.to_csv("gamestop_stores.csv", index=False)
    with open("gamestop_stores.json", "w") as f:
        json.dump(list(all_stores.values()), f, indent=2)

    print(f"Exported {len(records)} stores")
    return df


# --- Main ---
if __name__ == "__main__":
    print("Phase 1: Discovering all stores via grid search...")
    all_stores = scrape_all_stores()
    print(f"Discovered {len(all_stores)} unique stores")

    print("Phase 2: Enriching with detail page data...")
    all_stores = enrich_stores(all_stores)

    print("Phase 3: Exporting...")
    df = export_data(all_stores)
    print(df.describe())
```

---

## 8. Proxy & Rate Limiting Recommendations

- **Cloudflare bypass:** Use `curl_cffi` with `impersonate="chrome"` for the most reliable TLS fingerprint matching. Alternatively, use `playwright` with stealth plugins.
- **Residential proxy rotation:** Rotate IP per batch of 10-20 requests or on any 403/challenge response.
- **Rate limiting:** 1-2 requests per second is conservative and sustainable. The grid search (Phase 1) completes in under 2 minutes. Store detail enrichment (Phase 2, ~4000 pages) takes 30-60 minutes at this rate.
- **Session management:** After solving the initial Cloudflare challenge, reuse the `cf_clearance` cookie for the session. Re-solve if it expires (typically after 15-30 minutes).
- **Error handling:** Implement exponential backoff on 429/503 responses. The API returns error pages (not JSON) when overloaded — check `Content-Type` header before parsing.

---

## 9. Complete Data Fields Summary

| Field | Source | Description |
|-------|--------|-------------|
| Store ID | API | Unique numeric identifier |
| Name | API | Store location name |
| Address 1 & 2 | API | Street address and suite |
| City | API | City name |
| State Code | API | Two-letter state abbreviation |
| Postal Code | API | US zip code |
| Latitude / Longitude | API | Geocoordinates |
| Phone | API | Store phone number |
| Store Mode | API | Active/inactive status |
| Brand Icon | API | Brand identifier (e.g., "store-detail-gamestop") |
| Store Operation Hours | API | JSON: day, open time, close time (24h military) |
| Midday Closure | API | Boolean — whether store closes midday |
| Distance | API | Miles from search point (contextual) |
| Description | Detail Page | Templated SEO description of store offerings |
| knowsAbout | Detail Page | Product/service categories (Video Games, Pokemon Cards, etc.) |
| Payment Accepted | Detail Page | Cash, Credit Card, Personal Checks |
| Currencies Accepted | Detail Page | USD |
| Store Image URL | Detail Page | Storefront image URL |
| Canonical URL | Detail Page | Full URL to store detail page |
| Opening Hours (Schema) | Detail Page | Schema.org formatted hours strings |

---

## 10. Key Findings & Caveats

1. **No "get all stores" endpoint exists.** Geographic grid search is the only viable enumeration method.
2. **The OCAPI is locked.** Salesforce Commerce Cloud's native REST API requires a `client_id` that is not publicly available.
3. **No store sitemap.** Unlike many retailers, GameStop does not publish store URLs in their XML sitemap.
4. **Store IDs are non-sequential.** They range from ~100 to ~8000+ but are sparse — iterating by ID would waste thousands of requests on 404s.
5. **All stores currently return `brandIcon: "store-detail-gamestop"`** — the ThinkGeek brand references in the JavaScript are legacy code from when ThinkGeek stores existed.
6. **The `storesResultsHtml` field** contains pre-rendered HTML with the store detail page URLs, which is essential for Phase 2 URL construction.
7. **The `storeOperationHours` field** is a JSON string embedded within the JSON response (double-encoded) — it needs to be parsed twice.
8. **The `knowsAbout` array** on detail pages appears to be uniform across stores (same product categories), but should be verified across a sample during scraping.

---

*Research conducted: February 5, 2026*
*Target: gamestop.com store locator infrastructure*
