# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-retailer web scraper that collects retail store locations from Verizon, AT&T, Target, T-Mobile, Walmart, Best Buy, Telus, Cricket, and Bell. Features concurrent execution, change detection, checkpoint/resume system, and optional Oxylabs proxy integration.

## Environment Setup

Requires Python 3.9-3.14. Use the self-healing setup script for automated environment configuration:
```bash
# Recommended: automated setup with diagnostics and auto-fix
python scripts/setup.py

# Or manual setup:
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Use `/project-setup` skill in Claude Code for guided setup assistance.

## Common Commands

```bash
# Run single retailer
python run.py --retailer verizon

# Run all retailers concurrently
python run.py --all

# Run with resume from checkpoints
python run.py --all --resume

# Test mode (10 stores per retailer)
python run.py --all --test

# Limit stores per retailer
python run.py --retailer target --limit 100

# Check status without running
python run.py --status

# Run with Oxylabs proxy
python run.py --all --proxy residential

# Validate proxy credentials before running
python run.py --all --proxy residential --validate-proxy

# Export in multiple formats
python run.py --retailer target --format json,csv,excel

# Incremental mode (only new/changed stores)
python run.py --all --incremental

# Targeted state scraping (Verizon only)
python run.py --retailer verizon --states MD,PA,RI

# Force URL re-discovery
python run.py --retailer verizon --refresh-urls

# Exclude specific retailers
python run.py --all --exclude bestbuy att

# Web Scraper API with JS rendering
python run.py --retailer walmart --proxy web_scraper_api --render-js

# Geo-targeted proxy
python run.py --retailer target --proxy residential --proxy-country ca

# Cloud storage sync to GCS
python run.py --retailer verizon --cloud

# Cloud sync for all retailers
python run.py --all --cloud

# Cloud with custom bucket
python run.py --all --cloud --gcs-bucket my-backup-bucket

# Cloud with timestamped history copies
python run.py --retailer target --cloud --gcs-history

# Disable cloud (overrides env/config)
python run.py --all --no-cloud
```

### Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_change_detector.py

# Run scraper unit tests
pytest tests/test_scrapers/

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Linting

```bash
# Lint all Python files (matches CI)
pylint $(git ls-files '*.py')
```

### Docker

```bash
# Build and run
docker-compose up -d

# Run specific retailer
docker-compose run scraper python run.py --retailer verizon

# View logs
docker-compose logs -f scraper
```

## Architecture

```
run.py                          # Main CLI entry point - handles arg parsing, concurrent execution
├── src/scrapers/               # Retailer-specific scrapers
│   ├── __init__.py             # Scraper registry & dynamic loader
│   ├── verizon.py              # 4-phase HTML crawl
│   ├── att.py                  # XML sitemap
│   ├── target.py               # Gzipped sitemap + API
│   ├── tmobile.py              # Paginated sitemaps
│   ├── walmart.py              # Multiple gzipped sitemaps
│   ├── bestbuy.py              # XML sitemap
│   ├── telus.py                # Uberall API (Canadian)
│   ├── cricket.py              # Yext API (US)
│   └── bell.py                 # Sitemap + JSON-LD (Canadian)
├── src/shared/
│   ├── utils.py                # HTTP helpers, checkpoints, delays, store validation
│   ├── constants.py            # Centralized magic numbers (HTTP, CACHE, PAUSE, WORKERS, etc.) (#171)
│   ├── concurrency.py          # Global concurrency and rate limit management (#153)
│   ├── cache.py                # URL caching (URLCache, RichURLCache) - legacy
│   ├── cache_interface.py      # Unified caching interface with consistent TTL (#154)
│   ├── session_factory.py      # Thread-safe session creation for parallel workers
│   ├── proxy_client.py         # Oxylabs proxy abstraction (ProxyMode, ProxyClient)
│   ├── export_service.py       # Multi-format export (JSON, CSV, Excel, GeoJSON)
│   ├── request_counter.py      # Rate limiting tracker
│   ├── status.py               # Progress reporting (interface for future UI)
│   ├── notifications.py        # Pluggable notification system (Slack, console)
│   ├── cloud_storage.py        # GCS integration for backup/sync
│   ├── run_tracker.py          # Run metadata and state tracking
│   └── scraper_manager.py      # Process lifecycle management
├── src/setup/                  # Self-healing project setup
│   ├── probe.py                # Environment probing (Python, venv, packages, etc.)
│   ├── fix.py                  # Idempotent auto-fix functions
│   ├── verify.py               # Test suite verification
│   └── runner.py               # Main orchestration with checkpoints
├── src/change_detector.py      # Detects new/closed/modified stores between runs
└── config/
    ├── retailers.yaml          # Global config: proxy settings, per-retailer overrides
    └── *_config.py             # Per-retailer Python configs
