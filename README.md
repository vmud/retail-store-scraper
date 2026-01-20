# Multi-Retailer Store Scraper

A production-ready Python web scraper that collects retail store locations from multiple retailer websites. Features concurrent execution, intelligent change detection, optional proxy integration, and a modern real-time monitoring dashboard.

## Features

### Core Capabilities
- **Multi-Retailer Support**: Verizon, AT&T, Target, T-Mobile, Walmart, Best Buy (WIP)
- **Concurrent Execution**: Run all retailers simultaneously for faster completion
- **Change Detection**: Detect new, closed, and modified stores between runs with incremental mode
- **Checkpoint System**: Resume from interruptions without data loss
- **Memory Efficient**: Streaming JSON parser for large datasets (50MB+ files)
- **Flexible Export**: JSON, CSV, Excel, and GeoJSON format support

### Anti-Blocking & Performance
- **Oxylabs Proxy Integration**: Support for residential proxies and Web Scraper API
- **JavaScript Rendering**: Dynamic content scraping for complex sites
- **Smart Rate Limiting**: Configurable delays and pause thresholds
- **User-Agent Rotation**: Multiple browser signatures
- **Automatic Retry**: HTTP 429/500 error handling with exponential backoff

### Deployment & Monitoring
- **Docker Support**: Multi-stage builds with health checks and non-root user
- **Systemd Integration**: Production-grade service for Linux servers
- **Web Dashboard**: Real-time monitoring with soft dark theme UI
- **API Rate Limiting**: Flask-Limiter integration for dashboard endpoints
- **Security Hardening**: CSRF protection, XSS prevention, path traversal safeguards

## Quick Links

- **[Deployment Guide](DEPLOYMENT.md)**: Complete deployment instructions for remote dev servers
- **[Agent Guide](AGENTS.md)**: Contributor instructions, structure, and coding standards
- **[Claude Guide](CLAUDE.md)**: AI assistant context and development patterns

## Quick Start

### Local Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/retail-store-scraper.git
cd retail-store-scraper

# Create virtual environment (requires Python 3.8-3.11)
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Copy environment template
cp .env.example .env
# Edit .env with your Oxylabs credentials (if using proxies)
```

### Remote Server Deployment

For production deployment to a remote dev server, see the comprehensive [Deployment Guide](DEPLOYMENT.md) with detailed instructions for:
- Docker deployment (recommended)
- Native Python deployment
- Systemd service deployment
- Network security and monitoring

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
python run.py --all --exclude bestbuy --resume

# Verbose logging for debugging
python run.py --retailer verizon --verbose
```

## CLI Options

### Basic Options
| Option | Description |
|--------|-------------|
| `--retailer, -r` | Run specific retailer (verizon, att, target, tmobile, walmart, bestbuy) |
| `--all, -a` | Run all enabled retailers concurrently |
| `--exclude, -e` | Exclude retailers when using --all (comma-separated) |
| `--resume` | Resume from checkpoints |
| `--incremental` | Only process new/changed stores (change detection mode) |
| `--test` | Quick test mode (limit 10 stores per retailer) |
| `--limit N` | Limit stores per retailer (cannot combine with --test) |
| `--status` | Show progress without running scrapers |
| `--verbose, -v` | Verbose output with debug logging |

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
| `--format FORMATS` | Export formats: `json`, `csv`, `excel`, `geojson` (comma-separated) |
| `--no-export` | Skip export generation |

## Project Structure

```
retail-store-scraper/
├── run.py                      # Unified CLI entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── config/
│   ├── retailers.yaml          # All retailer configurations
│   └── *_config.py             # Per-retailer Python configs
├── src/
│   ├── change_detector.py      # Change detection system
│   ├── shared/
│   │   ├── utils.py            # HTTP, checkpoints, exports
│   │   └── request_counter.py  # Rate limiting
│   └── scrapers/
│       ├── verizon.py
│       ├── att.py
│       ├── target.py
│       ├── tmobile.py
│       ├── walmart.py
│       └── bestbuy.py
├── dashboard/
│   ├── app.py                  # Flask backend API
│   ├── index.html              # Dashboard entry point
│   ├── vite.config.js          # Vite build configuration
│   └── src/
│       ├── main.js             # App initialization
│       ├── api.js              # API client
│       ├── state.js            # Reactive state store
│       ├── components/         # UI components
│       └── styles/             # CSS design system
├── deploy/
│   ├── scraper.service         # Systemd unit file
│   └── install.sh              # Linux deployment script
└── data/                       # Output data (gitignored)
    └── {retailer}/
        ├── checkpoints/
        ├── output/
        └── history/
```

## Web Dashboard

The dashboard provides real-time monitoring of scraper operations with a modern soft dark theme.

### Features

