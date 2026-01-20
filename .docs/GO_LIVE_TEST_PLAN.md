# Go-Live Test Plan

## 1) Purpose
Validate the multi-retailer scraper and dashboard are production-ready.
This plan covers functional, integration, security, performance, and
deployment readiness tests required before go-live.

## 2) Scope
In scope:
- Scraper CLI flows (single retailer, all, resume, incremental)
- Proxy modes (direct, residential, web_scraper_api)
- Data export (json, csv, excel, geojson)
- Change detection and history
- Dashboard API and UI
- Deployment (docker-compose, systemd)
- Security regressions for API + UI

Out of scope:
- Full data accuracy audit for every store location
- Vendor SLAs and upstream site stability

## 3) Environments
Required:
- Staging (mirror of production configuration)
- Production (smoke tests only)

Test data location:
- Use a dedicated staging data directory or namespace to avoid
  contaminating production history files.

## 4) Preconditions
- Python 3.11 environment configured
- `.env` populated with valid proxy credentials
- `config/retailers.yaml` reviewed and validated
- Dashboard running (Flask app)
- Disk space and log directories available

## 5) Test Matrix (Required Before Go-Live)

### 5.1 Scraper Smoke Tests (per retailer)
Goal: confirm selectors, URLs, and parsing still work against live sites.

Run each enabled retailer with:
- direct proxy mode
- residential proxy mode
- web_scraper_api mode (where applicable, e.g. Walmart, Best Buy)

Example:
```
python run.py --retailer verizon --limit 5 --proxy direct --verbose
python run.py --retailer verizon --limit 5 --proxy residential --verbose
python run.py --retailer walmart --limit 5 --proxy web_scraper_api --render-js --verbose
```

Pass criteria:
- Non-zero store count (unless retailer is known to be empty)
- `data/{retailer}/output/stores_latest.json` created
- Required fields present: store_id, name, street_address, city, state
- No repeated errors in logs

### 5.2 End-to-End Pipeline
Goal: verify full pipeline and history tracking.

Run:
```
python run.py --all --test --verbose
python run.py --all --resume --test --verbose
python run.py --all --incremental --test --verbose
```

Pass criteria:
- `stores_latest.json` and `stores_previous.json` rotate correctly
- `history/changes_*.json` generated
- No duplicate store IDs within a run

### 5.3 Checkpoint/Resume + Interruption Recovery
Goal: validate resume state and no data loss.

Steps:
1) Start a scrape with `--limit 100`
2) Interrupt (SIGTERM)
3) Resume with `--resume`

Pass criteria:
- Resumes from saved checkpoint
- Final output has no duplicates
- Summary shows full completion

### 5.4 Export Formats (CLI + API)
Goal: confirm output formats are valid end-to-end.

CLI:
```
python run.py --retailer target --limit 5 --format json,csv,excel,geojson
```

API:
- GET /api/export/formats
- GET /api/export/{retailer}/{format}
- POST /api/export/multi

Pass criteria:
- Files created and non-empty
- GeoJSON coordinates valid
- CSV/Excel sanitized for formula injection

### 5.5 Dashboard API + UI (UAT Suites)
Goal: validate UI workflows and API contracts.

Run UAT suites:
- init, status, control, config, logs, ui, proxy, perf, history

Pass criteria:
- Start/stop/restart works via UI and API
- Config changes validate and persist
- Logs and run history render
- UI elements (modal, toast, metrics) functional

### 5.6 Performance and Stability
Goal: ensure acceptable response times and no runaway resources.

Run:
- UAT PerfSuite thresholds
- Long-running scrape (e.g., 1+ hours) with log growth monitoring

Pass criteria:
- API responses within thresholds
- No memory leaks or runaway CPU usage
- Logs rotate or remain within acceptable size

### 5.7 Security Regression Tests
Goal: prevent known vulnerabilities from reappearing.

Required checks:
- Path traversal attempts on API endpoints (logs, export, runs)
- XSS injection in config editor and log viewer

Pass criteria:
- 4xx for traversal attempts
- XSS payloads not executed or reflected

### 5.8 Deployment Validation
Goal: verify production deployment method is functional.

Docker:
```
docker-compose up -d
docker-compose run scraper python run.py --retailer verizon --limit 5
```

Systemd:
```
sudo ./deploy/install.sh
sudo systemctl start retail-scraper
sudo systemctl status retail-scraper
```

Pass criteria:
- Services start and stop cleanly
- Logs and data files created in expected paths
- `--status` returns valid status

## 6) Automation Gaps (Should Be Added)
Required to harden go-live readiness:
- Unit tests for `validate_store_data` and `validate_stores_batch`
- Parser fixture tests per retailer (static HTML/JSON responses)
- End-to-end API flow tests (start -> status -> stop -> history)
- Front-end unit tests (keyboard, modal, config editor)

## 7) Reporting
For each run, record:
- Date/time, environment
- Command executed
- Store counts by retailer
- Any errors or warnings
- Links to logs and artifacts

## 8) Go-Live Sign-Off Criteria
Go-live can proceed only when:
- All Required sections (5.1 through 5.8) pass
- No P0/P1 issues remain open
- Performance thresholds are met
- Deployment verified in staging
- Production smoke test passes

## 9) Production Smoke Test (Day-of Go-Live)
Run a minimal, low-risk validation:
```
python run.py --retailer att --limit 5 --proxy direct
python run.py --status
```

Pass criteria:
- Successful execution with clean logs
- Status reflects completed run
