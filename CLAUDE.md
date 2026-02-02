# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-retailer web scraper that collects retail store locations from Verizon, AT&T, Target, T-Mobile, Walmart, Best Buy, Telus, Cricket, and Bell. Features concurrent execution, change detection, checkpoint/resume system, and optional Oxylabs proxy integration.

## Environment Setup

Requires Python 3.8-3.11:
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Common Commands

```bash
# Run single retailer
python run.py --retailer verizon

# Run all retailers concurrently
python run.py --all

# Run with resume from checkpoints
python run.py --all --resume

# Test mode (10 stores per retailer)
python run.py --all --test

# Limit stores per retailer
python run.py --retailer target --limit 100

# Check status without running
python run.py --status

# Run with Oxylabs proxy
python run.py --all --proxy residential

# Validate proxy credentials before running
python run.py --all --proxy residential --validate-proxy

# Export in multiple formats
python run.py --retailer target --format json,csv,excel

# Incremental mode (only new/changed stores)
python run.py --all --incremental

# Targeted state scraping (Verizon only)
python run.py --retailer verizon --states MD,PA,RI

# Force URL re-discovery
python run.py --retailer verizon --refresh-urls

# Exclude specific retailers
python run.py --all --exclude bestbuy att

# Web Scraper API with JS rendering
python run.py --retailer walmart --proxy web_scraper_api --render-js

# Geo-targeted proxy
python run.py --retailer target --proxy residential --proxy-country ca

# Cloud storage sync to GCS
python run.py --retailer verizon --cloud

# Cloud sync for all retailers
python run.py --all --cloud

# Cloud with custom bucket
python run.py --all --cloud --gcs-bucket my-backup-bucket

# Cloud with timestamped history copies
python run.py --retailer target --cloud --gcs-history

# Disable cloud (overrides env/config)
python run.py --all --no-cloud
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_change_detector.py

# Run scraper unit tests
pytest tests/test_scrapers/

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Linting

```bash
# Lint all Python files (matches CI)
pylint $(git ls-files '*.py')
```

### Docker

```bash
# Build and run
docker-compose up -d

# Run specific retailer
docker-compose run scraper python run.py --retailer verizon

# View logs
docker-compose logs -f scraper
```

## Architecture

```
run.py                          # Main CLI entry point - handles arg parsing, concurrent execution
├── src/scrapers/               # Retailer-specific scrapers
│   ├── __init__.py             # Scraper registry & dynamic loader
│   ├── verizon.py              # 4-phase HTML crawl
│   ├── att.py                  # XML sitemap
│   ├── target.py               # Gzipped sitemap + API
│   ├── tmobile.py              # Paginated sitemaps
│   ├── walmart.py              # Multiple gzipped sitemaps
│   ├── bestbuy.py              # XML sitemap
│   ├── telus.py                # Uberall API (Canadian)
│   ├── cricket.py              # Yext API (US)
│   └── bell.py                 # Sitemap + JSON-LD (Canadian)
├── src/shared/
│   ├── utils.py                # HTTP helpers, checkpoints, delays, store validation
│   ├── cache.py                # URL caching (URLCache, RichURLCache)
│   ├── session_factory.py      # Thread-safe session creation for parallel workers
│   ├── proxy_client.py         # Oxylabs proxy abstraction (ProxyMode, ProxyClient)
│   ├── export_service.py       # Multi-format export (JSON, CSV, Excel, GeoJSON)
│   ├── request_counter.py      # Rate limiting tracker
│   ├── status.py               # Progress reporting (interface for future UI)
│   ├── notifications.py        # Pluggable notification system (Slack, console)
│   ├── cloud_storage.py        # GCS integration for backup/sync
│   ├── run_tracker.py          # Run metadata and state tracking
│   └── scraper_manager.py      # Process lifecycle management
├── src/change_detector.py      # Detects new/closed/modified stores between runs
└── config/
    ├── retailers.yaml          # Global config: proxy settings, per-retailer overrides
    └── *_config.py             # Per-retailer Python configs
```

### Scraper Interface

All scrapers implement a `run()` function with this signature:
```python
def run(session, retailer_config, retailer: str, **kwargs) -> dict:
    # Returns: {'stores': [...], 'count': int, 'checkpoints_used': bool}
```

### Key Defaults (from utils.py)

- `DEFAULT_MIN_DELAY = 2.0` / `DEFAULT_MAX_DELAY = 5.0` - delay between requests
- `DEFAULT_MAX_RETRIES = 3` - HTTP retry attempts
- `DEFAULT_TIMEOUT = 30` - request timeout in seconds
- `DEFAULT_RATE_LIMIT_BASE_WAIT = 30` - wait time on 429 errors

### Dual Delay Profiles

Retailers can define separate delay profiles for direct and proxied requests in `config/retailers.yaml`:
```yaml
delays:
  direct:      # Conservative (no proxy)
    min_delay: 2.0
    max_delay: 5.0
  proxied:     # Aggressive (with proxy)
    min_delay: 0.2
    max_delay: 0.5
