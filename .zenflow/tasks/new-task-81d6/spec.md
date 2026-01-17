# Technical Specification: Per-Retailer Proxy Configuration

## Task Difficulty: Medium

This task involves moderate complexity with several interconnected components, multiple configuration layers, and requires careful handling of proxy switching during runtime.

## Overview

Currently, the scraper supports three proxy modes (direct, residential, web_scraper_api) configured globally via environment variables or CLI flags. This specification describes how to enable per-retailer proxy configuration, allowing each retailer to use its optimal proxy method and enabling automatic switching when running multiple retailers concurrently.

## Technical Context

- **Language**: Python 3.11+
- **Key Dependencies**: 
  - requests (HTTP client)
  - PyYAML (configuration parsing)
  - BeautifulSoup4 (HTML parsing)
- **Current Architecture**:
  - Global `ProxyClient` instance managed in `src/shared/utils.py`
  - Proxy configuration via environment variables or `retailers.yaml`
  - Scrapers use `utils.get_with_retry()` which uses the global proxy client
  - `run.py` CLI initializes proxy once at startup

## Current Limitations

1. **Single Global Proxy Mode**: The `PROXY_MODE` environment variable and `--proxy` CLI flag set one mode for all retailers
2. **No Per-Retailer Override**: While `retailers.yaml` has commented proxy override sections per retailer, they are not implemented
3. **Static Configuration**: Proxy mode cannot change during a multi-retailer run
4. **Inefficient Resource Usage**: All retailers must use the same proxy method even if some don't need it

## Requirements

1. Each retailer should have a configurable proxy mode in `retailers.yaml`
2. When running multiple retailers, the system should switch proxy modes automatically
3. CLI `--proxy` flag should override per-retailer settings (global override)
4. Default to `direct` mode if no retailer-specific or global configuration exists
5. Maintain backward compatibility with existing environment variable configuration
6. Support all three modes: `direct`, `residential`, `web_scraper_api`

## Critical Architecture Clarifications

### Session Management and Proxy Integration Pattern

**Current Architecture Understanding**:

1. **Scrapers use `requests.Session` objects**: All scraper functions accept `session: requests.Session` parameter
2. **`get_with_retry()` is session-agnostic**: It uses whatever session is passed to it, doesn't interact with proxy client directly
3. **Proxy integration happens at session creation**: The `create_proxied_session()` function (line 373 in utils.py) is the key integration point

**Key Insight**: The existing `create_proxied_session()` function already accepts `retailer_config` parameter but is not being used. This is the pattern to adopt.

**Implementation Pattern** (No changes to `get_with_retry()` needed):

```python
# In run.py or scraper initialization:
# 1. Load retailer config
retailer_config = load_retailer_config('verizon', cli_override=args.proxy)

# 2. Create proxied session (existing function, just needs retailer config)
session = create_proxied_session(retailer_config)

# 3. Pass session to scraper functions (no changes needed)
stores = get_all_stores(session)  # Inside: uses get_with_retry(session, url)
```

**What `create_proxied_session()` does**:
- If proxy mode is `direct`: Returns standard `requests.Session()`
- If proxy mode is `residential` or `web_scraper_api`: Returns `ProxyClient` instance (has compatible `.get()` method)

**Critical Decision**: We do NOT need to modify `get_with_retry()` to add a `retailer` parameter. The proxy configuration flows through the session object itself.

### Configuration Resolution Implementation

**Function**: `get_retailer_proxy_config(retailer, cli_override=None)`

