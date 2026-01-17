# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-retailer web scraper that collects retail store locations from Verizon, AT&T, Target, T-Mobile, Walmart, and Best Buy. Features concurrent execution, change detection, checkpoint/resume system, and optional Oxylabs proxy integration.

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

# Check status without running
python run.py --status

# Run with Oxylabs proxy
python run.py --all --proxy residential
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_change_detector.py

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
│   └── bestbuy.py              # XML sitemap (WIP, disabled)
├── src/shared/
│   ├── utils.py                # HTTP helpers, checkpoints, exports, delays
│   ├── proxy_client.py         # Oxylabs proxy abstraction (ProxyMode, ProxyClient)
│   ├── request_counter.py      # Rate limiting tracker
│   └── status.py               # Progress reporting
├── src/change_detector.py      # Detects new/closed/modified stores between runs
├── config/
│   ├── retailers.yaml          # Global config: proxy settings, per-retailer overrides
│   └── *_config.py             # Per-retailer Python configs
└── dashboard/app.py            # Flask monitoring UI
```

## Key Patterns

### Adding a New Retailer

1. Create `src/scrapers/newretailer.py` - implement scraper class
2. Create `config/newretailer_config.py` - retailer-specific settings
3. Register in `src/scrapers/__init__.py` - add to scraper registry
4. Add config block to `config/retailers.yaml` - sitemap URLs, delays, output fields

### Proxy Configuration

Proxies configured via environment variables (see `.env.example`):
- `OXYLABS_RESIDENTIAL_USERNAME/PASSWORD` - for residential proxy mode
- `OXYLABS_SCRAPER_API_USERNAME/PASSWORD` - for Web Scraper API mode
- `OXYLABS_USERNAME/PASSWORD` - fallback for both modes

Proxy modes in `config/retailers.yaml`:
- `direct` - no proxy (default)
- `residential` - rotating residential IPs
- `web_scraper_api` - managed service with JS rendering

### Output Structure

Data stored in `data/{retailer}/`:
- `output/stores_latest.json` - current run
- `output/stores_previous.json` - previous run (for change detection)
- `checkpoints/` - resumable state
- `history/changes_YYYY-MM-DD.json` - change reports

### Anti-Blocking

Configurable in `config/retailers.yaml`:
- `min_delay/max_delay` - random delays between requests
- `pause_50_requests/pause_200_requests` - longer pauses at thresholds
- User-agent rotation in `src/shared/utils.py` (DEFAULT_USER_AGENTS)
