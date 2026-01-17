# Proxy Functions Manual Testing Guide

This guide provides step-by-step instructions for manually testing all three proxy modes with the retail store scraper.

---

## Prerequisites

### 1. Oxylabs Account Setup

You'll need Oxylabs credentials for testing proxy modes. Sign up at https://oxylabs.io/

**Important:** Oxylabs provides SEPARATE credentials for different products:
- **Residential Proxies:** Usually format `customer_XXXXX`
- **Web Scraper API:** Usually your account email or API-specific username

### 2. Set Up Environment Variables

Create a `.env` file or set environment variables:

```bash
# For residential proxies testing
export OXYLABS_RESIDENTIAL_USERNAME="customer_your_username"
export OXYLABS_RESIDENTIAL_PASSWORD="your_password"

# For Web Scraper API testing
export OXYLABS_SCRAPER_API_USERNAME="your_api_username"
export OXYLABS_SCRAPER_API_PASSWORD="your_api_password"

# Or use legacy fallback (works for both)
export OXYLABS_USERNAME="your_username"
export OXYLABS_PASSWORD="your_password"
```

---

## Test 1: Direct Mode (No Proxy)

**Purpose:** Verify basic scraping without proxies

### Commands:

```bash
# Test with AT&T (simple sitemap-based scraper)
python run.py --retailer att --limit 5 --proxy direct --verbose

# Expected behavior:
# - Uses standard requests.Session
# - Applies delays from config (0.5-1.0s)
# - No proxy authentication
# - Should scrape 5 stores successfully
```

### Verification Checklist:

- [ ] Scraper starts without errors
- [ ] Log shows "Created Session for mode: direct"
- [ ] 5 stores scraped successfully
- [ ] Output saved to `data/att/output/stores_latest.json`
- [ ] CSV saved to `data/att/output/stores_latest.csv`
- [ ] No proxy-related errors in logs

### Expected Output:

```
[att] Using default proxy mode: direct
[att] Created Session for mode: direct
[att] Starting scraper
[att] Discovered 5000+ store URLs from sitemap
[att] Scraping store 1/5: https://www.att.com/stores/...
[att] Scraping store 2/5: https://www.att.com/stores/...
...
[att] Saved 5 stores to JSON: data/att/output/stores_latest.json
[att] Saved 5 stores to CSV: data/att/output/stores_latest.csv
[att] Completed scraper
```

---

## Test 2: Residential Proxies

**Purpose:** Verify residential proxy integration with IP rotation

### Commands:

```bash
# Test with Verizon (configured for residential in YAML)
python run.py --retailer verizon --limit 5 --proxy residential --proxy-country us --verbose

# Alternative: Let YAML config determine mode
python run.py --retailer verizon --limit 5 --verbose
```

### Verification Checklist:

- [ ] Scraper starts with residential proxy credentials
- [ ] Log shows "Created ProxiedSession for mode: residential"
- [ ] Connections go through pr.oxylabs.io:7777
- [ ] Country targeting applied (US)
- [ ] IP rotation occurs between requests
- [ ] 5 stores scraped successfully
- [ ] No 407 Proxy Authentication errors

### Expected Output:

```
Proxy mode: residential (country: us)
[verizon] Using retailer-specific proxy mode: residential
[verizon] Created ProxiedSession for mode: residential
[verizon] Starting scraper
[verizon] Discovering states...
[verizon] Discovered 51 state pages
[verizon] Processing state: California
...
[verizon] Scraped 5 stores
[verizon] Saved 5 stores to JSON
```

### Debugging:

If you see authentication errors:
```
ERROR: 407 Proxy Authentication Required
```

**Solution:** Verify credentials are set correctly:
```bash
# Check credentials
echo $OXYLABS_RESIDENTIAL_USERNAME
echo $OXYLABS_RESIDENTIAL_PASSWORD

# Re-export if needed
export OXYLABS_RESIDENTIAL_USERNAME="customer_XXXXX"
export OXYLABS_RESIDENTIAL_PASSWORD="your_password"
```

---

## Test 3: Web Scraper API

**Purpose:** Verify Web Scraper API integration with JavaScript rendering

### Commands:

```bash
# Test with Walmart (JS-heavy site)
python run.py --retailer walmart --limit 5 --proxy web_scraper_api --render-js --verbose

# Alternative: Let YAML config determine mode
python run.py --retailer walmart --limit 5 --verbose
```

### Verification Checklist:

- [ ] Scraper starts with Web Scraper API credentials
- [ ] Log shows "Created ProxiedSession for mode: web_scraper_api"
- [ ] Requests POST to https://realtime.oxylabs.io/v1/queries
- [ ] JavaScript rendering enabled (render=html in payload)
- [ ] Fully rendered HTML returned
- [ ] 5 stores scraped successfully
- [ ] `job_id` and `credits_used` logged

### Expected Output:

