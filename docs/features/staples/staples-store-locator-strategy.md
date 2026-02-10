# Staples Store Locator - Data Extraction Strategy

## Executive Summary

Staples operates approximately **500-600 retail stores** across the United States. This document details two primary API approaches for extracting store location data, services, features, and hours of operation, along with detailed recommendations for leveraging **OxyLabs Residential Proxies** and **Web Scraper API** (with JS rendering) to reliably execute the extraction at scale.

**Last Updated:** February 2026
**Target URLs:**
- `https://www.staples.com/stores` (Store locator page)
- `https://www.staplesconnect.com` (StaplesConnect community pages)

---

## Architecture Overview

Staples uses a **Next.js** application with server-side rendering. The store locator is embedded as an iframe/component powered by StaplesConnect (`staplesconnect.com`). Two separate API systems serve store data:

1. **Staples BFF Proxy** (`/ele-lpd/api/sparxProxy/storeLocator`) — Internal API proxied through the staples.com domain; used by the store finder UI widget
2. **StaplesConnect REST API** (`staplesconnect.com/api/store/`) — Direct REST endpoints on the community subdomain; richer data but aggressive bot protection

---

## OxyLabs Integration Recommendations

### Service Selection Matrix

| Use Case | Recommended Service | Rationale |
|----------|-------------------|-----------|
| StaplesConnect store detail API (`/api/store/{num}`) | **Web Scraper API** (universal source) | Simple GET requests; OxyLabs handles bot bypass, IP rotation, and retries automatically |
| Store locator proxy (`/ele-lpd/api/sparxProxy/storeLocator`) | **Web Scraper API** (JS rendering + fetch_resource) | Requires session cookies from rendered page; fetch_resource captures the XHR response directly |
| StaplesConnect services API | **Web Scraper API** (universal source) | Direct GET requests to REST endpoint |
| Bulk store number scanning (0001-2000) | **Web Scraper API** (Push-Pull batch) | Submit up to 5,000 URLs in a single batch request for async processing |
| Fallback / custom Playwright scripts | **Residential Proxies** | Route Playwright/Puppeteer traffic through residential IPs when you need full browser control |

### Recommendation Summary

**Primary: Use the OxyLabs Web Scraper API for all extraction tasks.** It handles bot protection bypass, IP rotation, session management, and JavaScript rendering — eliminating the need for custom Playwright/Puppeteer infrastructure. The `fetch_resource` browser instruction can capture the storeLocator XHR response directly, and the Push-Pull batch endpoint enables processing thousands of store URLs asynchronously.

**Fallback: Use OxyLabs Residential Proxies** only if you need to run custom browser automation scripts (Playwright/Puppeteer) with more control than the Web Scraper API provides.

---

### Approach A: Web Scraper API with `fetch_resource` (Store Locator)

This is the most elegant approach. Navigate to the Staples store page with JS rendering enabled, use browser instructions to enter a ZIP code and trigger the store search, then use `fetch_resource` to capture the storeLocator XHR response directly as structured JSON.

```python
import requests
import base64
import json
import time

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret  # pragma: allowlist secret

def search_stores_via_web_scraper(zip_code):
    """
    Uses OxyLabs Web Scraper API with JS rendering and browser instructions
    to trigger the store locator search and capture the XHR response.
    """
    payload = {
        "source": "universal",
        "url": "https://www.staples.com/stores",
        "render": "html",
        "browser_instructions": [
            # Wait for the page to fully load
            {"type": "wait", "wait_time_s": 3},
            # Click the "Your store" button to open the store finder panel
            {
                "type": "click",
                "selector": {
                    "type": "css",
                    "value": "[data-testid='store-locator-btn'], .store-selector-btn, a[href*='store']"
                },
                "on_error": "skip"
            },
            {"type": "wait", "wait_time_s": 2},
            # Enter ZIP code in the store search input
            {
                "type": "input",
                "selector": {
                    "type": "css",
                    "value": "input[placeholder*='city, state, zip'], input[type='text'][name*='store']"
                },
                "value": zip_code
            },
            # Click the "Look Up" button
            {
                "type": "click",
                "selector": {
                    "type": "text",
                    "value": "Look Up"
                }
            },
            # Capture the storeLocator XHR response
            {
                "type": "fetch_resource",
                "filter": "storeLocator",
                "timeout_s": 15
            }
        ]
    }

    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=180
    )

    if response.status_code == 200:
        data = response.json()
        content = data.get("results", [{}])[0].get("content", "")
        try:
            store_data = json.loads(content)
            return store_data.get("results", {}).get("stores", [])
        except json.JSONDecodeError:
            return []
    return []


# Sweep ZIP codes to discover all stores
zip_codes = [
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

all_stores = {}
for zip_code in zip_codes:
    stores = search_stores_via_web_scraper(zip_code)
    for store in stores:
        sn = store.get("storeNumber")
        if sn and sn not in all_stores:
            all_stores[sn] = store
    print(f"ZIP {zip_code}: found {len(stores)} stores, total unique: {len(all_stores)}")
    time.sleep(1)  # OxyLabs handles rate limiting, but be courteous

print(f"\nTotal unique stores discovered: {len(all_stores)}")
```

