# Technical Specification: Multi-Retailer Scraper Dashboard

## Complexity Assessment: **Medium-Hard**

This task requires:
- Multi-retailer status tracking system (backend refactor)
- Scraper orchestration and control (start/stop/configure)
- Real-time progress monitoring UI
- Configuration management interface
- Historical run tracking
- Error handling and logging UI

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
```
flask>=3.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
pyyaml>=6.0.0
aiohttp>=3.9.0  (for async scraping)
```

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
POST /api/scraper/start             # Start scraper(s)
POST /api/scraper/stop              # Stop scraper(s)
POST /api/scraper/pause             # Pause scraper(s)
POST /api/scraper/resume            # Resume scraper(s)
GET  /api/config                    # Get configuration
POST /api/config                    # Update configuration
GET  /api/runs/<retailer>           # Historical runs
GET  /api/logs/<retailer>/<run_id>  # Run logs
```

**Implementation Strategy:**
- Use threading/subprocess to run scrapers asynchronously
- Store process references in memory (dict keyed by retailer)
- Signal-based pause/resume mechanism
- Atomic checkpoint updates for safety

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
   - Phase indicators
   - Control buttons (start/stop/pause/configure)

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
  run_tracker.py           # Run metadata tracking
  scraper_manager.py       # Scraper lifecycle management
data/
  {retailer}/
    runs/
      {run_id}.json        # Run metadata
    logs/
      {run_id}.log         # Run logs
    checkpoints/
      {checkpoint}.json    # Progress checkpoints
    output/
      {file}.json/csv      # Final output
```

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
Response: {retailers.yaml content}

POST /api/config
Content-Type: application/json
Body: {updated retailers.yaml}
```

## 6. Verification Approach

### Testing Strategy
1. **Unit Tests** (`pytest`)
   - `test_multi_retailer_status.py` - Status calculation for all retailers
   - `test_run_tracker.py` - Run metadata tracking
   - `test_scraper_manager.py` - Lifecycle management

2. **Integration Tests**
   - API endpoint functionality
   - Concurrent scraper execution
   - Progress updates during active runs

3. **Manual Verification**
   - Start Verizon scraper, verify real-time progress
   - Start multiple scrapers concurrently
   - Test pause/resume functionality
   - Verify configuration changes persist
   - Check historical run data accuracy

### Lint & Type Checking
```bash
# No specific commands found in codebase
# Will ask user for project standards
```

### Manual Testing Checklist
- [ ] Dashboard loads with all retailers
- [ ] Status updates every 5 seconds
- [ ] Start button initiates scraping
- [ ] Stop button terminates gracefully
- [ ] Progress bars update accurately
- [ ] Configuration modal saves changes
- [ ] Historical runs display correctly
- [ ] Logs viewer shows real-time logs
- [ ] Error handling displays user-friendly messages
- [ ] Responsive design works on mobile

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

### Running the Dashboard
```bash
# Start dashboard server
python dashboard/app.py

# Access at http://localhost:5000
```

### File Permissions
- `data/` directory must be writable
- Log files in `logs/` directory
- Configuration in `config/` must be readable/writable

### Environment Variables
- Proxy credentials loaded from env (existing pattern)
- No new environment variables required

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