- **Real-time Updates**: Auto-refreshes every 5 seconds with no visual flash
- **Retailer Cards**: Progress bars, store counts, duration, and phase tracking
- **Brand Identity**: Each retailer has its logo and accent color
- **Config Editor**: Edit `retailers.yaml` directly from the UI
- **Log Viewer**: Filter logs by level (INFO, WARNING, ERROR, DEBUG)
- **Change Detection**: Delta report showing new, closed, and modified stores

### Running the Dashboard

```bash
# Start the Flask server
cd dashboard
python app.py

# Access at http://localhost:5001

# With API authentication (optional)
export DASHBOARD_API_KEY=$(openssl rand -hex 32)
python app.py
```

**Dashboard Features:**
- Real-time scraper status and progress tracking
- Live log viewer with level filtering (INFO, WARNING, ERROR, DEBUG)
- Configuration editor for `retailers.yaml`
- Change detection reports (new/closed/modified stores)
- Export panel for downloading data in multiple formats
- Keyboard shortcuts (ESC to close modals, etc.)
- Auto-refresh every 5 seconds with smooth animations

### Development

```bash
cd dashboard

# Install dependencies
npm install

# Development mode with hot reload
npm run dev

# Production build
npm run build
```

### Screenshot

![Dashboard](https://github.com/vmud/retail-store-scraper/assets/dashboard-preview.png)

## Docker Deployment

### Quick Start

```bash
# Build and run all services (dashboard + scraper)
docker compose up -d

# Check container status
docker compose ps

# View logs
docker compose logs -f scraper
docker compose logs -f dashboard

# Access dashboard at http://localhost:5001
```

### Container Management

```bash
# Run specific retailer
docker compose exec scraper python run.py --retailer verizon

# Run all with proxies
docker compose exec scraper python run.py --all --proxy residential --resume

# Check scraper status
docker compose exec scraper python run.py --status

# Stop services
docker compose down

# Rebuild after code changes
docker compose build
docker compose up -d
```

### Environment Variables

```bash
# Set proxy credentials
export OXYLABS_RESIDENTIAL_USERNAME=your_username
export OXYLABS_RESIDENTIAL_PASSWORD=your_password

# Set dashboard API key (optional)
export DASHBOARD_API_KEY=$(openssl rand -hex 32)

# Start with environment
docker compose up -d
```

**Container Features:**
- Multi-stage build for smaller image size (non-root user, security hardening)
- Health checks for dashboard service
- Automatic restarts on failure
- Volume mounts for data persistence
- Isolated network for security

## Linux Server Deployment

For detailed deployment instructions including network setup, security, and troubleshooting, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Quick Deploy

```bash
# Clone repository on server
git clone https://github.com/yourusername/retail-store-scraper.git
cd retail-store-scraper

# Run installation script as root
sudo ./deploy/install.sh

# Configure environment
sudo nano /opt/retail-store-scraper/.env

# Start services
sudo systemctl start retail-scraper
sudo systemctl enable retail-scraper

# Check status
sudo systemctl status retail-scraper

# View logs
sudo journalctl -u retail-scraper -f
```

### Systemd Management

```bash
# Start/stop/restart
sudo systemctl start retail-scraper
sudo systemctl stop retail-scraper
sudo systemctl restart retail-scraper

# Enable/disable auto-start
sudo systemctl enable retail-scraper
sudo systemctl disable retail-scraper

# Check scraper status remotely
ssh user@server "cd /opt/retail-store-scraper && ./venv/bin/python run.py --status"
```

## Data Output

### Output Files

- `data/{retailer}/output/stores_latest.json` - Current run data
- `data/{retailer}/output/stores_latest.csv` - Current run CSV
- `data/{retailer}/output/stores_previous.json` - Previous run data

### Change Detection

```bash
# Run with incremental mode to detect changes
python run.py --retailer target --incremental
```

Change reports are saved to `data/{retailer}/history/changes_YYYY-MM-DD.json` and include:
- New stores (opened since last run)
- Closed stores (removed since last run)
- Modified stores (changed attributes)

## Configuration

### Retailer Configuration

Edit `config/retailers.yaml` to customize:
- Request delays
- Pause thresholds
- Enabled/disabled retailers
- Output fields

### Anti-Blocking Settings

Each retailer has configurable anti-blocking measures:
- `min_delay` / `max_delay`: Random delay between requests
- `pause_50_requests`: Pause after every 50 requests
- `pause_200_requests`: Longer pause after 200 requests
- User-agent rotation (4 different browsers)

### Oxylabs Proxy Integration (Optional)

For faster scraping with reduced blocking risk, integrate with [Oxylabs](https://oxylabs.io/) proxy services.

#### Setup

1. Sign up at [Oxylabs](https://oxylabs.io/) and get your credentials
2. Set environment variables:
   ```bash
   export OXYLABS_USERNAME=your_username
   export OXYLABS_PASSWORD=your_password
   ```

3. Or create a `.env` file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

#### Proxy Modes

| Mode | Description | Best For |
|------|-------------|----------|
| `direct` | No proxy (default) | Testing, low-volume |
| `residential` | 175M+ rotating residential IPs | Most retailers |
| `web_scraper_api` | Managed service with JS rendering | Walmart, Best Buy |

#### Usage

```bash
# Run with residential proxies
python run.py --all --proxy residential

# Run with Web Scraper API (includes JS rendering)
python run.py --retailer walmart --proxy web_scraper_api --render-js

# Specify country for geo-targeting
python run.py --all --proxy residential --proxy-country us

# Configure in retailers.yaml (per-retailer override)
# See config/retailers.yaml for examples
```

#### Docker with Proxies

```bash
# Set credentials and run
OXYLABS_USERNAME=user OXYLABS_PASSWORD=pass \
  docker-compose run scraper python run.py --all --proxy residential
```

## Expected Performance

| Metric | Direct Mode | Residential Proxy | Web Scraper API |
|--------|-------------|-------------------|-----------------|
| Full run (6 retailers) | 8-12 hours | 1-2 hours | 30-60 mins |
| Incremental run | 1-2 hours | 15-30 mins | 5-15 mins |
| Test mode (60 stores) | 5-10 mins | 1-2 mins | <1 min |
| IP blocking risk | Medium | Very Low | None |
| Rate limit handling | Manual delays | Automatic rotation | Managed service |
| JavaScript rendering | ❌ No | ❌ No | ✅ Yes |
| Memory usage (peak) | ~500MB | ~500MB | ~300MB |

**Performance Tips:**
- Use `--proxy residential` for 6-8x speedup without blocking
- Use `--incremental` after first run to only process changes
- Use `--resume` to continue interrupted runs without data loss
- Run retailers individually during peak hours to reduce server load

## Supported Retailers

| Retailer | Status | Discovery Method |
|----------|--------|------------------|
| Verizon | ✅ Active | 4-phase HTML crawl |
| AT&T | ✅ Active | XML Sitemap |
| Target | ✅ Active | Gzipped Sitemap + API |
| T-Mobile | ✅ Active | Paginated Sitemaps |
| Walmart | ✅ Active | Multiple Gzipped Sitemaps |
| Best Buy | 🚧 WIP | XML Sitemap |

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

# Run integration tests only
pytest tests/test_proxy_integration.py -v

# Run with verbose output
pytest tests/ -v -s
```

### Linting

```bash
# Lint all Python files (matches CI pipeline)
pylint $(git ls-files '*.py')

# Lint specific file
pylint src/scrapers/verizon.py

# Check for common issues
pylint --disable=all --enable=E,F src/
```

### Adding a New Retailer

1. **Create scraper module**: `src/scrapers/newretailer.py`
   - Implement `run(session, retailer_config, retailer, **kwargs)` function
   - Return `{'stores': [...], 'count': int, 'checkpoints_used': bool}`
   - Use `src/shared/utils.py` helpers for HTTP requests and validation

2. **Add configuration**: `config/newretailer_config.py`
   - Define sitemap URLs, delays, retry settings
   - Export required store fields

3. **Register scraper**: `src/scrapers/__init__.py`
   - Add to `SCRAPER_REGISTRY` dict
   - Import scraper module

4. **Configure retailer**: `config/retailers.yaml`
   - Add retailer block with enabled flag, delays, output fields
   - Optionally set proxy mode and rendering settings

5. **Write tests**: `tests/test_scrapers/test_newretailer.py`
   - Test scraper function with mocked responses
   - Verify data validation and checkpoint handling
   - Test error handling and edge cases

6. **Run validation**:
   ```bash
   # Test scraper
   python run.py --retailer newretailer --test
   
   # Run unit tests
   pytest tests/test_scrapers/test_newretailer.py -v
   
   # Lint code
   pylint src/scrapers/newretailer.py
   ```

### CI/CD Pipeline

GitHub Actions workflows:
- **Pylint**: Runs on every push/PR to check code quality
- **Pytest**: Runs full test suite on Python 3.8-3.11
- **Security**: Scans for vulnerabilities and secrets

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the coding standards in [AGENTS.md](AGENTS.md)
4. Write tests for new functionality
5. Run linter and tests locally
6. Commit changes with conventional commit messages (`feat:`, `fix:`, `docs:`)
7. Push to your fork and open a Pull Request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- **Oxylabs** for proxy infrastructure
- **Flask** and **Vite** for dashboard framework
- **Pytest** for testing framework
- All contributors who helped improve this project
