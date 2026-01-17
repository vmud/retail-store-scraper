# Technical Specification: Multi-Retailer Scraper Dashboard

## Complexity Assessment: **Medium-Hard**

This task requires:
- Multi-retailer status tracking system (backend refactor)
- Scraper orchestration and control (start/stop/restart with resume)
- Real-time progress monitoring UI
- Configuration management interface with validation/rollback
- Historical run tracking
- Error handling and logging UI

**Scope Decisions**:
- **No pause/resume**: Use restart-from-checkpoint workflow instead
- **Internal tool**: Flask development server is sufficient
- **Smoke tests only**: Minimal automated testing for critical paths
- **Config editing**: Full implementation with robust validation and rollback

## 1. Technical Context

### Language & Framework
- **Backend**: Python 3.x with Flask
- **Frontend**: Vanilla JavaScript (no framework dependencies)
- **Styling**: Embedded CSS (following existing pattern)
- **Data Format**: JSON for API responses

### Existing Architecture
- Flask dashboard exists (`dashboard/app.py`) - currently Verizon-only
- Status tracking module (`src/shared/status.py`) - hardcoded for Verizon
- Multi-retailer scraper system with 6 retailers (Verizon, AT&T, Target, T-Mobile, Walmart, Best Buy)
- YAML-based configuration (`config/retailers.yaml`)
- Checkpoint-based progress tracking
- CLI orchestration (`run.py`) with concurrent execution support

### Dependencies
All required dependencies already exist in `requirements.txt`:
```
flask>=3.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
pyyaml>=6.0.0
aiohttp>=3.9.0  (for async scraping)
```

### Existing Utilities to Reuse

The codebase has robust utilities in `src/shared/utils.py` that should be leveraged:

**Progress Tracking:**
- `save_checkpoint(data, filepath)` - Atomic checkpoint saves with temp file
- `load_checkpoint(filepath)` - Load checkpoint data
- Both handle JSON serialization and error handling

**Logging:**
- `setup_logging(log_file)` - Configured logging with file + console handlers
- Already creates log directories and handles log rotation

**Data Export:**
- `save_to_csv(stores, filepath, fieldnames)` - CSV export utility
- `save_to_json(stores, filepath)` - JSON export utility

**Request Handling:**
- `get_with_retry()` - Request retry logic with exponential backoff
- `random_delay()` - Rate limiting delays
- `get_headers()` - User agent rotation

**Proxy Integration:**
- `ProxyClient` - Existing proxy client with Oxylabs support
- `get_proxy_client()` - Client instance management

**Reuse Strategy:**
- Run tracker should use `save_checkpoint()` for metadata persistence
- Logs should use existing `setup_logging()` infrastructure
- Status calculation should leverage existing checkpoint format

## 2. Implementation Approach

### Phase 1: Backend - Multi-Retailer Status System
Refactor status tracking to support all retailers dynamically.

**Changes Required:**
1. **`src/shared/status.py`** - Generalize from Verizon-specific to multi-retailer
   - Create `get_retailer_status(retailer: str)` function
   - Create `get_all_retailers_status()` function
   - Support different discovery methods (sitemap vs. HTML crawl)
   - Track per-retailer checkpoints and progress

2. **New: `src/shared/run_tracker.py`** - Track scraping run metadata
   - Run ID, start/end times, status (running/paused/complete/failed)
   - Error logs and statistics
   - Store in `data/{retailer}/runs/` directory

### Phase 2: Backend - Scraper Control API
Add endpoints to manage scraping operations.

**New API Endpoints in `dashboard/app.py`:**
```
GET  /api/status                    # All retailers status
GET  /api/status/<retailer>         # Single retailer status
POST /api/scraper/start             # Start scraper(s) with optional resume
POST /api/scraper/stop              # Stop scraper(s)
GET  /api/config                    # Get configuration
POST /api/config                    # Update configuration (with validation)
GET  /api/runs/<retailer>           # Historical runs
GET  /api/logs/<retailer>/<run_id>  # Run logs
```