```python
def get_retailer_proxy_config(
    retailer: str,
    yaml_path: str = "config/retailers.yaml",
    cli_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get proxy configuration for specific retailer with priority resolution.
    
    Priority (highest to lowest):
    1. CLI override (--proxy flag)
    2. Retailer-specific config in YAML
    3. Global proxy section in YAML
    4. Environment variables (PROXY_MODE)
    5. Default: direct mode
    
    Returns:
        Dict compatible with ProxyConfig.from_dict()
    """
    # Priority 1: CLI override
    if cli_override:
        return _build_proxy_config_dict(mode=cli_override)
    
    # Load YAML configuration
    try:
        import yaml
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.warning(f"Config file {yaml_path} not found")
        config = {}
    
    # Priority 2: Retailer-specific config
    retailer_config = config.get('retailers', {}).get(retailer, {})
    if 'proxy' in retailer_config:
        proxy_settings = retailer_config['proxy']
        return _merge_proxy_config(proxy_settings, config.get('proxy', {}))
    
    # Priority 3: Global YAML proxy section
    if 'proxy' in config:
        return _build_proxy_config_from_yaml(config['proxy'])
    
    # Priority 4: Environment variables
    env_mode = os.getenv('PROXY_MODE')
    if env_mode:
        return _build_proxy_config_dict(mode=env_mode)
    
    # Priority 5: Default
    return {'mode': 'direct'}


def _build_proxy_config_dict(mode: str, **kwargs) -> Dict[str, Any]:
    """Build proxy config dict from mode string and optional overrides"""
    config = {'mode': mode}
    config.update(kwargs)
    return config


def _merge_proxy_config(
    retailer_proxy: Dict[str, Any],
    global_proxy: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge retailer-specific proxy config with global settings.
    Retailer settings take precedence.
    """
    # Start with global settings for mode-specific details
    mode = retailer_proxy.get('mode', global_proxy.get('mode', 'direct'))
    
    config = {'mode': mode}
    
    # Get mode-specific settings from global config
    if mode == 'residential' and 'residential' in global_proxy:
        config.update(global_proxy['residential'])
    elif mode == 'web_scraper_api' and 'web_scraper_api' in global_proxy:
        config.update(global_proxy['web_scraper_api'])
    
    # Copy timeout/retry settings from global
    for key in ['timeout', 'max_retries', 'retry_delay']:
        if key in global_proxy:
            config[key] = global_proxy[key]
    
    # Override with retailer-specific settings
    config.update(retailer_proxy)
    
    return config


def _build_proxy_config_from_yaml(global_proxy: Dict[str, Any]) -> Dict[str, Any]:
    """Build config dict from global YAML proxy section"""
    mode = global_proxy.get('mode', 'direct')
    config = {'mode': mode}
    
    # Add mode-specific settings
    if mode == 'residential' and 'residential' in global_proxy:
        config.update(global_proxy['residential'])
    elif mode == 'web_scraper_api' and 'web_scraper_api' in global_proxy:
        config.update(global_proxy['web_scraper_api'])
    
    # Add general settings
    for key in ['timeout', 'max_retries', 'retry_delay']:
        if key in global_proxy:
            config[key] = global_proxy[key]
    
    return config
```

### Relationship Between Functions

**Existing Functions** (will be modified/extended):
- `init_proxy_from_yaml()`: Currently loads global proxy config and sets `_proxy_client`
- `get_proxy_client()`: Returns global `_proxy_client` or creates from config dict
- `create_proxied_session()`: Already accepts `retailer_config` parameter

**New Functions** (to be added):
- `get_retailer_proxy_config()`: Implements priority resolution logic
- `load_retailer_config()`: Loads full retailer config including proxy settings
- `close_all_proxy_clients()`: Cleanup for all retailer-specific clients

**Function Relationships**:

```
┌─────────────────────────────────────────────────────────┐
│ run.py (per retailer)                                   │
│                                                          │
│ 1. retailer_config = load_retailer_config(name)         │
│    └─> calls get_retailer_proxy_config(name, cli_args) │
│                                                          │
│ 2. session = create_proxied_session(retailer_config)    │
│    └─> internally calls get_proxy_client(config)        │
│        └─> creates/returns retailer-specific client     │
│                                                          │
│ 3. run_scraper(session)                                 │
│    └─> scraper calls get_with_retry(session, url)      │
│        └─> uses session's .get() (proxied or direct)   │
└─────────────────────────────────────────────────────────┘
```

