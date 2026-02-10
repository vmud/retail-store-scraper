# Application Design Process: Store Intelligence Platform

> **Document Type**: Process Guide
> **Purpose**: Step-by-step process for producing Claude Code-optimized design artifacts and automation infrastructure, sufficient for Claude Code to build the application with minimal per-session context loading.
> **Audience**: Solo founder/operator working with Claude Code as primary engineering team
> **Created**: 2026-02-06
> **Revision**: 2 — restructured for AI-first artifact production and automation planning

---

## How This Process Works

### The Core Problem This Solves

Claude Code sessions start with zero context. Every session must re-learn what the app is, what decisions were made, and what to build next. This process produces **context packages** — concise, structured artifacts optimized for Claude Code consumption — not traditional design documents written for human committees.

### What Gets Built (Two Tracks)

This process runs two parallel tracks:

**Track 1: Design Artifacts** — The decisions and specifications Claude Code needs to build correctly.

```
docs/design/
├── 00-business-context.md       # Domain knowledge + glossary
├── 01-brd.md                    # Requirements with IDs, priorities, acceptance criteria
├── 02-personas.md               # User types + their journeys (drives UI decisions)
├── 03-product-scope.md          # What's in MVP vs later (the scope contract)
├── 04-system-architecture.md    # Tech stack, component diagram, integration pattern
├── 05-data-model.md             # Schema DDL, entity relationships, data flow
├── 06-api-design.md             # OpenAPI-style endpoint specs with request/response schemas
├── 07-ui-ux.md                  # Screen inventory, wireframes, interaction patterns
├── 08-integration.md            # Scraper-to-app bridge, scheduling, error propagation
├── 09-infrastructure.md         # Hosting, CI/CD, environments, costs
├── 10-security.md               # Auth, RBAC, monitoring, compliance
├── 11-roadmap.md                # Sprint breakdown with context packages
└── decisions/                   # ADRs (one per major technical choice)
    ├── DECISION-LOG.md          # Running index of all decisions
    ├── ADR-001-*.md
    └── ...
```

**Track 2: Automation Infrastructure** — The skills, CLAUDE.md sections, agents, and hooks that make Claude Code efficient at building this app.

```
app-repo/                        # The new app repository
├── CLAUDE.md                    # Progressively built across phases
├── .claude/
│   ├── skills/                  # Custom slash commands for development workflows
│   ├── agents/                  # Custom agents for specialized tasks
│   └── rules/                   # Coding standards, patterns, conventions
└── docs/
    └── sprints/                 # Self-contained context packages per sprint
        ├── sprint-01.md         # Everything Claude needs for Sprint 1
        ├── sprint-02.md
        └── ...
```

### Design Principles for Artifacts

Every document produced by this process follows these rules:

1. **Tables over prose** — Decisions, requirements, and specs use tables. Claude parses tables faster than paragraphs.
2. **IDs on everything** — Requirements (FR-001), features (F-001), ADRs (ADR-001). Claude can cross-reference by ID.
3. **Schemas are code** — Database schemas are SQL. API specs are structured markdown with request/response JSON. No hand-waving.
4. **Decisions are explicit** — Every `[DECISION]` marker produces a row in `DECISION-LOG.md` and optionally a full ADR.
5. **Context budget awareness** — Each sprint context package stays under 500 lines. If Claude needs to read more, it's linked, not inlined.

### Session Pattern

Every design phase follows this session pattern:

```
1. Start Claude Code session
2. Prompt: "Read docs/process/app-design-process.md, Phase N. Read all listed inputs. Produce the deliverable."
3. Collaborate on decisions (you provide domain knowledge, Claude structures it)
4. Claude writes the deliverable document
5. Claude updates the automation artifacts (CLAUDE.md section, skill, etc.)
6. You review the decision gate checklist
7. Move to Phase N+1
```

---

## Phase 0: Business Context Consolidation

### Purpose

Produce a single reference document containing all domain knowledge, so no subsequent session needs to re-extract this from your head.

### Inputs

- Your business need statement (store lists, territory design, self-service)
- Your solution statement (automated scraping, self-service portal, territory tools)
- Existing project: `retail-store-scraper/` (15+ retailers, change detection, export)
- Your domain expertise in field marketing operations

### Activities

**Activity 0.1: Domain Knowledge Extraction** [BRAINSTORM]

Claude interviews you and structures answers into these sections:

| Section | What Goes Here |
|---------|---------------|
| Business Model | Who pays, for what, how the money flows |
| Users | Who uses this tool, their roles, their technical level |
| Current Workflow | How store lists and territories are managed today (the pain) |
| Competitive Landscape | What tools exist, why they fail, what the gap is |
| Domain Glossary | 20+ terms defined (MSA, isochrone, territory, alignment, etc.) |
| Existing Asset | What the scraper already does (capabilities table) |
| Constraints | Budget, team (solo + Claude Code), timeline, tech preferences |
| Open Questions | Things not yet decided (captured, not answered) |

**Activity 0.2: Existing Scraper Capability Audit**

Claude reads the scraper codebase and produces a capability matrix:

```markdown
| Capability | Status | Module | Notes |
|-----------|--------|--------|-------|
| Multi-retailer scraping | Done | src/scrapers/*.py | 15+ retailers |
| Change detection | Done | src/change_detector.py | New/closed/modified |
| Export (CSV/Excel/GeoJSON) | Done | src/shared/export_service.py | |
| Store validation | Done | src/shared/utils.py | validate_store_data() |
| Proxy integration | Done | src/shared/proxy_client.py | Oxylabs residential/API |
| GCS cloud sync | Done | src/shared/cloud_storage.py | |
| Database output | Gap | — | Currently JSON files only |
| API interface | Gap | — | CLI only, no HTTP API |
| Scheduling | Gap | — | Manual or cron, no built-in scheduler |
```

### Deliverable

`docs/design/00-business-context.md` — structured as above, max 300 lines.

### Automation Output

**CLAUDE.md seed section** (for the new app repo, drafted now):