```
Proxy mode: web_scraper_api (country: us)
JavaScript rendering enabled
[walmart] Using retailer-specific proxy mode: web_scraper_api
[walmart] Created ProxiedSession for mode: web_scraper_api
[walmart] Starting scraper
[walmart] Discovering store URLs from sitemaps...
[walmart] Processing sitemap: sitemap_store_supercenter.xml.gz
[walmart] Scraping store 1/5: https://www.walmart.com/store/...
[walmart] Rendered page with __NEXT_DATA__ (job_id: abc123, credits: 1.5)
...
[walmart] Scraped 5 stores
[walmart] Saved 5 stores to JSON
```

### Debugging:

If you see API errors:
```
ERROR: 401 Unauthorized
```

**Solution:** Verify API credentials:
```bash
# Check API credentials
echo $OXYLABS_SCRAPER_API_USERNAME
echo $OXYLABS_SCRAPER_API_PASSWORD

# Re-export if needed
export OXYLABS_SCRAPER_API_USERNAME="your_api_username"
export OXYLABS_SCRAPER_API_PASSWORD="your_api_password"
```

---

## Test 4: Configuration Priority Order

**Purpose:** Verify CLI override works and takes precedence over YAML config

### Test 4.1: CLI Override Beats YAML

Walmart is configured for `web_scraper_api` in YAML. Override with residential:

```bash
python run.py --retailer walmart --limit 5 --proxy residential --verbose
```

**Expected:** Log should show "residential" mode, NOT "web_scraper_api"

```
[walmart] Using CLI override proxy mode: residential
[walmart] Created ProxiedSession for mode: residential
```

### Test 4.2: Per-Retailer Config Beats Global

Verizon has per-retailer config for residential. Run without CLI override:

```bash
python run.py --retailer verizon --limit 5 --verbose
```

**Expected:** Should use residential (from per-retailer config)

```
[verizon] Using retailer-specific proxy mode: residential
```

### Test 4.3: Fallback to Direct on Missing Credentials

Try residential mode without credentials:

```bash
unset OXYLABS_RESIDENTIAL_USERNAME
unset OXYLABS_RESIDENTIAL_PASSWORD
unset OXYLABS_USERNAME
unset OXYLABS_PASSWORD

python run.py --retailer verizon --limit 5 --proxy residential --verbose
```

**Expected:** Should fall back to direct mode with warning

```
[verizon] Missing credentials for residential mode, falling back to direct
[verizon] Created Session for mode: direct
```

---

## Test 5: All Retailers Concurrently

**Purpose:** Verify concurrent execution with proxy modes

### Commands:

```bash
# Run all retailers with residential proxies
python run.py --all --test --proxy residential --verbose

# Run all with their configured modes (from YAML)
python run.py --all --test --verbose
```

### Verification Checklist:

- [ ] All 5 retailers start concurrently
- [ ] Each retailer uses correct proxy mode
- [ ] No proxy credential conflicts
- [ ] All retailers complete successfully
- [ ] Summary shows results for all retailers

### Expected Output:

```
Starting concurrent scrape for 5 retailers: ['verizon', 'att', 'target', 'tmobile', 'walmart']
[verizon] Created ProxiedSession for mode: residential
[att] Created Session for mode: direct
[target] Created Session for mode: direct
[tmobile] Created Session for mode: direct
[walmart] Created ProxiedSession for mode: web_scraper_api
...
========================================
SCRAPING RESULTS
========================================
  verizon: completed (10 stores)
  att: completed (10 stores)
  target: completed (10 stores)
  tmobile: completed (10 stores)
  walmart: completed (10 stores)
```

---

## Test 6: Error Handling

### Test 6.1: Rate Limiting (429)

Intentionally trigger rate limiting by scraping many pages quickly:

```bash
# Scrape 100 stores without delays (will likely hit rate limit)
python run.py --retailer target --limit 100 --verbose
```

**Expected Behavior:**
- First ~50 requests succeed
- Hit 429 rate limit
- Automatic exponential backoff
- Retry after wait
- Eventually succeeds

**Log Output:**
```
[target] Fetching store 45/100
[target] Fetching store 46/100
WARNING: Rate limited (429), waiting 30.0s (attempt 1/3)
[target] Retrying after backoff...
[target] Fetching store 46/100 (retry)
```

### Test 6.2: Invalid Credentials

Use invalid credentials:

```bash
export OXYLABS_RESIDENTIAL_USERNAME="invalid_user"
export OXYLABS_RESIDENTIAL_PASSWORD="invalid_pass"

python run.py --retailer verizon --limit 5 --proxy residential --verbose
```

**Expected Behavior:**
- Proxy authentication fails (407)
- Scraper handles error gracefully
- May fall back to direct mode or fail gracefully

### Test 6.3: Network Timeout

Test timeout handling with very short timeout:

```bash
# Edit config/retailers.yaml temporarily
# Set timeout: 1 for a retailer
python run.py --retailer att --limit 5 --verbose
```

**Expected Behavior:**
- Some requests timeout
- Automatic retry
- Eventually succeeds or returns None for failed stores

