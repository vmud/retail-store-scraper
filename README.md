# Multi-Retailer Store Scraper

A production-ready Python web scraper that collects retail store locations from multiple US and Canadian retailer websites. Features concurrent execution, intelligent change detection, checkpoint/resume, cloud storage sync, and optional Oxylabs proxy integration.

## Features

### Core Capabilities
- **11 Retailers**: Verizon, AT&T, Target, T-Mobile, Walmart, Best Buy, Telus, Cricket Wireless, Bell, Costco, Sam's Club
- **Concurrent Execution**: Run all retailers simultaneously with global concurrency management
- **Change Detection**: Detect new, closed, and modified stores between runs with incremental mode
- **Checkpoint System**: Resume from interruptions without data loss
- **Flexible Export**: JSON, CSV, Excel, and GeoJSON format support
- **Cloud Storage**: Sync results to Google Cloud Storage for backup and team access
- **Store Schema**: Centralized store data schema with standardized field naming across all retailers

### Anti-Blocking & Performance
- **Oxylabs Proxy Integration**: Support for residential proxies and Web Scraper API
- **JavaScript Rendering**: Dynamic content scraping via Web Scraper API for bot-protected sites
- **Dual Delay Profiles**: Automatic fast/slow switching based on proxy mode (5-10x speedup)
- **Global Concurrency Limits**: Prevents CPU oversubscription when running all retailers
- **Smart Rate Limiting**: Configurable delays, pause thresholds, and proxy rate limits
- **User-Agent Rotation**: Multiple browser signatures
- **URL Caching**: 7-day cache for discovered store URLs (reduces repeat work)

### Observability & Reliability
- **Sentry.io Integration**: Error monitoring with retailer-specific context and breadcrumbs
- **Structured Logging**: JSON-formatted log output for observability pipelines
- **Self-Healing Setup**: Automated environment probing, diagnostics, and auto-fix
- **Comprehensive Type Hints**: Full type annotations across core modules

## Quick Links

- **[Deployment Guide](DEPLOYMENT.md)**: Complete deployment instructions for remote dev servers
- **[Agent Guide](AGENTS.md)**: Contributor instructions, structure, and coding standards
- **[Claude Guide](CLAUDE.md)**: AI assistant context and development patterns

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/retail-store-scraper.git
cd retail-store-scraper

# Recommended: automated setup with diagnostics and auto-fix
python scripts/setup.py

# Or manual setup (requires Python 3.9-3.14)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional: Copy environment template
cp .env.example .env
# Edit .env with your Oxylabs credentials (if using proxies)
```

### Basic Usage

```bash
# Run a single retailer
python run.py --retailer verizon

# Run all retailers concurrently
python run.py --all

# Run with resume (continue from checkpoints)
python run.py --all --resume

# Run in test mode (10 stores per retailer)
python run.py --all --test

# Check current status without running
python run.py --status

# Limit stores per retailer
python run.py --retailer target --limit 100

# Incremental mode (only process changes)
python run.py --all --incremental --resume
```

### Advanced Usage

```bash
# Run with Oxylabs residential proxy
python run.py --all --proxy residential --resume

# Run with Web Scraper API and JavaScript rendering
python run.py --retailer walmart --proxy web_scraper_api --render-js

# Validate proxy credentials before running
python run.py --all --proxy residential --validate-proxy

# Export in multiple formats
python run.py --retailer target --format json,csv,excel,geojson

# Exclude specific retailers
python run.py --all --exclude bestbuy att --resume

# Targeted state scraping (Verizon only)
python run.py --retailer verizon --states MD,PA,RI

# Force URL re-discovery
python run.py --retailer verizon --refresh-urls

# Geo-targeted proxy
python run.py --retailer target --proxy residential --proxy-country ca

# Cloud storage sync to GCS
python run.py --retailer verizon --cloud

# Cloud with timestamped history copies
python run.py --all --cloud --gcs-history

# Disable cloud (overrides env/config)
python run.py --all --no-cloud