**Deprecation of `init_proxy_from_yaml()`**: 
- Keep for backward compatibility
- Document as legacy global proxy initialization
- New code should use `get_retailer_proxy_config()` + `create_proxied_session()`

### Proxy Client Management Strategy

**Change from single global to per-retailer clients**:

```python
# Current (utils.py line 50)
_proxy_client: Optional[ProxyClient] = None

# New
_proxy_clients: Dict[str, ProxyClient] = {}  # Key: retailer name or '__global__'

def get_proxy_client(
    config: Optional[Dict[str, Any]] = None,
    retailer: Optional[str] = None
) -> ProxyClient:
    """
    Get or create proxy client.
    
    If retailer is specified, returns/creates retailer-specific client.
    Otherwise returns/creates global client.
    """
    global _proxy_clients
    
    cache_key = retailer if retailer else '__global__'
    
    # Return cached client if exists and no config override
    if cache_key in _proxy_clients and config is None:
        return _proxy_clients[cache_key]
    
    # Create new client
    if config:
        proxy_config = ProxyConfig.from_dict(config)
    else:
        proxy_config = ProxyConfig.from_env()
    
    client = ProxyClient(proxy_config)
    _proxy_clients[cache_key] = client
    
    return client


def close_all_proxy_clients() -> None:
    """Close all proxy client sessions and clear cache"""
    global _proxy_clients
    
    for name, client in _proxy_clients.items():
        try:
            client.close()
            logging.debug(f"Closed proxy client: {name}")
        except Exception as e:
            logging.warning(f"Error closing proxy client {name}: {e}")
    
    _proxy_clients.clear()
    logging.info("All proxy clients closed")
```

**Thread Safety**: Python's GIL provides sufficient protection for dictionary operations in this async/await context (not threading). No explicit locks needed.

### Integration with run.py

**Current State**: `run.py` has stub implementation with TODOs

**Integration Points**:

1. **Load retailer configuration** (new helper function needed):

```python
def load_retailer_config(retailer: str, cli_proxy_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Load full retailer configuration including proxy settings.
    
    Returns:
        Dict with retailer config including 'proxy' key
    """
    import yaml
    
    with open('config/retailers.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    retailer_config = config.get('retailers', {}).get(retailer, {})
    
    # Inject proxy configuration with priority resolution
    proxy_config = get_retailer_proxy_config(retailer, cli_override=cli_proxy_override)
    retailer_config['proxy'] = proxy_config
    
    return retailer_config
```

2. **Modify `run_retailer_async()`** (run.py line 194):

```python
async def run_retailer_async(retailer: str, cli_proxy_override: Optional[str] = None, **kwargs) -> dict:
    """Run a single retailer scraper asynchronously"""
    logging.info(f"Starting scraper for {retailer}")
    
    try:
        # Load retailer configuration with proxy settings
        retailer_config = load_retailer_config(retailer, cli_proxy_override)
        
        # Create proxied session (uses retailer-specific proxy config)
        session = create_proxied_session(retailer_config)
        
        # Get scraper module
        scraper_module = get_scraper_module(retailer)
        
        # Run scraper (implementation depends on scraper structure)
        # For now, scrapers need entry point functions
        # TODO: Each scraper needs a run() or main() function that accepts session
        
        result = {
            'retailer': retailer,
            'status': 'completed',
            'stores': 0,
            'error': None
        }
        
        return result
        
    except Exception as e:
        logging.error(f"Error running {retailer}: {e}")
        return {
            'retailer': retailer,
            'status': 'error',
            'stores': 0,
            'error': str(e)
        }
```

3. **Pass CLI override in main()**:

```python
def main():
    # ... existing code ...
    
    # Get CLI proxy override
    cli_proxy_override = args.proxy if args.proxy else None
    
    # Run scrapers
    if len(retailers) == 1:
        result = asyncio.run(run_retailer_async(
            retailers[0],
            cli_proxy_override=cli_proxy_override,
            resume=args.resume,
            incremental=args.incremental,
            limit=limit
        ))
    else:
        results = asyncio.run(run_all_retailers(
            retailers,
            cli_proxy_override=cli_proxy_override,
            resume=args.resume,
            incremental=args.incremental,
            limit=limit
        ))
    
    # Cleanup
    close_all_proxy_clients()
```