**Implementation Strategy:**
- Use `subprocess.Popen()` to run scrapers asynchronously
- Store process references in memory (dict keyed by retailer)
- Graceful shutdown via process termination (SIGTERM)
- Resume via checkpoint detection (existing `--resume` flag in `run.py`)
- Config updates use atomic write (temp file + move) with YAML validation

### Phase 3: Frontend - Dashboard UI
Build comprehensive monitoring and control interface.

**UI Components:**
1. **Header Section**
   - Global status indicator (active scrapers count)
   - Last refresh timestamp
   - Manual refresh button

2. **Summary Cards**
   - Total stores scraped
   - Active retailers count
   - Overall progress percentage
   - Estimated time remaining

3. **Retailer Cards Grid** (matching mockup.html design)
   - Individual retailer status (running/complete/pending/disabled)
   - Progress bars with percentage
   - Stats grid (stores/duration/requests)
   - Phase indicators (Phase 1: States, Phase 2: Cities, Phase 3: URLs, Phase 4: Extract)
   - Control buttons (start/stop/restart-with-resume/configure)

4. **Configuration Modal**
   - Edit retailer-specific settings
   - Enable/disable retailers
   - Proxy configuration
   - Rate limiting settings

5. **Run History Panel**
   - List of past runs per retailer
   - Success/failure status
   - Duration and store count
   - View logs button

6. **Logs Viewer Modal**
   - Stream logs for active runs
   - View historical run logs
   - Filter by level (INFO/WARNING/ERROR)

### Phase 4: Real-Time Updates
Implement efficient progress updates.

**Strategy:**
- Auto-refresh every 5 seconds (configurable)
- Only fetch changed data (compare timestamps)
- Visual indicators for active scrapers
- Toast notifications for errors/completions

## 3. Source Code Structure Changes

### New Files
```
dashboard/
  static/
    dashboard.css          # Extracted styles
    dashboard.js           # Frontend logic
src/shared/
  run_tracker.py           # Run metadata tracking (uses utils.save_checkpoint)
  scraper_manager.py       # Scraper lifecycle management (subprocess wrapper)
tests/                     # NEW: Test infrastructure
  test_status.py           # Smoke tests for status calculation
  test_api.py              # Smoke tests for API endpoints
```

### New Directories (Data Structure)
```
data/{retailer}/          # Existing: per-retailer data
  runs/                   # NEW: Run metadata files
    {run_id}.json         # Run metadata (start/end times, stats, errors)
  checkpoints/            # EXISTING: Progress checkpoints
    states.json           # Phase 1: States (Verizon only)
    cities.json           # Phase 2: Cities (Verizon only)
    store_urls.json       # Phase 3: Store URLs (Verizon only)
    sitemap_urls.json     # Sitemap-based scrapers (AT&T, Target, etc.)
  output/                 # EXISTING: Final output files
    {retailer}_stores.csv
    {retailer}_stores.json
  logs/                   # NEW: Per-run log files
    {run_id}.log          # Individual run logs

logs/                     # EXISTING: Global application logs
  scraper.log             # Main scraper log (global)
```

**Note**: The distinction between `logs/` (global app logs) and `data/{retailer}/logs/` (per-run logs) is intentional for better organization.

### Modified Files
```
dashboard/app.py           # Add new API endpoints
src/shared/status.py       # Generalize to multi-retailer
src/shared/utils.py        # Add run tracking utilities
run.py                     # Add API mode for dashboard control
```

## 4. Data Model Changes

