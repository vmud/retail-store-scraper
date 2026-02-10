# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-retailer web scraper that collects retail store locations from 15 US/Canadian retailers (Verizon, AT&T, Target, T-Mobile, Walmart, Best Buy, Telus, Cricket, Bell, Home Depot, Staples, Apple, Costco, Sam's Club, Lowe's). Features concurrent execution, change detection, checkpoint/resume, and Oxylabs proxy integration.

## Environment Setup

Requires Python 3.9-3.14.

```bash
# Recommended: automated setup with diagnostics and auto-fix
python scripts/setup.py

# Or manual:
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pre-commit install
```

## Commands

```bash
# Run scrapers
python run.py --retailer verizon           # Single retailer
python run.py --all                        # All retailers concurrently
python run.py --all --test                 # Test mode (10 stores each)
python run.py --all --resume               # Resume from checkpoints
python run.py --all --proxy residential    # With Oxylabs proxy
python run.py --status                     # Check status without running

# Testing
pytest tests/                              # All tests
pytest tests/test_scrapers/test_verizon.py # Single scraper test
pytest tests/ --cov=src --cov-report=html  # With coverage

# Linting (matches CI)
pylint $(git ls-files '*.py')

# Pre-commit hooks
pre-commit run --all-files
```

Key CLI flags: `--limit N`, `--format json,csv,excel`, `--incremental`, `--exclude retailer1 retailer2`, `--states MD,PA` (Verizon only), `--cloud` (GCS sync), `--refresh-urls`.

## Architecture

### Request Flow

`run.py` parses CLI args → loads `config/retailers.yaml` → for each retailer, dynamically imports from `src/scrapers/` via `SCRAPER_REGISTRY` in `__init__.py` → scraper uses `src/shared/` utilities for HTTP, delays, caching, concurrency → results exported to `data/{retailer}/output/` → change detector compares against previous run.

### Scraper Contract

Every scraper implements a `run()` function:
```python
def run(session, retailer_config, retailer: str, **kwargs) -> dict:
    # Returns: {'stores': [...], 'count': int, 'checkpoints_used': bool}
```

Each scraper uses a different discovery strategy (sitemaps, APIs, HTML crawling, GraphQL) but outputs a uniform store dict. Store data validated via `validate_store_data()` from `src/shared/utils.py`. Required fields: `store_id`, `name`, `street_address`, `city`, `state`.

### Key Modules in src/shared/

27 modules (split from a monolithic `utils.py`). The most important to understand:

- **constants.py** — All magic numbers as frozen dataclasses (`HTTP`, `CACHE`, `PAUSE`, `WORKERS`, `VALIDATION`). Import these instead of hardcoding values.
- **concurrency.py** — `GlobalConcurrencyManager` singleton coordinates worker slots across all scrapers. Configured in `retailers.yaml` under `concurrency:`.
- **proxy_client.py** — Oxylabs abstraction (`ProxyMode`, `ProxyClient`). Modes: `direct`, `residential`, `web_scraper_api`.
- **store_schema.py** — Central store data model. All scrapers normalize to this schema.
- **scrape_runner.py** — Shared orchestration patterns (discovery → extraction → export pipeline).
- **export_service.py** — Multi-format export (JSON, CSV, Excel, GeoJSON).
- **cloud_storage.py** — GCS sync for backup. See `.env.example` for `GCS_*` vars.
- **validation.py** — Store data validation. Required fields: `store_id`, `name`, `street_address`, `city`, `state`.
- **cache_interface.py** — Unified caching with consistent TTL (replaces legacy `cache.py`).
- **sentry_integration.py** — Sentry.io error monitoring with retailer-specific context.

Other modules (`http.py`, `delays.py`, `checkpoint.py`, `io.py`, `session_factory.py`, `store_serializer.py`, `scraper_utils.py`, `structured_logging.py`, `logging_config.py`, `notifications.py`, `request_counter.py`, `run_tracker.py`, `scraper_manager.py`, `status.py`) are smaller utilities discoverable by reading imports. Legacy aliases in `utils.py` preserve backward compatibility.