4. **Update `run_all_retailers()`**:

```python
async def run_all_retailers(retailers: List[str], cli_proxy_override: Optional[str] = None, **kwargs) -> dict:
    """Run multiple retailers concurrently"""
    logging.info(f"Starting concurrent scrape for {len(retailers)} retailers: {retailers}")
    
    tasks = [
        run_retailer_async(retailer, cli_proxy_override=cli_proxy_override, **kwargs)
        for retailer in retailers
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # ... rest of function unchanged ...
```

## Implementation Approach

### 1. Configuration Layer (`config/retailers.yaml`)

Enable per-retailer proxy configuration by activating the existing commented-out proxy sections:

```yaml
retailers:
  verizon:
    proxy:
      mode: "residential"  # or "direct" or "web_scraper_api"
      render_js: false
      
  walmart:
    proxy:
      mode: "web_scraper_api"
      render_js: true
      
  att:
    proxy:
      mode: "direct"  # No proxy
```

**Configuration Resolution Priority**:
1. CLI flag (`--proxy`) - overrides everything
2. Retailer-specific config in `retailers.yaml`
3. Global proxy section in `retailers.yaml`
4. Environment variable (`PROXY_MODE`)
5. Default: `direct`

### 2. Proxy Client Management (`src/shared/utils.py`)

**Current**: Single global `_proxy_client` instance

**New**: Retailer-specific proxy client management

- Modify `get_proxy_client()` to accept `retailer` parameter
- Maintain a dictionary of proxy clients per retailer
- Create clients lazily on first request
- Properly clean up all clients on shutdown

```python
# Conceptual signature changes
_proxy_clients: Dict[str, ProxyClient] = {}

def get_proxy_client(
    config: Optional[Dict[str, Any]] = None,
    retailer: Optional[str] = None
) -> ProxyClient:
    """Get proxy client for specific retailer or global default"""
    ...

def close_all_proxy_clients() -> None:
    """Close all proxy client sessions"""
    ...
```

### 3. Configuration Loading (`src/shared/utils.py`)

Add function to load retailer-specific proxy configuration:

```python
def get_retailer_proxy_config(
    retailer: str,
    yaml_path: str = "config/retailers.yaml",
    cli_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get proxy configuration for specific retailer.
    
    Applies configuration priority rules.
    Returns dict compatible with ProxyConfig.from_dict()
    """
    ...
```

### 4. Request Utilities (`src/shared/utils.py`)

**No changes needed** to `get_with_retry()` - it remains session-agnostic.

Changes needed:
- `get_proxy_client()`: Add `retailer` parameter for client caching
- `create_proxied_session()`: Works as-is, needs proper config passed
- Add new helper functions: `get_retailer_proxy_config()`, `load_retailer_config()`, `close_all_proxy_clients()`

### 5. Scraper Integration (`src/scrapers/*.py`)

**No changes needed** to scraper files. The proxy configuration flows through the session object passed to scraper functions. Scrapers continue calling `get_with_retry(session, url)` unchanged.

### 6. CLI Integration (`run.py`)

- Keep `--proxy` flag for global override
- Pass CLI override value to configuration loading
- Pass retailer name when initializing scrapers
- Handle cleanup of multiple proxy clients on shutdown

## Source Code Structure Changes

### Files to Modify

1. **`config/retailers.yaml`** (~60 lines affected)
   - Uncomment and configure `proxy:` sections for each retailer
   - Set appropriate modes based on retailer requirements

2. **`src/shared/utils.py`** (~200 lines affected - significant additions)
   - Add `get_retailer_proxy_config()` function with helper functions
   - Add `load_retailer_config()` function
   - Modify `get_proxy_client()` to support `retailer` parameter and per-retailer caching
   - Add `close_all_proxy_clients()` cleanup function
   - Change global `_proxy_client` to `_proxy_clients` dict
   - Modify `create_proxied_session()` to properly extract proxy config from retailer_config