```markdown
## Project Overview
Store Intelligence Platform — self-service store list management and territory design
for field marketing operations. The retail-store-scraper project is the data engine.

## Domain Glossary
[Extracted from Activity 0.1 — top 10 terms inline, full glossary linked]
```

### Decision Gate

- [ ] Domain glossary has 20+ terms
- [ ] Scraper capability matrix is accurate (you verified against actual codebase)
- [ ] Open questions list is explicit
- [ ] You reviewed and corrected domain misunderstandings

### Who

- **You**: Primary domain knowledge source
- **Claude Code**: Knowledge synthesizer agent (Opus)

---

## Phase 1: Business Requirements Document

### Purpose

Formalize what the system must do. Every subsequent design decision traces to a requirement ID from this document.

### Inputs

- `docs/design/00-business-context.md`

### Activities

**Activity 1.1: Business Objectives Table**

| ID | Objective | Success Metric | Current State | Target State |
|----|-----------|---------------|---------------|-------------|
| BO-001 | Eliminate manual store list management | Clean store list in < 5 min | Hours of manual work | Self-service download |
| BO-002 | Self-service territory design | Territory in < 30 min, no GIS analyst | Every request needs GIS analyst | 3 basic territory types available to business users |
| BO-003 | Proactive change detection | Closures detected within 48h | Discovered when field rep arrives | Automated detection + alerts |

**Activity 1.2: Functional Requirements** [BRAINSTORM]

Produce a table, not prose. For each requirement:

| ID | Area | Description | Priority | Acceptance Criteria | Release |
|----|------|-------------|----------|--------------------|---------|
| FR-001 | Store Data | View store list by retailer | Must | User selects retailer, sees paginated store table | MVP |
| FR-002 | Store Data | Filter stores by state/city | Must | Multi-select state filter narrows results | MVP |
| FR-003 | Export | Download store list as CSV | Must | CSV contains all visible columns, respects filters | MVP |
| ... | | | | | |

Target: 30-50 requirements across these areas:
1. Store Data Management (view, search, filter, detail)
2. Export (CSV, Excel, GeoJSON, async for large sets)
3. Change Detection (new/closed/modified, history)
4. Territory Design (MSA, radius, drive time — v0.2/v0.3)
5. Notifications (email, webhook — v0.4)
6. User Management (auth, roles, org)
7. Administration (scraper control, data quality)

**Activity 1.3: Non-Functional Requirements**

| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Performance | Store list page load | < 2s for 1000 rows |
| NFR-002 | Performance | Map render with pins | < 3s for 5000 pins |
| NFR-003 | Scale | Concurrent users | 10 (MVP), 100 (v1.0) |
| NFR-004 | Data Freshness | Store data age | < 7 days |
| NFR-005 | Availability | Uptime | 99% (MVP) |
| NFR-006 | Browser Support | Browsers | Chrome, Firefox, Safari (latest 2) |

**Activity 1.4: Constraints Table**

| Constraint | Value | Impact |
|-----------|-------|--------|
| Team | Solo founder + Claude Code | No complex ops, prefer managed services |
| Budget (infra) | $50/mo ceiling for MVP | Limits hosting choices |
| Timeline | MVP in 8 weeks | Constrains scope |
| Existing tech | Python scraper | Backend likely Python |

### Deliverable

`docs/design/01-brd.md` — requirements tables with IDs. Max 200 lines.

### Automation Output

**CLAUDE.md addition:**

```markdown
## Requirements Reference
See docs/design/01-brd.md for full requirements.
MVP scope: FR-001 through FR-0XX. Territory features deferred to v0.2+.
```

### Decision Gate

- [ ] 30+ functional requirements with IDs and acceptance criteria
- [ ] Every requirement has MoSCoW priority and release assignment
- [ ] NFRs have quantitative targets
- [ ] Constraints are realistic (you confirmed budget/timeline)

### Who

- **You**: Priority decisions, domain validation
- **Claude Code**: Business analyst agent (Opus)

---

## Phase 2: User Personas and Journeys

### Purpose

Define who uses the app and their critical workflows. This drives UI design and feature prioritization.

### Inputs

- `docs/design/01-brd.md`
- `docs/design/00-business-context.md`

### Activities

**Activity 2.1: Persona Cards** [BRAINSTORM]

Produce 3-5 persona cards. Each is a structured block, not a narrative:

```markdown
### Persona: Operations Manager
- **Role**: Manages store lists across client programs
- **Tech Level**: Low (Excel power user, no GIS)
- **Frequency**: Weekly
- **Primary Tasks**: Download store lists, check for closures, update programs
- **Success**: Clean store list in 5 minutes instead of 2 hours
- **Frustration**: Manual data wrangling, stale lists, missed closures
```

**Activity 2.2: Critical User Journeys**

For each persona, map their top 3 journeys as step tables:

| Step | User Action | System Response | Screen |
|------|------------|-----------------|--------|
| 1 | Selects "Verizon" from retailer dropdown | Loads store list (paginated) | Store List |
| 2 | Filters to MD, PA, VA | Table updates with filtered results | Store List |
| 3 | Clicks "Export CSV" | Downloads file with filtered stores | Store List |

Priority journeys (drives MVP screen inventory):
1. Get a clean store list for a retailer filtered by states
2. See what stores opened or closed recently
3. Create MSA-based territories (v0.2)
4. Create drive-time territories (v0.3)

### Deliverable

`docs/design/02-personas.md` — persona cards + journey tables. Max 150 lines.

### Decision Gate

- [ ] 3+ personas defined with tech level and frequency
- [ ] 6+ user journeys mapped with step tables
- [ ] Journeys trace to specific requirements (FR-xxx)

### Who

- **You**: Validate personas against real people in these roles
- **Claude Code**: UX researcher agent (Opus)

---

## Phase 3: Product Scope and Feature Prioritization

### Purpose

Draw the hard line between MVP and later. This is the scope contract. Nothing ships in MVP unless it's on this list.

### Inputs

- `docs/design/01-brd.md` (requirements)
- `docs/design/02-personas.md` (user needs)

### Activities

**Activity 3.1: Feature Inventory** [BRAINSTORM]

Expand requirements into concrete features. Each feature is user-visible:

