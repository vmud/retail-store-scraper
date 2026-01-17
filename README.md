# Multi-Retailer Store Scraper

A scalable Python web scraper that collects retail store locations from multiple retailer websites. Supports concurrent execution across retailers, change detection for efficient reruns, and deployment on remote Linux servers.

## Features

- **Multi-Retailer Support**: Verizon, AT&T, Target, T-Mobile, Walmart, Best Buy (WIP)
- **Concurrent Execution**: Run all retailers simultaneously for faster completion
- **Change Detection**: Detect new, closed, and modified stores between runs
- **Checkpoint System**: Resume from interruptions without data loss
- **Anti-Blocking Measures**: User-agent rotation, random delays, rate limit handling
- **Docker Support**: Containerized deployment with docker-compose
- **Systemd Integration**: Persistent service for Linux servers
- **Web Dashboard**: Real-time monitoring with soft dark theme UI

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/vmud/retail-store-scraper.git
cd retail-store-scraper

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Usage

```bash
# Run a single retailer
python run.py --retailer verizon

# Run all retailers concurrently
python run.py --all

# Run with resume (continue from checkpoints)
python run.py --all --resume

# Run in test mode (10 stores per retailer)
python run.py --all --test

# Check status
python run.py --status

# Limit stores per retailer
python run.py --retailer target --limit 100
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--retailer, -r` | Run specific retailer (verizon, att, target, tmobile, walmart, bestbuy) |
| `--all, -a` | Run all retailers concurrently |
| `--exclude, -e` | Exclude retailers when using --all |
| `--resume` | Resume from checkpoints |
| `--incremental` | Only process new/changed stores |
| `--test` | Quick test mode (10 stores) |
| `--limit N` | Limit stores per retailer |
| `--status` | Show progress without running |
| `--verbose, -v` | Verbose output |

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
```

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

```bash
# Build and run all services
docker-compose up -d

# Run specific retailer
docker-compose run scraper python run.py --retailer verizon

# View logs
docker-compose logs -f scraper

# Access dashboard
# http://localhost:5000
```

## Linux Server Deployment

```bash
# Run installation script as root
sudo ./deploy/install.sh

# Start the service
sudo systemctl start retail-scraper

# Check status
sudo systemctl status retail-scraper

# View logs
sudo journalctl -u retail-scraper -f

# Check scraper status via SSH
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

| Metric | Direct Mode | With Proxies |
|--------|-------------|--------------|
| Full run (6 retailers) | ~8-12 hours | ~1-2 hours |
| Incremental run | ~1-2 hours | ~15-30 mins |
| IP blocking risk | Medium | Very Low |
| Rate limit handling | Manual delays | Automatic |

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
# All tests
pytest tests/

# Specific test file
pytest tests/test_change_detector.py

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Adding a New Retailer

1. Create scraper module: `src/scrapers/newretailer.py`
2. Add configuration: `config/newretailer_config.py`
3. Register in `src/scrapers/__init__.py`
4. Add to `config/retailers.yaml`
5. Write tests

## License

MIT License - see LICENSE file for details.