---

## Test 7: Resume from Checkpoint

**Purpose:** Verify checkpoint/resume works with proxies

### Commands:

```bash
# Start a long scrape
python run.py --retailer verizon --limit 100 --proxy residential &
SCRAPER_PID=$!

# Let it run for 30 seconds then kill
sleep 30
kill $SCRAPER_PID

# Resume from checkpoint
python run.py --retailer verizon --limit 100 --resume --proxy residential --verbose
```

### Verification Checklist:

- [ ] Checkpoint saved during first run
- [ ] Second run loads checkpoint
- [ ] Resumes from correct position
- [ ] No duplicate stores scraped
- [ ] Final output contains all unique stores

**Expected Log:**
```
[verizon] Resuming from index 45
[verizon] Already processed 45 stores, continuing...
```

---

## Test 8: Proxy Statistics

**Purpose:** Verify proxy client statistics tracking

### Commands:

```python
# In Python shell
from src.shared.utils import get_proxy_client

config = {'mode': 'residential'}
client = get_proxy_client(config)

# Make some requests (mock)
for i in range(10):
    client.get('https://example.com')  # Will fail but increments counter

# Check stats
stats = client.get_stats()
print(stats)
```

**Expected Output:**
```python
{
    'mode': 'residential',
    'request_count': 10,
    'country': 'us',
    'render_js': False
}
```

---

## Troubleshooting Guide

### Problem: 407 Proxy Authentication Required

**Cause:** Invalid or missing proxy credentials

**Solution:**
1. Verify credentials are set:
   ```bash
   echo $OXYLABS_RESIDENTIAL_USERNAME
   echo $OXYLABS_RESIDENTIAL_PASSWORD
   ```
2. Check credentials match your Oxylabs product (Residential vs API)
3. Try legacy fallback credentials:
   ```bash
   export OXYLABS_USERNAME="your_username"
   export OXYLABS_PASSWORD="your_password"
   ```

### Problem: 401 Unauthorized (Web Scraper API)

**Cause:** Invalid Web Scraper API credentials

**Solution:**
1. Verify API credentials:
   ```bash
   echo $OXYLABS_SCRAPER_API_USERNAME
   echo $OXYLABS_SCRAPER_API_PASSWORD
   ```
2. Ensure you're using API credentials, not residential proxy credentials
3. Check Oxylabs dashboard for correct API username

### Problem: Timeout Errors

**Cause:** Network latency, slow proxy response, or site blocking

**Solution:**
1. Increase timeout in config:
   ```yaml
   proxy:
     timeout: 120  # Increase from default 60
   ```
2. Enable JavaScript rendering for JS-heavy sites:
   ```bash
   python run.py --retailer walmart --proxy web_scraper_api --render-js
   ```

### Problem: "ProxyClient has no attribute 'headers'"

**Cause:** Old code using ProxyClient directly instead of ProxiedSession

**Solution:** This should not occur if git change is applied. Verify:
```python
from src.shared.utils import create_proxied_session
session = create_proxied_session({'proxy': {'mode': 'residential'}})
assert hasattr(session, 'headers')  # Should pass
```

### Problem: Scrapers Creating Own Sessions

**Cause:** Scraper not updated to use provided session

**Solution:** All scrapers should accept session parameter:
```python
def run(session, config: dict, **kwargs) -> dict:
    # Use provided session, don't create new one
    response = session.get(url)
```

---

## Performance Benchmarks

### Expected Latency by Mode

| Mode | Avg Latency | Notes |
|------|-------------|-------|
| Direct | 100-500ms | Depends on site speed |
| Residential | 500-2000ms | Proxy overhead + rotation |
| Web Scraper API | 2000-5000ms | JS rendering + managed service |

### Throughput Estimates

| Mode | Stores/Min | Notes |
|------|------------|-------|
| Direct | 30-60 | With delays |
| Residential | 20-40 | With proxy overhead |
| Web Scraper API | 10-20 | JS rendering overhead |

---

## Success Criteria

All manual tests should meet these criteria:

1. ✅ All three proxy modes connect and authenticate successfully
2. ✅ Stores are scraped and saved to JSON/CSV
3. ✅ No authentication or credential errors
4. ✅ Configuration priority order works correctly
5. ✅ CLI overrides work as expected
6. ✅ Error handling is graceful (no crashes)
7. ✅ Retry logic works for transient failures
8. ✅ Checkpoint/resume works correctly
9. ✅ Concurrent execution works without conflicts
10. ✅ Resource cleanup happens (no leaks)

---

## Next Steps After Manual Testing

1. **Document any issues found** in GitHub issues
2. **Update configuration** based on performance observations
3. **Adjust timeouts/delays** if needed for your use case
4. **Set up monitoring** for production use
5. **Schedule regular test runs** to catch regressions

---

**Testing Completed:** [Date]  
**Tested By:** [Your Name]  
**Issues Found:** [Number]  
**Status:** [PASS/FAIL]