| ID | Feature | Area | Release | Traces To |
|----|---------|------|---------|-----------|
| F-001 | Retailer selector dropdown | Store Data | MVP | FR-001 |
| F-002 | Store list table (sortable, paginated) | Store Data | MVP | FR-001 |
| F-003 | State/city filter panel | Store Data | MVP | FR-002 |
| F-004 | CSV export with active filters | Export | MVP | FR-003 |
| F-005 | Excel export with active filters | Export | MVP | FR-003 |
| F-006 | Store map view with pins | Store Data | MVP | FR-006 |
| F-007 | Store detail panel (address, phone, hours) | Store Data | MVP | FR-007 |
| F-008 | Change summary dashboard | Changes | MVP | FR-010 |
| F-009 | Recent changes table | Changes | MVP | FR-011 |
| F-020 | MSA territory builder | Territory | v0.2 | FR-020 |
| F-021 | Distance radius territory builder | Territory | v0.2 | FR-021 |
| F-030 | Drive time isochrone builder | Territory | v0.3 | FR-022 |
| F-040 | Store change notification config | Alerts | v0.4 | FR-030 |

**Activity 3.2: MVP Scope Statement** [DECISION]

Write a single paragraph that a Claude Code session can read to know exactly what's in scope:

> **MVP (v0.1)**: A web application where business users select a retailer, view the current store list in a table or on a map, filter by state/city, and download as CSV or Excel. A dashboard shows summary stats and recent store changes (new, closed). Data is sourced from the retail-store-scraper and refreshed on a schedule. Users authenticate with email/password. No territory features, no notifications, no multi-tenant.

**Activity 3.3: Feature Specifications** [FOR MVP FEATURES ONLY]

For each MVP feature, produce a spec block:

```markdown
### F-001: Retailer Selector
**Release**: MVP | **Priority**: Must | **Persona**: Operations Manager
**Traces to**: FR-001

**Behavior**: Dropdown showing all enabled retailers with store counts.
Selecting a retailer loads the store list view for that retailer.

**Acceptance Criteria**:
- [ ] Shows retailer name and store count
- [ ] Sorted alphabetically
- [ ] Only enabled retailers appear
- [ ] Selection persists in URL (bookmarkable)

**Data**: GET /api/retailers → [{slug, name, store_count, last_updated}]
```

### Deliverable

`docs/design/03-product-scope.md` — feature table + MVP statement + feature specs. Max 300 lines.

### Automation Output

**CLAUDE.md addition:**

```markdown
## Product Scope
MVP: Store list viewing, filtering, export (CSV/Excel), map view, change dashboard.
NOT in MVP: Territories, notifications, multi-tenant.
Full feature list: docs/design/03-product-scope.md
```

### Decision Gate

- [ ] Every feature has an ID, release assignment, and requirement trace
- [ ] MVP scope statement is one paragraph (Claude can read it in 3 seconds)
- [ ] MVP features have acceptance criteria
- [ ] Territory features are explicitly v0.2+
- [ ] MVP can realistically ship in 6-8 weeks of Claude Code sprints

### Who

- **You**: Final scope decisions
- **Claude Code**: Product manager agent (Opus)

---

## Phase 4: System Architecture

### Purpose

Choose the tech stack and define how components connect. Every ADR produced here becomes a permanent reference for all future Claude Code sessions.

### Inputs

- `docs/design/03-product-scope.md`
- `docs/design/01-brd.md` (NFRs, constraints)
- Existing scraper codebase

### Activities

**Activity 4.1: Architecture Pattern** [DECISION] [ADR]

| Pattern | Pros | Cons | Verdict |
|---------|------|------|---------|
| Python API + React SPA | Rich map interactions, API-first | Two codebases | **Likely best** |
| Django + HTMX | Simpler, one codebase | Limited map interactivity | Maybe for MVP |
| Next.js full-stack | SSR, one language | Python scraper integration harder | Mismatch |

Produce: `decisions/ADR-001-architecture-pattern.md`

**Activity 4.2: Tech Stack Selection** [DECISION] [ADR per choice]

Produce a single tech stack table — this goes directly into CLAUDE.md:

| Layer | Choice | Rationale | ADR |
|-------|--------|-----------|-----|
| Backend | FastAPI / Django | [decided] | ADR-002 |
| Frontend | React + TypeScript | [decided] | ADR-003 |
| Database | PostgreSQL + PostGIS | [decided] | ADR-004 |
| Map Library | Mapbox GL / Leaflet | [decided] | ADR-005 |
| Component Library | shadcn/ui / Ant Design | [decided] | ADR-006 |
| Isochrone API | Mapbox / TravelTime | [decided] | ADR-007 |
| Auth | Clerk / Auth0 / custom | [decided] | ADR-008 |
| Hosting | Railway / Render / Fly | [decided] | ADR-009 |

**Activity 4.3: Component Architecture**

Produce a structured component diagram Claude can reference:

```
[React SPA] ←HTTP→ [FastAPI Backend]
                      ├── /api/auth/* → [Auth Service]
                      ├── /api/retailers/* → [Store Service] → [PostgreSQL + PostGIS]
                      ├── /api/stores/* → [Store Service]
                      ├── /api/exports/* → [Export Service] → [File Storage]
                      ├── /api/territories/* → [Territory Service] → [Isochrone API]
                      └── /api/admin/* → [Admin Service] → [Scraper Engine]
                                                              ↑
                                                   [retail-store-scraper]
                                                   (existing, runs on schedule)
```

**Activity 4.4: Scraper-to-App Bridge** [DECISION] [ADR]

| Option | How It Works | Complexity | Coupling |
|--------|-------------|-----------|---------|
| A: Shared DB | Scraper writes to PostgreSQL | Medium | Tight |
| B: File ingest | Scraper writes JSON, app imports | Low | Loose |
| C: API ingest | Scraper POSTs to app API | Medium | Medium |

Produce: `decisions/ADR-010-scraper-integration.md`

### Deliverable

`docs/design/04-system-architecture.md` — tech stack table + component diagram + ADR index. Max 200 lines.

### Automation Output

**CLAUDE.md addition** (critical — this is read every session):