### Configuration

- `config/retailers.yaml` — Central config: per-retailer delays, proxy settings, concurrency limits, output fields, `enabled` flag
- `config/{retailer}_config.py` — Per-retailer Python configs (URLs, parsing selectors, field mappings)
- `.env` / `.env.example` — Secrets: Oxylabs credentials, GCS service account

Retailers can define dual delay profiles (direct vs proxied) in `retailers.yaml`. Set `enabled: false` to disable a retailer from `--all`.

### Output Structure

```
data/{retailer}/
├── output/stores_latest.json      # Current run
├── output/stores_previous.json    # Previous run (for change detection)
├── checkpoints/                   # Resumable state
└── history/                       # Change reports
```

## Adding a New Retailer

1. Create `src/scrapers/{retailer}.py` — implement `run()` per the contract above
2. Create `config/{retailer}_config.py` — URLs, selectors, field mappings
3. Register in `src/scrapers/__init__.py` → `SCRAPER_REGISTRY`
4. Add config block in `config/retailers.yaml` — delays, output fields, proxy mode
5. Create `tests/test_scrapers/test_{retailer}.py` — unit tests with mocked HTTP

Use `/add-retailer` skill for guided assistance.

## Code Style

- **Docstrings**: Google style (`Args:`, `Returns:`, `Raises:`)
- **Max line length**: 120 chars (pylint)
- **Type hints**: All public functions should have type annotations

## Security Rules (Project-Specific)

These are enforced by pre-commit hooks (bandit, detect-secrets, safety, custom import checker):

- **XML**: Use `defusedxml`, never `xml.etree` (enforced by `scripts/check_unsafe_imports.py`)
- **Serialization**: Use `json`, never `pickle` or `marshal`
- **No `eval()`/`exec()`/`os.system()`** in production code
- **Secrets**: Environment variables only, update `.env.example` when adding new ones
- **Dependencies**: Pin versions in `requirements.txt`
- **Secret detection baseline**: `.secrets.baseline` — use `pragma: allowlist secret` for false positives in docs

## CI / GitHub Actions

- **claude-code-action** (PR reviews): Uses `anthropic_api_key` from 1Password (not OAuth tokens). Debug with `show_full_output: true`. Rerun: `gh pr update-branch <number>`.
- **1Password integration**: `1password/load-secrets-action@v2` loads secrets. See `docs/1password-github-actions.md`.

## Multi-Agent Development

See `.claude/rules/devops-workflow.md` (auto-loaded) for full rules. Quick reference:

- **Worktree isolation**: `git worktree add ../retail-store-scraper--{branch} -b {type}/{agent}-{task}`
- **Agent IDs in commits**: `Agent: cc1` (or `cc2`, `cursor`, `copilot`, etc.)
- **High-conflict files**: `run.py`, `config/retailers.yaml`, `CLAUDE.md`, `requirements.txt`

## Scale Roadmap

The project is scaling from 15 to 50-100 retailers. See [`docs/plans/2026-02-09-scale-roadmap.md`](docs/plans/2026-02-09-scale-roadmap.md) for the full plan. Track progress via GitHub issues labeled `roadmap`.

**Key architectural rule (target state):** All business logic will move to `src/core/` (pure Python API). The CLI (`run.py`, currently 1,075 lines) and any future frontend become thin presentation layers. `src/core/` does not exist yet — Phase 1 creates it.

**Phases:**
1. **Foundation** — Extract `src/core/` from `run.py`, auto-discovery registry, base scraper classes
2. **Groups & Testing** — Retailer groups (`--group wireless`), fixture-driven tests, `--validate`, `--scaffold`
3. **Observability** — Run ledger, enhanced `--status` with health rules

## Behavioral Guidelines

- Focus narrowly on the specific task before broadening exploration. Front-load actionable steps.
- When implementing features, create modules with corresponding test files.
- For setup/config tasks, verify with a test command before considering complete.
- For code reviews, use structured checklists. Reply to PR comment threads via `gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`.