```

### Scraper Interface

All scrapers implement a `run()` function with this signature:
```python
def run(session, retailer_config, retailer: str, **kwargs) -> dict:
    # Returns: {'stores': [...], 'count': int, 'checkpoints_used': bool}
```

### Key Defaults (from constants.py - Issue #171)

Magic numbers are centralized in `src/shared/constants.py` as frozen dataclasses:
- `HTTP.MIN_DELAY = 2.0` / `HTTP.MAX_DELAY = 5.0` - delay between requests
- `HTTP.MAX_RETRIES = 3` - HTTP retry attempts
- `HTTP.TIMEOUT = 30` - request timeout in seconds
- `HTTP.RATE_LIMIT_BASE_WAIT = 30` - wait time on 429 errors
- `PAUSE.SHORT_THRESHOLD = 50` / `PAUSE.LONG_THRESHOLD = 200` - rate-limiting pauses
- `CACHE.URL_CACHE_EXPIRY_DAYS = 7` - URL cache expiry
- `WORKERS.PROXIED_WORKERS = 5` / `WORKERS.DIRECT_WORKERS = 1` - parallel workers
- `EXPORT.FIELD_SAMPLE_SIZE = 100` - export field discovery
- `TEST_MODE.STORE_LIMIT = 10` - test mode store limit
- `VALIDATION.*` - coordinate and ZIP validation bounds

See `src/shared/constants.py` for complete list. Backward-compatible aliases exist in `utils.py` for legacy code.

### Dual Delay Profiles

Retailers can define separate delay profiles for direct and proxied requests in `config/retailers.yaml`:
```yaml
delays:
  direct:      # Conservative (no proxy)
    min_delay: 2.0
    max_delay: 5.0
  proxied:     # Aggressive (with proxy)
    min_delay: 0.2
    max_delay: 0.5
```
- Provides 5-7x speedup when using residential proxies
- Automatically selects appropriate delays based on proxy mode
- Falls back to direct delays when no proxy is configured

### Performance Features

- **Parallel workers**: Configure `discovery_workers` and `parallel_workers` in retailers.yaml for concurrent request handling
- **URL caching**: 7-day cache for discovered store URLs (reduces repeat work on subsequent runs)
- **Verizon optimization**: 9.6x speedup with parallel discovery + extraction using proxies

## Key Patterns

### Adding a New Retailer

1. Create `src/scrapers/newretailer.py` - implement scraper class
2. Create `config/newretailer_config.py` - retailer-specific settings
3. Register in `src/scrapers/__init__.py` - add to scraper registry
4. Add config block to `config/retailers.yaml` - sitemap URLs, delays, output fields

### Enabling/Disabling Retailers

Set `enabled: false` in `config/retailers.yaml` to disable a retailer:
```yaml
retailers:
  bestbuy:
    enabled: false  # Won't appear in CLI choices or --all
```

The CLI uses `get_enabled_retailers()` which respects this setting.

### Concurrency Configuration

Global concurrency limits prevent CPU oversubscription when multiple retailers run concurrently (Issue #153).

**Configuration in `config/retailers.yaml`:**
```yaml
concurrency:
  # Maximum concurrent workers across ALL retailers
  global_max_workers: 10

  # Per-retailer worker limits (overrides default if specified)
  per_retailer_max:
    verizon: 7      # High parallelism with proxy
    target: 5       # API-based, can handle more
    walmart: 3      # JS rendering is resource-heavy
    bell: 1         # Respects crawl-delay: 10

  # Proxy rate limiting (requests per second)
  proxy_rate_limit: 10.0
