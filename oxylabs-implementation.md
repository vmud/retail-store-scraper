# Oxylabs Implementation Guide for Python Developers

This guide provides comprehensive documentation for implementing Oxylabs Residential Proxy and Web Scraper API services in Python projects.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Residential Proxies](#residential-proxies)
   - [Authentication](#authentication)
   - [Basic Usage](#basic-usage)
   - [Location Targeting](#location-targeting)
   - [Session Control](#session-control)
   - [Protocols](#protocols)
3. [Web Scraper API](#web-scraper-api)
   - [Integration Methods](#integration-methods)
   - [Sources and Targets](#sources-and-targets)
   - [JavaScript Rendering](#javascript-rendering)
   - [Browser Instructions](#browser-instructions)
4. [Python SDK](#python-sdk)
5. [Best Practices](#best-practices)
6. [Error Handling](#error-handling)
7. [Response Codes Reference](#response-codes-reference)

---

## Getting Started

### Prerequisites

- Python 3.5 or above
- Oxylabs account with API credentials (username and password)
- Sign up at: https://oxylabs.io or start a free trial

### Installation

```bash
pip install oxylabs
pip install requests  # For direct API usage
```

---

## Residential Proxies

Residential Proxies contain real IP addresses provided by Internet Service Providers (ISPs). These IPs are attached to physical devices across the globe, making them ideal for replicating human behavior and avoiding blocks.

### Key Features
- Automatic IP rotation
- Coverage in 195+ locations
- Country, city, state, continent, ZIP code, and coordinate-level targeting
- Session control (up to 24 hours)
- HTTP, HTTPS, and SOCKS5 protocol support

### Authentication

**Proxy Entry Point:**
```
pr.oxylabs.io:7777
```

**Credential Format:**
```
customer-USERNAME:PASSWORD
```

### Basic Usage

```python
import urllib.request

username = 'YOUR_USERNAME'
password = 'YOUR_PASSWORD'

# Create proxy entry point
entry = f'http://customer-{username}:{password}@pr.oxylabs.io:7777'

# Configure proxy handler
proxy_handler = urllib.request.ProxyHandler({
    'http': entry,
    'https': entry,
})

# Build opener and make request
opener = urllib.request.build_opener(proxy_handler)
response = opener.open('https://ip.oxylabs.io/location')
print(response.read())
```

**Using the `requests` library:**

```python
import requests

username = 'YOUR_USERNAME'
password = 'YOUR_PASSWORD'

proxies = {
    'http': f'http://customer-{username}:{password}@pr.oxylabs.io:7777',
    'https': f'http://customer-{username}:{password}@pr.oxylabs.io:7777',
}

response = requests.get('https://ip.oxylabs.io/location', proxies=proxies)
print(response.text)
```

### Location Targeting

#### Country Targeting

Add `cc-COUNTRY_CODE` to the username string using ISO 3166-1 alpha-2 format:

```python
import urllib.request

username = 'YOUR_USERNAME'
password = 'YOUR_PASSWORD'
country = 'DE'  # Germany

entry = f'http://customer-{username}-cc-{country}:{password}@pr.oxylabs.io:7777'

proxy_handler = urllib.request.ProxyHandler({
    'http': entry,
    'https': entry,
})

opener = urllib.request.build_opener(proxy_handler)
print(opener.open('https://ip.oxylabs.io/location').read())
```

**Common Country Codes:**
| Country | Code |
|---------|------|
| United States | US |
| United Kingdom | GB |
| Germany | DE |
| France | FR |
| Japan | JP |
| Australia | AU |
| Canada | CA |

#### City Targeting

Add `city-CITY_NAME` along with the country code:

```python
# London, UK proxy
entry = f'http://customer-{username}-cc-GB-city-london:{password}@pr.oxylabs.io:7777'

# For cities with spaces, replace space with underscore
# St. Petersburg: city-st_petersburg
# Rio de Janeiro: city-rio_de_janeiro
```

#### State Targeting (US Only)

```python
# California proxy
entry = f'http://customer-{username}-st-us_california:{password}@pr.oxylabs.io:7777'
```

#### Country-Specific Entry Nodes

For higher performance, use country-specific entry points:

| Country | Entry Point |
|---------|-------------|
| USA | us-pr.oxylabs.io:10000 |
| UK | gb-pr.oxylabs.io:20000 |
| Germany | de-pr.oxylabs.io:30000 |
| France | fr-pr.oxylabs.io:40000 |
| Japan | jp-pr.oxylabs.io:40000 |

```python
# Using US-specific entry node
entry = f'http://customer-{username}:{password}@us-pr.oxylabs.io:10000'
```

### Session Control

To keep the same IP across multiple requests, use the `sessid` parameter:

```python
import urllib.request
import random

username = 'YOUR_USERNAME'
password = 'YOUR_PASSWORD'
country = 'DE'
session_id = random.random()  # or any alphanumeric string

entry = f'http://customer-{username}-cc-{country}-sessid-{session_id}:{password}@pr.oxylabs.io:7777'

proxy_handler = urllib.request.ProxyHandler({
    'http': entry,
    'https': entry,
})

opener = urllib.request.build_opener(proxy_handler)

# All requests with the same session_id will use the same IP
for i in range(5):
    response = opener.open('https://ip.oxylabs.io/location')
    print(response.read())
```

**Session Time Extension:**

By default, sessions expire after 10 minutes or 60 seconds of inactivity. Use `sesstime` to extend (max 1440 minutes / 24 hours):

```python
# Keep session for 30 minutes
session_time = 30  # minutes
entry = f'http://customer-{username}-cc-{country}-sessid-{session_id}-sesstime-{session_time}:{password}@pr.oxylabs.io:7777'
```

### Protocols

**HTTP (default):**
```python
entry = f'http://customer-{username}:{password}@pr.oxylabs.io:7777'
```

**HTTPS (encrypted):**
```python
entry = f'https://customer-{username}:{password}@pr.oxylabs.io:7777'
```

**SOCKS5:**
```python
import requests

proxies = {
    'http': f'socks5h://customer-{username}:{password}@pr.oxylabs.io:7777',
    'https': f'socks5h://customer-{username}:{password}@pr.oxylabs.io:7777',
}
```

**Note:** SOCKS5 does not support country-specific entry nodes. Use username parameters for location targeting.

---

## Web Scraper API

The Web Scraper API is an all-in-one web data collection platform that handles crawling URLs, bypassing IP blocks, data parsing, and cloud storage delivery.

### API Endpoint

```
POST https://realtime.oxylabs.io/v1/queries
```

### Integration Methods

#### 1. Realtime (Synchronous)

Best for simple requests. Keep connection open until completion.

```python
import requests
from pprint import pprint

payload = {
    'source': 'universal',
    'url': 'https://example.com',
    'geo_location': 'United States',
}

response = requests.post(
    'https://realtime.oxylabs.io/v1/queries',
    auth=('YOUR_USERNAME', 'YOUR_PASSWORD'),
    json=payload,
)

pprint(response.json())
```

**Important:** Set client timeout to 180 seconds for rendered pages.

#### 2. Push-Pull (Asynchronous)

Recommended for large-scale operations. Submit job, receive notification when complete.

```python
import asyncio
from oxylabs import AsyncClient

async def main():
    client = AsyncClient('YOUR_USERNAME', 'YOUR_PASSWORD')
    
    tasks = [
        client.universal.scrape_url(
            'https://example.com',
            timeout=35,
            poll_interval=3,
        ),
        client.universal.scrape_url(
            'https://another-site.com',
            timeout=45,
            poll_interval=5,
        ),
    ]
    
    for future in asyncio.as_completed(tasks):
        result = await future
        print(result.raw)

asyncio.run(main())
```

#### 3. Proxy Endpoint

Use the API like a traditional proxy:

```python
from oxylabs import ProxyClient

proxy = ProxyClient('YOUR_USERNAME', 'YOUR_PASSWORD')

# Add optional headers
proxy.add_user_agent_header('desktop_chrome')
proxy.add_geo_location_header('Germany')
proxy.add_render_header('html')

result = proxy.get('https://www.example.com')
print(result.text)
```

### Sources and Targets

| Target | URL Source | Query/ID Source |
|--------|------------|-----------------|
| Any website | `universal` | N/A |
| Amazon | `amazon` | `amazon_product`, `amazon_search` |
| Google | `google` | `google_search`, `google_ads` |
| Bing | `bing` | `bing_search` |
| Walmart | `walmart` | `walmart_search`, `walmart_product` |
| eBay | `ebay` | `ebay_search`, `ebay_product` |

### Basic Request Examples

**Universal Source (Any Website):**

```python
import requests

payload = {
    'source': 'universal',
    'url': 'https://example.com/product-page',
}

response = requests.post(
    'https://realtime.oxylabs.io/v1/queries',
    auth=('USERNAME', 'PASSWORD'),
    json=payload,
)

print(response.json())
```

**Amazon Product:**

```python
payload = {
    'source': 'amazon_product',
    'query': 'B07FZ8S74R',  # ASIN
    'geo_location': '90210',
    'parse': True,
}
```

**Google Search:**

```python
payload = {
    'source': 'google_search',
    'query': 'best python libraries',
    'geo_location': 'California,United States',
    'parse': True,
}
```

### JavaScript Rendering

For dynamic pages that require JavaScript execution:

```python
import requests

payload = {
    'source': 'universal',
    'url': 'https://example.com',
    'render': 'html',  # or 'png' for screenshot
}

response = requests.post(
    'https://realtime.oxylabs.io/v1/queries',
    auth=('USERNAME', 'PASSWORD'),
    json=payload,
    timeout=180,  # Important: extend timeout for rendered pages
)

print(response.json())
```

**Render Options:**
- `html` - Get fully rendered HTML content
- `png` - Get Base64-encoded screenshot

### Browser Instructions

Execute browser actions like clicking, scrolling, and inputting text:

```python
import requests

payload = {
    'source': 'universal',
    'url': 'https://www.ebay.com/',
    'render': 'html',  # Required for browser instructions
    'browser_instructions': [
        {
            'type': 'input',
            'value': 'laptop',
            'selector': {
                'type': 'xpath',
                'value': "//input[@class='gh-tb ui-autocomplete-input']"
            }
        },
        {
            'type': 'click',
            'selector': {
                'type': 'xpath',
                'value': "//input[@type='submit']"
            }
        },
        {
            'type': 'wait',
            'wait_time_s': 5
        }
    ]
}

response = requests.post(
    'https://realtime.oxylabs.io/v1/queries',
    auth=('USERNAME', 'PASSWORD'),
    json=payload,
    timeout=180,
)
```

**Supported Browser Instructions:**
- `click` - Click an element
- `input` - Enter text into a field
- `wait` - Wait for specified seconds
- `scroll` - Scroll the page
- `fetch_resource` - Capture XHR/Fetch requests

### Advanced Parameters

```python
payload = {
    'source': 'universal',
    'url': 'https://example.com',
    'user_agent_type': 'desktop',
    'geo_location': 'United States',
    'parse': True,
    'render': 'html',
    'context': [
        {
            'key': 'headers',
            'value': {
                'Content-Type': 'application/json',
                'Custom-Header': 'custom value'
            }
        },
        {
            'key': 'cookies',
            'value': [
                {'key': 'session_id', 'value': 'abc123'}
            ]
        },
        {
            'key': 'session_id',
            'value': 'my_session_123'  # Keep same proxy IP
        },
        {
            'key': 'follow_redirects',
            'value': True
        }
    ]
}
```

---

## Python SDK

The official Oxylabs Python SDK provides a simplified interface with automatic request management and error handling.

### Installation

```bash
pip install oxylabs
```

### Basic Usage

```python
from oxylabs import RealtimeClient

client = RealtimeClient('YOUR_USERNAME', 'YOUR_PASSWORD')

# Scrape any URL
result = client.universal.scrape_url('https://example.com')
print(result.raw)

# Scrape with parsing
result = client.amazon.scrape_search('headset', parse=True)
for item in result.results[0].content['results']['organic']:
    print(f"{item['asin']}: {item['title']}")
```

### Available Methods

| Target | Methods |
|--------|---------|
| `amazon` | `scrape_search`, `scrape_url`, `scrape_product`, `scrape_pricing`, `scrape_reviews` |
| `google` | `scrape_search`, `scrape_url`, `scrape_ads`, `scrape_suggestions`, `scrape_images` |
| `bing` | `scrape_search`, `scrape_url` |
| `universal` | `scrape_url` |

### Using Custom Parameters

```python
from oxylabs import RealtimeClient
from oxylabs.utils.types import user_agent_type, render, domain

client = RealtimeClient('YOUR_USERNAME', 'YOUR_PASSWORD')

result = client.google.scrape_search(
    'python web scraping',
    user_agent_type=user_agent_type.DESKTOP,
    render=render.HTML,
    domain=domain.COM,
    start_page=1,
    pages=3,
)
```

### Custom Parsing Instructions

```python
client = RealtimeClient('YOUR_USERNAME', 'YOUR_PASSWORD')

result = client.universal.scrape_url(
    'https://example.com',
    parse=True,
    parsing_instructions={
        'title': {
            '_fns': [
                {
                    '_fn': 'xpath_one',
                    '_args': ['//h1/text()']
                }
            ]
        },
        'price': {
            '_fns': [
                {
                    '_fn': 'xpath_one',
                    '_args': ['//span[@class="price"]/text()']
                }
            ]
        }
    }
)
```

### Browser Instructions with SDK

```python
client = RealtimeClient('YOUR_USERNAME', 'YOUR_PASSWORD')

result = client.universal.scrape_url(
    'https://www.ebay.com/',
    render='html',
    browser_instructions=[
        {
            'type': 'input',
            'value': 'laptop',
            'selector': {
                'type': 'xpath',
                'value': "//input[@class='gh-tb ui-autocomplete-input']"
            }
        },
        {
            'type': 'click',
            'selector': {
                'type': 'xpath',
                'value': "//input[@type='submit']"
            }
        },
        {
            'type': 'wait',
            'wait_time_s': 10
        }
    ]
)
```

---

## Best Practices

### 1. Timeout Configuration

Always set appropriate timeouts, especially for rendered pages:

```python
import requests

# For rendered pages, use 180 seconds
response = requests.post(
    'https://realtime.oxylabs.io/v1/queries',
    auth=('USERNAME', 'PASSWORD'),
    json=payload,
    timeout=180,
)
```

### 2. Session Management

Use sessions for tasks requiring consistent IP:

```python
# Generate unique session IDs
import uuid
session_id = str(uuid.uuid4())

# For Residential Proxies
entry = f'http://customer-{username}-sessid-{session_id}:{password}@pr.oxylabs.io:7777'

# For Web Scraper API
payload['context'] = [{'key': 'session_id', 'value': session_id}]
```

### 3. Retry Logic

Implement exponential backoff for failed requests:

```python
import time
import requests
from requests.exceptions import RequestException

def make_request_with_retry(url, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                auth=('USERNAME', 'PASSWORD'),
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            print(f"Attempt {attempt + 1} failed. Retrying in {wait_time}s...")
            time.sleep(wait_time)
```

### 4. Rate Limiting

Respect rate limits to avoid 429 errors:

```python
import time
from collections import deque
from threading import Lock

class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()
    
    def wait(self):
        with self.lock:
            now = time.time()
            # Remove old requests
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] - (now - self.time_window)
                time.sleep(sleep_time)
            
            self.requests.append(time.time())
```

### 5. Efficient Geo-Targeting

Use the most specific entry point for your needs:

```python
# For US-only scraping, use country-specific entry
entry = f'http://customer-{username}:{password}@us-pr.oxylabs.io:10000'

# For multi-country, use main entry with cc parameter
entry = f'http://customer-{username}-cc-DE:{password}@pr.oxylabs.io:7777'
```

### 6. Handling Dynamic Content

For JavaScript-heavy sites:

```python
payload = {
    'source': 'universal',
    'url': 'https://spa-website.com',
    'render': 'html',
    'browser_instructions': [
        {'type': 'wait', 'wait_time_s': 5}  # Wait for content to load
    ]
}
```

---

## Error Handling

### Common Errors and Solutions

**401 Unauthorized:**
```python
# Check credentials
if response.status_code == 401:
    print("Invalid credentials. Verify username and password.")
```

**429 Too Many Requests:**
```python
if response.status_code == 429:
    print("Rate limit exceeded. Implement backoff or contact account manager.")
    time.sleep(60)
```

**524 Timeout:**
```python
if response.status_code == 524:
    print("Request timed out. Try:")
    print("- Increasing timeout")
    print("- Simplifying the request")
    print("- Retrying later")
```

### Robust Error Handling Example

```python
import requests
from requests.exceptions import RequestException

def scrape_with_error_handling(payload):
    try:
        response = requests.post(
            'https://realtime.oxylabs.io/v1/queries',
            auth=('USERNAME', 'PASSWORD'),
            json=payload,
            timeout=180,
        )
        
        if response.status_code == 200:
            data = response.json()
            # Check for parser errors
            if 'results' in data:
                for result in data['results']:
                    if 'browser_instructions_error' in result:
                        print(f"Browser instruction error: {result['browser_instructions_error']}")
                    if 'browser_instructions_warnings' in result:
                        print(f"Warnings: {result['browser_instructions_warnings']}")
            return data
        
        elif response.status_code == 401:
            raise Exception("Authentication failed")
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded")
        elif response.status_code == 400:
            error_data = response.json()
            raise Exception(f"Bad request: {error_data}")
        else:
            response.raise_for_status()
            
    except RequestException as e:
        print(f"Request failed: {e}")
        raise
```

---

## Response Codes Reference

### API Response Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 202 | Accepted | Request accepted (async) |
| 204 | No Content | Job not completed yet |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Invalid credentials |
| 403 | Forbidden | No access to resource |
| 404 | Not Found | Job ID not available |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side issue |
| 524 | Timeout | Service unavailable |
| 612 | Internal Error | Job failed, retry free |
| 613 | Failed After Retries | Multiple failures |

### Parser Status Codes

| Code | Status | Description |
|------|--------|-------------|
| 12000 | Success | Full parsed content |
| 12002 | Failure | Parse failed |
| 12003 | Not Supported | Page type not supported |
| 12004 | Partial Success | Some fields missing |
| 12005 | Partial Success | Default values used |

### Session Codes

| Code | Status | Description |
|------|--------|-------------|
| 15001 | Session Expired | Create new session |
| 15002 | Session Failed | Retry creation |
| 15003 | Session Update Failed | Retry update |

---

## Additional Resources

- **Documentation:** https://developers.oxylabs.io
- **Python SDK:** https://github.com/oxylabs/oxylabs-sdk-python
- **Dashboard:** https://dashboard.oxylabs.io
- **Support:** support@oxylabs.io
- **IP Verification:** https://ip.oxylabs.io/location

---

*Last Updated: January 2026*