# Project Assessment & Development Roadmap

**Date:** 2026-02-06
**Target User:** Business user (Operations/GIS role, average technical skills)
**Goal:** Make this tool world-class as an internal corporate application
**Deployment model:** Centralized web application (not locally distributed)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Target User & Design Principles](#target-user--design-principles)
4. [Application Design](#application-design)
5. [Development Roadmap](#development-roadmap)
6. [Build Sequence](#build-sequence)
7. [Technical Architecture](#technical-architecture)
8. [Risk Register](#risk-register)
9. [Success Metrics](#success-metrics)

---

## Executive Summary

The retail store scraper is a technically strong data collection engine covering 15 major US and Canadian retailers (~37,000 store locations). It has solid foundations: checkpoint/resume, change detection, multi-format export, proxy integration, and cloud storage backup.

However, it was built as a **developer tool**, not a **business application**. A GIS analyst or operations user cannot use it today without CLI skills, Python knowledge, and access to proxy credentials.

This roadmap transforms it into a **centralized web application** that:

- **Runs on a server**, not on user laptops (scraping is long-running, needs always-on scheduling, and proxy credentials must not be distributed)
- **Presents three screens** to business users: Home (status), Explore (map + search), Changes (what's new)
- **Probes for changes** every 6 hours without full scrapes, alerting users when new data is available
- **Supports territory design** via MSA boundaries, radius distance, and drive-time isochrones — eliminating the most common reason GIS analysts round-trip data through ArcGIS
- **Keeps the CLI** for developers who add/debug scrapers

### Key architectural decision: centralized, not distributed

Proxy credentials (Oxylabs) cannot be distributed to user laptops. Scraping runs for hours and requires an always-on machine for scheduling. Data consistency requires a single canonical dataset. The target user should never see `pip install` or a Python traceback. The web app runs on a single Docker host; users access it via browser.

---

## Current State Assessment

### What Works Well

| Capability | Maturity | Notes |
|-----------|----------|-------|
| **Scraper coverage** | Strong | 15 retailers, ~37K stores, diverse strategies (API, sitemap, HTML) |
| **Data collection engine** | Strong | Parallel execution, checkpoint/resume, rate limiting, anti-blocking |
| **Proxy integration** | Strong | Oxylabs residential + Web Scraper API, dual delay profiles, hybrid mode |
| **Export formats** | Good | JSON, CSV, Excel (formatted), GeoJSON with coordinate validation |
| **Change detection** | Good | New/closed/modified stores, SHA256 fingerprinting, collision handling |
| **Cloud storage** | Good | GCS integration with history, object versioning |
| **Security posture** | Good | defusedxml, CSV injection protection, bandit scanning, pre-commit hooks |
| **Testing** | Good | 1,288 tests, 55 files, multi-Python-version CI, security scanning |
| **Docker support** | Good | Multi-stage build, non-root user, health checks |

### What Doesn't Exist

| Gap | Impact |
|-----|--------|
| **No web UI** | Tool is unusable without CLI skills. Dashboard directory is empty — no templates, no JS, no CSS. Docker references it but nothing renders. |
| **No scheduling** | Every scrape requires manual CLI execution |
| **No change probing** | Can't detect data changes without running a full scrape |
| **No map visualization** | GeoJSON is exported but there's no viewer |
| **No territory design** | Analysts export to ArcGIS for basic point-in-polygon work |
| **No alerting** | `src/shared/notifications.py` is stubbed but unimplemented |
| **No data exploration** | Users get raw 37K-row files, no search or filter |
| **No user documentation** | Only developer-focused CLAUDE.md |

### Scraper Reliability Tiers

| Tier | Scrapers | Risk |
|------|----------|------|
| **Robust** | Verizon, Target, Home Depot, Staples, Cricket | Low — API-based or multi-fallback |
| **Solid** | AT&T, T-Mobile, Walmart, Best Buy, Sam's Club | Medium — sitemap-dependent |
| **Fragile** | Lowe's, Bell, Telus, Apple, Costco | Higher — HTML parsing, single-point-of-failure APIs |

Lowe's is the highest-risk scraper: brace-depth JSON extraction from HTML will break on any page restructure.

---

## Target User & Design Principles

### Persona: Operations/GIS Analyst

**Name:** Sarah (composite persona)
**Role:** Marketing operations, GIS analysis, territory planning
**Skills:** Comfortable with Excel and basic GIS tools (ArcGIS/QGIS). Can follow written procedures. Not comfortable with command line, Python, or YAML configuration.

**Sarah's actual questions:**
- "How many Verizon stores are in the Southeast region?"
- "Did Target open or close any stores this month?"
- "I need a spreadsheet of all T-Mobile locations in California."
- "Is our store data current or stale?"
- "Can I redraw the Northwest territory to balance store counts?"

The scraper is invisible plumbing. Sarah cares about **fresh, correct store data** and **knowing when something changed.**

### Design Principles

1. **The scraper is invisible.** No proxy modes, no checkpoint files, no YAML. Sarah clicks "Update" and gets fresh data.
2. **Three screens, not fifteen.** Home, Explore, Changes. Everything fits into one of these mental models.
3. **Show status, not logs.** Green/yellow/red dots, not stack traces. "Updated Feb 3" not "exit code 0."
4. **Export matches what you see.** The download button exports exactly the filtered/visible data, not a raw 37K-row dump.
5. **Alerts are proactive.** The dashboard tells Sarah when data changed, not the other way around.
6. **Territory design lives next to the data.** No round-tripping through ArcGIS for basic spatial analysis.

---

## Application Design

### Navigation

```
[ Home ]  [ Explore ]  [ Changes ]  [ Territories ]              Sarah v
```

Four screens. One navigation bar. No settings page, no log viewer, no YAML editor. Developer tools stay in the CLI.

### Screen 1: Home ("Is everything OK?")

What Sarah sees on login. Answers one question: **can I trust the data right now?**

```
+-----------------------------------------------------------+
|  Store Data Hub                                           |
|                                                           |
|  Data Freshness                        Last probed: 2h ago|
|  +-------------------------------------------------------+
|  |                                                       |
|  |  * Verizon     2,014 stores    Updated Feb 3          |
|  |  * AT&T        1,987 stores    Updated Feb 3          |
|  |  * Target      1,812 stores    Updated Feb 3          |
|  |  * T-Mobile    4,102 stores    Updated Feb 3          |
|  |  * Walmart     4,698 stores    Updated Feb 3          |
|  |  * Best Buy    1,389 stores    Updated Feb 3          |
|  |  ...13 more retailers                                 |
|  |                                                       |
|  |  ! 2 retailers have new data available                |
|  |    AT&T - sitemap changed Feb 5                       |
|  |    Apple - site updated Feb 6                         |
|  |                            [ Update These Now ]       |
|  |                                                       |
|  +-------------------------------------------------------+
|                                                           |
|  Recent Activity                                          |
|  +-------------------------------------------------------+
|  |  Feb 3   All retailers updated       37,214 stores    |
|  |  Feb 3   Target: +3 new, -1 closed                    |
|  |  Jan 27  All retailers updated       37,212 stores    |
|  |  Jan 27  Walmart: +12 new, -4 closed                  |
|  +-------------------------------------------------------+
+-----------------------------------------------------------+
```

**Key behaviors:**
- Colored dots: green (fresh), yellow (getting stale), red (failed or very old)
- Change alerts powered by the **probe system** (see below), not full scrapes
- "Update These Now" triggers a full scrape for only the changed retailers
- Recent Activity uses business language ("+3 new stores") not system language ("exit code 0")
- **Data source:** Reads existing `data/*/output/*.json` files + probe cache

### Screen 2: Explore ("Show me the data")

Where the GIS analyst lives. Map on top, table on bottom, filters on the side.

```
+-----------------------------------------------------------+
|  Explore                                                  |
|                                                           |
|  Filters          +-------------------------------------+ |
|  +----------+     |                                     | |
|  |Retailer  |     |         (Leaflet map with pins)     | |
|  |X Verizon |     |                                     | |
|  |X AT&T    |     |    **  *                            | |
|  |_ Target  |     |   ****** **                         | |
|  |_ T-Mobile|     |    **********                       | |
|  |...       |     |     ********  ***                   | |
|  |          |     |      **** *****                     | |
|  |State     |     |                                     | |
|  |[CA, TX v]|     |  Showing 3,987 of 37,214 stores    | |
|  |          |     +-------------------------------------+ |
|  |City      |                                            |
|  |[________]|     +-------------------------------------+ |
|  |          |     | Name          City      State  Ph   | |
|  |Status    |     | Verizon #1042 San Fran  CA   415..  | |
|  |@ All     |     | AT&T Downt.. Los Ang..  CA   213..  | |
|  |o New     |     | Verizon #887 Houston    TX   713..  | |
|  |o Closed  |     | AT&T River.. San Ant..  TX   210..  | |
|  |o Changed |     | ...                                 | |
|  |          |     |              Page 1 of 40           | |
|  |[Download]|     +-------------------------------------+ |
|  +----------+                                            |
+-----------------------------------------------------------+
```

**Key behaviors:**
- Map is the hero — GIS users think spatially
- Filters are persistent on the left, not hidden behind menus
- Table below map shows the same filtered data in tabular form
- **"Download" exports exactly what's filtered** — not the whole dataset
- Status filter (New/Closed/Changed) surfaces change detection data inline
- Store count shows filtered vs. total so users know they're looking at a subset
- Click a map pin for store details popup

### Screen 3: Changes ("What changed?")

Answers the recurring business question: are stores opening or closing?

```
+-----------------------------------------------------------+
|  Changes                                                  |
|                                                           |
|  Period  [ Last 30 days v ]   Retailer [ All v ]          |
|                                                           |
|  Summary                                                  |
|  +-------------------------------------------------------+
|  |  +47 new stores    -12 closed    ~23 modified         |
|  +-------------------------------------------------------+
|                                                           |
|  New Stores                                               |
|  +-------------------------------------------------------+
|  |  Feb 3  Target #1847     Austin, TX                   |
|  |  Feb 3  Target #1849     Pflugerville, TX             |
|  |  Feb 3  Target #1851     Round Rock, TX               |
|  |  Feb 3  Walmart #5512    Mesa, AZ                     |
|  |  Jan 27 Verizon          Bethesda, MD                 |
|  +-------------------------------------------------------+
|                                                           |
|  Closed Stores                                            |
|  +-------------------------------------------------------+
|  |  Feb 3  Best Buy #1204   Topeka, KS                   |
|  |  Feb 3  AT&T             Riverside, CA                |
|  +-------------------------------------------------------+
|                                                           |
|                                      [ Download CSV ]     |
+-----------------------------------------------------------+
```

**Key behaviors:**
- Summary headline gives the numbers immediately
- Grouped by change type (new/closed/modified), not by retailer
- Period defaults to "last 30 days" — the most common reporting window
- Download CSV for pasting into emails/reports
- **Data source:** Reads existing `data/*/history/changes_*.json` files

### Screen 4: Territories ("Design my coverage areas")

Where the tool goes from data viewer to business tool.

```
+-----------------------------------------------------------+
|  Territories                                              |
|                                                           |
|  Territory Set: [ Q1 2026 Verizon Regions v ] [+ New]     |
|                                                           |
|  +-----------------------------------------------------+ |
|  |                                                     | |
|  |  Method: ( ) MSA  ( ) Radius  ( ) Drive Time       | |
|  |                                                     | |
|  |      +----------+                                   | |
|  |      | NW Region|    +------------+                 | |
|  |      |  * * *   |    | NE Region  |                 | |
|  |      |  *  *    |    |  *** * **  |                 | |
|  |      +----------+    |  *******   |                 | |
|  |                      +------------+                 | |
|  |   +--------------+                                  | |
|  |   |  SW Region   |  +--------------+               | |
|  |   |   ** ****    |  |  SE Region   |               | |
|  |   |   *******    |  |   **** **    |               | |
|  |   +--------------+  +--------------+               | |
|  |                                                     | |
|  +-----------------------------------------------------+ |
|                                                           |
|  Territory       Stores  States  Balance                  |
|  +-----------------------------------------------------+ |
|  |  Northwest      312    5      v Under                 | |
|  |  Northeast      487    9      ^ Over                  | |
|  |  Southwest      398    4      * OK                    | |
|  |  Southeast      341    8      * OK                    | |
|  |  -- Unassigned  476    --                             | |
|  +-----------------------------------------------------+ |
|  Target: 385 stores/territory (avg)                       |
|  Imbalance: 175 between highest and lowest                |
|                                                           |
|  [ Export Boundaries ]  [ Export Assignment Table ]        |
+-----------------------------------------------------------+
```

**Three territory methods:**

| Method | How it works | External dependency | Cost |
|--------|-------------|-------------------|------|
| **MSA** | User picks Metropolitan Statistical Areas from dropdown. Stores auto-assign via point-in-polygon. | None — Census Bureau TIGER/Line boundary files (free, public domain, ~15MB, 384 MSAs). Also supports CSAs, counties, ZIP code tabulation areas. | Free |
| **Radius** | User clicks map or enters address + distance in miles. Circle drawn, stores within it assigned. | Geocoder for address input. Nominatim (free, self-hosted) or Google Geocoding ($5/1,000 requests). | ~Free |
| **Drive time** | User clicks map or enters address + minutes. Isochrone polygon follows road network. Stores within polygon assigned. | Routing API: OpenRouteService (free tier: 500/day, or self-hosted Docker), HERE ($0.59/1,000), or self-hosted Valhalla (free, needs ~10GB OSM data + 2GB RAM). | Free to low |

**Key insight:** All three methods produce the same output — a GeoJSON polygon. Once a polygon exists, territory assignment is identical regardless of how it was created. One pipeline handles all methods:

```
Method layer (polygon source)
  MSA picker       -> GeoJSON polygon
  Radius tool      -> GeoJSON polygon
  Drive time API   -> GeoJSON polygon
        |
        v
Assignment layer (shared, Turf.js client-side)
  Point-in-polygon -> store assignments
  Balance stats    -> count per territory
        |
        v
Output layer (shared)
  Map visualization
  Territory table with balance indicators
  Export: boundaries (GeoJSON/KML) + assignments (CSV/Excel)
```

**Territory features:**
- Save/load multiple territory sets ("Q1 2026 Verizon Regions", "Southeast Pilot")
- Mix methods within a set — MSA for one territory, drive-time for another
- Balance view shows over/under relative to average store count
- Import existing boundaries from GeoJSON/KML files
- **Change-driven territory alerts**: when a store opens/closes, the system identifies which territory is affected

**What this is NOT:**
- Not a replacement for ArcGIS. No demographic enrichment (population, income), no print cartography, no raster analysis, no 3D, no offline field use.
- Covers the specific workflow where analysts export store data to ArcGIS just to draw regions around store clusters and count them. That round-trip is eliminated.
- If drive-time territories need demographic overlay, export the boundaries to ArcGIS for enrichment. The tools complement each other.
- Census demographic data (population, median income per territory) could be added later using free American Community Survey data, but is not in the initial build.

---

## Change Probe System

### Purpose

Detect changes at retailer websites without running full scrapes. Probes run every 6 hours (~30 seconds total), cost 1-5 HTTP requests per retailer, and power the "changes detected" alerts on the Home screen.

### Probe strategies by retailer

| Strategy | Retailers | How it works | Requests | Savings |
|----------|----------|-------------|----------|---------|
| **Sitemap headers** | AT&T, Best Buy, T-Mobile, Bell, Sam's Club | `HEAD` request to sitemap URL, compare `ETag`/`Last-Modified` against cache | 1-2 | 90%+ |
| **Gzip size check** | Target, Walmart | `HEAD` request, compare `Content-Length` of gzipped sitemap | 1-4 | 90%+ |
| **API ETag** | Telus | `HEAD` request to Uberall API endpoint | 1 | 95% |
| **Build ID** | Apple | Fetch storelist page, extract Next.js `buildId`, compare against cache | 1 | 70% |
| **Sample query** | Home Depot, Staples | Query 1-2 states or 100 store numbers, compare count | 2-100 | 95% |
| **Content hash** | Verizon, Lowe's | Fetch top-level directory page, SHA256 hash, compare | 1-2 | 60-70% |
| **Grid sample** | Cricket | Query 10-20 geographic grid points instead of 1,200 | 10-20 | 98% |
| **Not feasible** | Costco | Requires JS rendering; no lightweight option | N/A | 0% |

### Probe cache

Small JSON file per retailer in `data/probe_cache/`:

```json
{
  "retailer": "att",
  "strategy": "sitemap_headers",
  "last_probed": "2026-02-06T06:00:00Z",
  "cached_etag": "\"5f3a8b2c\"",
  "cached_last_modified": "Wed, 05 Feb 2026 14:30:00 GMT",
  "changed": true,
  "change_reason": "Last-Modified header changed from Jan 28 to Feb 5"
}
```

### Dashboard integration

- Probes run on APScheduler (same scheduler as full scrapes)
- Home screen reads probe cache and displays alerts
- "Update These Now" button triggers full scrape for only changed retailers
- Optional Slack/email alert when probes detect changes

---

## Development Roadmap

### Revised Phase Structure

The original 5 generic phases are replaced with a concrete build sequence reflecting design decisions made during planning:

```
Week 1-2:  Dashboard Foundation
           Home screen, Changes screen, "Update Now" button
           Probe system for change detection

Week 2-3:  Data Exploration
           SQLite data loader, search/filter API
           Leaflet map with store pins
           Filtered export (CSV, Excel, GeoJSON)

Week 3-4:  Territory Design
           MSA boundary layer + picker
           Radius tool (Turf.js)
           Drive-time isochrones (OpenRouteService)
           Territory save/load, balance view, export

Week 4-5:  Operational Maturity
           Scheduled runs (APScheduler)
           Email + Slack notifications
           Data quality indicators
           Scraper health monitoring

Week 5-6:  Hardening
           Regression detection + quality gates
           Data versioning + rollback
           User documentation (in-app help)
           Access control (SSO or basic auth)

Ongoing:   Technical debt, new retailers, API formalization
```

### Day-by-day build sequence (Weeks 1-4)

Each day produces something a user can open in a browser and get value from.

**Day 1: Flask + Home screen**
- Flask app with Jinja2 templates, Tailwind CSS (CDN)
- Home route reads `data/*/output/*.json`, shows retailer table with name, store count, last modified date
- Green/yellow/red dots based on file age
- **Deliverable:** User can see what data exists and how fresh it is

**Day 2: Changes screen**
- Read `data/*/history/changes_*.json`, show new/closed/modified stores
- Filter by retailer and period
- Download CSV of filtered changes
- **Deliverable:** User can see what stores opened/closed

**Day 3: "Update Now" button**
- Subprocess call to `run.py` triggered from the browser
- Server-sent events (SSE) for real-time progress
- Run result stored in SQLite
- **Deliverable:** User can trigger a scrape without touching the terminal

**Day 4: SQLite data loader + search API**
- After each scrape, load JSON into normalized SQLite database
- Search API with filters: retailer, state, city, ZIP, store type, status
- Paginated table with sortable columns
- **Deliverable:** User can search and filter stores

**Day 5: Leaflet map**
- Leaflet.js map on the Explore screen
- Load stores as GeoJSON layer, retailer-colored pins with clustering
- Click pin for store details popup
- Filters sync between map and table
- **Deliverable:** User can see stores on a map

**Day 6: Probe system**
- `src/shared/probe.py` with per-retailer strategies
- Probe cache in `data/probe_cache/`
- Home screen reads cache, shows "changes detected" alerts
- **Deliverable:** Dashboard alerts users when data may be stale

**Day 7: Filtered export**
- "Download" button on Explore screen exports exactly the visible filtered data
- CSV, Excel, GeoJSON format options
- **Deliverable:** User gets the exact slice they need, not a 37K-row dump

**Day 8: Territory system — MSA + radius**
- Download Census TIGER/Line MSA boundaries, pre-process to GeoJSON
- MSA picker: dropdown or click-on-map selection
- Radius tool: click point + enter miles, Turf.js draws circle
- Point-in-polygon assignment via Turf.js
- Territory table with store counts
- **Deliverable:** User can create territories from MSAs or radius circles

**Day 9: Territory system — drive time**
- OpenRouteService API integration for isochrone generation
- User clicks point + selects 15/30/45/60 minutes
- Isochrone polygon rendered on map, stores assigned
- Cache isochrone results (same center + time = same polygon)
- **Deliverable:** User can create drive-time territories

**Day 10: Territory management**
- Save/load territory sets (SQLite)
- Name territories, mix methods within a set
- Balance view: store count per territory, over/under indicators
- Import boundaries from GeoJSON/KML
- Export: boundaries (GeoJSON/KML) + assignment table (CSV/Excel)
- **Deliverable:** Full territory design workflow without ArcGIS

### Week 4-5: Operational Maturity

**Scheduling:**
- APScheduler integrated into Flask
- Cron-like schedule per retailer in `config/retailers.yaml`
- Dashboard page to view upcoming/past scheduled runs
- Run queue prevents overlapping executions

**Alerting:**
- Email via SMTP (corporate relay)
- Slack webhook (already stubbed in `src/shared/notifications.py`)
- Alert on: scrape complete, scrape failed, store count anomaly (>10% drop), probe detects changes

**Data quality indicators:**
- Per-retailer metrics on Home screen: field completeness, coordinate coverage, freshness
- Green/yellow/red per metric
- Alert if quality drops below thresholds

**Scraper health:**
- Health page showing per-scraper: last success, last failure, success rate (30 days), expected vs. actual store count
- Powered by run history in SQLite

### Week 5-6: Hardening

**Quality gates:**
```yaml
# config/retailers.yaml
quality_gates:
  verizon:
    min_stores: 1800
    max_stores: 2500
    required_fields_threshold: 0.95
    coordinate_coverage_threshold: 0.90
```
- After each run, check store count within range, required fields present, coordinates valid
- Flag bad runs, optionally prevent overwriting known-good data
- Send alert on regression

**Data versioning:**
- Keep last N runs per retailer (default 10)
- One-click rollback from dashboard
- Diff view between any two runs

**User documentation:**
- Quick Start Guide (1 page, in-app help)
- Data Dictionary (what each field means, per retailer)
- Runbook (what to do when a scrape fails)

**Access control:**
- Phase 1: HTTP Basic Auth with user list in environment variables
- Phase 2: OIDC/SAML SSO integration
- Roles: Viewer (browse/download), Operator (run scrapes/manage schedules), Admin (configure/audit)

---

## Technical Architecture

### Deployment

```
+---------------------------------------------+
|  Server (single Docker host or small VM)     |
|                                              |
|  +----------+  +----------+  +-----------+   |
|  | Flask     |  | Scheduler|  | Scraper   |  |
|  | Dashboard |  | (APSched)|  | Engine    |  |
|  | (HTMX)   |  |          |  | (existing)|  |
|  +-----+----+  +----+-----+  +-----+-----+  |
|        |             |              |         |
|        +-------------+--------------+         |
|                      |                        |
|              +-------+-------+                |
|              |    SQLite     |                |
|              |  + data/*.json|                |
|              +---------------+                |
+---------------------------------------------+
         |
         |  HTTPS (internal network)
         v
+-------------------+
|  Business Users   |
|  (browser only)   |
+-------------------+
```

**Infrastructure:** One container (or two via docker-compose). No Kubernetes. No microservices. No external database server. SQLite handles the scale — 37K stores across 15 retailers is trivially small.

### Technology Stack

| Need | Choice | Rationale |
|------|--------|-----------|
| **Backend** | Flask (existing) | Already in the codebase, sufficient for server-rendered app |
| **Templates** | Jinja2 | Ships with Flask, server-rendered HTML |
| **Interactivity** | HTMX + Alpine.js | Minimal JS, progressive enhancement, no build step |
| **Styling** | Tailwind CSS | Utility-first, responsive by default, fast to develop |
| **Map** | Leaflet.js + OpenStreetMap | Free, open-source, no API key costs |
| **Spatial operations** | Turf.js (client-side) | Point-in-polygon, area, distance — runs in browser |
| **Isochrones** | OpenRouteService API | Free tier (500/day), or self-hosted Docker for unlimited |
| **Geocoding** | Nominatim (self-hosted) or Google | Address-to-coordinate for radius/drive-time center |
| **Boundary data** | Census TIGER/Line | MSA, county, ZIP boundaries — free, public domain |
| **Charts** | Chart.js | Lightweight, good for dashboards |
| **Database** | SQLite (via SQLAlchemy) | Zero infrastructure, handles the data volume easily |
| **Search** | SQLite FTS5 | Built-in full-text search, no Elasticsearch needed |
| **Scheduling** | APScheduler | Python-native, integrates with Flask |
| **Email** | smtplib (stdlib) | No additional dependency |
| **Real-time updates** | Server-sent events (SSE) | Simpler than WebSockets, sufficient for progress updates |

### Data Flow

```
Probe (every 6h)                    Full Scrape (scheduled or on-demand)
  15 retailers                        Triggered by:
  1-5 requests each                   - User clicks "Update Now"
  ~30 seconds total                   - Weekly schedule
  No proxy needed (mostly)            - Probe detects changes
       |                                     |
       v                                     v
  probe_cache/*.json                  data/*/output/*.json
       |                                     |
       v                                     v
  Home screen alerts                  SQLite database (loaded post-scrape)
                                             |
                                     +-------+-------+
                                     |       |       |
                                     v       v       v
                                   Explore  Changes  Territories
                                   screen   screen   screen
```

---

## Technical Debt to Address

Prioritized by business impact:

1. **Lowe's scraper fragility** — Replace brace-depth JSON extraction with proper HTML parser targeting `<script>` tags. Highest-risk scraper pattern. Address in Week 4-5.

2. **Store schema fragmentation** — `zip` vs `postal_code`, inconsistent field names across scrapers. `store_schema.py` normalization exists but isn't applied consistently. Enforce at scraper level, not just export. Address during SQLite loader build (Week 2).

3. **Notification stubs** — `src/shared/notifications.py` exists but needs real email/Slack implementation. Address in Week 4.

4. **Inconsistent XML parsing** — Not all scrapers use `defusedxml`. Standardize. Address opportunistically.

5. **No integration tests** — All 1,288 tests use mocks. Add canary tests (one URL per retailer) on a schedule to detect structural changes. Address in Week 5.

6. **Missing UAT framework** — `tests/uat/` referenced in CLAUDE.md but doesn't exist. Build as part of hardening.

7. **Run tracker migration** — `runs/{run_id}.json` files should move to SQLite once the dashboard database exists (Day 3).

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Retailer blocks scraper** | High | High | Proxy rotation, respectful delays, fallback strategies |
| **Website structure changes break scraper** | High | High | Probe system detects early; quality gates prevent bad data from publishing |
| **Drive-time API rate limits** | Medium | Medium | Cache isochrone results aggressively; self-host Valhalla if free tier insufficient |
| **Scope creep into full GIS platform** | High | Medium | Clear boundary: no demographics, no print cartography, no raster. Export to ArcGIS for those. |
| **Dashboard performance with 37K+ points on map** | Medium | Medium | Marker clustering (Leaflet.markercluster), server-side pagination, pre-aggregate |
| **Single developer dependency** | Medium | High | Simple tech stack (Flask/HTMX/SQLite), no exotic frameworks, document decisions |
| **Business user adoption** | Medium | High | Involve users in design feedback early; each build day produces usable output |
| **Proxy credential security** | Low | High | Centralized server — credentials never distributed to user machines |
| **Territory design expectations exceed scope** | Medium | Medium | Set clear "this is not ArcGIS" expectations. Export path to ArcGIS for advanced work. |

---

## Success Metrics

### Week 2 (Foundation complete)
- [ ] Business user can see all retailer data freshness in a browser
- [ ] Business user can see store openings/closings without reading JSON files
- [ ] Business user can trigger a scrape from the browser
- [ ] Probes detect changes at 14/15 retailers without full scrapes

### Week 3 (Exploration complete)
- [ ] Users can view stores on a map and filter by retailer/state/city
- [ ] Users can search for specific stores by name or location
- [ ] "Download" exports exactly the filtered subset (not raw files)

### Week 4 (Territories complete)
- [ ] Users can create territories via MSA selection
- [ ] Users can create territories via radius from a point
- [ ] Users can create territories via drive-time isochrones
- [ ] Territory balance view shows over/under at a glance
- [ ] Territory boundaries exportable as GeoJSON/KML
- [ ] Assignment table exportable as CSV/Excel

### Week 5-6 (Operational maturity)
- [ ] Scrapes run on a weekly schedule without manual intervention
- [ ] Email/Slack notifications on completion, failure, and anomalies
- [ ] Scraper failures detected within 24 hours (down from potentially weeks)
- [ ] Store count regressions flagged before bad data is published
- [ ] New team member can onboard in <30 minutes

### Ongoing
- [ ] SSO authentication enforced
- [ ] Downstream systems consume data via REST API
- [ ] Historical trends visible per retailer
- [ ] 99.5% dashboard uptime

---

## Appendix: Current Retailer Coverage

| Retailer | Country | Strategy | Est. Stores | Proxy Required | Probe Strategy |
|----------|---------|----------|-------------|----------------|----------------|
| Verizon | US | HTML crawl (4-phase) | ~2,000 | Residential | Content hash |
| AT&T | US | XML sitemap | ~2,000 | Residential | Sitemap headers |
| Target | US | Gzipped sitemap + API | ~1,800 | Residential | Gzip size check |
| T-Mobile | US | Paginated sitemaps | ~4,000 | Web Scraper API | Sitemap headers |
| Walmart | US | Multiple gzipped sitemaps | ~4,700 | Hybrid | Gzip size check |
| Best Buy | US | XML sitemap + JS rendering | ~1,400 | Web Scraper API | Sitemap headers |
| Cricket | US | Yext API (geographic grid) | ~13,600 | Direct | Grid sample |
| Home Depot | US | GraphQL API | ~2,000 | Direct | Sample query |
| Staples | US | API scan + REST API + locator | ~1,500 | Web Scraper API | Sample query |
| Apple | US | Next.js SSR | ~272 | Direct | Build ID |
| Costco | US | HTML scraping | ~600 | Web Scraper API | Not feasible |
| Sam's Club | US | Sitemap + HTML | ~600 | Hybrid | Sitemap headers |
| Lowe's | US | HTML + Redux JSON | ~1,761 | Residential | Content hash |
| Telus | CA | Uberall API | ~857 | Residential | API ETag |
| Bell | CA | Sitemap + JSON-LD | ~251 | Direct | Sitemap headers |
| **Total** | | | **~37,000** | | **14/15 probable** |
