# Spec and build

## Configuration
- **Artifacts Path**: {@artifacts_path} → `.zenflow/tasks/{task_id}`

---

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:
- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Technical Specification
<!-- chat-id: 86cfd8be-eb3b-416e-b3d7-d78ac0471c6a -->

**Completed**: Created comprehensive technical specification in `spec.md`
- **Complexity**: Medium-Hard
- **Approach**: Multi-phase implementation (Backend → API → Frontend → Polish)
- **Files**: 6 new files, 4 modified files
- **Key Components**: Multi-retailer status tracking, scraper orchestration API, dashboard UI

---

### [x] Step: Backend - Multi-Retailer Status System
<!-- chat-id: bcee6ba8-85c8-4815-93ad-9fa80a66ae0c -->

**Completed**: Refactored status tracking to support all 6 retailers dynamically.

**Files Modified:**
- `src/shared/status.py` - Generalized status calculation
  - Added `get_retailer_status(retailer: str)` function
  - Added `get_all_retailers_status()` function
  - Supports different discovery methods (html_crawl, sitemap, sitemap_gzip, sitemap_paginated)
  - Dynamic checkpoint path resolution via `get_checkpoint_path()`
  - HTML crawl method: 4 phases (states, cities, urls, extract)
  - Sitemap methods: 2 phases (sitemap, extract)

**Files Created:**
- `src/shared/run_tracker.py` - Run metadata tracking
  - `RunTracker` class for tracking individual runs
  - Metadata includes: run_id, status, timestamps, config, stats, phases, errors
  - Helper functions: `get_run_history()`, `get_latest_run()`, `get_active_run()`, `cleanup_old_runs()`
  - Uses existing checkpoint utilities for persistence

**Verification Completed:**
- ✅ Tested status calculation for all 6 retailers (verizon, att, target, tmobile, walmart, bestbuy)
- ✅ Verified checkpoint path resolution for each retailer
- ✅ Confirmed phase detection works for html_crawl (4 phases) and sitemap methods (2 phases)
- ✅ Tested RunTracker with stats updates, error logging, and status transitions

---

### [x] Step: Backend - Scraper Control & Management
<!-- chat-id: 3f5c9c40-888d-4ea5-bbed-46d3ba072fd5 -->

**Completed**: Implemented scraper lifecycle management and control system.

**Files Created:**
- `src/shared/scraper_manager.py` - Process lifecycle management
  - `ScraperManager` class for managing scraper processes
  - `start()` - Start scrapers with subprocess.Popen, supports resume/limit/test/proxy options
  - `stop()` - Graceful shutdown with SIGTERM, fallback to SIGKILL after timeout
  - `restart()` - Stop and start with resume flag support
  - `is_running()` - Check if scraper process is active
  - `get_status()` / `get_all_status()` - Query running scrapers
  - `stop_all()` - Bulk stop operation
  - `cleanup_exited()` - Clean up finished processes
  - Singleton pattern with `get_scraper_manager()`

**Files Modified:**
- `src/shared/__init__.py` - Added exports for scraper_manager, run_tracker, and status modules

**Integration:**
- Uses existing `run.py` CLI via subprocess
- Integrates with `RunTracker` to track PIDs and metadata
- Leverages existing checkpoint system for resume functionality
- Creates per-run log files in `data/{retailer}/logs/{run_id}.log`
- Validates retailer config before starting

**Production-Ready Features:**
- ✅ Thread-safe with `threading.Lock` for Flask integration
- ✅ Process state persistence - recovers running processes after restart
- ✅ Updates RunTracker status when processes exit (complete/failed)
- ✅ Windows compatibility - handles SIGTERM vs terminate()
- ✅ Automatic cleanup on exit - atexit handler stops all scrapers
- ✅ Handles both live and recovered processes
- ✅ Error tracking on startup failures