### Approach B: Web Scraper API Direct GET (StaplesConnect Detail)

For enriching store data with the StaplesConnect REST API, use the `universal` source with direct GET requests. OxyLabs handles the bot protection bypass.

```python
import requests
import json

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret  # pragma: allowlist secret

def get_store_detail(store_number):
    """
    Fetches detailed store info from StaplesConnect API via OxyLabs Web Scraper API.
    Returns full store JSON including timezone, plaza, region, services with descriptions.
    """
    payload = {
        "source": "universal",
        "url": f"https://www.staplesconnect.com/api/store/{store_number}",
        "context": [
            {"key": "follow_redirects", "value": False}
        ]
    }

    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )

    if response.status_code == 200:
        data = response.json()
        content = data.get("results", [{}])[0].get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    return None


def get_store_services(store_number):
    """
    Fetches detailed service info for a store.
    """
    payload = {
        "source": "universal",
        "url": f"https://www.staplesconnect.com/api/store/service/getStoreServicesByStoreNumber/{store_number}"
    }

    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )

    if response.status_code == 200:
        data = response.json()
        content = data.get("results", [{}])[0].get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    return None


# Example: Enrich a single store
detail = get_store_detail("1571")
services = get_store_services("1571")
if detail:
    print(json.dumps(detail, indent=2))
```

### Approach C: Web Scraper API Push-Pull Batch (Bulk Store Scan)

For scanning all possible store numbers at once, use the Push-Pull batch endpoint. Submit up to 5,000 StaplesConnect URLs in a single request for async processing.

```python
import requests
import json
import time

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret

def submit_batch_store_scan(store_numbers):
    """
    Submits a batch of store detail URLs for async processing.
    Returns job IDs for result retrieval.
    Max 5,000 URLs per batch.
    """
    urls = [
        f"https://www.staplesconnect.com/api/store/{num}"
        for num in store_numbers
    ]

    payload = {
        "source": "universal",
        "url": urls,
        "context": [
            {"key": "follow_redirects", "value": False},
            {"key": "successful_status_codes", "value": [200, 404]}
        ]
    }

    response = requests.post(
        "https://data.oxylabs.io/v1/queries/batch",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )

    if response.status_code == 200:
        return response.json()
    return None


def retrieve_batch_results(job_id):
    """Retrieves results for a completed batch job."""
    response = requests.get(
        f"https://data.oxylabs.io/v1/queries/{job_id}/results",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        timeout=60
    )
    if response.status_code == 200:
        return response.json()
    return None


# Generate all possible store numbers (0001-2000)
store_numbers = [str(i).zfill(4) for i in range(1, 2001)]

# Submit in batches of 5000 (we only have 2000, so one batch)
batch_response = submit_batch_store_scan(store_numbers)

if batch_response:
    queries = batch_response.get("queries", [])
    print(f"Submitted {len(queries)} jobs")

    # Poll for results (or use callback URL for production)
    time.sleep(60)  # Wait for processing

    valid_stores = []
    for query in queries:
        job_id = query.get("id")
        results = retrieve_batch_results(job_id)
        if results:
            for result in results.get("results", []):
                content = result.get("content", "")
                status = result.get("status_code", 0)
                if status == 200:
                    try:
                        store = json.loads(content)
                        valid_stores.append(store)
                    except json.JSONDecodeError:
                        pass

    print(f"Found {len(valid_stores)} valid stores")
```