# Verbose logging for debugging
python run.py --retailer verizon --verbose
```

## CLI Options

### Basic Options
| Option | Description |
|--------|-------------|
| `--retailer, -r` | Run specific retailer |
| `--all, -a` | Run all enabled retailers concurrently |
| `--exclude, -e` | Exclude retailers when using --all |
| `--resume` | Resume from checkpoints |
| `--incremental` | Only process new/changed stores (change detection mode) |
| `--refresh-urls` | Force URL re-discovery (ignore cached store URLs) |
| `--states STATES` | Comma-separated state abbreviations to scrape (Verizon only) |
| `--test` | Quick test mode (limit 10 stores per retailer) |
| `--limit N` | Limit stores per retailer (cannot combine with --test) |
| `--status` | Show progress without running scrapers |
| `--verbose, -v` | Verbose output with debug logging |
| `--log-file PATH` | Log file path (default: logs/scraper.log) |

### Proxy Options
| Option | Description |
|--------|-------------|
| `--proxy MODE` | Proxy mode: `direct`, `residential`, `web_scraper_api` |
| `--proxy-country CODE` | Country code for geo-targeting (default: us) |
| `--render-js` | Enable JavaScript rendering (requires web_scraper_api mode) |
| `--validate-proxy` | Test proxy credentials before running |

### Export Options
| Option | Description |
|--------|-------------|
| `--format FORMATS` | Export formats: `json`, `csv`, `excel`, `geojson` (comma-separated, default: json,csv) |

### Cloud Storage Options
| Option | Description |
|--------|-------------|
| `--cloud` | Enable cloud storage sync (uploads to GCS after local export) |
| `--no-cloud` | Disable cloud storage sync (overrides env/config) |
| `--gcs-bucket NAME` | Override GCS bucket name |
| `--gcs-history` | Upload timestamped copies to history/ folder |

## Supported Retailers

| Retailer | Country | Discovery Method | Proxy Mode |
|----------|---------|------------------|------------|
| Verizon | US | 4-phase HTML crawl | Residential |
| AT&T | US | XML Sitemap | Residential |
| Target | US | Gzipped Sitemap + API | Residential |
| T-Mobile | US | Paginated Sitemaps | Web Scraper API |
| Walmart | US | Multiple Gzipped Sitemaps | Hybrid (Residential + WSAPI) |
| Best Buy | US | XML Sitemap | Web Scraper API |
| Cricket Wireless | US | Yext API (geo-grid) | Direct |
| Costco | US | Page scrape | Web Scraper API |
| Sam's Club | US | Sitemap | Hybrid (Direct + WSAPI) |
| Telus | Canada | Uberall API | Residential |
| Bell | Canada | Sitemap + JSON-LD | Direct |

## Project Structure

```
retail-store-scraper/
├── run.py                          # Unified CLI entry point
├── requirements.txt
├── Dockerfile                      # Multi-stage build (non-root, security hardened)
├── docker-compose.yml
├── scripts/
│   └── setup.py                    # Self-healing project setup
├── config/
│   ├── retailers.yaml              # All retailer configurations, concurrency, proxy, cloud
│   └── *_config.py                 # Per-retailer Python configs
├── src/
│   ├── change_detector.py          # Change detection system
│   ├── setup/                      # Self-healing setup module
│   │   ├── probe.py                # Environment probing
│   │   ├── fix.py                  # Idempotent auto-fix
│   │   ├── verify.py               # Verification suite
│   │   └── runner.py               # Orchestration with checkpoints
│   ├── shared/
│   │   ├── constants.py            # Centralized magic numbers (HTTP, cache, workers, etc.)
│   │   ├── concurrency.py          # Global concurrency and rate limit management
│   │   ├── cache_interface.py      # Unified caching with consistent TTL
│   │   ├── session_factory.py      # Thread-safe session creation
│   │   ├── proxy_client.py         # Oxylabs proxy abstraction
│   │   ├── export_service.py       # Multi-format export (JSON, CSV, Excel, GeoJSON)
│   │   ├── cloud_storage.py        # GCS integration for backup/sync
│   │   ├── store_schema.py         # Central store data schema
│   │   ├── store_serializer.py     # Store data serialization
│   │   ├── scrape_runner.py        # Shared scrape runner for unified orchestration
│   │   ├── scraper_utils.py        # Common scraper patterns
│   │   ├── structured_logging.py   # JSON-formatted structured logging
│   │   ├── sentry_integration.py   # Sentry.io error monitoring
│   │   ├── logging_config.py       # Logging configuration
│   │   ├── http.py                 # HTTP helpers and retry logic
│   │   ├── delays.py               # Delay and rate-limiting utilities
│   │   ├── checkpoint.py           # Checkpoint management
│   │   ├── validation.py           # Store data validation
│   │   ├── io.py                   # File I/O utilities
│   │   ├── notifications.py        # Pluggable notifications (Slack, console)
│   │   ├── run_tracker.py          # Run metadata tracking
│   │   ├── scraper_manager.py      # Process lifecycle management
│   │   ├── request_counter.py      # Rate limiting tracker
│   │   ├── status.py               # Progress reporting
│   │   ├── cache.py                # URL caching (legacy)
│   │   └── utils.py                # Backward-compatible aliases
│   └── scrapers/
│       ├── __init__.py             # Scraper registry and dynamic loader
│       ├── verizon.py              # 4-phase HTML crawl
│       ├── att.py                  # XML sitemap
│       ├── target.py               # Gzipped sitemap + API
│       ├── tmobile.py              # Paginated sitemaps
│       ├── walmart.py              # Multiple gzipped sitemaps (hybrid proxy)
│       ├── bestbuy.py              # XML sitemap + Web Scraper API
│       ├── telus.py                # Uberall API (Canadian)
│       ├── cricket.py              # Yext API geo-grid (US)
│       ├── bell.py                 # Sitemap + JSON-LD (Canadian)
│       ├── costco.py               # Page scrape with Akamai bypass
│       └── samsclub.py             # Sitemap + hybrid proxy
├── deploy/
│   ├── rsync-deploy.sh             # Production deployment via rsync
│   ├── validate.sh                 # Deployment validation
│   └── diagnose-network.sh         # Network troubleshooting
├── .github/workflows/              # CI/CD pipelines
└── data/                           # Output data (gitignored)
    └── {retailer}/
        ├── checkpoints/
        ├── output/
        └── history/