**Verification Completed:**
- ✅ Start a scraper via manager (process spawned and verified with os.kill)
- ✅ Stop a running scraper gracefully (SIGTERM sent, timeout handling works)
- ✅ Restart with resume flag (checkpoint loaded, resume=True in config)
- ✅ Handle errors during scraper execution (ValueError for invalid/disabled retailers)
- ✅ Multiple concurrent scrapers (started 3 retailers simultaneously)
- ✅ Log file creation in correct location (data/{retailer}/logs/)
- ✅ Run tracking integration (PIDs, configs, run IDs preserved correctly)
- ✅ RunTracker status updated on process exit (status=complete, config preserved)
- ✅ Process recovery on manager restart (finds running processes via PID check)

---

### [x] Step: API - Control Endpoints
<!-- chat-id: 61258bbc-a282-4d13-a959-b5be53f32bcd -->

**Completed**: Implemented comprehensive REST API for scraper control and monitoring.

**Files Modified:**
- `dashboard/app.py` - Added 10 new API endpoints with full error handling

**Endpoints Implemented:**
- ✅ `GET /api/status` - All retailers status with global stats
- ✅ `GET /api/status/<retailer>` - Single retailer status (404 on invalid)
- ✅ `POST /api/scraper/start` - Start scraper(s) with options (resume, test, proxy, etc.)
- ✅ `POST /api/scraper/stop` - Stop scraper(s) gracefully with timeout
- ✅ `POST /api/scraper/restart` - Restart with resume support
- ✅ `GET /api/runs/<retailer>` - Historical runs with limit parameter
- ✅ `GET /api/logs/<retailer>/<run_id>` - View logs with tail/follow options
- ✅ `GET /api/config` - Get current YAML configuration
- ✅ `POST /api/config` - Update configuration with validation

**Key Features Implemented:**
- ✅ Config validation: YAML syntax, required fields (name, enabled, base_url, discovery_method)
- ✅ Config backup: Timestamped backups in `config/backups/` directory
- ✅ Atomic writes: Temp file → validate → atomic replace (no partial updates)
- ✅ Comprehensive error responses: 400/404/500 with detailed error messages
- ✅ Batch operations: Start/stop "all" retailers at once
- ✅ Thread-safe: Uses scraper manager singleton with lock
- ✅ JSON API: All responses return proper JSON with error details

**Verification Completed:**
- ✅ Tested all endpoints with curl (see `tests/test_api_endpoints.sh`)
- ✅ Error handling verified (invalid retailer, missing params, YAML errors)
- ✅ Config validation tested (invalid YAML syntax rejected)
- ✅ Config validation tested (missing required fields rejected)
- ✅ Config backup created successfully with timestamp
- ✅ Atomic write confirmed (temp file → validate → replace)
- ✅ Run history endpoint returns correct data
- ✅ Status endpoints return proper structure for all 6 retailers

**Security Fixes Applied:**
- ✅ Fixed path traversal vulnerability in logs endpoint (retailer validation + run_id sanitization)
- ✅ Removed broken log streaming (follow parameter) - now returns full log content
- ✅ Added Content-Type validation on all POST endpoints (415 error if not JSON)
- ✅ Enhanced config validation: URL format, positive numbers, discovery method
- ✅ Added retailer validation to `/api/runs/<retailer>` endpoint
- ✅ Added batch support ("all") to restart endpoint for consistency
- ✅ Config reload mechanism implemented (forces fresh load after update)
- ✅ All security tests passing (see `tests/test_security_fixes.sh`)

---

### [ ] Step: Frontend - Core Dashboard UI

Build main dashboard interface with retailer cards and status display.

**Files to Create:**
- `dashboard/static/dashboard.css` - Extracted styles
- `dashboard/static/dashboard.js` - Frontend logic

**Files to Modify:**
- `dashboard/app.py` - Serve static files, update main route

**Components to Implement:**
1. Header with global status
2. Summary cards (total stores, active retailers, progress)
3. Retailer cards grid with:
   - Status indicators (running/complete/pending/disabled)
   - Progress bars with percentage
   - Stats (stores/duration/requests)
   - Phase indicators (Phase 1-4 for Verizon, different for sitemap scrapers)
   - Control buttons (start/stop/restart with resume/configure)