### Approach D: Web Scraper API POST (Store Locator Direct)

Directly call the storeLocator proxy endpoint using the Web Scraper API's HTTP POST support. This bypasses the need for JS rendering entirely by making a direct API call.

```python
import requests
import base64
import json

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret

def search_stores_direct_post(zip_code, radius=200):
    """
    Calls the storeLocator proxy API directly via OxyLabs Web Scraper API
    using HTTP POST with a JSON body. No JS rendering needed.
    """
    # Base64-encode the POST body
    post_body = json.dumps({"address": zip_code, "radius": radius})
    encoded_body = base64.b64encode(post_body.encode()).decode()

    payload = {
        "source": "universal",
        "url": "https://www.staples.com/ele-lpd/api/sparxProxy/storeLocator",
        "context": [
            {"key": "http_method", "value": "post"},
            {"key": "content", "value": encoded_body},
            {"key": "force_headers", "value": True},
            {"key": "headers", "value": {
                "Content-Type": "application/json"
            }}
        ]
    }

    response = requests.post(
        "https://realtime.oxylabs.io/v1/queries",
        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
        json=payload,
        timeout=60
    )

    if response.status_code == 200:
        data = response.json()
        content = data.get("results", [{}])[0].get("content", "")
        try:
            store_data = json.loads(content)
            return store_data.get("results", {}).get("stores", [])
        except json.JSONDecodeError:
            return []
    return []
```

> **Note:** The storeLocator endpoint is session-dependent and may require cookies from a prior page visit. If this direct POST approach returns 404, fall back to Approach A (fetch_resource with JS rendering) or Approach E (Residential Proxies with Playwright).

### Approach E: Residential Proxies with Playwright (Full Control Fallback)

When you need full browser control — for example, to handle complex cookie/session flows that the Web Scraper API cannot replicate — route your Playwright automation through OxyLabs Residential Proxies.

```python
from playwright.sync_api import sync_playwright
import json
import time

OXYLABS_USERNAME = "YOUR_USERNAME"
OXYLABS_PASSWORD = "YOUR_PASSWORD"  # pragma: allowlist secret

# Residential proxy connection string
PROXY_URL = f"http://customer-{OXYLABS_USERNAME}:OXYLABS_PASSWORD@pr.oxylabs.io:7777"  # pragma: allowlist secret

# For US-specific IPs with session persistence:
PROXY_URL_US_SESSION = (
    f"http://customer-{OXYLABS_USERNAME}"
    f"-cc-US-sessid-staples001-sesstime-10"
    f":{OXYLABS_PASSWORD}@pr.oxylabs.io:7777"
)


def scrape_with_residential_proxy():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            proxy={
                "server": "http://pr.oxylabs.io:7777",
                "username": f"customer-{OXYLABS_USERNAME}-cc-US-sessid-staples001",
                "password": OXYLABS_PASSWORD,
            }
        )
        context = browser.new_context()
        page = context.new_page()

        # Navigate and establish session
        page.goto("https://www.staples.com/stores")
        page.wait_for_load_state("networkidle")

        all_stores = {}
        zip_codes = ["90210", "10001", "60601", "75201"]  # Add more

        for zip_code in zip_codes:
            # Use page.evaluate to call the API within the session context
            result = page.evaluate("""
                (zipCode) => {
                    return new Promise((resolve) => {
                        const xhr = new XMLHttpRequest();
                        xhr.open('POST',
                            '/ele-lpd/api/sparxProxy/storeLocator', true);
                        xhr.setRequestHeader('Content-Type',
                            'application/json');
                        xhr.onload = () => {
                            try {
                                resolve(JSON.parse(xhr.responseText));
                            } catch(e) {
                                resolve({error: e.message});
                            }
                        };
                        xhr.onerror = () => resolve({error: 'failed'});
                        xhr.send(JSON.stringify({
                            address: zipCode, radius: 200
                        }));
                    });
                }
            """, zip_code)

            stores = result.get("results", {}).get("stores", [])
            for store in stores:
                sn = store.get("storeNumber")
                if sn:
                    all_stores[sn] = store

            time.sleep(2)

        browser.close()
        return all_stores


# For StaplesConnect detail enrichment via residential proxy:
def enrich_via_residential_proxy(store_numbers):
    import urllib.request

    all_details = []
    for num in store_numbers:
        proxy_handler = urllib.request.ProxyHandler({
            "https": (
                f"http://customer-{OXYLABS_USERNAME}"
                f"-cc-US:{OXYLABS_PASSWORD}@pr.oxylabs.io:7777"
            )
        })
        opener = urllib.request.build_opener(proxy_handler)

        try:
            url = f"https://www.staplesconnect.com/api/store/{num}"
            req = urllib.request.Request(url)
            resp = opener.open(req, timeout=30)
            data = json.loads(resp.read().decode())
            all_details.append(data)
        except Exception as e:
            pass  # Store number doesn't exist or blocked

        time.sleep(3)

    return all_details
```