### Run Metadata (`data/{retailer}/runs/{run_id}.json`)
```json
{
  "run_id": "verizon_20260117_044500",
  "retailer": "verizon",
  "status": "running",
  "started_at": "2026-01-17T04:45:00Z",
  "completed_at": null,
  "config": {
    "resume": false,
    "incremental": false,
    "limit": null,
    "proxy_mode": "direct"
  },
  "stats": {
    "stores_scraped": 1247,
    "requests_made": 1250,
    "errors": 3,
    "duration_seconds": 3600
  },
  "phases": {
    "states": {"total": 51, "completed": 51, "status": "complete"},
    "cities": {"total": 1423, "completed": 1423, "status": "complete"},
    "urls": {"total": 2100, "completed": 2100, "status": "complete"},
    "extract": {"total": 2100, "completed": 1247, "status": "in_progress"}
  },
  "errors": [
    {"timestamp": "...", "message": "...", "url": "..."}
  ]
}
```

### Status API Response (`/api/status`)
```json
{
  "global": {
    "active_scrapers": 3,
    "total_stores_today": 47892,
    "overall_progress": 68.4
  },
  "retailers": {
    "verizon": {
      "enabled": true,
      "status": "running",
      "current_run": "verizon_20260117_044500",
      "progress": 88.0,
      "stats": {...},
      "phases": {...}
    },
    "att": {
      "enabled": true,
      "status": "complete",
      "last_run": "att_20260116_120000",
      "progress": 100.0,
      "stats": {...}
    }
  }
}
```

## 5. Interface Changes

### API Contracts

#### Start Scraper
```http
POST /api/scraper/start
Content-Type: application/json

{
  "retailer": "verizon",  # or "all" for all enabled
  "config": {
    "resume": false,
    "incremental": false,
    "limit": null,
    "proxy_mode": "direct"
  }
}

Response:
{
  "status": "started",
  "run_id": "verizon_20260117_044500",
  "message": "Scraper started successfully"
}
```

#### Stop Scraper
```http
POST /api/scraper/stop
Content-Type: application/json

{
  "retailer": "verizon"  # or "all"
}

Response:
{
  "status": "stopped",
  "message": "Scraper stopped successfully"
}
```

### Configuration API
```http
GET /api/config
Response: 
{
  "proxy": {...},
  "defaults": {...},
  "retailers": {...}
}

POST /api/config
Content-Type: application/json
Body: {updated retailers.yaml structure}

Response (success):
{
  "status": "updated",
  "message": "Configuration saved successfully",
  "backup_file": "config/retailers.yaml.backup.20260117_044500"
}

Response (validation error):
{
  "status": "error",
  "message": "Invalid YAML structure",
  "errors": ["retailers.verizon.min_delay must be numeric", ...]
}
```

**Validation & Rollback Strategy:**
1. Create backup: `config/retailers.yaml.backup.{timestamp}`
2. Write to temp file: `config/retailers.yaml.tmp`
3. Validate YAML syntax with `yaml.safe_load()`
4. Validate required fields (mode, enabled, base_url, etc.)
5. Validate types (min_delay is float, enabled is bool, etc.)
6. If validation passes: atomic move temp → `retailers.yaml`
7. If validation fails: delete temp, return error response
8. Keep last 5 backups, delete older ones

## 6. Verification Approach

### Testing Strategy

**Smoke Tests Only** (minimal automated testing for critical paths):

1. **`tests/test_status.py`** - Status calculation smoke tests
   - Test `get_retailer_status('verizon')` with mock checkpoints
   - Test `get_all_retailers_status()` returns all 6 retailers
   - Test phase detection for sitemap vs HTML crawl methods

2. **`tests/test_api.py`** - API endpoint smoke tests
   - Test `GET /api/status` returns valid JSON
   - Test `POST /api/scraper/start` with invalid retailer returns 400
   - Test `POST /api/config` with invalid YAML returns error