```markdown
## Tech Stack
- Backend: [choice] (Python 3.11+)
- Frontend: [choice] (TypeScript)
- Database: PostgreSQL 16 + PostGIS 3.4
- Map: [choice]
- UI Components: [choice]
- Auth: [choice]
- Hosting: [choice]

## Architecture
[Component diagram from Activity 4.3]

## Key ADRs
| ADR | Decision | Link |
|-----|----------|------|
| ADR-001 | [pattern] | docs/design/decisions/ADR-001-*.md |
| ... | ... | ... |
```

**Skill created**: `.claude/skills/new-sprint/SKILL.md` — scaffolding for starting a new sprint (reads context package, sets up branch).

### Decision Gate

- [ ] Tech stack table is complete (all layers decided)
- [ ] Component diagram shows all services and their connections
- [ ] Scraper integration pattern chosen
- [ ] ADRs written for each major decision
- [ ] You can explain to someone why each technology was chosen

### Who

- **You**: Technology preferences, budget review
- **Claude Code**: System architect agent (Opus). Can parallelize: architecture + GIS tech eval + database eval (3 sessions).

---

## Phase 5: Data Model

### Purpose

Produce the database schema as runnable SQL. Claude Code sessions will reference this DDL directly.

### Inputs

- `docs/design/04-system-architecture.md`
- `docs/design/03-product-scope.md` (what data MVP needs)
- Existing: `src/shared/store_schema.py` (canonical store fields)

### Activities

**Activity 5.1: Entity-Relationship Table**

| Entity | Attributes (key ones) | Relations |
|--------|----------------------|-----------|
| Retailer | slug, name, enabled, store_count, last_scrape_at | has many Stores |
| Store | store_id, name, address, city, state, zip, lat/lng, geom, attributes(JSONB) | belongs to Retailer |
| StoreChange | type(new/closed/modified), detected_at, details(JSONB) | belongs to Store |
| User | email, name, role, org_id | belongs to Organization |
| Organization | name, slug | has many Users |
| Territory | name, type(msa/radius/isochrone), params(JSONB), boundary(GEOMETRY) | has many TerritoryAssignments |
| TerritoryAssignment | territory_id, store_id | links Territory to Store |
| ScrapeRun | retailer_id, started_at, status, store_count, changes_count | belongs to Retailer |
| Export | user_id, retailer_id, format, filters(JSONB), status, file_path | belongs to User |

**Activity 5.2: Schema DDL** [DECISION: flexible fields approach]

Produce actual SQL that can be used in migrations:

```sql
-- This goes directly into the migration file
CREATE TABLE retailers (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    store_count INTEGER DEFAULT 0,
    last_scrape_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE stores (
    id SERIAL PRIMARY KEY,
    retailer_id INTEGER REFERENCES retailers(id),
    store_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    street_address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(10),
    zip VARCHAR(20),
    phone VARCHAR(50),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    country VARCHAR(10) DEFAULT 'US',
    url TEXT,
    attributes JSONB DEFAULT '{}',
    geom GEOMETRY(Point, 4326),
    is_active BOOLEAN DEFAULT true,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(retailer_id, store_id)
);

CREATE INDEX idx_stores_geom ON stores USING GIST(geom);
CREATE INDEX idx_stores_retailer_active ON stores(retailer_id, is_active);
CREATE INDEX idx_stores_state ON stores(state);
-- [continue for all tables]
```

**Activity 5.3: Data Ingestion Flow**

```
Scraper output (JSON) → [Ingest Script/Service] → PostgreSQL
                              ├── UPSERT stores (match on retailer_id + store_id)
                              ├── Mark missing stores as inactive
                              ├── Generate StoreChange records
                              └── Update retailer.store_count, last_scrape_at
```

### Deliverable

`docs/design/05-data-model.md` — ER table + full DDL + ingestion flow. Max 250 lines.

### Automation Output

**CLAUDE.md addition:**

```markdown
## Database
PostgreSQL 16 + PostGIS 3.4. Schema: docs/design/05-data-model.md
Key tables: retailers, stores (with PostGIS geom column), store_changes, territories
Flexible fields: JSONB `attributes` column on stores for retailer-specific data
Migration tool: [Alembic / Django migrations]
```

### Decision Gate

- [ ] DDL is valid SQL (Claude tested it mentally or you ran it)
- [ ] All MVP features can be served by this schema
- [ ] PostGIS spatial column and index are present
- [ ] JSONB approach for flexible fields is decided
- [ ] Ingestion flow handles upserts and change detection
- [ ] Territory tables exist (even if not populated until v0.2)

### Who

- **You**: Review domain model accuracy
- **Claude Code**: Database architect agent (Opus)

---

## Phase 6: API Design

### Purpose

Define the API contract as structured specs that Claude Code can implement directly. Every endpoint spec becomes a buildable unit.

### Inputs

- `docs/design/05-data-model.md`
- `docs/design/03-product-scope.md` (MVP features)

### Activities

**Activity 6.1: API Style** [DECISION]

Choose REST (recommended for this use case). Document versioning strategy.

**Activity 6.2: Endpoint Specifications**

For each endpoint, produce a structured spec block that Claude can implement from:

```markdown
### GET /api/retailers
**Auth**: Required
**Description**: List all enabled retailers with store counts
**Query Params**: none
**Response 200**:
```json
{
  "data": [
    {"slug": "verizon", "name": "Verizon", "store_count": 6123, "last_updated": "2026-02-06T10:00:00Z"}
  ]
}
```
**Errors**: 401 Unauthorized

### GET /api/retailers/{slug}/stores
**Auth**: Required
**Description**: Paginated store list for a retailer
**Query Params**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| state | string[] | — | Filter by state codes (comma-separated) |
| city | string | — | Filter by city (partial match) |
| is_active | boolean | true | Filter by active status |
| page | integer | 1 | Page number |
| per_page | integer | 50 | Items per page (max 200) |
| sort | string | name | Sort field |
| order | string | asc | Sort order |
**Response 200**:
```json
{
  "data": [{"id": 1, "store_id": "V001", "name": "...", "latitude": 39.28, "longitude": -76.61, ...}],
  "meta": {"total": 234, "page": 1, "per_page": 50, "pages": 5}
}
```
```