### OxyLabs Configuration Tips

| Parameter | Recommended Value | Purpose |
|-----------|------------------|---------|
| `geo_location` | `"United States"` | Ensure US-based IP for staples.com |
| `session_id` | `"staples-session-001"` | Maintain same proxy IP across requests (10 min TTL) |
| `user_agent_type` | `"desktop"` | Match typical browser user agent |
| `render` | `"html"` | Required for JS rendering / fetch_resource |
| `timeout_s` (browser instructions) | `15` | Allow time for storeLocator XHR response |
| Residential Proxy `sesstime` | `10` (minutes) | Keep same IP for session-dependent requests |
| Residential Proxy `cc` | `US` | US-only residential IPs |

### Cost Optimization

- **Approach B (direct GET to StaplesConnect)** is the most cost-effective — no JS rendering overhead, one simple request per store.
- **Approach C (batch)** is most efficient for bulk scanning — processes thousands of URLs asynchronously with a single API call.
- **Approach A (fetch_resource)** costs more per request due to JS rendering but yields the most reliable results for the session-dependent storeLocator endpoint.
- **Approach E (residential proxies)** billed by bandwidth, best for custom automation needs.
- **Avoid rendering when possible** — rendered requests consume significantly more traffic than non-rendered requests.

### Recommended Execution Plan

```
Phase 1: Bulk Store Discovery (Approach C — Push-Pull Batch)
  - Submit store numbers 0001-2000 via batch to StaplesConnect API
  - Also submit 5001-5500 to catch outlier stores
  - Filter results: 200 = valid store, 404 = not found
  - Cost: ~2,500 non-rendered requests

Phase 2: Store Discovery Gap-Fill (Approach A or D — Store Locator)
  - Use storeLocator with ~100 ZIP codes to find any stores
    missed by the number scan
  - Compare discovered store numbers against Phase 1 results
  - Cost: ~100 rendered requests (if using Approach A)

Phase 3: Service Enrichment (Approach B — Direct GET)
  - For each valid store, fetch services via StaplesConnect
  - Cost: ~600 non-rendered requests

Total estimated: ~3,200 API calls
```

---

## API #1: Store Locator Proxy (Primary - Recommended)

### Endpoint

```
POST https://www.staples.com/ele-lpd/api/sparxProxy/storeLocator
Content-Type: application/json
```

### Request Body