**Test Infrastructure:**
- Create `tests/` directory (doesn't currently exist)
- Use `pytest` and `pytest-flask` for testing
- Mock file I/O and subprocess calls
- No integration tests or full scraper runs

**Manual Verification:**
- Start Verizon scraper, verify real-time progress
- Start multiple scrapers concurrently
- Test stop functionality
- Test restart with resume (--resume flag)
- Verify configuration changes persist with rollback
- Check historical run data accuracy

### Lint & Type Checking
```bash
# No linting commands found in codebase
# Manual code review only
```

### Manual Testing Checklist
- [ ] Dashboard loads with all 6 retailers displayed
- [ ] Status updates every 5 seconds via auto-refresh
- [ ] Start button initiates scraping (verify process spawned)
- [ ] Stop button terminates gracefully (verify SIGTERM sent)
- [ ] Restart with resume uses existing checkpoints
- [ ] Progress bars update accurately (match checkpoint data)
- [ ] Phase indicators show correct status (Phase 1-4 for Verizon, different for sitemap scrapers)
- [ ] Configuration modal opens and displays current YAML
- [ ] Configuration saves create backup file
- [ ] Invalid configuration shows error and rolls back
- [ ] Historical runs display correctly per retailer
- [ ] Logs viewer shows run logs with proper formatting
- [ ] Error handling displays user-friendly messages
- [ ] No console errors in browser developer tools

## 7. UI Design Guidelines

Following the mockup.html aesthetic:
- **Color Scheme**: Dark blue gradient background (#1e3a5f to #0d1b2a)
- **Cards**: White with subtle shadows and hover effects
- **Status Colors**:
  - Running: Green (#10b981)
  - Complete: Blue (#dbeafe)
  - Pending: Gray (#f3f4f6)
  - Error: Red (#ef4444)
- **Typography**: System font stack (-apple-system, BlinkMacSystemFont, ...)
- **Retailer Brand Colors**: Verizon (#cd040b), AT&T (#00a8e0), Target (#cc0000), T-Mobile (#e20074), Walmart (#0071ce), Best Buy (#0046be)
- **Animations**: Pulse for active status, smooth transitions on hover

## 8. Security Considerations

- **No authentication** (internal tool assumption)
- **Input validation** on all API endpoints
- **Safe YAML parsing** (use `yaml.safe_load`)
- **Process isolation** for scraper execution
- **No credential exposure** in API responses
- **Rate limiting** on control endpoints (prevent spam)

## 9. Performance Considerations

- **Efficient polling**: Only fetch changed data
- **Lazy loading**: Don't load all run history upfront
- **Checkpoint caching**: Cache status reads for 1-2 seconds
- **Background processes**: Don't block API responses
- **Memory limits**: Clean up completed run references

## 10. Deployment Notes

**Target Environment**: Internal tool only (development server is sufficient)

### Running the Dashboard
```bash
# Start dashboard server (Flask development server)
python dashboard/app.py

# Access at http://localhost:5000
# Note: Only accessible from localhost by default (host='0.0.0.0' already configured)
```

### File Permissions
- `data/` directory must be writable (for checkpoints, runs, logs)
- `logs/` directory must be writable (for global logs)
- `config/` directory must be readable/writable (for YAML updates and backups)

### Environment Variables
- Proxy credentials loaded from env (existing pattern)
- No new environment variables required

### Production Considerations (NOT REQUIRED)
Since this is an internal tool, the following are NOT needed:
- WSGI server (gunicorn/uwsgi)
- CORS configuration
- SSL/HTTPS
- Authentication/authorization
- Rate limiting (beyond basic spam prevention)
- Load balancing or horizontal scaling

### Static File Serving
Flask is configured to serve static files from `dashboard/static/` directory (will be added to app.py):
```python
app = Flask(__name__, static_folder='static', static_url_path='/static')
```

---

## Implementation Plan

Given the complexity, this should be broken into detailed steps:

1. **Backend Status Refactor** - Generalize status.py for all retailers
2. **Run Tracking System** - Implement run metadata and logging
3. **Scraper Manager** - Process lifecycle management
4. **API Endpoints** - Add control and status APIs
5. **Frontend UI** - Build dashboard interface
6. **Real-Time Updates** - Implement polling mechanism
7. **Configuration UI** - Build config editor
8. **Historical Runs** - Add run history panel
9. **Testing & Polish** - Fix bugs, improve UX
10. **Documentation** - Update README with dashboard usage

Each step should be incrementally testable.