```

**How it works:**
- `GlobalConcurrencyManager` is a thread-safe singleton that coordinates all scrapers
- Each request acquires both a global slot and a retailer-specific slot
- Prevents resource exhaustion when running `--all` with many parallel workers
- Automatically loaded from `retailers.yaml` at startup

**Usage in scrapers:**
```python
from src.shared.concurrency import GlobalConcurrencyManager

manager = GlobalConcurrencyManager()
with manager.acquire_slot('verizon'):
    # Make request within concurrency limits
    response = session.get(url)
```

### Proxy Configuration

Proxies configured via environment variables (see `.env.example`):
- `OXYLABS_RESIDENTIAL_USERNAME/PASSWORD` - for residential proxy mode
- `OXYLABS_SCRAPER_API_USERNAME/PASSWORD` - for Web Scraper API mode
- `OXYLABS_USERNAME/PASSWORD` - fallback for both modes

Proxy modes in `config/retailers.yaml`:
- `direct` - no proxy (default, 2-5s delays)
- `residential` - rotating residential IPs (0.2-0.5s delays, 9.6x faster)
- `web_scraper_api` - managed service with JS rendering

### 1Password for GitHub Actions

GitHub Actions can securely access secrets from 1Password using a service account.

**Setup:**
1. Create 1Password Service Account with vault access
2. Store token as GitHub Secret: `OP_SERVICE_ACCOUNT_TOKEN`  <!-- pragma: allowlist secret -->
3. Use `1password/load-secrets-action@v2` in workflows

**Usage in workflows:**
```yaml
- name: Load secrets from 1Password
  uses: 1password/load-secrets-action@v2
  with:
    export-env: true
  env:
    OP_SERVICE_ACCOUNT_TOKEN: ${{ secrets.OP_SERVICE_ACCOUNT_TOKEN }}
    OXYLABS_RESIDENTIAL_USERNAME: op://DEV/OXYLABS_RESIDENTIAL/username
    OXYLABS_RESIDENTIAL_PASSWORD: op://DEV/OXYLABS_RESIDENTIAL/credential
```

See [docs/1password-github-actions.md](docs/1password-github-actions.md) for full documentation.

### Claude Code Action (PR Reviews)

The `claude-code-action` workflow uses Anthropic API keys loaded from 1Password:
- **Use `anthropic_api_key`** - OAuth tokens (`claude setup-token`) have validation issues in CI
- **Debug with `show_full_output: true`** - reveals actual error messages instead of generic failures
- **Trigger CI reruns**: `gh pr update-branch <number>` or `gh run rerun <run-id>`
- **Required permissions**: `pull-requests: write` for posting review comments

### Cloud Storage (GCS)

Sync scraped data to Google Cloud Storage for backup and team access.

**Environment variables** (see `.env.example`):
- `GCS_SERVICE_ACCOUNT_KEY` - path to service account JSON file
- `GCS_BUCKET_NAME` - GCS bucket name
- `GCS_PROJECT_ID` - GCP project ID (optional, auto-detected)
- `GCS_ENABLE_HISTORY` - enable timestamped history copies

**YAML config** in `config/retailers.yaml`:
```yaml
cloud_storage:
  enabled: true        # or use --cloud CLI flag
  max_retries: 3
  retry_delay: 2.0
  enable_history: false
```

**GCS bucket structure**:
```
gs://{bucket}/
├── verizon/stores_latest.json    # Overwritten each run (versioned by GCS)
├── verizon/stores_latest.csv
├── att/stores_latest.json
└── history/                      # Optional (--gcs-history)
    └── verizon/stores_2026-01-26_143022.json