```json
{
  "address": "90210",
  "radius": 50
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `address` | string | Yes | ZIP code, city name, or full address |
| `radius` | number | Yes | Search radius in miles (tested up to 500) |

### Response Schema

```json
{
  "staplesURL": "//www.staples.com",
  "results": {
    "status": "SUCCESS",
    "stores": [ /* array of store objects */ ],
    "count": 10
  }
}
```

### Store Object Schema

```json
{
  "storeNumber": "1967",
  "address": {
    "addressLine1": "5665 W. Wilshire Blvd.",
    "city": "Los Angeles",
    "state": "CA",
    "zipcode": "90036",
    "country": "USA",
    "phoneNumber": "3237616404",
    "faxNumber": "3236739453"
  },
  "workingHours": [
    {
      "openTime": "8am",
      "closeTime": "9pm",
      "day": "Monday",
      "index": 1
    }
  ],
  "gmtOffset": -8,
  "latitude": 34.0628,
  "longitude": -118.352,
  "distance": 3.17,
  "placeId": "ChIJJYyMg--5woAReHfejh-9T14",
  "storeStatus": "Open",
  "storeStatusTime": "Closes at 9 pm",
  "closingSoon": false,
  "StoreOpenTime": "Open til 9pm",
  "today": 4,
  "features": [
    {
      "featureName": "PPS",
      "featureLabel": "Passport Photo Services",
      "featureTooltip": "Passport Photo Services."
    }
  ],
  "instoreServices": [
    "Print and Marketing Services",
    "Document Printing",
    "Shredding Services"
  ]
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `storeNumber` | string | 4-digit store identifier (e.g., "0001", "1967") |
| `address.addressLine1` | string | Street address |
| `address.city` | string | City name |
| `address.state` | string | 2-letter state code |
| `address.zipcode` | string | 5-digit ZIP code |
| `address.country` | string | Country code ("USA") |
| `address.phoneNumber` | string | Phone (digits only, no formatting) |
| `address.faxNumber` | string | Fax (digits only) |
| `workingHours` | array | 7 objects, one per day of week |
| `workingHours[].openTime` | string | Opening time (e.g., "8am") |
| `workingHours[].closeTime` | string | Closing time (e.g., "9pm") |
| `workingHours[].day` | string | Day name (e.g., "Monday") |
| `workingHours[].index` | number | Day index (1=Monday ... 7=Sunday) |
| `gmtOffset` | number | GMT timezone offset (e.g., -8 for PST) |
| `latitude` | number | Store latitude coordinate |
| `longitude` | number | Store longitude coordinate |
| `distance` | number | Distance from search point in miles |
| `placeId` | string | Google Places ID for the location |
| `storeStatus` | string | Current status ("Open" / "Closed") |
| `storeStatusTime` | string | Status detail (e.g., "Closes at 9 pm") |
| `closingSoon` | boolean | Whether the store is closing soon |
| `StoreOpenTime` | string | Short open time text (e.g., "Open til 9pm") |
| `today` | number | Current day index (1=Monday ... 7=Sunday) |
| `features` | array | Store feature objects (capabilities) |
| `features[].featureName` | string | Feature code (e.g., "PPS", "ISP", "CPC") |
| `features[].featureLabel` | string | Human-readable feature name |
| `features[].featureTooltip` | string | Feature description (may contain HTML) |
| `instoreServices` | array | String array of in-store service names |

### Known Feature Codes

| Code | Label |
|------|-------|
| PPS | Passport Photo Services |
| ISP | Buy online. Pickup in store |
| TS | Technology Services |
| F1 | Computer Workstation |
| STS | Ship to Store |
| CPC | Print & Marketing Services |
| UPS | UPS® Prepaid Drop-off |
| MPR | Mobile Printing |
| FSU | Full-service UPS® Shipping |

### Known In-Store Services

- Print and Marketing Services
- Document Printing
- Shredding Services
- Recycling Services
- Amazon Lockers
- Amazon Returns
- UPS Shipping & Drop-off
- iPostal1
- Tech Services
- PC Tune-Up
- Passport Services
- TSA Precheck
- Design Services
- Direct Mail
- Affirm
- Business Protection
- Gry Mattr

### Important Limitations

- **Maximum 10 stores per request** — The API always returns at most 10 stores regardless of radius. No pagination parameters accepted.
- **Session-dependent** — Requires valid session cookies from staples.com. Direct API calls without a browser session return 404.
- **Rate limiting** — Aggressive bot detection (PerimeterX/Akamai). Rapid sequential requests trigger blocks.

---

## API #2: StaplesConnect REST API (Secondary - Richer Data)

### Store Detail Endpoint

```
GET https://www.staplesconnect.com/api/store/{storeNumber}
```

Returns comprehensive store detail JSON. No authentication required, but aggressive bot protection is active.

### Store Services Endpoint

```
GET https://www.staplesconnect.com/api/store/service/getStoreServicesByStoreNumber/{storeNumber}
```

### StaplesConnect Store Detail Schema

```json
{
  "id": 1571,
  "address": {
    "address_1": "1100 State Route 35",
    "address_2": "STE A",
    "city": "Ocean Township",
    "region": "NJ",
    "postal_code": "07712",
    "country": "US",
    "latitude": 40.2395,
    "longitude": -74.0362,
    "urlAddress": "1100-state-route-35",
    "urlState": "nj",
    "urlCity": "ocean-township"
  },
  "name": "Staples Retail Store 1571 - Ocean Township NJ",
  "latitude": 40.2395,
  "longitude": -74.0362,
  "faxNumber": "7325172393",
  "phoneNumber": "7329189446",
  "storeTitle": "Staples Ocean Township, NJ",
  "storeNumber": "1571",
  "timezone": "America/New_York",
  "storeHours": [
    {
      "open24Hr": false,
      "close24Hr": false,
      "open": "08:00 AM",
      "close": "09:00 PM",
      "formattedStoreHours": "8:00 AM - 9:00 PM",
      "dayShort": "MON",
      "day": "MONDAY"
    }
  ],
  "plazaMall": "Plaza at Ocean",
  "publishedStatus": "ACTIVE",
  "storeRegion": "R230",
  "storeDistrict": "D155",
  "storeDivision": "Northeast",
  "storeServices": [
    {
      "serviceId": 1,
      "serviceName": "Print and Marketing Services",
      "serviceDescription": "...",
      "serviceImageUrl": "...",
      "serviceLandingPageUrl": "...",
      "active": true
    }
  ],
  "location": {
    "type": "Point",
    "coordinates": [-74.0362, 40.2395]
  }
}
```

### Additional StaplesConnect Fields vs. Locator API

| Field | Description |
|-------|-------------|
| `id` | Internal database ID |
| `address.address_2` | Suite/unit number |
| `address.urlAddress` | URL-friendly address slug |
| `address.urlState` | URL-friendly state slug |
| `address.urlCity` | URL-friendly city slug |
| `timezone` | IANA timezone (e.g., "America/New_York") |
| `storeHours[].formattedStoreHours` | Formatted hours string |
| `plazaMall` | Shopping center/plaza name |
| `publishedStatus` | Store status ("ACTIVE") |
| `storeRegion` | Internal region code (e.g., "R230") |
| `storeDistrict` | Internal district code (e.g., "D155") |
| `storeDivision` | Division name (e.g., "Northeast") |
| `storeServices[].serviceId` | Service numeric ID |
| `storeServices[].serviceDescription` | Full service description |
| `storeServices[].serviceImageUrl` | Service icon/image URL |
| `storeServices[].serviceLandingPageUrl` | Service detail page URL |
| `storeServices[].active` | Whether service is currently active |
| `location` | GeoJSON Point object |

---

## Store Number Intelligence

### Known Range

- **Minimum:** 0001 (Brighton, MA)
- **Maximum observed:** 5311
- **Majority range:** 0001 - 1967 (most stores)
- **Outliers:** 5308, 5311 (very high numbers, likely special/new stores)
- **Pattern:** Non-sequential. Not all numbers in range are valid stores.

### Estimated Total Store Count

Based on geographic sampling with ~90 ZIP codes, **515 unique stores** were found. With denser sampling, the actual count is estimated at **~500-600 active stores**.

---

## Data Field Comparison: Locator vs. StaplesConnect

| Data Point | Locator API | StaplesConnect API |
|------------|:-----------:|:------------------:|
| Store number | ✅ | ✅ |
| Address | ✅ | ✅ (more detail) |
| Phone/Fax | ✅ | ✅ |
| Coordinates | ✅ | ✅ |
| Working hours | ✅ | ✅ (formatted) |
| Features/capabilities | ✅ | ❌ |
| In-store services | ✅ (names only) | ✅ (full detail) |
| Store status | ✅ (real-time) | ❌ |
| Distance from search | ✅ | ❌ |
| GMT offset | ✅ | ❌ |
| Timezone (IANA) | ❌ | ✅ |
| Google Place ID | ✅ | ❌ |
| Plaza/Mall name | ❌ | ✅ |
| Region/District/Division | ❌ | ✅ |
| Service descriptions | ❌ | ✅ |
| Service images | ❌ | ✅ |
| Published status | ❌ | ✅ |
| URL-friendly slugs | ❌ | ✅ |
| GeoJSON location | ❌ | ✅ |

---

## Bot Protection & Rate Limiting

### Observed Protections

| Aspect | Details | OxyLabs Mitigation |
|--------|---------|-------------------|
| **Bot Detection** | PerimeterX / Akamai JS challenge | Web Scraper API bypasses automatically |
| **Rate Limiting** | Blocks after ~50-100 rapid requests | Residential Proxies rotate IPs; Web Scraper API handles retries |
| **CORS** | StaplesConnect API blocks cross-origin | Web Scraper API makes server-side requests (no CORS) |
| **Session Requirement** | storeLocator requires valid cookies | `fetch_resource` with JS rendering maintains session; or use `session_id` context |
| **IP Blocking** | Temporary blocks on aggressive patterns | Residential Proxies provide fresh IPs per request |

---

## robots.txt Analysis

**Source:** `https://www.staples.com/robots.txt` (Last modified: 2024-12-17)

### Key Observations

- **User-agent: *** — All robots allowed
- `/stores` path is **NOT disallowed** — Store pages are crawlable
- `*/storelocator/storesSearch.json*` is **explicitly disallowed** — Legacy JSON store search endpoint is blocked
- `*/StaplesStoreInventory*` is **disallowed**
- **Store sitemap exists:** `https://sitemap.staples.com/sitemap-index-stores.xml.gz` is referenced but was not accessible during testing

---

## Terms & Conditions Summary

**Source:** `https://www.staples.com/hc?id=52e40651-0852-4ad7-a532-45017c287d50`

### Relevant Clauses

1. **COPYRIGHTS, TRADEMARKS & RESTRICTIONS:** Prohibits reproduction, republication, or distribution of Materials from the Site without prior written permission.

2. **CONDUCT OF USERS:** Prohibits transmitting unlawful materials, viruses, or violating applicable laws.

3. **No explicit anti-scraping clause** — The T&C does not specifically mention automated access, web scraping, bots, or data mining. However, the general copyright/material reproduction restrictions apply broadly.

### Risk Assessment

| Factor | Risk Level | Notes |
|--------|-----------|-------|
| robots.txt compliance | **Low** | /stores not disallowed; storesSearch.json is |
| Terms of Use | **Medium** | No specific anti-scraping clause, but general material reproduction restriction exists |
| Bot detection | **Low** (with OxyLabs) | Web Scraper API and Residential Proxies effectively bypass bot detection |
| API access | **Low** (with OxyLabs) | APIs not authenticated; OxyLabs handles session/cookie management |

---

## Quick Reference

| Item | Value |
|------|-------|
| Primary API | `POST /ele-lpd/api/sparxProxy/storeLocator` |
| Secondary API | `GET https://www.staplesconnect.com/api/store/{num}` |
| Services API | `GET https://www.staplesconnect.com/api/store/service/getStoreServicesByStoreNumber/{num}` |
| Auth Required | No (session cookies needed for primary) |
| Max Results | 10 per locator query |
| Store Count | ~500-600 active stores |
| Store Number Range | 0001 - 5311 (sparse) |
| robots.txt | /stores NOT disallowed |
| Bot Protection | PerimeterX/Akamai JS challenge |
| **OxyLabs Web Scraper API** | `https://realtime.oxylabs.io/v1/queries` (Realtime) |
| **OxyLabs Batch Endpoint** | `https://data.oxylabs.io/v1/queries/batch` (Push-Pull, up to 5,000 URLs) |
| **OxyLabs Residential Proxy** | `pr.oxylabs.io:7777` (HTTP/HTTPS/SOCKS5) |
| **Recommended Approach** | Approach C (batch scan) + Approach B (detail enrichment) |