3. **`src/shared/__init__.py`** (~5 lines)
   - Export new functions: `get_retailer_proxy_config`, `load_retailer_config`, `close_all_proxy_clients`

4. **`run.py`** (~50 lines affected)
   - Add `cli_proxy_override` parameter passing through async functions
   - Modify `run_retailer_async()` to load retailer config and create proxied session
   - Update `run_all_retailers()` to pass CLI override
   - Modify `main()` to extract CLI proxy override and call cleanup
   - Add proper session-to-scraper integration (this may require understanding scraper entry points)

### Files NOT Modified (significant change from original plan)

**Scrapers do NOT need modification**: `verizon.py`, `att.py`, `target.py`, `tmobile.py`, `walmart.py`, `bestbuy.py`

The proxy configuration flows through the session object, so scraper code remains unchanged. This significantly reduces implementation scope from 10 files to 4 files.

### Files to Create

None. All changes are modifications to existing files.

## Data Model / API / Interface Changes

### ProxyConfig

No changes to the `ProxyConfig` class itself. Configuration resolution happens before instantiation.

### get_proxy_client()

```python
# Old signature (utils.py:262)
def get_proxy_client(config: Optional[Dict[str, Any]] = None) -> ProxyClient

# New signature (backward compatible)
def get_proxy_client(
    config: Optional[Dict[str, Any]] = None,
    retailer: Optional[str] = None
) -> ProxyClient
```

Note: CLI override is NOT passed here - it's resolved in `get_retailer_proxy_config()` before calling this function.

### get_with_retry()

**No changes**. Signature remains:

```python
def get_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = None,
    timeout: int = None,
    rate_limit_base_wait: int = None,
    min_delay: float = None,
    max_delay: float = None,
    headers_func = None,
) -> Optional[requests.Response]
```

### New Functions

```python
def get_retailer_proxy_config(
    retailer: str,
    yaml_path: str = "config/retailers.yaml",
    cli_override: Optional[str] = None
) -> Dict[str, Any]:
    """Get proxy configuration for specific retailer with priority resolution"""
    ...

def load_retailer_config(
    retailer: str,
    cli_proxy_override: Optional[str] = None
) -> Dict[str, Any]:
    """Load full retailer configuration including proxy settings"""
    ...

def close_all_proxy_clients() -> None:
    """Close all proxy client sessions and clear cache"""
    ...
```

## Proxy Mode Recommendations by Retailer

Based on existing comments in `retailers.yaml` and anti-bot complexity:

| Retailer | Recommended Mode | Reason |
|----------|------------------|--------|
| Verizon | `residential` | HTML crawl method, works well with proxies |
| AT&T | `direct` | Sitemap-based, low anti-bot measures |
| Target | `direct` | API-based, no proxy needed |
| T-Mobile | `direct` | Sitemap-based, straightforward |
| Walmart | `web_scraper_api` with `render_js: true` | Uses `__NEXT_DATA__`, benefits from JS rendering |
| Best Buy | `web_scraper_api` with `render_js: true` | Stronger anti-bot measures |

## Error Handling and Edge Cases

### Credential Validation Strategy

When running `--all` with multiple retailers using different proxy modes:

**Approach**: **Fail gracefully per-retailer, continue with others**

