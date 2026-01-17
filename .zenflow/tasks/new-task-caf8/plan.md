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

### [x] Step: Frontend - Core Dashboard UI
<!-- chat-id: 4ef560d4-267b-431f-ad2f-953069dcde83 -->

**Completed**: Built main dashboard interface with retailer cards and status display.

**Files Created:**
- ✅ `dashboard/static/dashboard.css` - Complete styles matching mockup design
- ✅ `dashboard/static/dashboard.js` - Frontend logic with dynamic rendering
- ✅ `dashboard/templates/index.html` - Main template file

**Files Modified:**
- ✅ `dashboard/app.py` - Added render_template, serve static files, API transformation

**Components Implemented:**
1. ✅ Header with global status indicator and auto-refreshing timestamp
2. ✅ Summary cards (total stores, active retailers, overall progress, est. remaining)
3. ✅ Retailer cards grid with:
   - ✅ Status indicators (running/complete/pending/disabled) with color coding
   - ✅ Progress bars with smooth animations (0.8s ease-in-out transition)
   - ✅ Stats grid (stores/duration/requests)
   - ✅ Phase indicators with dynamic icons (✓ for complete, ⟳ for active)
   - ✅ Retailer-specific brand colors and logos

**Design Features:**
- ✅ Dark blue gradient background matching mockup (#1e3a5f to #0d1b2a)
- ✅ Retailer brand colors: Verizon #cd040b, AT&T #00a8e0, Target #cc0000, etc.
- ✅ Smooth hover effects on cards (transform: translateY(-3px))
- ✅ Pulsing animation on active scraper status
- ✅ Responsive grid layout (auto-fit, minmax(420px, 1fr))

**API Integration:**
- ✅ Added `_transform_status_for_frontend()` function to convert backend format
- ✅ Transforms backend "global" to frontend "summary"
- ✅ Converts phase dictionaries to arrays for easier rendering
- ✅ Formats numbers with commas and duration in human-readable format

**Verification Completed:**
- ✅ Dashboard loads successfully at http://localhost:5001/
- ✅ All 6 retailers display correctly
- ✅ Cards match mockup design aesthetically
- ✅ Responsive layout works on desktop
- ✅ Static files (CSS/JS) served correctly via Flask
- ✅ API returns properly formatted data

---

### [x] Step: Frontend - Real-Time Updates
<!-- chat-id: b1bba614-5f52-4be2-b7dc-c4df1dbffa76 -->

**Completed**: Implemented auto-refresh and real-time progress monitoring.

**Files Modified:**
- ✅ `dashboard/static/dashboard.js` - Complete polling mechanism with auto-refresh

**Features Implemented:**
- ✅ Auto-refresh every 5 seconds via `setInterval()`
- ✅ Visual indicators for active scrapers (pulsing green badge)
- ✅ Smooth progress bar animations (CSS transition: width 0.8s ease-in-out)
- ✅ Last updated timestamp with relative time ("just now", "5 seconds ago", etc.)
- ✅ Real-time update of:
  - Global status badge (active scraper count)
  - Summary cards (total stores, progress percentage)
  - Retailer cards (progress bars, stats, phase indicators)
- ✅ Page visibility API integration - pauses updates when tab is hidden
- ✅ Error handling with user-friendly error messages
- ✅ Automatic error recovery on successful API response

**Implementation Details:**
- `startAutoRefresh(intervalSeconds)` - Starts polling with configurable interval
- `updateDashboard()` - Fetches data from `/api/status` and updates UI
- `updateLastRefreshTime()` - Updates timestamp every second
- `stopAutoRefresh()` - Cleans up intervals when page is hidden
- Page visibility handler - Saves resources when user switches tabs

**Verification Completed:**
- ✅ Dashboard updates automatically every 5 seconds
- ✅ Progress bars animate smoothly on data changes
- ✅ Global status indicator updates when scrapers start/stop
- ✅ Last refresh timestamp updates every second
- ✅ Polling stops when tab is hidden (verified via browser devtools)
- ✅ Polling resumes when tab becomes visible again
- ✅ Error messages display when API is unreachable
- ✅ No console errors during operation

---

### [x] Step: Frontend - Configuration Management
<!-- chat-id: 703093af-ddb9-46da-b49a-fe75fe4c4950 -->
<!-- Note: Initial commit was incomplete. Functions fully implemented in follow-up session. -->

**Completed**: Implemented configuration editor with modal interface and validation.

**Files Modified:**
- ✅ `dashboard/static/dashboard.js` - Added configuration management functions (openConfigModal, closeConfigModal, saveConfig, validateConfigSyntax, showModalAlert, showNotification)
- ✅ `dashboard/static/dashboard.css` - Added modal, alert, notification, and config editor styles  
- ✅ `dashboard/templates/index.html` - Added configuration modal markup

**Features Implemented:**
- ✅ Configuration button in header and per-retailer Config buttons
- ✅ Modal to view/edit YAML configuration with monospace editor
- ✅ Loads current config via `GET /api/config`
- ✅ Saves config via `POST /api/config` with validation
- ✅ Client-side validation before API call (checks for retailers key, minimum structure)
- ✅ Display server-side validation errors in modal
- ✅ Show success message with backup file path
- ✅ Auto-close modal after successful save (2 second delay)
- ✅ Click outside modal to close
- ✅ Toast notifications for success/error messages

**Implementation Details:**
- `openConfigModal()` - Fetches config and displays in textarea editor
- `closeConfigModal()` - Hides modal
- `saveConfig()` - Validates and saves config with server-side validation
- `validateConfigSyntax()` - Client-side YAML structure validation
- `showModalAlert()` - Displays alerts within modal
- `showNotification()` - Toast-style notifications with auto-dismiss

**Validation Features:**
- ✅ Client-side: Required "retailers:" key, minimum YAML structure
- ✅ Server-side: Full YAML syntax validation (via existing API)
- ✅ Server-side: Required fields validation (name, enabled, base_url, discovery_method)
- ✅ Server-side: Data type validation (booleans, URLs, numbers)
- ✅ User-friendly error messages with details array
- ✅ Prevents saving invalid configurations
- ✅ Atomic writes with automatic rollback on error

**Verification Completed:**
- ✅ Config modal opens and displays current YAML correctly
- ✅ Textarea has monospace font and proper styling
- ✅ Save button works with loading state ("Saving...")
- ✅ Valid changes save successfully and create backup (tested via curl)
- ✅ Invalid YAML syntax rejected with error message (tested via curl)
- ✅ Missing required fields rejected with detailed errors
- ✅ Config file updates correctly after save
- ✅ Backup files created in `config/backups/` directory
- ✅ Dashboard refreshes after successful save
- ✅ Click outside modal closes it
- ✅ Toast notifications appear and auto-dismiss after 5 seconds
- ✅ All JavaScript functions exist and are callable
- ✅ All CSS classes exist and are properly styled
- ✅ API endpoints (GET/POST /api/config) working correctly

**Additional Features Added:**
- ✅ Scraper control buttons (Start/Stop/Restart) on each retailer card
- ✅ Toast notifications for scraper control actions
- ✅ Integration with `/api/scraper/start`, `/api/scraper/stop`, `/api/scraper/restart` endpoints

---

### [x] Step: Frontend - Run History & Logs
<!-- chat-id: 51836257-e8d7-4ed6-9f49-18210c3aabcc -->

**Completed**: Implemented run history panel and log viewer with filtering.

**Files Modified:**
- ✅ `dashboard/static/dashboard.js` - Added run history and log viewer functions
- ✅ `dashboard/static/dashboard.css` - Added styles for run history panel and log modal
- ✅ `dashboard/templates/index.html` - Added log viewer modal markup

**Features Implemented:**
- ✅ Run history panel (collapsible) in each retailer card
- ✅ "View Run History" button toggles panel with slide animation
- ✅ Lists past 5 runs per retailer with status badges
- ✅ Run items show: run ID, status, start/end times, stores scraped
- ✅ "View Logs" button opens modal for each run
- ✅ Log viewer modal with dark terminal-style theme
- ✅ Log filtering by level (All/INFO/WARNING/ERROR/DEBUG)
- ✅ Syntax highlighting for log levels and timestamps
- ✅ Click outside modal to close
- ✅ Statistics showing visible/total lines

**Implementation Details:**
JavaScript Functions:
- `toggleRunHistory(retailer)` - Toggles collapsible run history panel
- `loadRunHistory(retailer)` - Fetches runs from `/api/runs/<retailer>`
- `createRunItem(retailer, run)` - Renders run history item HTML
- `openLogViewer(retailer, runId)` - Opens log modal and loads logs
- `closeLogViewer()` - Closes log modal
- `loadLogs()` - Fetches logs from `/api/logs/<retailer>/<run_id>`
- `parseLogLine(line)` - Extracts log level and timestamp
- `displayLogs(parsedLines)` - Renders logs with syntax highlighting
- `toggleLogFilter(level)` - Filters logs by level
- `updateLogFilterButtons()` - Updates filter button active states
- `updateLogStats(parsedLines)` - Updates visible/total lines count

CSS Additions:
- `.run-history-toggle` - Collapsible button styles
- `.run-history-panel` - Slide-out panel with max-height animation
- `.run-item` - Run history item with color-coded status borders
- `.modal-overlay` - Full-screen modal backdrop
- `.modal-toolbar` - Log filter buttons toolbar
- `.log-container` - Terminal-style dark theme for logs
- `.log-line` - Individual log line with hover effects
- `.log-level` / `.log-timestamp` - Syntax highlighting classes

**Verification Completed:**
- ✅ Dashboard loads with run history buttons on all retailer cards
- ✅ Run history panel opens/closes smoothly with animation
- ✅ Run history displays past runs with correct data (tested with Verizon's 10 runs)
- ✅ "View Logs" button opens modal with correct title
- ✅ Logs load successfully from API
- ✅ Log filtering works for all levels (All/INFO/WARNING/ERROR/DEBUG)
- ✅ Filter buttons toggle active state correctly
- ✅ Log statistics update when filters change
- ✅ Click outside modal closes it
- ✅ No console errors during operation
- ✅ Log viewer displays timestamps and levels with syntax highlighting

---

### [x] Step: Testing & Bug Fixes
<!-- chat-id: new-task-caf8 -->

**Completed**: Comprehensive test suite with 36 passing smoke tests and manual verification.

**Test Infrastructure Setup:**
- ✅ Created `tests/conftest.py` with pytest-flask fixtures
- ✅ pytest-flask already in requirements.txt
- ✅ Flask app and client fixtures configured

**Smoke Tests Written:**
- ✅ `tests/test_status.py` - 14 tests for status calculation
  - Test `get_retailer_status()` returns correct structure
  - Test `get_all_retailers_status()` returns all 6 retailers
  - Test phase detection for html_crawl (4 phases) and sitemap (2 phases)
  - Test progress calculation and scraper_active detection
  - Test invalid retailer handling
  - Test disabled retailer status
- ✅ `tests/test_api.py` - 22 tests for API endpoints
  - Test `GET /api/status` returns transformed frontend data
  - Test `GET /api/status/<retailer>` for valid/invalid retailers
  - Test `POST /api/scraper/start` with validation
  - Test `POST /api/scraper/stop` with validation
  - Test `POST /api/scraper/restart` with validation
  - Test `GET /api/config` returns YAML content
  - Test `POST /api/config` with validation and error handling
  - Test `GET /api/runs/<retailer>` with limit parameter
  - Test `GET /api/logs/<retailer>/<run_id>` with path traversal protection
  - Test Content-Type validation (415 for non-JSON)
  - Test all 6 retailers present in status response

**Manual Testing:**
- ✅ Dashboard loads successfully (HTML served correctly)
- ✅ API endpoints respond with proper data
- ✅ Error handling verified (invalid retailer, missing params)
- ✅ Path traversal protection verified (404 returned)
- ✅ Edge cases tested (no data scenario shows "pending" status)
- ✅ Run history API returns complete and failed runs

**Verification:**
- ✅ All 36 smoke tests pass: `pytest tests/test_status.py tests/test_api.py`
- ✅ Manual test checklist completed
- ✅ API returns proper status codes (200, 400, 404, 415, 500)
- ✅ No errors during dashboard operation
- ✅ Security features working (path traversal blocked, content-type validation)

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
