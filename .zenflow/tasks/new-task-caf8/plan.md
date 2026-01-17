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

### [ ] Step: Backend - Multi-Retailer Status System
<!-- chat-id: bcee6ba8-85c8-4815-93ad-9fa80a66ae0c -->

Refactor status tracking from Verizon-only to support all retailers dynamically.

**Files to Modify:**
- `src/shared/status.py` - Generalize status calculation
  - Add `get_retailer_status(retailer: str)` function
  - Add `get_all_retailers_status()` function
  - Support different discovery methods (sitemap vs HTML crawl)
  - Dynamic checkpoint path resolution

**Files to Create:**
- `src/shared/run_tracker.py` - Track run metadata (ID, timestamps, stats, errors)

**Verification:**
- Test status calculation for all 6 retailers
- Verify checkpoint path resolution
- Check phase detection for different scraper types

---

### [ ] Step: Backend - Scraper Control & Management

Implement scraper lifecycle management and control system.

**Files to Create:**
- `src/shared/scraper_manager.py` - Process lifecycle management
  - Start/stop scrapers (subprocess.Popen wrapper)
  - Track running processes (in-memory dict)
  - Handle graceful shutdown (SIGTERM)
  - Support restart with resume (--resume flag)

**Reuse Existing:**
- Use existing `run.py` CLI interface via subprocess
- Leverage existing checkpoint system for resume

**Verification:**
- Start a scraper via manager (verify process spawned)
- Stop a running scraper gracefully (verify SIGTERM sent)
- Restart with resume flag (verify checkpoint loaded)
- Handle errors during scraper execution

---

### [ ] Step: API - Control Endpoints

Add REST API endpoints for scraper control and monitoring.

**Files to Modify:**
- `dashboard/app.py` - Add new endpoints
  - `GET /api/status` - All retailers status
  - `GET /api/status/<retailer>` - Single retailer
  - `POST /api/scraper/start` - Start scraper(s) with optional resume
  - `POST /api/scraper/stop` - Stop scraper(s)
  - `GET /api/runs/<retailer>` - Historical runs
  - `GET /api/config` - Get configuration
  - `POST /api/config` - Update configuration with validation

**Key Implementations:**
- Config validation: YAML syntax, required fields, type checking
- Config backup: Create timestamped backup before update
- Atomic writes: Temp file → validate → move (no partial updates)
- Error responses: Return validation errors with details

**Verification:**
- Test each endpoint with curl/Postman
- Verify error handling (invalid retailer, missing params)
- Test config update with invalid YAML (should rollback)
- Test config update with valid YAML (should create backup)
- Check concurrent request handling

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