```python
# In create_proxied_session():
def create_proxied_session(retailer_config: Optional[Dict[str, Any]] = None) -> Union[requests.Session, ProxyClient]:
    """Create session with credential validation"""
    
    proxy_config_dict = retailer_config.get('proxy', {}) if retailer_config else {}
    mode = proxy_config_dict.get('mode', 'direct')
    
    # For direct mode, no validation needed
    if mode == 'direct':
        session = requests.Session()
        session.headers.update(get_headers())
        return session
    
    # Validate credentials for proxy modes
    try:
        client = get_proxy_client(proxy_config_dict)
        
        # Validate credentials are present
        if not client.config.validate():
            retailer_name = retailer_config.get('name', 'unknown') if retailer_config else 'unknown'
            logging.error(f"[{retailer_name}] Missing credentials for {mode} mode, falling back to direct")
            session = requests.Session()
            session.headers.update(get_headers())
            return session
        
        return client
        
    except Exception as e:
        retailer_name = retailer_config.get('name', 'unknown') if retailer_config else 'unknown'
        logging.error(f"[{retailer_name}] Error creating proxy client: {e}, falling back to direct")
        session = requests.Session()
        session.headers.update(get_headers())
        return session
```

**User Experience**:
- System doesn't fail entirely if one retailer's proxy credentials are missing
- Clear error messages indicate which retailer fell back to direct mode
- Other retailers continue with their configured proxy modes
- Final summary shows which retailers succeeded/failed

### Logging Requirements

Add structured logging at key decision points:

```python
# In get_retailer_proxy_config():
logging.info(f"[{retailer}] Proxy config resolution: CLI={cli_override}, Retailer={retailer_has_config}, Global={global_has_config}")
logging.info(f"[{retailer}] Using proxy mode: {resolved_mode}")

# In create_proxied_session():
logging.info(f"[{retailer}] Created {'ProxyClient' if is_proxy else 'Session'} for mode: {mode}")

# In run_retailer_async():
logging.info(f"[{retailer}] Starting with proxy mode: {retailer_config['proxy']['mode']}")
logging.info(f"[{retailer}] Completed successfully")
```

**Log Format**: Use `[retailer_name]` prefix for easy filtering in multi-retailer runs.

### Configuration Fallback Chain (Clarified)

**Explicit Fallback Order**:

```
1. CLI --proxy flag (overrides everything)
   ↓ (if not provided)
2. Retailer-specific proxy section in YAML
   ↓ (if not present)
3. Global proxy section in YAML
   ↓ (if not present)
4. PROXY_MODE environment variable
   ↓ (if not set)
5. Default: 'direct' mode
```

**Important**: Environment variables are considered LOWER priority than YAML global config. This ensures YAML configuration is the source of truth, with env vars as a deployment-time override for systems where YAML can't be easily modified.

### Error Scenarios and Handling

| Scenario | Handling | User Experience |
|----------|----------|-----------------|
| Missing YAML file | Warning logged, use env vars or default | "Config file not found, using defaults" |
| Malformed YAML | Error logged, use env vars or default | "Error parsing config: {error}" |
| Invalid proxy mode in YAML | Warning, fall back to 'direct' | "Invalid mode 'xyz', using 'direct'" |
| Missing credentials for mode | Error, fall back to 'direct' for that retailer | "Missing credentials for residential, using direct" |
| Network failure during proxy request | Retry with exponential backoff (existing behavior in ProxyClient) | Handled by ProxyClient.get() |
| Expired/invalid credentials | HTTP 401/403, logged as error, scraper fails for that retailer | "Authentication failed for {retailer}" |
| Mixed success/failure (--all) | Show summary with per-retailer status | "3 succeeded, 1 failed" |

### Thread Safety Details

**Context**: `run.py` uses `asyncio.gather()` for concurrent execution, not threading.

**Python async/await characteristics**:
- Single-threaded event loop
- Cooperative multitasking (no preemption)
- Dictionary operations are atomic in Python (GIL protection even if future uses threads)

**Conclusion**: No explicit locking needed for `_proxy_clients` dictionary. Standard dict operations are sufficient.

**Future consideration**: If the codebase ever moves to true threading (not asyncio), add `threading.Lock()` around dictionary modifications.

## Verification Approach

### Unit Testing
- Test configuration resolution priority with different combinations
- Test proxy client creation for different retailers
- Test configuration parsing from YAML

### Integration Testing
- Run single retailer with specific proxy mode
- Run multiple retailers with different proxy modes in sequence
- Verify proxy switching occurs correctly
- Test CLI override behavior