Cover all MVP endpoints:
- Auth: login, register, refresh, logout
- Retailers: list, detail
- Stores: list (paginated + filterable), detail, search (cross-retailer)
- Exports: create (async), status, download
- Changes: list by retailer, summary
- Admin: trigger scrape, scraper status

Sketch v0.2 territory endpoints as placeholders.

### Deliverable

`docs/design/06-api-design.md` — endpoint specs with request/response schemas. Max 400 lines.

### Automation Output

**CLAUDE.md addition:**

```markdown
## API Conventions
- REST, JSON, Bearer token auth
- Pagination: ?page=1&per_page=50, response includes meta.total/pages
- Filtering: query params (state=MD,PA)
- Errors: {"error": "message", "code": "ERROR_CODE"}
- Full spec: docs/design/06-api-design.md
```

### Decision Gate

- [ ] Every MVP feature has supporting endpoints
- [ ] Request/response schemas are defined (not just paths)
- [ ] Pagination and filtering patterns are consistent
- [ ] Error format is standardized
- [ ] Async export flow is designed
- [ ] Territory endpoints are sketched (v0.2 placeholder)

### Who

- **You**: Review API usability
- **Claude Code**: API designer agent (Opus)

---

## Phase 7: UI/UX Design

### Purpose

Produce screen specifications and interaction patterns that Claude Code can implement. Wireframes are text-based (Claude can't consume images). Every screen maps to API endpoints.

### Inputs

- `docs/design/02-personas.md` (who uses each screen)
- `docs/design/03-product-scope.md` (MVP features)
- `docs/design/06-api-design.md` (what data is available)
- `.claude/rules/ui-design.md` (Nielsen's heuristics)

### Activities

**Activity 7.1: Screen Inventory**

| Screen | Route | Primary Persona | Features | API Endpoints |
|--------|-------|----------------|----------|--------------|
| Dashboard | / | All | Summary stats, recent changes | GET /api/retailers, GET /api/changes/summary |
| Store List | /retailers/:slug/stores | Ops Manager | Table, filters, export | GET /api/retailers/:slug/stores |
| Store Map | /retailers/:slug/map | Ops Manager | Map pins, clusters, popups | GET /api/retailers/:slug/stores?per_page=all |
| Store Detail | /retailers/:slug/stores/:id | Ops Manager | Full store info | GET /api/retailers/:slug/stores/:id |
| Export | /exports | Ops Manager | Create export, history | POST /api/exports, GET /api/exports |
| Changes | /retailers/:slug/changes | Ops Manager | Change history table | GET /api/retailers/:slug/changes |
| Settings | /settings | Admin | Profile, org, scraper config | Various admin endpoints |
| Login | /login | All | Auth form | POST /api/auth/login |

**Activity 7.2: Screen Specifications**

For each screen, produce a structured spec (not a wireframe drawing):

```markdown
### Screen: Store List (/retailers/:slug/stores)

**Layout**: Sidebar filters (left, collapsible) + main content (table)

**Components**:
| Component | Behavior | Data Source |
|-----------|----------|-------------|
| Retailer breadcrumb | Shows current retailer, links back to dashboard | URL param |
| State filter | Multi-select dropdown, all US states | Static list |
| City filter | Text search, autocomplete | Derived from store data |
| Store table | Sortable columns, paginated | GET /api/retailers/:slug/stores |
| Export button | Opens export config modal | — |
| Map toggle | Switches to map view | — |
| "Last updated" badge | Shows retailer.last_updated | GET /api/retailers/:slug |

**Table Columns**: Store ID, Name, Address, City, State, ZIP, Phone, Status
**Default Sort**: Name ASC
**Pagination**: 50 per page, bottom pagination controls

**States**:
- Loading: Table skeleton (6 rows)
- Empty: "No stores match your filters. Try broadening your search."
- Error: Toast notification + retry button
```

**Activity 7.3: Interaction Patterns**

| Pattern | Implementation |
|---------|---------------|
| Loading | Skeleton screens (tables), spinner (map) |
| Empty state | Helpful message + suggestion |
| Error | Toast for transient, inline for forms |
| Confirmation | Modal for destructive actions |
| Navigation | Top nav (Retailers, Exports, Settings) + breadcrumbs |
| Responsive | Desktop-first (1280px+), tablet functional, mobile read-only |

**Activity 7.4: Component Library** [DECISION]

Choose and document. This goes into CLAUDE.md so every session uses the same components.

### Deliverable

`docs/design/07-ui-ux.md` — screen inventory + screen specs + patterns. Max 400 lines.

### Automation Output

**CLAUDE.md addition:**

```markdown
## Frontend Conventions
- Component library: [choice]
- Routing: [React Router / Next.js App Router]
- State management: [React Query for server state]
- Screen specs: docs/design/07-ui-ux.md
- Desktop-first (1280px+). Tablet functional. Mobile read-only.
- All tables use skeleton loading (6 rows). All async ops show toast feedback.
```

**Skill created**: `.claude/skills/new-component/SKILL.md` — scaffolds a new React component with test file following project patterns.

### Decision Gate

- [ ] Every MVP screen has a structured spec (not just a name)
- [ ] Screens map to API endpoints (data source is explicit)
- [ ] Component library is chosen
- [ ] Loading/error/empty states are defined
- [ ] Map interaction handles 5000+ pins (clustering)

### Who

- **You**: Validate against real workflows
- **Claude Code**: UI designer agent (Opus). Can parallelize: screen specs + map interaction design (2 sessions).

---

## Phase 8: Integration Architecture

### Purpose

Design how the existing retail-store-scraper connects to the new app. This is the bridge.

### Inputs

- `docs/design/04-system-architecture.md` (bridge decision from ADR-010)
- `docs/design/05-data-model.md` (ingestion flow)
- Existing scraper codebase

### Activities

**Activity 8.1: Capability-to-App Mapping**

| App Need | Scraper Capability | Gap | Action |
|----------|-------------------|-----|--------|
| Store data in DB | JSON file output | No DB adapter | Build ingest script |
| On-demand refresh | CLI `run.py --retailer X` | No API trigger | Add scheduler or admin trigger |
| Change detection | `ChangeDetector` class | No DB integration | Pipe changes to store_changes table |
| Data normalization | `store_schema.py` | Already done | Reuse as-is |
| Store validation | `validate_store_data()` | Already done | Reuse as-is |

**Activity 8.2: Scraper Modifications List**

Explicit list of changes to the existing scraper codebase:

1. Add database write adapter (or standalone ingest script)
2. Ensure all scrapers output `scraped_at` timestamp consistently
3. Add run metadata endpoint (or file) the app can consume
4. [Others based on chosen integration pattern]

**Activity 8.3: Scheduling Design** [DECISION]

| Approach | Complexity | Fit |
|----------|-----------|-----|
| Cron + `run.py` | Low | Good for MVP |
| Celery/APScheduler in app | Medium | Good for admin UI triggers |
| GitHub Actions scheduled | Low | Already have GHA infrastructure |

### Deliverable

`docs/design/08-integration.md` — mapping table + modifications list + scheduling design. Max 150 lines.

### Decision Gate

- [ ] Every app data need maps to a scraper capability or identified gap
- [ ] Scraper modification list is explicit
- [ ] Scheduling approach decided
- [ ] Integration does not break existing scraper CLI

### Who

- **You**: Validate that proposed changes are acceptable to existing scraper
- **Claude Code**: Integration architect agent (Opus) — reads the scraper codebase

---

## Phase 9: Infrastructure and Deployment

### Purpose

Choose hosting, define environments, design CI/CD. Optimized for solo operator.

### Inputs

- `docs/design/04-system-architecture.md` (tech stack)
- `docs/design/01-brd.md` (constraints, budget)

### Activities

**Activity 9.1: Hosting Decision** [DECISION] [ADR]

| Option | Cost/mo | PostGIS? | Background Jobs? | Fit |
|--------|---------|----------|-------------------|-----|
| Railway | $5-20 | Plugin | Yes | Good for MVP |
| Render | $7-25 | Yes | Yes (cron) | Good for MVP |
| Fly.io | $5-20 | Yes (volume) | Yes | Good, more control |
| VPS (Hetzner) | $10-20 | Yes (self-managed) | Yes | Cheapest, more ops |

**Activity 9.2: Environment Design**

| Environment | Purpose | How |
|-------------|---------|-----|
| Local | Dev + test | Docker Compose (app + Postgres/PostGIS) |
| Staging | Pre-production | [Hosting platform] preview env |
| Production | Live | [Hosting platform] |

**Activity 9.3: CI/CD Pipeline**

```
Push → Lint (backend + frontend) → Test → Build → Deploy staging (auto) → Deploy prod (manual)
```

**Activity 9.4: Database Migration Strategy**

Tool: [Alembic / Django migrations]. Migrations in git. Applied on deploy. Downgrade path required.

### Deliverable

`docs/design/09-infrastructure.md` — hosting decision + environment table + CI/CD pipeline. Max 150 lines.

### Automation Output

**CLAUDE.md addition:**

```markdown
## Infrastructure
- Hosting: [choice]
- Database: PostgreSQL + PostGIS on [choice]
- CI/CD: GitHub Actions → lint → test → build → deploy
- Local dev: Docker Compose
- Migrations: [Alembic / Django] — always create downgrade

## Common Commands
[app-specific commands added here as they're created]
```

### Decision Gate

- [ ] Hosting platform chosen with cost estimate
- [ ] CI/CD pipeline defined
- [ ] Docker Compose for local dev is planned
- [ ] Monthly cost is within budget constraint

### Who

- **You**: Budget and ops tolerance decisions
- **Claude Code**: DevOps agent (Sonnet — sufficient for this phase)

---

## Phase 10: Security and Operations

### Purpose

Define auth, authorization, monitoring. Non-optional even for MVP.

### Inputs

- `docs/design/04-system-architecture.md`
- `docs/design/06-api-design.md`
- Security Review Checklist from scraper's `CLAUDE.md`

### Activities

**Activity 10.1: Authentication** [DECISION] [ADR]

| Option | Complexity | Cost | Fit |
|--------|-----------|------|-----|
| Clerk | Low | Free tier (5K MAU) | Fast to implement |
| Auth0 | Low | Free tier (7K MAU) | Enterprise-grade |
| Custom (JWT) | Medium | Free | Full control |

**Activity 10.2: Authorization Matrix**

| Role | Stores | Exports | Territories | Admin |
|------|--------|---------|-------------|-------|
| Viewer | Read | Download | View | None |
| Operator | Read | Create + Download | Create + Edit | None |
| Admin | All | All | All | Full |

**Activity 10.3: Monitoring Plan**

| What | How | Alert When |
|------|-----|------------|
| App uptime | Health check endpoint | Down > 1 min |
| API latency | Request logging | p95 > 2s |
| Scraper health | Run metadata | Retailer fails 2x |
| Error rate | Sentry | > 5 errors/hour |

### Deliverable

`docs/design/10-security.md` — auth decision + RBAC matrix + monitoring plan. Max 150 lines.

### Automation Output

**CLAUDE.md addition:**

```markdown
## Security
- Auth: [choice] — see ADR-008
- Roles: viewer, operator, admin (see docs/design/10-security.md)
- API auth: Bearer token on all /api/* endpoints
- Never log tokens, passwords, or API keys
- Use parameterized queries (no string interpolation in SQL)
```

### Decision Gate

- [ ] Auth approach chosen
- [ ] RBAC matrix defined
- [ ] Monitoring plan covers app + scraper + database
- [ ] Security patterns are documented for Claude Code to follow

### Who

- **You**: Security posture decisions
- **Claude Code**: Security architect agent (Opus)

---

## Phase 11: Development Roadmap and Sprint Context Packages

### Purpose

Break MVP into sprints. For each sprint, produce a **self-contained context package** — a single document that a Claude Code session reads to know exactly what to build.

### Inputs

- All Phase 0-10 documents

### Activities

**Activity 11.1: Sprint Breakdown** [DECISION]

| Sprint | Name | Goal | Duration |
|--------|------|------|----------|
| 1 | Foundation | User can register, log in, see retailer list | 1-2 weeks |
| 2 | Store Data | User can browse stores by retailer with filters | 1-2 weeks |
| 3 | Map + Export | User can view stores on map and download CSV/Excel | 1-2 weeks |
| 4 | Changes + Polish | Dashboard, change history, error handling, performance | 1-2 weeks |

**Activity 11.2: Sprint Context Packages**

For each sprint, produce a self-contained context document at `docs/sprints/sprint-NN.md`:

```markdown
# Sprint 1: Foundation

## Goal
User can register, log in, and see a list of retailers with store counts.

## What to Build

### Backend
| Task | File(s) | Tests | Acceptance |
|------|---------|-------|------------|
| Project scaffolding | app/, requirements.txt, Dockerfile | — | App starts on port 8000 |
| Database setup | alembic/, models/ | — | Migrations run cleanly |
| Retailer model + seed | models/retailer.py, seeds/ | test_retailer_model.py | 15 retailers seeded |
| Auth endpoints | api/auth.py | test_auth.py | Register, login, refresh, logout |
| Retailer list endpoint | api/retailers.py | test_retailers.py | GET /api/retailers returns list |

### Frontend
| Task | File(s) | Tests | Acceptance |
|------|---------|-------|------------|
| Project scaffolding | frontend/, package.json | — | App renders at localhost:3000 |
| Auth pages | pages/login, pages/register | — | User can register and log in |
| Retailer list page | pages/retailers | — | Shows retailer cards with counts |
| API client setup | lib/api.ts | — | Typed API client with auth headers |

### Infrastructure
| Task | Acceptance |
|------|------------|
| Docker Compose (app + DB) | `docker-compose up` starts everything |
| CI pipeline (lint + test) | GitHub Actions runs on push |

## API Endpoints This Sprint
[Copy relevant endpoint specs from docs/design/06-api-design.md]

## Database Tables This Sprint
[Copy relevant DDL from docs/design/05-data-model.md]

## Decisions Already Made (Do Not Re-Decide)
- Backend: [FastAPI/Django] (ADR-002)
- Frontend: [React/Next.js] (ADR-003)
- Database: PostgreSQL + PostGIS (ADR-004)
- Auth: [Clerk/Auth0/custom] (ADR-008)

## Definition of Done
- [ ] All tests pass
- [ ] Lint passes (backend + frontend)
- [ ] Docker Compose starts cleanly
- [ ] User can register, log in, see retailer list
- [ ] CI pipeline green
```

**Activity 11.3: Post-MVP Roadmap (high-level)**

| Release | Sprints | Theme | Key Features |
|---------|---------|-------|-------------|
| v0.2 | 5-7 | Territory Basics | MSA builder, radius builder, territory export |
| v0.3 | 8-9 | Drive Time | Isochrone API integration, drive time builder |
| v0.4 | 10-11 | Alerts | Notification config, email/webhook delivery |
| v1.0 | 12+ | Platform | Multi-tenant, team features, advanced analytics |

**Activity 11.4: Technical Risks**

| Risk | Impact | Mitigation |
|------|--------|------------|
| PostGIS complexity | Delays sprint 1 | Start with simple lat/lng, add PostGIS queries later |
| Map performance (50K pins) | Poor UX | Server-side clustering, viewport-based loading |
| Isochrone API cost | Budget in v0.3 | Evaluate free tiers early |
| Scraper breakage during dev | Stale data | Keep scraper running independently |

### Deliverable

`docs/design/11-roadmap.md` — sprint table + risk table. Max 100 lines.
`docs/sprints/sprint-01.md` through `sprint-04.md` — context packages.

### Decision Gate (FINAL — "Ready to Build")

- [ ] All Phase 0-10 documents complete
- [ ] Sprint context packages cover all MVP features
- [ ] Each sprint is self-contained (Claude Code reads one file to start)
- [ ] Tech stack decisions are in CLAUDE.md
- [ ] No unresolved open questions that block Sprint 1
- [ ] Repository structure is decided (same repo / monorepo / separate)

### Who

- **You**: Final review of the entire plan
- **Claude Code**: Technical PM agent (Opus)

---

## Automation Plan

### What Gets Built Alongside the Design

As you progress through phases, the following automation artifacts accumulate in the new app repo:

| Phase | Automation Artifact | Purpose |
|-------|-------------------|---------|
| 0 | CLAUDE.md seed (project overview + glossary) | Every session knows what the app is |
| 1 | CLAUDE.md: requirements reference | Sessions can trace features to requirements |
| 3 | CLAUDE.md: MVP scope statement | Sessions know what's in/out of scope |
| 4 | CLAUDE.md: tech stack table + architecture diagram | Sessions use correct technologies |
| 4 | `.claude/skills/new-sprint/SKILL.md` | Start any sprint with `/new-sprint` |
| 5 | CLAUDE.md: database section | Sessions know the schema |
| 6 | CLAUDE.md: API conventions | Sessions follow consistent API patterns |
| 7 | CLAUDE.md: frontend conventions | Sessions follow consistent UI patterns |
| 7 | `.claude/skills/new-component/SKILL.md` | Scaffold components with `/new-component` |
| 9 | CLAUDE.md: infrastructure + common commands | Sessions can run/deploy the app |
| 10 | CLAUDE.md: security rules | Sessions follow security patterns |
| 11 | `.claude/skills/implement-sprint/SKILL.md` | Full sprint execution workflow |

### CLAUDE.md Progressive Build

By Phase 11, the app's CLAUDE.md should contain:

```markdown
# CLAUDE.md — Store Intelligence Platform

## Project Overview
[From Phase 0]

## MVP Scope
[From Phase 3 — one paragraph]

## Tech Stack
[From Phase 4 — table]

## Architecture
[From Phase 4 — component diagram]

## Database
[From Phase 5 — key tables, migration tool]

## API Conventions
[From Phase 6 — patterns, error format]

## Frontend Conventions
[From Phase 7 — component library, state management, responsive strategy]

## Infrastructure
[From Phase 9 — hosting, CI/CD, common commands]

## Security
[From Phase 10 — auth, roles, rules]

## Common Commands
[From Phase 9 — build, test, deploy, lint]

## Development Workflow
- Read the sprint context package at docs/sprints/sprint-NN.md before starting
- Follow TDD: write tests first, then implement
- Run full test suite before creating PR
- Use /implement-sprint to start a sprint

## Key ADRs
[From Phase 4 — decision index table]

## Domain Glossary
[From Phase 0 — top 10 terms, full glossary linked]
```

### Skills to Create

| Skill | Created In | What It Does |
|-------|-----------|-------------|
| `/new-sprint` | Phase 4 | Reads sprint context package, creates branch, runs setup |
| `/new-component` | Phase 7 | Scaffolds React component + test file + story |
| `/implement-sprint` | Phase 11 | Full TDD sprint execution: read context → write tests → implement → test → PR |
| `/add-endpoint` | Phase 6 | Scaffolds API endpoint + test + route registration |
| `/add-migration` | Phase 5 | Creates Alembic migration from description |

### Hooks to Configure

| Hook | Purpose |
|------|---------|
| PostToolUse:Write (*.py) | Auto-run `python -m py_compile` on edited Python files |
| PostToolUse:Write (*.tsx) | Auto-run TypeScript compiler check on edited files |
| PreCommit | Run lint + type check before commit |

### Custom Agents

| Agent | Purpose |
|-------|---------|
| `sprint-reviewer` | Reviews sprint implementation against context package |
| `api-tester` | Tests API endpoints against specs from 06-api-design.md |
| `data-validator` | Validates ingested store data quality |

---

## Context Loading Strategy

### How Claude Code Sessions Consume These Artifacts

Every Claude Code session for this app should load context in this order:

```
1. CLAUDE.md (auto-loaded — contains tech stack, conventions, commands)
2. Sprint context package (docs/sprints/sprint-NN.md — read at session start)
3. Relevant design docs (linked from sprint package — read on demand)
4. ADRs (read only if making a decision that might conflict)
```

### Context Budget

| Artifact | Target Size | Why |
|----------|-------------|-----|
| CLAUDE.md | < 200 lines | Auto-loaded every session, must be concise |
| Sprint context package | < 500 lines | Primary working document per sprint |
| Design docs (each) | 100-400 lines | Referenced on demand, not loaded in full |
| ADRs (each) | 50-100 lines | Consulted only when relevant |

### Session Startup Prompt Template

```
Read docs/sprints/sprint-NN.md. This is your context package for this sprint.
The CLAUDE.md already has the tech stack and conventions.
Follow TDD: write tests first, then implement.
Start with the first unchecked task in the sprint package.
```

---

## How to Start

1. Create the directory structure:
   ```bash
   mkdir -p docs/design/decisions docs/sprints
   ```

2. Start Phase 0:
   ```
   Read docs/process/app-design-process.md, Phase 0.
   Interview me about the business and produce docs/design/00-business-context.md.
   Start with: "Tell me about your business model — who pays, for what, and how."
   ```

3. Follow each phase sequentially. At each decision gate, check every box before advancing.

4. After Phase 11, all sprint context packages exist. Start building:
   ```
   Read docs/sprints/sprint-01.md. Follow TDD. Start with the first task.
   ```

---

## Document Templates

### ADR Template

```markdown
# ADR-NNN: [Title]
**Status**: Proposed | Accepted | Superseded
**Date**: YYYY-MM-DD

## Context
[Why this decision is needed — 2-3 sentences]

## Decision
[What was decided — 1-2 sentences]

## Options Considered
| Option | Pros | Cons |
|--------|------|------|
| A | ... | ... |
| B | ... | ... |

## Consequences
- Positive: [what improves]
- Negative: [what trade-offs accepted]
```

### Decision Log (`docs/design/decisions/DECISION-LOG.md`)

```markdown
| Date | ID | Decision | Choice | Rationale | ADR |
|------|-----|----------|--------|-----------|-----|
| 2026-02-06 | D-001 | Architecture pattern | SPA+API | Rich map interactions needed | ADR-001 |
```

### Feature Spec Template

```markdown
### F-XXX: [Name]
**Release**: MVP | **Priority**: Must | **Persona**: [who]
**Traces to**: FR-XXX

**Behavior**: [what it does]
**Acceptance Criteria**:
- [ ] [testable criterion]
**Data**: [API endpoint or data source]
```

---

## Agent Mapping by Phase

| Phase | Agent Type | Model | Focus |
|-------|-----------|-------|-------|
| 0 | voltagent-meta:knowledge-synthesizer | Opus | Domain knowledge organization |
| 1 | voltagent-biz:business-analyst | Opus | Requirements structuring |
| 2 | voltagent-biz:ux-researcher | Opus | Persona and journey design |
| 3 | voltagent-biz:product-manager | Opus | Feature scoping and prioritization |
| 4 | voltagent-core-dev:fullstack-developer | Opus | Architecture and tech stack |
| 4 | voltagent-data-ai:postgres-pro | Opus | PostGIS and spatial evaluation (parallel) |
| 5 | voltagent-data-ai:postgres-pro | Opus | Schema design |
| 6 | voltagent-core-dev:api-designer | Opus | Endpoint specification |
| 7 | voltagent-core-dev:ui-designer | Opus | Screen specs and interaction patterns |
| 8 | voltagent-core-dev:fullstack-developer | Opus | Scraper-to-app integration |
| 9 | voltagent-infra:devops-engineer | Sonnet | Hosting, CI/CD |
| 10 | voltagent-infra:security-engineer | Opus | Auth, RBAC, monitoring |
| 11 | voltagent-biz:project-manager | Opus | Sprint planning |

### Parallelization Opportunities

| Phase | What Can Run in Parallel | Sessions |
|-------|------------------------|----------|
| Phase 4 | Architecture eval + GIS tech eval + DB eval | 3 |
| Phase 7 | Screen specs + Map interaction design | 2 |
| Sprints | Backend tasks + Frontend tasks (within a sprint) | 2 |

---

*End of process document.*