```

**Setup**:
1. Create GCS bucket with object versioning enabled
2. Create service account with `Storage Object Admin` role
3. Download service account key JSON
4. Set `GCS_SERVICE_ACCOUNT_KEY` and `GCS_BUCKET_NAME` in `.env`

### Output Structure

Data stored in `data/{retailer}/`:
- `output/stores_latest.json` - current run
- `output/stores_previous.json` - previous run (for change detection)
- `checkpoints/` - resumable state
- `history/changes_{retailer}_YYYY-MM-DD_HH-MM-SS-ffffff.json` - change reports

Additional output directories:
- `runs/{run_id}.json` - run metadata tracking
- `logs/{run_id}.log` - per-run log files

### Anti-Blocking

Configurable in `config/retailers.yaml`:
- `min_delay/max_delay` - random delays between requests
- `pause_50_requests/pause_200_requests` - longer pauses at thresholds
- User-agent rotation in `src/shared/utils.py` (DEFAULT_USER_AGENTS)

### Store Data Validation

Use `validate_store_data()` from `src/shared/utils.py` to validate scraped data:
```python
from src.shared.utils import validate_store_data, validate_stores_batch

result = validate_store_data(store)  # Returns ValidationResult
summary = validate_stores_batch(stores)  # Returns summary dict
```

Required fields: `store_id`, `name`, `street_address`, `city`, `state`
Recommended fields: `latitude`, `longitude`, `phone`, `url`

## Test Structure

```
tests/
├── test_scrapers/           # Unit tests for individual scrapers
│   ├── test_target.py
│   ├── test_att.py
│   ├── test_verizon.py
│   ├── test_tmobile.py
│   ├── test_walmart.py
│   ├── test_bestbuy.py
│   ├── test_cricket.py
│   └── test_bell.py
├── test_setup/              # Setup module tests
│   ├── test_probe.py        # Environment probing tests
│   ├── test_fix.py          # Auto-fix function tests
│   └── test_runner.py       # Orchestration tests
├── test_change_detector.py  # Change detection tests
├── test_proxy_client.py     # Proxy integration tests
├── test_export_service.py   # Export format tests
├── test_cache_interface.py  # Cache interface tests (#154)
└── uat/                     # User Acceptance Testing framework
    ├── protocol.py          # UAT test protocol
    ├── helpers.py           # Test utilities
    ├── report.py            # Test reporting
    └── suites/              # Test suites by feature
        ├── config.py, control.py, error.py
        ├── history.py, init.py, logs.py, perf.py
        └── proxy.py, status.py
```

## Multi-Agent Development

This repository supports parallel development by multiple AI agents. See `.claude/rules/devops-workflow.md` for comprehensive multi-agent workflow rules.

**Quick Reference:**
- Use git worktrees for isolation: `git worktree add ../retail-store-scraper--{branch} -b {type}/{agent}-{task}`
- Agent IDs: `cc1`, `cc2` (Claude Code), `cursor`, `copilot`, `gemini`, `aider`, `human`
- Include agent ID in commits: `Agent: cc1`
- High-conflict files (coordinate before editing): `run.py`, `config/retailers.yaml`, `CLAUDE.md`, `requirements.txt`

### Custom Agents (.claude/agents/)

**PR lifecycle agents** — orchestrated by pr-coordinator:
- `pr-coordinator` (opus) — triages open PRs and spawns sub-agents
- `pr-reviewer` (opus) — code review with project security checklist enforcement
- `ci-monitor` (sonnet) — diagnoses CI failures (pytest, pylint, bandit, etc.)
- `comment-resolver` (sonnet) — implements reviewer feedback and resolves threads
- `conflict-resolver` (opus) — three-way merge analysis and resolution
- `rebase-manager` (sonnet) — branch sync with force-push safety (requires user confirmation)

**Project-specific agents:**
- `data-quality-reviewer` — validates scraped store data before GCS sync
- `scraper-validator` — checks scraper implementations against project patterns
- `proxy-tester` — tests Oxylabs proxy configuration

## Deployment

Deployment tools in `deploy/`:
- `rsync-deploy.sh` - production deployment via rsync
- `validate.sh` - deployment validation checks
- `diagnose-network.sh` - network troubleshooting utilities

## Session Scope

When asked to explore or set up something, focus narrowly on the specific task before broadening exploration. Do not spend a session exploring the codebase without taking concrete action toward the goal. Front-load actionable steps — complete at least one deliverable before doing broad discovery.

## Implementation Standards

When implementing features from design plans, create all modules with corresponding test files and ensure CLI is functional before marking complete.

## Setup & Configuration

For configuration/setup tasks (MCP, credentials, integrations), always verify the setup works with a simple test command before considering the task complete.

## Code Review

When doing code reviews, create a structured review checklist and document findings in a markdown file before discussing with user.

When resolving code review comments across PRs:
- Use parallel task agents to handle multiple PRs simultaneously
- After fixing code, mark GitHub review comment threads as resolved using the GitHub CLI (`gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies`)
- Always confirm with user whether to push changes and resolve threads, or just prepare commits

## Code Style

### Docstrings (Google Style)

All functions and methods should use Google-style docstrings:

```python
def function_name(arg1: str, arg2: int = 10) -> bool:
    """Short one-line description.

    Args:
        arg1: Description of the first argument
        arg2: Description with default value noted

    Returns:
        Description of return value.

    Raises:
        ValueError: When input validation fails
    """
