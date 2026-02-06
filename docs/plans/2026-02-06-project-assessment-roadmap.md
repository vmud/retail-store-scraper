# Project Assessment & Development Roadmap

**Date:** 2026-02-06
**Target User:** Business user (Operations/GIS role, average technical skills)
**Goal:** Make this tool world-class as an internal corporate application

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Gap Analysis for Business Users](#gap-analysis-for-business-users)
4. [Development Roadmap](#development-roadmap)
5. [Phase Details](#phase-details)
6. [Risk Register](#risk-register)
7. [Success Metrics](#success-metrics)

---

## Executive Summary

The retail store scraper is a technically strong data collection engine covering 15 major US and Canadian retailers (~30,000+ store locations). It has solid foundations: checkpoint/resume, change detection, multi-format export, proxy integration, cloud storage backup, and a basic Flask dashboard.

However, it was built as a **developer tool**, not a **business application**. The gap between its current state and a world-class internal corporate tool is significant but addressable. The primary deficiencies are:

1. **No self-service operation** - requires CLI and Python knowledge to run
2. **No data exploration** - users get raw files, not answers
3. **No scheduling or automation** - manual execution only
4. **No alerting** - silent failures, no notifications for stakeholders
5. **Brittle scraper maintenance** - HTML structure changes break scrapers silently
6. **No audit trail** - limited accountability and compliance tracking

The roadmap below is organized into 5 phases, progressing from "usable by non-developers" to "world-class internal platform."

---

## Current State Assessment

### What Works Well

| Capability | Maturity | Notes |
|-----------|----------|-------|
| **Scraper coverage** | Strong | 15 retailers, ~30K+ stores, diverse strategies (API, sitemap, HTML) |
| **Data collection engine** | Strong | Parallel execution, checkpoint/resume, rate limiting, anti-blocking |
| **Proxy integration** | Strong | Oxylabs residential + Web Scraper API, dual delay profiles, hybrid mode |
| **Export formats** | Good | JSON, CSV, Excel (formatted), GeoJSON with coordinate validation |
| **Change detection** | Good | New/closed/modified stores, fingerprinting, collision handling |
| **Cloud storage** | Good | GCS integration with history, versioning |
| **Security posture** | Good | defusedxml, CSV injection protection, bandit scanning, pre-commit hooks |
| **Testing** | Good | 1,288 tests, 55 files, multi-version CI, security scanning |
| **Configuration** | Good | YAML-driven, per-retailer overrides, environment variables |
| **Docker support** | Good | Multi-stage build, non-root user, health checks |
| **Error monitoring** | Adequate | Sentry integration for error tracking |

### What Needs Work

| Area | Current State | Impact on Business User |
|------|--------------|------------------------|
| **Dashboard** | Skeleton Flask app, no templates exist | Users cannot operate the tool without CLI |
| **Scheduling** | None | Someone must manually run scrapes |
| **Data visualization** | None | Users get raw files, no maps or charts |
| **Search & filter** | None | No way to find specific stores or regions |
| **Alerting** | Notification stubs only | Failures go unnoticed |
| **User documentation** | Developer-focused CLAUDE.md only | Business users have no onboarding path |
| **Data quality monitoring** | Basic validation only | No dashboards showing data health |
| **Scraper health** | CI health checks only | No user-visible scraper status page |
| **Access control** | API key stub in Docker env | No role-based access or SSO |
| **Audit logging** | Run tracker exists | No user-facing audit trail |
| **Historical analysis** | Change reports as JSON files | No trend visualization |

### Dashboard Assessment (Critical Gap)

The Dockerfile references `dashboard/app.py` and exposes port 5001 with health checks, but the dashboard directory contains only a minimal Flask skeleton. There are no HTML templates, no JavaScript, and no CSS. The dashboard API has basic endpoints (`/api/status`) but no actual UI rendering. This means:

- The Docker health check works (API responds)
- But there is **no usable web interface**
- The business user has **zero self-service capability**

### Scraper Reliability Matrix

| Tier | Scrapers | Risk Level |
|------|----------|------------|
| **Tier 1 - Robust** | Verizon, Target, Home Depot, Staples, Cricket | Low - API-based or multi-fallback |
| **Tier 2 - Solid** | AT&T, T-Mobile, Walmart, Best Buy, Sam's Club | Medium - sitemap-dependent |
| **Tier 3 - Fragile** | Lowe's, Bell, Telus, Apple, Costco | Higher - HTML parsing or single-point-of-failure APIs |

Lowe's deserves special attention: its Redux JSON extraction via brace-depth matching is the most fragile pattern in the codebase and will break on any significant HTML restructure.

---

## Gap Analysis for Business Users

### Persona: Operations/GIS Analyst

**Skills:** Comfortable with Excel, basic GIS tools (ArcGIS/QGIS), can follow written procedures, not comfortable with command line or Python.

**Needs:**
- Run scrapes on a schedule without touching a terminal
- View store data on a map
- Compare current vs. previous data
- Export filtered datasets for their region/retailer
- Get notified when scrapes complete or fail
- Understand data freshness and quality at a glance
- Share results with colleagues

### Gap Severity Matrix

| Gap | Severity | Reason |
|-----|----------|--------|
| No web UI for operations | **Critical** | Tool is unusable without CLI skills |
| No scheduling | **Critical** | Requires human to manually trigger runs |
| No map visualization | **High** | Core need for GIS users; GeoJSON export exists but no viewer |
| No data quality dashboard | **High** | Users can't tell if data is trustworthy |
| No alerting/notifications | **High** | Silent failures erode trust |
| No search/filter on data | **High** | Users need regional slices, not 30K-row files |
| No user documentation | **Medium** | Onboarding and troubleshooting friction |
| No historical trends | **Medium** | Users want to see store count changes over time |
| No access control | **Medium** | Needed before broader rollout |
| No data download portal | **Medium** | Users shouldn't need to know file paths |
| No scraper health visibility | **Medium** | Users need confidence the system is working |
| Fragile scrapers | **Medium** | Undetected breakage destroys data trust |

---

## Development Roadmap

### Overview

```
Phase 1: Foundation (Make it Usable)
  - Web dashboard with core operations
  - Scheduled runs
  - Basic alerting

Phase 2: Intelligence (Make it Useful)
  - Map visualization
  - Search, filter, and export
  - Data quality dashboard

Phase 3: Reliability (Make it Trustworthy)
  - Scraper health monitoring
  - Self-healing scrapers
  - Automated regression detection

Phase 4: Scale (Make it Enterprise-Ready)
  - Access control and SSO
  - Audit logging
  - Multi-tenant configuration
  - API for downstream systems

Phase 5: Excellence (Make it World-Class)
  - Historical analytics
  - Anomaly detection
  - Custom report builder
  - Mobile-responsive design
  - Competitive intelligence features
```

### Timeline Dependency Graph

```
Phase 1 ──────► Phase 2 ──────► Phase 5
    │               │
    └──► Phase 3 ───┘
              │
              └──► Phase 4
```

Phases 1 is prerequisite for everything. Phases 2 and 3 can run in parallel after Phase 1. Phase 4 depends on Phase 3. Phase 5 depends on Phases 2 and 3.

---

## Phase Details

### Phase 1: Foundation (Make it Usable)

**Goal:** A non-technical user can operate the scraper through a web browser.

#### 1.1 Web Dashboard - Core Operations

Build a real web dashboard on the existing Flask skeleton.

**Pages:**
- **Home/Status** - overview of all retailers with last run time, store count, status (green/yellow/red)
- **Run Scraper** - form to select retailers, proxy mode, export formats, and click "Run"
- **Run History** - table of past runs with status, duration, store counts, error summaries
- **Downloads** - file browser for data/retailer/output/ with download links

**Technical approach:**
- Use HTMX + Alpine.js for interactivity (no heavy frontend framework needed)
- Tailwind CSS for styling (utility-first, fast to build)
- Server-sent events (SSE) for real-time run progress
- Flask-SQLAlchemy with SQLite for run metadata (replace JSON file tracking)

**Key decisions:**
- Keep it server-rendered with HTMX for progressive enhancement. The target user doesn't need a SPA, and this minimizes frontend complexity
- SQLite is sufficient for a single-team internal app. Migrate to PostgreSQL only if concurrent write pressure becomes an issue
- Authentication deferred to Phase 4 (internal network assumption)

#### 1.2 Scheduled Runs

**Implementation:**
- APScheduler integrated into the Flask app (or separate scheduler process)
- Cron-like configuration in `config/retailers.yaml`:
  ```yaml
  scheduling:
    verizon:
      cron: "0 2 * * 1"  # Every Monday at 2am
      proxy: residential
    target:
      cron: "0 3 * * 1"
  ```
- Dashboard page to view/edit schedules
- Run queue to prevent overlapping executions

**Why not cron directly?** A cron job requires server access and doesn't integrate with the dashboard's run history, status tracking, or notifications.

#### 1.3 Basic Alerting

**Implementation:**
- Email notifications via SMTP (most corporate environments have internal relay)
- Slack webhook integration (already stubbed in `src/shared/notifications.py`)
- Alert conditions:
  - Scrape completed (summary with store counts)
  - Scrape failed (error details)
  - Store count anomaly (>10% drop from previous run)
  - Scrape duration anomaly (>2x normal)
- Configuration in `config/retailers.yaml`:
  ```yaml
  notifications:
    email:
      enabled: true
      recipients: ["ops-team@company.com"]
      on_failure: true
      on_success: true
      on_anomaly: true
    slack:
      enabled: true
      webhook_url_env: "SLACK_WEBHOOK_URL"
      channel: "#store-data"
  ```

#### 1.4 User Documentation

- **Quick Start Guide** - 1-page "how to use the dashboard"
- **Runbook** - standard operating procedures (what to do when a scrape fails)
- **Data Dictionary** - what each field means, per retailer
- **FAQ** - common questions from the business user perspective
- Accessible from within the dashboard (help menu)

---

### Phase 2: Intelligence (Make it Useful)

**Goal:** Users can explore, visualize, and extract the data they need without downloading raw files.

#### 2.1 Map Visualization

**Implementation:**
- Leaflet.js map on a dedicated "Map" page
- Load GeoJSON directly (already exported by the tool)
- Retailer-colored markers with clustering for zoom levels
- Click marker for store details popup
- Filter by retailer, state, store type
- Side panel with filtered store list

**Why Leaflet over Google Maps / Mapbox?** Leaflet is free, open-source, and sufficient for point data visualization. No API key costs for an internal tool. Switch to Mapbox only if satellite imagery or advanced routing is needed.

**Data pipeline:**
- Pre-generate per-retailer GeoJSON after each run
- Combined all-retailers GeoJSON for the map view
- Use spatial indexing if performance becomes an issue (>50K points)

#### 2.2 Search, Filter, and Export

**Implementation:**
- Server-side search API with these filters:
  - Retailer (multi-select)
  - State/province (multi-select)
  - City (text search)
  - ZIP/postal code (text or radius)
  - Store type (e.g., corporate vs dealer)
  - Status (open/closed/modified)
  - Date range (scraped_at)
- Results displayed in a paginated table with sortable columns
- "Export filtered results" button (CSV, Excel, GeoJSON)
- Saved filters (bookmarkable URLs at minimum)

**Data backend:**
- SQLite with FTS5 for full-text search
- Load scraped data into a normalized SQLite database after each run
- This becomes the single source of truth for the dashboard (raw files remain as backup)

**Why SQLite?** Avoids adding PostgreSQL infrastructure for what is fundamentally a read-heavy workload with periodic bulk writes. SQLite handles the scale (30K stores across 15 retailers = ~500K records/year with history) without external dependencies.

#### 2.3 Data Quality Dashboard

**Implementation:**
- Dashboard page showing per-retailer data quality metrics:
  - Completeness: % of stores with all required fields
  - Coordinate coverage: % with valid lat/long
  - Phone coverage: % with phone numbers
  - Address completeness: % with full street/city/state/zip
  - Freshness: time since last successful scrape
  - Consistency: % matching expected store count (vs. historical average)
- Visual indicators (green/yellow/red) per metric
- Trend sparklines showing quality over time

**Data source:**
- Extend `validate_store_data()` to return per-field metrics
- Store quality metrics in SQLite after each run
- Alert if quality drops below configurable thresholds

#### 2.4 Change Detection UI

**Implementation:**
- Dedicated "Changes" page showing:
  - New stores (with map pins)
  - Closed stores (with map pins)
  - Modified stores (diff view showing what changed)
  - Timeline of changes per retailer
- Filterable by retailer, date range, change type
- Export change reports as CSV/Excel

**Data already exists** in `data/{retailer}/history/changes_*.json`. This phase surfaces it in the UI.

---

### Phase 3: Reliability (Make it Trustworthy)

**Goal:** The system self-monitors, alerts on issues, and minimizes silent failures.

#### 3.1 Scraper Health Monitoring

**Implementation:**
- **Health check page** in dashboard showing per-scraper:
  - Last successful run and store count
  - Last failure and error message
  - Success rate (last 30 days)
  - Average run duration with trend
  - Data freshness (hours since last scrape)
  - Expected vs. actual store count
- **Endpoint health** (extend existing `scraper-health.yml` CI workflow):
  - Daily automated checks that key URLs are reachable
  - Results visible in dashboard
  - Alert on consecutive failures

#### 3.2 Scraper Regression Detection

**Implementation:**
- After each run, automatically check:
  - Store count within expected range (configurable per retailer)
  - No more than X% of stores missing required fields
  - Coordinates within expected geographic bounds
  - No sudden field schema changes (new/missing columns)
- If regression detected:
  - Flag the run in the dashboard (yellow/red status)
  - Send alert via configured notification channels
  - Optionally prevent the new data from overwriting the previous "known good" data

**Configuration in retailers.yaml:**
```yaml
quality_gates:
  verizon:
    min_stores: 1800
    max_stores: 2500
    required_fields_threshold: 0.95
    coordinate_coverage_threshold: 0.90
  target:
    min_stores: 1600
    max_stores: 2000
```

#### 3.3 Scraper Self-Healing

**Implementation:**
- **Automatic retry with backoff** on transient failures (partially exists)
- **Circuit breaker** pattern: after N consecutive failures, pause the scraper and alert
- **Fallback strategies** per scraper:
  - If sitemap URL changes, try common alternatives
  - If HTML structure changes, fall back to broader CSS selectors
  - If API endpoint changes, check for redirect
- **Lowe's hardening**: Replace brace-depth JSON extraction with proper HTML parser + `<script>` tag targeting

#### 3.4 Data Versioning

**Implementation:**
- Keep last N runs of data per retailer (configurable, default 10)
- Enable rollback: if current run is bad, restore previous version with one click
- Diff view between any two runs
- GCS object versioning already enabled; extend dashboard to browse versions

---

### Phase 4: Scale (Make it Enterprise-Ready)

**Goal:** The tool is ready for broader organizational deployment with proper governance.

#### 4.1 Access Control

**Implementation:**
- OIDC/SAML SSO integration (most corporate environments)
- Role-based access:
  - **Viewer**: browse data, download exports, view maps
  - **Operator**: run scrapes, manage schedules, view logs
  - **Admin**: configure retailers, manage users, view audit logs
- API key authentication for programmatic access (external systems)

**Lightweight alternative** if SSO is not immediately available:
- HTTP Basic Auth with user list in environment variables
- Upgrade to SSO in a subsequent iteration

#### 4.2 Audit Logging

**Implementation:**
- Log all significant actions:
  - Who triggered a scrape and when
  - Configuration changes
  - Data exports (who downloaded what)
  - Schedule modifications
- Stored in SQLite (or separate audit database)
- Viewable in dashboard by Admin role
- Retention policy (configurable, default 1 year)

#### 4.3 REST API for Downstream Systems

**Implementation:**
- Formalize the dashboard's API endpoints:
  - `GET /api/v1/stores?retailer=verizon&state=CA` - query stores
  - `GET /api/v1/stores/{id}` - single store detail
  - `GET /api/v1/retailers` - list retailers with status
  - `GET /api/v1/runs` - run history
  - `GET /api/v1/changes?retailer=verizon&since=2026-01-01` - changes feed
  - `POST /api/v1/runs` - trigger a scrape
- OpenAPI/Swagger documentation
- Rate limiting
- API key authentication

**Use case:** Downstream GIS systems, BI tools, or data warehouses can pull data programmatically instead of parsing files.

#### 4.4 Multi-Environment Configuration

**Implementation:**
- Separate configurations for dev/staging/production
- Environment-specific proxy settings
- Docker Compose profiles for different deployment scenarios
- Helm chart for Kubernetes deployment (if the organization uses k8s)

---

### Phase 5: Excellence (Make it World-Class)

**Goal:** The tool provides insights, not just data.

#### 5.1 Historical Analytics

**Implementation:**
- **Store count trend charts** per retailer (line chart over time)
- **Geographic expansion/contraction heatmaps**
- **Store type distribution** pie/bar charts
- **Competitive landscape view**: overlay multiple retailers on the same map
- **State/metro area coverage comparison** across retailers

**Data requirement:** Requires Phase 3's data versioning to have historical snapshots.

#### 5.2 Anomaly Detection

**Implementation:**
- Statistical anomaly detection on:
  - Store count time series (detect sudden openings/closings)
  - Geographic clustering changes
  - Scrape performance metrics
- Alert when anomalies detected
- Machine learning optional: simple statistical methods (z-score, moving average) are sufficient for the data volumes involved

#### 5.3 Custom Report Builder

**Implementation:**
- Drag-and-drop report builder:
  - Select retailers and date range
  - Choose fields to include
  - Add filters
  - Choose output format (PDF, Excel, PowerPoint)
- Save report templates for recurring use
- Schedule automated report delivery via email

#### 5.4 Mobile-Responsive Design

**Implementation:**
- Responsive Tailwind CSS (achievable if adopted in Phase 1)
- Touch-friendly map controls
- Key metrics viewable on phone
- Progressive Web App (PWA) for offline access to last sync

#### 5.5 Competitive Intelligence Features

**Implementation:**
- **Proximity analysis**: find all competitor stores within X miles of each of your locations
- **Coverage gap analysis**: identify geographic areas where competitors have stores but you don't
- **Store density heatmaps**: visualize retail concentration by metro area
- **Trade area overlap**: estimate customer overlap between nearby stores

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Retailer blocks scraper** | High | High | Proxy rotation, respectful delays, multiple fallback strategies |
| **Website structure changes break scraper** | High | High | Phase 3 regression detection + alerting; HTML-parsing scrapers are most vulnerable |
| **Scope creep** | High | Medium | Phase gates with clear deliverables; MVP each phase before expanding |
| **Dashboard performance with large datasets** | Medium | Medium | SQLite with proper indexing; paginate all queries; pre-aggregate metrics |
| **Single developer dependency** | Medium | High | Document architecture decisions; keep code simple; avoid exotic frameworks |
| **Proxy costs scale** | Medium | Medium | Optimize request counts; cache aggressively; use direct mode where possible |
| **Data quality drift** | Medium | High | Phase 3 quality gates catch issues before they reach users |
| **Business user adoption** | Medium | High | Phase 1 documentation + UX focus; involve users in design feedback |
| **GCS costs** | Low | Low | Object lifecycle policies; compress before upload |

---

## Success Metrics

### Phase 1 (Foundation)
- [ ] Business user can trigger a scrape from the browser
- [ ] Scrapes run on a daily/weekly schedule without manual intervention
- [ ] Users receive email/Slack notification when a scrape completes or fails
- [ ] New team member can onboard in <30 minutes using documentation

### Phase 2 (Intelligence)
- [ ] Users can view stores on a map and filter by retailer/state
- [ ] Users can search for stores by city, ZIP, or name
- [ ] Users can export filtered subsets without touching raw files
- [ ] Data quality is visible at a glance with green/yellow/red indicators

### Phase 3 (Reliability)
- [ ] All scraper failures trigger alerts within 5 minutes
- [ ] Store count regressions are automatically flagged before data is published
- [ ] Scraper health history is visible in the dashboard for the last 90 days
- [ ] Mean time to detect a broken scraper is <24 hours (down from potentially weeks)

### Phase 4 (Enterprise)
- [ ] SSO authentication enforced for all dashboard access
- [ ] All actions are audit-logged
- [ ] Downstream systems consume data via REST API
- [ ] 99.5% dashboard uptime

### Phase 5 (Excellence)
- [ ] Users create custom reports without developer assistance
- [ ] Competitive proximity analysis available for any retailer combination
- [ ] Historical trends visible for any retailer over the last 12 months
- [ ] Dashboard is mobile-accessible

---

## Technical Debt to Address Across All Phases

These items should be addressed opportunistically as part of the phased work:

1. **Lowe's scraper fragility** - Replace brace-depth JSON extraction with proper HTML parser targeting `<script>` tags. This is the highest-risk scraper pattern in the codebase.

2. **Inconsistent XML parsing** - Not all scrapers use `defusedxml`. Security scanning may flag this. Standardize on `defusedxml.ElementTree` everywhere.

3. **Missing UAT framework** - `tests/uat/` is referenced in CLAUDE.md but doesn't exist. Build it as part of Phase 3's quality focus.

4. **Store schema fragmentation** - Different scrapers use slightly different field names (e.g., `zip` vs `postal_code`). The `store_schema.py` normalization helps but isn't applied consistently. Enforce normalization at the scraper level, not just at export.

5. **No integration tests** - All 1,288 tests use mocks. Add a small suite of "canary" integration tests that hit real endpoints (one URL per retailer) to detect structural changes early. Run these on a schedule, not on every commit.

6. **Dashboard skeleton** - The Flask app referenced by Docker exists but has no actual UI. Either build it (Phase 1) or remove the Docker references to avoid confusion.

7. **Notification stubs** - `src/shared/notifications.py` exists but needs real implementation for email/Slack delivery.

8. **Run tracker JSON files** - `runs/{run_id}.json` should migrate to SQLite once the dashboard database exists (Phase 1).

---

## Recommended Technology Stack Additions

| Need | Recommendation | Rationale |
|------|---------------|-----------|
| **Frontend interactivity** | HTMX + Alpine.js | Minimal JS, server-rendered, fast to develop |
| **CSS framework** | Tailwind CSS | Utility-first, responsive, no custom CSS needed |
| **Map** | Leaflet.js + OpenStreetMap | Free, open-source, sufficient for point data |
| **Charts** | Chart.js or Apache ECharts | Lightweight, good for dashboards |
| **Database** | SQLite (via SQLAlchemy) | Zero infrastructure, sufficient for scale |
| **Task scheduling** | APScheduler | Python-native, integrates with Flask |
| **Email** | smtplib (stdlib) | No dependency needed |
| **PDF reports** | WeasyPrint or reportlab | Python-native PDF generation |
| **Search** | SQLite FTS5 | Built-in full-text search, no Elasticsearch needed |

---

## Appendix: Current Retailer Coverage

| Retailer | Country | Strategy | Est. Stores | Proxy Required |
|----------|---------|----------|-------------|----------------|
| Verizon | US | HTML crawl (4-phase) | ~2,000 | Residential |
| AT&T | US | XML sitemap | ~2,000 | Residential |
| Target | US | Gzipped sitemap + API | ~1,800 | Residential |
| T-Mobile | US | Paginated sitemaps | ~4,000 | Web Scraper API |
| Walmart | US | Multiple gzipped sitemaps | ~4,700 | Hybrid |
| Best Buy | US | XML sitemap + JS rendering | ~1,400 | Web Scraper API |
| Cricket | US | Yext API (geographic grid) | ~13,600 | Direct |
| Home Depot | US | GraphQL API | ~2,000 | Direct |
| Staples | US | API scan + REST API + locator | ~1,500 | Web Scraper API |
| Apple | US | Next.js SSR | ~272 | Direct |
| Costco | US | HTML scraping | ~600 | Web Scraper API |
| Sam's Club | US | Sitemap + HTML | ~600 | Hybrid |
| Lowe's | US | HTML + Redux JSON | ~1,761 | Residential |
| Telus | CA | Uberall API | ~857 | Residential |
| Bell | CA | Sitemap + JSON-LD | ~251 | Direct |
| **Total** | | | **~37,000** | |