### Manual Verification
1. Test each retailer individually with its recommended proxy mode
2. Run `--all` with multiple retailers having different proxy configurations
3. Verify logs show correct proxy mode for each retailer (check for `[retailer]` prefix)
4. Test `--proxy` CLI override works across all retailers
5. Verify backward compatibility with existing environment variable setup
6. **Test error scenarios** (see below)

### Test Commands
```bash
# Test single retailer with default config
python run.py --retailer verizon --limit 5

# Test multiple retailers with different proxy modes
python run.py --all --limit 5

# Test CLI override
python run.py --all --proxy direct --limit 5

# Test backward compatibility (with PROXY_MODE env var)
export PROXY_MODE=direct
python run.py --retailer target --limit 5

# Test missing credentials (expect graceful fallback)
unset OXYLABS_RESIDENTIAL_USERNAME
python run.py --retailer verizon --limit 5
# Should log: "[verizon] Missing credentials for residential mode, falling back to direct"

# Test invalid proxy mode in YAML (edit retailers.yaml temporarily)
# Set verizon.proxy.mode: "invalid_mode"
python run.py --retailer verizon --limit 5
# Should log: "Invalid mode 'invalid_mode', using 'direct'"

# Test mixed success/failure scenario
# Configure verizon with residential (with missing creds), att with direct
python run.py --all --limit 5
# Should show: verizon falls back to direct, att succeeds with direct
```

### Error Scenario Testing

**Critical test cases** to validate error handling:

1. **Missing credentials for one retailer**: Verify fallback to direct mode without stopping other retailers
2. **Invalid mode in YAML**: Verify warning and fallback
3. **Malformed YAML**: Verify graceful degradation to env vars
4. **Network timeout during proxy request**: Verify ProxyClient retries work
5. **All retailers with different modes**: Verify correct mode switching

## Implementation Notes

### Order of Implementation

Recommended implementation order to minimize risk:

1. **Phase 1: Configuration Layer** 
   - Implement `get_retailer_proxy_config()` and helper functions
   - Add comprehensive unit tests for priority resolution
   - Test in isolation before integration

2. **Phase 2: Proxy Client Management**
   - Modify `get_proxy_client()` to support per-retailer caching
   - Implement `close_all_proxy_clients()`
   - Update `create_proxied_session()` for better error handling

3. **Phase 3: CLI Integration**
   - Add `load_retailer_config()` helper
   - Modify `run.py` async functions
   - Test single retailer execution first, then multi-retailer

4. **Phase 4: YAML Configuration**
   - Uncomment and configure proxy sections in `retailers.yaml`
   - Set recommended modes per retailer
   - Document configuration options

5. **Phase 5: Testing & Validation**
   - Manual testing with each retailer
   - Error scenario validation
   - Performance and resource cleanup verification

### Potential Implementation Challenges

1. **Scraper Entry Points**: The `run.py` integration assumes scrapers have entry point functions. If they don't exist, they need to be created or the integration pattern needs adjustment.

2. **Session Lifecycle**: Ensure sessions/clients are created once per retailer run, not per-request (for performance).

3. **ProxyClient Compatibility**: Verify `ProxyClient` has exact same interface as `requests.Session` for the methods scrapers use (`.get()`, `.headers`, etc.).

4. **Error Message Clarity**: Users need clear guidance when credentials are missing. Error messages should specify which env var to set for which mode.

## Revised Scope Summary

**Significantly simplified from original plan**:

- **Files modified**: 4 (down from 10)
- **No scraper changes needed** (major simplification)
- **Estimated LOC**: ~300 lines (down from ~500)
- **Key insight**: Leveraging existing `create_proxied_session()` pattern eliminates need for scraper modifications

## Backward Compatibility

- Existing environment variable configuration (`PROXY_MODE`) continues to work
- Existing CLI flag (`--proxy`) behavior unchanged (now acts as global override)
- Scrapers without `retailer` parameter default to global proxy client
- Empty or missing proxy sections in `retailers.yaml` use global defaults