**Design Guidelines:**
- Match mockup.html color scheme (dark blue gradient)
- Retailer-specific brand colors (Verizon #cd040b, AT&T #00a8e0, etc.)
- Smooth animations and hover effects

**Verification:**
- Dashboard loads successfully with all 6 retailers
- All retailers display correctly
- Cards match mockup design aesthetically
- Responsive layout works on desktop
- No console errors in browser

---

### [ ] Step: Frontend - Real-Time Updates

Implement auto-refresh and real-time progress monitoring.

**Files to Modify:**
- `dashboard/static/dashboard.js` - Add polling mechanism

**Features:**
- Auto-refresh every 5 seconds
- Visual indicators for active scrapers
- Smooth progress bar animations
- Last updated timestamp

**Verification:**
- Start scraper, verify progress updates automatically
- Check CPU/memory usage during polling
- Verify updates stop when scraper completes

---

### [ ] Step: Frontend - Configuration Management

Add configuration editor and modal interface.

**Files to Modify:**
- `dashboard/static/dashboard.js` - Configuration modal
- `dashboard/static/dashboard.css` - Modal styles

**Features:**
- Modal to view/edit retailer settings (JSON editor or form)
- Enable/disable retailers (toggle switches)
- Proxy configuration UI (mode, country, render_js)
- Rate limiting settings (min_delay, max_delay, etc.)
- Client-side validation before API call
- Display server-side validation errors
- Show success message with backup file path

**Validation Strategy:**
- Client-side: Check required fields, numeric types
- Server-side: Full YAML validation (already implemented in Step 3)
- Show user-friendly error messages

**Verification:**
- Open config modal, displays current YAML correctly
- Edit settings (enable/disable retailer, change delays)
- Save with valid changes (verify backup created)
- Save with invalid YAML (verify error shown, no changes made)
- Verify YAML file updated correctly
- Check backup file exists in `config/` directory

---

### [ ] Step: Frontend - Run History & Logs

Implement historical run tracking and log viewer.

**Files to Modify:**
- `dashboard/static/dashboard.js` - History panel and logs viewer
- `dashboard/static/dashboard.css` - Panel styles
- `dashboard/app.py` - Logs streaming endpoint

**Features:**
- Run history panel (collapsible)
- List past runs per retailer
- View logs button
- Real-time log streaming for active runs
- Filter logs by level (INFO/WARNING/ERROR)

**Verification:**
- Complete a scraping run
- View run in history panel
- Open logs viewer and verify content
- Test log filtering

---

### [ ] Step: Testing & Bug Fixes

Write smoke tests and fix issues discovered during integration.

**Test Infrastructure Setup:**
1. Create `tests/` directory
2. Add `pytest-flask` to requirements.txt
3. Create `tests/conftest.py` with fixtures

**Smoke Tests to Write:**
- `tests/test_status.py` - Status calculation
  - Test `get_retailer_status('verizon')` with mock checkpoints
  - Test `get_all_retailers_status()` returns all 6 retailers
  - Test phase detection for different scraper types
- `tests/test_api.py` - API endpoints
  - Test `GET /api/status` returns valid JSON
  - Test `POST /api/scraper/start` with invalid retailer returns 400
  - Test `POST /api/config` with invalid YAML returns error

**Manual Testing:**
- Run all scrapers concurrently (verify no conflicts)
- Test stop functionality (verify graceful shutdown)
- Test restart with resume (verify checkpoint usage)
- Verify error handling displays properly in UI
- Check edge cases (no data, failed runs, missing checkpoints)

**Verification:**
- All smoke tests pass: `pytest tests/`
- Manual test checklist completed (see spec.md)
- No console errors in browser
- API returns proper status codes (200, 400, 500)

---

### [ ] Step: Polish & Documentation

Final improvements and user documentation.

**Tasks:**
1. Improve error messages
2. Add loading states and spinners
3. Improve mobile responsiveness
4. Add tooltips for clarity
5. Performance optimization
6. Update README with dashboard usage

**Verification:**
- Dashboard feels polished and professional
- All UI elements work smoothly
- Documentation is clear and complete