```
- Provides 5-7x speedup when using residential proxies
- Automatically selects appropriate delays based on proxy mode
- Falls back to direct delays when no proxy is configured

### Performance Features

- **Parallel workers**: Configure `discovery_workers` and `parallel_workers` in retailers.yaml for concurrent request handling
- **URL caching**: 7-day cache for discovered store URLs (reduces repeat work on subsequent runs)
- **Verizon optimization**: 9.6x speedup with parallel discovery + extraction using proxies

## Key Patterns

### Adding a New Retailer

1. Create `src/scrapers/newretailer.py` - implement scraper class
2. Create `config/newretailer_config.py` - retailer-specific settings
3. Register in `src/scrapers/__init__.py` - add to scraper registry
4. Add config block to `config/retailers.yaml` - sitemap URLs, delays, output fields

### Enabling/Disabling Retailers

Set `enabled: false` in `config/retailers.yaml` to disable a retailer:
```yaml
retailers:
  bestbuy:
    enabled: false  # Won't appear in CLI choices or --all
```

The CLI uses `get_enabled_retailers()` which respects this setting.

### Proxy Configuration

Proxies configured via environment variables (see `.env.example`):
- `OXYLABS_RESIDENTIAL_USERNAME/PASSWORD` - for residential proxy mode
- `OXYLABS_SCRAPER_API_USERNAME/PASSWORD` - for Web Scraper API mode
- `OXYLABS_USERNAME/PASSWORD` - fallback for both modes

Proxy modes in `config/retailers.yaml`:
- `direct` - no proxy (default, 2-5s delays)
- `residential` - rotating residential IPs (0.2-0.5s delays, 9.6x faster)
- `web_scraper_api` - managed service with JS rendering

### Cloud Storage (GCS)

Sync scraped data to Google Cloud Storage for backup and team access.

**Environment variables** (see `.env.example`):
- `GCS_SERVICE_ACCOUNT_KEY` - path to service account JSON file
- `GCS_BUCKET_NAME` - GCS bucket name
- `GCS_PROJECT_ID` - GCP project ID (optional, auto-detected)
- `GCS_ENABLE_HISTORY` - enable timestamped history copies

**YAML config** in `config/retailers.yaml`:
```yaml
cloud_storage:
  enabled: true        # or use --cloud CLI flag
  max_retries: 3
  retry_delay: 2.0
  enable_history: false
```

**GCS bucket structure**:
```
gs://{bucket}/
├── verizon/stores_latest.json    # Overwritten each run (versioned by GCS)
├── verizon/stores_latest.csv
├── att/stores_latest.json
└── history/                      # Optional (--gcs-history)
    └── verizon/stores_2026-01-26_143022.json
```

**Setup**:
1. Create GCS bucket with object versioning enabled
2. Create service account with `Storage Object Admin` role
3. Download service account key JSON
4. Set `GCS_SERVICE_ACCOUNT_KEY` and `GCS_BUCKET_NAME` in `.env`

### Output Structure

Data stored in `data/{retailer}/`:
- `output/stores_latest.json` - current run
- `output/stores_previous.json` - previous run (for change detection)
- `checkpoints/` - resumable state
- `history/changes_{retailer}_YYYY-MM-DD_HH-MM-SS-ffffff.json` - change reports

Additional output directories:
- `runs/{run_id}.json` - run metadata tracking
- `logs/{run_id}.log` - per-run log files

### Anti-Blocking

Configurable in `config/retailers.yaml`:
- `min_delay/max_delay` - random delays between requests
- `pause_50_requests/pause_200_requests` - longer pauses at thresholds
- User-agent rotation in `src/shared/utils.py` (DEFAULT_USER_AGENTS)

### Store Data Validation

Use `validate_store_data()` from `src/shared/utils.py` to validate scraped data:
```python
from src.shared.utils import validate_store_data, validate_stores_batch

result = validate_store_data(store)  # Returns ValidationResult
summary = validate_stores_batch(stores)  # Returns summary dict
```

Required fields: `store_id`, `name`, `street_address`, `city`, `state`
Recommended fields: `latitude`, `longitude`, `phone`, `url`

## Test Structure

```
tests/
├── test_scrapers/           # Unit tests for individual scrapers
│   ├── test_target.py
│   ├── test_att.py
│   ├── test_verizon.py
│   ├── test_tmobile.py
│   ├── test_walmart.py
│   ├── test_bestbuy.py
│   ├── test_cricket.py
│   └── test_bell.py
├── test_change_detector.py  # Change detection tests
├── test_proxy_client.py     # Proxy integration tests
├── test_export_service.py   # Export format tests
└── uat/                     # User Acceptance Testing framework
    ├── protocol.py          # UAT test protocol
    ├── helpers.py           # Test utilities
    ├── report.py            # Test reporting
    └── suites/              # Test suites by feature
        ├── config.py, control.py, error.py
        ├── history.py, init.py, logs.py, perf.py
        └── proxy.py, status.py
```

## Deployment

Deployment tools in `deploy/`:
- `rsync-deploy.sh` - production deployment via rsync
- `validate.sh` - deployment validation checks
- `diagnose-network.sh` - network troubleshooting utilities