```

## Configuration

### Global Concurrency

Concurrency limits in `config/retailers.yaml` prevent CPU oversubscription when running `--all`:

```yaml
concurrency:
  global_max_workers: 10      # Max concurrent workers across ALL retailers
  per_retailer_max:
    verizon: 7                # High parallelism with proxy
    walmart: 3                # JS rendering is resource-heavy
    bell: 1                   # Respects crawl-delay: 10
  proxy_rate_limit: 10.0      # Requests/second for proxy modes
```

### Dual Delay Profiles

Each retailer defines separate delay profiles for direct and proxied requests:

```yaml
delays:
  direct:      # Conservative (no proxy)
    min_delay: 2.0
    max_delay: 5.0
  proxied:     # Aggressive (with proxy)
    min_delay: 0.2
    max_delay: 0.5
```

This provides 5-10x speedup when using residential proxies with automatic profile switching.

### Retailer Configuration

Edit `config/retailers.yaml` to customize:
- Request delays (dual profiles)
- Pause thresholds
- Enabled/disabled retailers
- Output fields
- Per-retailer proxy modes
- Worker counts

### Enabling/Disabling Retailers

```yaml
retailers:
  bestbuy:
    enabled: false  # Won't appear in CLI choices or --all
```

## Cloud Storage (GCS)

Sync scraped data to Google Cloud Storage for backup and team access.

### Setup

1. Create a GCS bucket with object versioning enabled
2. Create a service account with `Storage Object Admin` role
3. Download the service account key JSON
4. Set environment variables:

```bash
export GCS_SERVICE_ACCOUNT_KEY=/path/to/service-account.json
export GCS_BUCKET_NAME=your-bucket-name
```

### Usage

```bash
# Sync after scraping
python run.py --retailer verizon --cloud

# With timestamped history
python run.py --all --cloud --gcs-history

# Custom bucket
python run.py --all --cloud --gcs-bucket my-backup-bucket
```

### GCS Bucket Structure

```
gs://{bucket}/
├── verizon/stores_latest.json    # Overwritten each run (versioned by GCS)
├── verizon/stores_latest.csv
├── att/stores_latest.json
└── history/                      # Optional (--gcs-history)
    └── verizon/stores_2026-01-26_143022.json
```

## Oxylabs Proxy Integration

For faster scraping with reduced blocking risk, integrate with [Oxylabs](https://oxylabs.io/) proxy services.

### Setup

1. Sign up at [Oxylabs](https://oxylabs.io/)
2. Set environment variables:
   ```bash
   # Mode-specific credentials (preferred)
   export OXYLABS_RESIDENTIAL_USERNAME=your_username
   export OXYLABS_RESIDENTIAL_PASSWORD=your_password
   export OXYLABS_SCRAPER_API_USERNAME=your_username
   export OXYLABS_SCRAPER_API_PASSWORD=your_password

   # Or legacy fallback
   export OXYLABS_USERNAME=your_username
   export OXYLABS_PASSWORD=your_password
   ```

3. Or use `.env` file (copy from `.env.example`)

### Proxy Modes

| Mode | Description | Best For |
|------|-------------|----------|
| `direct` | No proxy (default) | Testing, low-volume |
| `residential` | 175M+ rotating residential IPs | Most retailers |
| `web_scraper_api` | Managed service with JS rendering | Bot-protected sites (Costco, Best Buy, T-Mobile) |

Some retailers use **hybrid mode** (e.g., Walmart, Sam's Club) where sitemaps are fetched directly but store pages use Web Scraper API for JavaScript rendering.

## Error Recovery

### HTTP-Level Retries (Automatic)
Every HTTP request automatically retries 3 times with exponential backoff for 429, 500, 502, 503, 504 errors.

### Checkpoint Resume
Failed store URLs are not marked as completed. Running with `--resume` retries any failed extractions:
```bash
python run.py --retailer verizon --proxy residential --resume
```

### Discovery Refresh
For Verizon's parallel discovery phases, force complete re-discovery:
```bash
python run.py --retailer verizon --proxy residential --refresh-urls
```

## Docker Deployment

### Quick Start

```bash
# Build and run
docker compose up -d