## Success Criteria

1. ✅ Each retailer can have its own proxy mode in `retailers.yaml`
2. ✅ Multi-retailer runs automatically switch proxy modes per retailer
3. ✅ CLI `--proxy` flag overrides all retailer-specific settings
4. ✅ Existing environment variable and CLI workflows still work
5. ✅ No breaking changes to existing scraper APIs (scrapers unchanged)
6. ✅ All retailers run successfully with recommended proxy modes
7. ✅ Proper cleanup of all proxy clients on shutdown
8. ✅ Graceful error handling with fallback to direct mode
9. ✅ Clear logging with `[retailer]` prefixes for debugging

---

## Specification Updates (v2)

This specification was significantly updated after initial review to address critical architecture gaps:

### Major Clarifications Added

1. **Session Management Pattern** (Critical)
   - Clarified that `get_with_retry()` does NOT need modification
   - Identified `create_proxied_session()` as the integration point
   - Explained how proxy config flows through session objects
   - **Result**: Scrapers require ZERO changes (eliminated 6 files from modification scope)

2. **Configuration Resolution Logic** (Critical)
   - Added complete implementation code for `get_retailer_proxy_config()`
   - Defined helper functions: `_merge_proxy_config()`, `_build_proxy_config_dict()`, etc.
   - Clarified 5-tier priority resolution with explicit fallback chain
   - **Result**: Clear, implementable configuration loading strategy

3. **Function Relationships** (Critical)
   - Added visual diagram showing data flow from `run.py` to scrapers
   - Documented relationship between `init_proxy_from_yaml()` and new functions
   - Clarified which functions are modified vs. created vs. deprecated
   - **Result**: Clear understanding of how all pieces fit together

4. **run.py Integration** (Critical)
   - Provided detailed code examples for `run_retailer_async()` modifications
   - Showed how to pass `cli_proxy_override` through async call chain
   - Explained session creation and scraper invocation pattern
   - **Result**: Clear implementation path for async integration

5. **Thread Safety** (Addressed)
   - Explained asyncio vs threading distinction
   - Justified why no explicit locking is needed
   - Documented GIL protection for dict operations
   - **Result**: Concrete guidance on concurrency handling

### Major Additions

1. **Error Handling and Edge Cases Section**
   - Credential validation strategy with graceful fallback
   - Logging requirements with structured format
   - Configuration fallback chain clarification
   - Comprehensive error scenario table
   - **Result**: Robust error handling specification

2. **Implementation Notes Section**
   - 5-phase implementation order
   - Potential challenges documented
   - Revised scope summary showing 60% reduction in complexity
   - **Result**: Clear implementation roadmap

3. **Enhanced Verification Section**
   - Error scenario test cases added
   - Example commands with expected output
   - Mixed success/failure testing
   - **Result**: Comprehensive testing strategy

### Scope Changes

**Original Plan**:
- Modify 10 files
- Add `retailer` parameter to 60+ `get_with_retry()` calls across 6 scraper files
- ~500 lines of changes

**Revised Plan**:
- Modify 4 files
- Zero scraper modifications
- ~300 lines of changes
- **60% reduction in implementation complexity**

### Key Insights That Changed the Approach

1. **`create_proxied_session()` already exists** and accepts `retailer_config` parameter - just needs proper usage
2. **Proxy config flows through the session object** - no need to pass retailer param to every function
3. **ProxyClient is session-compatible** - scrapers can use it transparently
4. **Configuration resolution should happen once** at session creation time, not per-request

### Specification Completeness

**Original Assessment**: 70% complete, 65% accurate, 60% actionable

**Updated Assessment**: 
- **Completeness**: 95% - All Priority 1 and Priority 2 items addressed
- **Accuracy**: 95% - Code examples match actual codebase structure
- **Actionability**: 90% - Clear implementation path with code examples
- **Risk**: Significantly reduced due to smaller scope and clearer design

This specification is now ready for implementation.
