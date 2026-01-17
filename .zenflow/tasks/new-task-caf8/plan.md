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
  - Start/stop/pause/resume scrapers
  - Track running processes
  - Handle graceful shutdown

**Verification:**
- Start a scraper via manager
- Stop a running scraper gracefully
- Handle errors during scraper execution

---

### [ ] Step: API - Control Endpoints

Add REST API endpoints for scraper control and monitoring.

**Files to Modify:**
- `dashboard/app.py` - Add new endpoints
  - `GET /api/status` - All retailers status
  - `GET /api/status/<retailer>` - Single retailer
  - `POST /api/scraper/start` - Start scraper(s)
  - `POST /api/scraper/stop` - Stop scraper(s)
  - `POST /api/scraper/pause` - Pause scraper(s)
  - `POST /api/scraper/resume` - Resume scraper(s)
  - `GET /api/runs/<retailer>` - Historical runs
  - `GET /api/config` - Get configuration
  - `POST /api/config` - Update configuration

**Verification:**
- Test each endpoint with curl/Postman
- Verify error handling (invalid retailer, missing params)
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
   - Status indicators
   - Progress bars
   - Stats (stores/duration/requests)
   - Phase indicators
   - Control buttons

**Verification:**
- Dashboard loads successfully
- All retailers display correctly
- Cards match mockup design
- Responsive layout works

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
- `dashboard/app.py` - Config save validation

**Features:**
- Modal to edit retailer settings
- Enable/disable retailers
- Proxy configuration UI
- Rate limiting settings
- Validation and error handling

**Verification:**
- Open config modal, edit settings
- Save and verify changes persist
- Test validation (invalid values)
- Verify YAML file updated correctly

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

Write tests and fix issues discovered during integration.

**Tests to Write:**
- `tests/test_multi_retailer_status.py` - Status calculation
- `tests/test_run_tracker.py` - Run metadata tracking
- `tests/test_scraper_manager.py` - Lifecycle management
- `tests/test_dashboard_api.py` - API endpoints

**Manual Testing:**
- Run all scrapers concurrently
- Test pause/resume functionality
- Verify error handling displays properly
- Check edge cases (no data, failed runs, etc.)

**Verification:**
- All tests pass: `pytest tests/`
- Manual test checklist completed
- No console errors in browser
- API returns proper status codes

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