```

**Verification:**
```bash
# Check docstring compliance
pydocstyle --convention=google --add-ignore=D100,D104 src/shared/

# Common ignores:
# D100 - Missing module docstring
# D104 - Missing package docstring
```

**Google style sections:**
- `Args:` - Function parameters
- `Returns:` - Return value description
- `Raises:` - Exceptions that may be raised
- `Yields:` - For generator functions
- `Examples:` - Usage examples (optional)
- `Note:` - Important notes (optional)

## Security Review Checklist

When reviewing code or implementing features, verify the following:

### Dependencies
- [ ] No new dependencies with known CVEs (`safety check`)
- [ ] Dependencies pinned to specific versions in requirements.txt
- [ ] Major version bumps reviewed for breaking changes
- [ ] Security-critical packages (aiohttp, requests, cryptography) at latest versions

### Imports
- [ ] No `xml.etree` - use `defusedxml` for XML parsing
- [ ] No `pickle` or `marshal` - use `json` for serialization
- [ ] No `eval()` or `exec()` anywhere in production code
- [ ] No `os.system()` - use `subprocess.run()` with `shell=False`

### Secrets
- [ ] No hardcoded API keys, passwords, or tokens
- [ ] Secrets loaded from environment variables only
- [ ] `.env.example` updated when adding new secrets
- [ ] Test files use mock/fake credentials (not real ones)

### Data Handling
- [ ] User/external input validated before use
- [ ] URLs validated before making requests
- [ ] File paths sanitized (no path traversal via `../`)
- [ ] JSON/XML from external sources parsed safely

### Cryptography
- [ ] SHA256+ for security-sensitive hashing (not MD5/SHA1)
- [ ] MD5 only used for non-security purposes (cache keys, checksums)
- [ ] `secrets.compare_digest()` for constant-time token comparison
- [ ] No custom cryptography implementations

### Pre-Commit Hooks
```bash
# Install hooks (one-time setup)
pip install pre-commit
pre-commit install

# Run all hooks manually
pre-commit run --all-files

# Run specific hook
pre-commit run bandit --all-files
pre-commit run detect-secrets --all-files
```

## 1Password / Credentials

When working with 1Password CLI or service account tokens:
- Environment variables set in shell profiles may not be inherited by GUI apps or LaunchAgents
- Use `launchctl setenv` or LaunchAgent plists to set system-wide env vars like `OP_SERVICE_ACCOUNT_TOKEN`
- Always verify token availability in subprocess contexts with `env | grep OP_`
- Check `~/.config/op/config` and 1Password desktop integration settings before modifying auth flows
- MCP servers need the env var inherited in their subprocess — check the parent process (Claude, terminal, LaunchAgent) passes variables correctly

## Debugging Tips

For MCP server configuration issues, check both the server's environment variable access AND how the parent process (Claude, terminal, LaunchAgent) passes those variables.

## Development Workflow

When implementing large features from a design plan, create all modules systematically with tests before moving to integration. Use the TUI scraping researcher project as a reference pattern.
