# Scale Roadmap: 50-100 Retailers

**Date:** 2026-02-09
**Target:** Support 50-100 retailer scrapers on a single machine with concurrent execution.
**Constraint:** All changes must preserve a clean `src/core/` API layer so a future frontend (web UI, REST API, or TUI) can drive the system without going through the CLI.

---

## Architecture Principle: Core API Separation

Before any feature work, extract business logic from `run.py` (1,075 lines) into a `src/core/` module. The CLI becomes a thin shell. This is not a separate phase — it's the *shape* of all implementation.

```
src/core/                          # Pure Python API — no CLI, no I/O assumptions
├── orchestrator.py                # run_retailer(), run_group(), run_all()
├── registry.py                    # Auto-discovery, get_retailers(), get_groups()
├── status.py                      # get_status(), get_health(), query_ledger()
├── scaffold.py                    # generate_scraper(), list_templates()
└── validator.py                   # validate_retailer(), smoke_test()

run.py                             # Thin CLI shell — parses args, calls src/core/*
```

Any consumer (CLI, REST API, web UI) imports from `src/core/` and gets identical behavior. No business logic in the presentation layer.

---

## Phase 1: Foundation

**Goal:** Make the codebase structurally ready for 50+ scrapers. Every subsequent phase depends on this.

### 1.1 Extract Core API from run.py

Split `run.py` into `src/core/orchestrator.py` (execution logic), `src/core/registry.py` (retailer lookup), and a thin CLI wrapper. The `run.py` file should shrink to ~200 lines of argparse + calls to `src/core/`.

**Acceptance criteria:**
- `from src.core.orchestrator import run_retailer` works from Python
- `run.py` contains zero business logic
- All existing CLI flags work identically

### 1.2 Auto-Discovery Scraper Registry

Replace the hardcoded `SCRAPER_REGISTRY` dict in `src/scrapers/__init__.py` with convention-based auto-discovery.