# Run specific retailer
docker compose exec scraper python run.py --retailer verizon

# Run all with proxies
docker compose exec scraper python run.py --all --proxy residential --resume

# Check status
docker compose exec scraper python run.py --status

# View logs
docker compose logs -f scraper

# Stop services
docker compose down
```

### Environment Variables

```bash
# Proxy credentials
export OXYLABS_RESIDENTIAL_USERNAME=your_username
export OXYLABS_RESIDENTIAL_PASSWORD=your_password

# Start with environment
docker compose up -d
```

### Container Features
- Multi-stage build for smaller image size
- Non-root user for security
- Health checks with automatic restarts
- Volume mounts for data persistence

## Data Output

### Output Files

- `data/{retailer}/output/stores_latest.json` - Current run data
- `data/{retailer}/output/stores_latest.csv` - Current run CSV
- `data/{retailer}/output/stores_previous.json` - Previous run data
- `data/{retailer}/history/changes_*.json` - Change detection reports
- `runs/{run_id}.json` - Run metadata
- `logs/{run_id}.log` - Per-run log files

### Change Detection

```bash
python run.py --retailer target --incremental
```

Change reports include new stores (opened since last run), closed stores (removed), and modified stores (changed attributes).

## Expected Performance

| Metric | Direct Mode | Residential Proxy | Web Scraper API |
|--------|-------------|-------------------|-----------------|
| Full run (11 retailers) | 10-16 hours | 2-4 hours | 1-2 hours |
| Incremental run | 2-3 hours | 20-40 mins | 10-20 mins |
| Test mode | 5-10 mins | 1-2 mins | <1 min |
| IP blocking risk | Medium | Very Low | None |
| JavaScript rendering | No | No | Yes |

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_change_detector.py

# Run scraper-specific tests
pytest tests/test_scrapers/

# Run with coverage report
pytest tests/ --cov=src --cov-report=html
```

### Linting

```bash
# Lint all Python files (matches CI pipeline)
pylint $(git ls-files '*.py')
```

### Adding a New Retailer

1. **Create scraper module**: `src/scrapers/newretailer.py`
   - Implement `run(session, retailer_config, retailer, **kwargs)` function
   - Return `{'stores': [...], 'count': int, 'checkpoints_used': bool}`
2. **Add configuration**: `config/newretailer_config.py`
3. **Register scraper**: Add to `SCRAPER_REGISTRY` in `src/scrapers/__init__.py`
4. **Configure retailer**: Add block in `config/retailers.yaml`
5. **Write tests**: `tests/test_scrapers/test_newretailer.py`
6. **Validate**:
   ```bash
   python run.py --retailer newretailer --test
   pytest tests/test_scrapers/test_newretailer.py -v
   pylint src/scrapers/newretailer.py
   ```

### CI/CD Pipelines

GitHub Actions workflows:
- **test.yml**: Full test suite on Python 3.9-3.14
- **pylint.yml**: Code quality checks on every push/PR
- **type-check.yml**: Static type checking
- **security.yml**: Vulnerability and secret scanning
- **docker.yml**: Docker image build verification
- **pr-validation.yml**: PR quality gates
- **claude-code-review.yml**: AI-assisted code review
- **multi-agent-pr.yml**: Multi-agent conflict detection and auto-labeling
- **scraper-health.yml**: Retailer endpoint health checks
- **scraper-proxy-test.yml**: Proxy connectivity validation
- **1password-secrets.yml**: Secure secret loading
- **release.yml**: Release automation

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Make your changes following the coding standards in [AGENTS.md](AGENTS.md)
4. Write tests for new functionality
5. Run linter and tests locally
6. Commit changes with conventional commit messages (`feat:`, `fix:`, `docs:`)
7. Push to your fork and open a Pull Request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- **Oxylabs** for proxy infrastructure
- **Sentry** for error monitoring
- **Google Cloud Storage** for cloud sync
- **Pytest** for testing framework
- All contributors who helped improve this project