**Rules:**
- Any `src/scrapers/*.py` file containing a `run()` function (or a `BaseScraper` subclass) is auto-registered
- Filename becomes retailer key: `walgreens.py` → `walgreens`
- Files starting with `_` are skipped (helpers, base classes)
- `retailers.yaml` `enabled: false` still respected
- Warn on startup if a scraper module fails to load (don't crash)

**Acceptance criteria:**
- Adding a new scraper requires zero edits to `__init__.py`
- Existing 15 scrapers work without modification
- `get_available_retailers()` returns dynamically discovered list

### 1.3 Base Scraper Classes

Introduce base classes that encode common patterns. Place in `src/scrapers/_base.py` (underscore prefix = skipped by auto-discovery).

```
BaseScraper                        # Lifecycle: setup → discover → extract → normalize
├── SitemapScraper                 # XML/gzipped sitemap discovery
├── ApiScraper                     # Paginated JSON API endpoints
├── GraphQLScraper                 # GraphQL query patterns
├── HtmlCrawlScraper               # Multi-phase HTML crawling
└── StoreLocatorApiScraper         # Geo-radius store locator APIs
```

`BaseScraper` handles:
- Session setup with proxy configuration
- Checkpoint save/load
- Delay enforcement (direct vs proxied profiles)
- Concurrency slot acquisition
- Progress logging
- Store validation and normalization
- The `run()` entry point (calls `discover_urls()` then `extract_store()`)

Subclasses override:
- `discover_urls() → list[str]` — find store URLs/identifiers
- `extract_store(url) → dict` — parse a single store page/response

**Migration:** Existing scrapers keep their current `run()` function. Both patterns (function-based and class-based) work with auto-discovery. Migration is incremental, not big-bang.

**Acceptance criteria:**
- At least 2 existing scrapers migrated to base classes as proof-of-concept
- New scrapers can be written in ~30 lines using a base class
- Old-style `run()` function scrapers still work

---

## Phase 2: Groups, Testing & Onboarding

**Goal:** Make adding a new retailer a 15-minute task with confidence it works correctly.

### 2.1 Retailer Groups

Add a `groups` taxonomy in `retailers.yaml`:

```yaml
groups:
  wireless:       [verizon, att, tmobile, cricket]
  home-improvement: [homedepot, lowes]
  warehouse-club: [costco, samsclub]
  department-store: [target, walmart]
  specialty:      [bestbuy, staples, apple, gamestop]
  canadian:       [telus, bell]
```

CLI additions:
```bash
python run.py --group wireless              # Run a group
python run.py --group wireless,canadian     # Multiple groups
python run.py --group wireless --exclude cricket  # Group minus specific
```

A retailer can belong to multiple groups. Warn if a scraper exists but isn't in any group.

**Acceptance criteria:**
- `--group` flag works with all existing flags (`--test`, `--proxy`, `--resume`, etc.)
- All 15 current scrapers assigned to at least one group
- `src/core/registry.py` exposes `get_groups()`, `get_retailers_in_group()`

### 2.2 Fixture-Driven Test Harness

Standardize scraper tests with fixture directories:

```
tests/test_scrapers/fixtures/{retailer}/
├── sitemap.xml (or api_response.json, graphql_response.json, etc.)
├── store_page.html (or store_detail.json)
└── expected_stores.json
```

A shared `conftest.py` auto-generates parametrized tests for any scraper that has fixtures:
- Discovery test (mocked HTTP → correct URL list)
- Extraction test (mocked page → correct store dict)
- Normalization test (required fields present, coordinates valid)
- Checkpoint round-trip test (save → load → same state)
- Field completeness test (recommended fields coverage %)

**Acceptance criteria:**
- Dropping fixture files for a new scraper produces 5 passing tests
- At least 5 existing scrapers have fixtures migrated
- `pytest tests/test_scrapers/ -k walgreens` works with only fixtures

### 2.3 Live Validation Mode

A `--validate` CLI flag that runs a scraper with `--limit 3` against the real site and checks:
- Got at least 1 store back
- Required fields present on all stores
- Coordinates within valid bounds (if present)
- No HTTP 4xx/5xx errors

```bash
python run.py --retailer walgreens --validate
python run.py --group wireless --validate
```

**Acceptance criteria:**
- Validate passes for all 15 current scrapers
- Clear pass/fail output with specific failure reasons
- `src/core/validator.py` exposes `validate_retailer()` for programmatic use

### 2.4 Scraper Scaffolding

A `--scaffold` command that generates a working scraper skeleton:

```bash
python run.py --scaffold walgreens --type sitemap
```

Generates:
- `src/scrapers/walgreens.py` — base class subclass with TODOs and inline guidance
- `config/walgreens_config.py` — config skeleton
- `tests/test_scrapers/fixtures/walgreens/` — empty fixture directory

Template types: `sitemap`, `api`, `graphql`, `html`, `locator` (matching base class hierarchy).

**Acceptance criteria:**
- Scaffolded scraper is immediately discoverable by auto-registry
- Running `--validate` on a scaffolded scraper gives clear "TODO not implemented" errors (not crashes)
- Each template includes comments pointing to a working example of the same type

---

## Phase 3: Observability

**Goal:** Know the health of 75 scrapers at a glance without reading log files.

### 3.1 Run Ledger

Every scraper run appends an entry to `data/.runs/ledger.jsonl` (JSON Lines, one entry per run):

```json
{
  "retailer": "verizon",
  "timestamp": "2026-02-09T14:30:00Z",
  "duration_seconds": 142,
  "stores_found": 1847,
  "stores_changed": 3,
  "stores_new": 1,
  "stores_closed": 0,
  "errors": 0,
  "proxy_mode": "residential",
  "status": "success"
}
```

**Acceptance criteria:**
- Ledger written atomically (no partial entries on crash)
- `src/core/status.py` exposes `query_ledger(retailer=None, since=None, limit=None)`
- Backward compatible — existing `runs/` metadata still works

### 3.2 Enhanced Status Dashboard

`--status` reads the ledger and presents a summary table:

```
Retailer       Group           Last Run    Stores  Changes  Health
──────────────────────────────────────────────────────────────────
verizon        wireless        2h ago      1,847   +1/-0    ✓ OK
att            wireless        2h ago      5,312   +3/-2    ✓ OK
walmart        dept-store      3d ago      4,706   0        ⚠ STALE
gamestop       specialty       never       —       —        — NEW
```

Health rules (configurable in `retailers.yaml`):
- **stale**: No successful run in X days (default: 7)
- **degraded**: Store count dropped >10% from previous run
- **failing**: Last N runs had errors (default: N=3)

```bash
python run.py --status                      # All retailers
python run.py --status --group wireless     # Group filter
python run.py --status --format json        # Machine-readable (for CI, future frontend)
```

**Acceptance criteria:**
- `--status --format json` output is stable and documented (future frontend contract)
- Existing GitHub Actions health check (#233) can consume `--status --format json`
- `src/core/status.py` exposes `get_status()`, `get_health()` for programmatic use

---

## Phase Summary

| Phase | Sections | Key Deliverable | Dependency |
|-------|----------|-----------------|------------|
| **1: Foundation** | Core API, Auto-Discovery, Base Classes | Codebase ready for scale | None |
| **2: Groups & Testing** | Groups, Test Harness, Validation, Scaffold | 15-minute retailer onboarding | Phase 1 |
| **3: Observability** | Run Ledger, Status Dashboard | Operational visibility at scale | Phase 1 |

Phases 2 and 3 are independent of each other and can be worked in parallel after Phase 1 completes. Within each phase, sections can be implemented as separate PRs.

---

## Out of Scope (Future)

- **Frontend (web UI, TUI, REST API)**: Not designed here, but `src/core/` API is the integration point. Every feature above exposes a programmatic API suitable for a future frontend.
- **Distributed execution**: Single-machine concurrent model is sufficient for 50-100 scrapers. Revisit if scrapers exceed 200 or execution time exceeds acceptable windows.
- **Scraper marketplace / plugin system**: At 100+ with external contributors, consider a plugin architecture. Current base-class pattern is sufficient for internal scaling.
