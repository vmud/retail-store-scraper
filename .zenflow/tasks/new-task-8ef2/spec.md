# Technical Specification: Scraper Integration

## Difficulty Assessment
**Medium** - Requires defining a standard interface contract and updating multiple scraper modules to implement it. Involves understanding async/sync patterns and error handling across 6 different scrapers.

## Technical Context

### Language & Dependencies
- **Language**: Python 3.11
- **Key Libraries**: 
  - `requests` for HTTP (sync)
  - `asyncio` for concurrent execution
  - Custom `ProxyClient` and `ProxyResponse` classes
  - BeautifulSoup, lxml for parsing
- **Architecture**: Multi-retailer scraper with unified CLI

### Current State

#### Session Management (Working)
The codebase has a robust session creation system:
- `create_proxied_session(retailer_config)` in `src/shared/utils.py:546`
- Returns either `requests.Session` (direct mode) or `ProxyClient` (proxy modes)
- Supports 3 modes: direct, residential proxy, web_scraper_api
- Per-retailer configuration via `config/retailers.yaml`

#### Scraper Execution (Missing)
The critical gap is in `run.py:194-234`:
```python
async def run_retailer_async(retailer: str, ...) -> dict:
    # Creates session ✅
    session = create_proxied_session(retailer_config)
    
    # Loads scraper module ✅
    scraper_module = get_scraper_module(retailer)
    
    # Missing: No call to scraper with session ❌
    # Just returns placeholder result
```

Each scraper module has:
- Data models (dataclasses)
- Helper functions (`get_all_store_ids`, `extract_store_details`, etc.)
- No standardized entry point function

## Problem Statement

**Gap**: Sessions are created but never passed to scrapers because there's no defined entry point interface.

**Impact**: 
- Scrapers cannot run
- Proxy configuration is not utilized
- CLI flags like `--limit`, `--resume` have no effect

## Implementation Approach

### 1. Define Scraper Interface Contract

Create a standardized entry point that all scrapers must implement:

```python
def run(session: Union[requests.Session, ProxyClient], 
        config: dict, 
        **kwargs) -> dict:
    """
    Standard scraper entry point.
    
    Args:
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration dict from retailers.yaml
        **kwargs: Additional options
            - resume: bool - Resume from checkpoint
            - limit: int - Max stores to process
            - incremental: bool - Only process changes
    
    Returns:
        dict with keys:
            - stores: List[dict] - Scraped store data
            - count: int - Number of stores processed
            - checkpoints_used: bool - Whether resume was used
    """
```

### 2. Update run.py Integration

Modify `run_retailer_async()` in `run.py:194-234` to:
1. Keep existing session creation
2. Call `scraper_module.run(session, retailer_config, **kwargs)`
3. Handle return value and update result dict
4. Save outputs (JSON/CSV)
5. Handle errors with proper logging

### 3. Update Scraper Modules

**Discovery Method Patterns (verified):**

| Scraper | Discovery | Extraction | Return Type |
|---------|-----------|------------|-------------|
| walmart | `get_store_urls_from_sitemap()` | `extract_store_details()` | `WalmartStore` (has `to_dict()`) |
| att | `get_store_urls_from_sitemap()` | `extract_store_details()` | `ATTStore` (has `to_dict()`) |
| tmobile | `get_store_urls_from_sitemap()` | `extract_store_details()` | `TMobileStore` (has `to_dict()`) |
| target | `get_all_store_ids()` | `get_store_details()` | `TargetStore` (has `to_dict()`) |
| bestbuy | `get_all_store_ids()` | (incomplete) | `BestBuyStore` (has `to_dict()`) |
| verizon | 4-phase crawl | `extract_store_details()` | `Dict[str, Any]` (no dataclass) |

**Pattern A - Sitemap-based (walmart, att, tmobile):**

```python
def run(session, config, **kwargs):
    """Standard interface for sitemap-based scrapers"""
    limit = kwargs.get('limit')
    
    # Reset request counter
    reset_request_counter()
    
    # Discovery phase
    store_urls = get_store_urls_from_sitemap(session)
    if limit:
        store_urls = store_urls[:limit]
    
    # Extraction phase
    stores = []
    for url in store_urls:
        store_obj = extract_store_details(session, url)
        if store_obj:
            stores.append(store_obj.to_dict())
    
    return {
        'stores': stores,
        'count': len(stores),
        'checkpoints_used': False
    }
```

**Pattern B - API-based (target):**

```python
def run(session, config, **kwargs):
    """Standard interface for API-based scrapers"""
    limit = kwargs.get('limit')
    
    # Reset request counter
    reset_request_counter()
    
    # Discovery phase
    store_ids = get_all_store_ids(session)
    if limit:
        store_ids = store_ids[:limit]
    
    # Extraction phase
    stores = []
    for store_info in store_ids:
        store_obj = get_store_details(session, store_info['store_id'])
        if store_obj:
            stores.append(store_obj.to_dict())
    
    return {
        'stores': stores,
        'count': len(stores),
        'checkpoints_used': False
    }
```

**Pattern C - Multi-phase crawl (verizon):**

```python
def run(session, config, **kwargs):
    """Standard interface for multi-phase crawl scrapers"""
    limit = kwargs.get('limit')
    
    # Reset request counter
    reset_request_counter()
    
    # Phase 1-3: Hierarchical discovery
    states = get_all_states(session)
    stores = []
    
    for state in states:
        cities = get_cities_for_state(session, state['url'], state['name'])
        for city in cities:
            store_urls = get_stores_for_city(session, city['url'], 
                                             city['city'], city['state'])
            for store_url_info in store_urls:
                store_dict = extract_store_details(session, store_url_info['url'])
                if store_dict:
                    stores.append(store_dict)  # Already a dict
                
                if limit and len(stores) >= limit:
                    break
            if limit and len(stores) >= limit:
                break
        if limit and len(stores) >= limit:
            break
    
    return {
        'stores': stores,
        'count': len(stores),
        'checkpoints_used': False
    }
```

**Note on bestbuy:** May need additional work to complete extraction logic before implementing `run()`.

### 4. Add Checkpoint Support

Integrate existing checkpoint utilities with specific implementation details:

**Checkpoint Timing:**
- Save checkpoint every N stores (from `config['checkpoint_interval']`, default 100)
- Example: `checkpoint_interval = config.get('checkpoint_interval', 100)`

**Checkpoint Location:**
- Path: `data/{retailer}/checkpoints/scrape_progress.json`
- Create directory if it doesn't exist: `Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)`

**Checkpoint Format:**
```python
{
    'completed_count': int,           # Number of stores processed
    'completed_urls': List[str],      # URLs/IDs already processed
    'stores': List[dict],             # Store data collected so far
    'last_updated': str               # ISO timestamp
}
```

**Resume Logic:**
```python
def run(session, config, **kwargs):
    resume = kwargs.get('resume', False)
    checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
    
    stores = []
    completed_urls = set()
    
    # Load checkpoint if resuming
    if resume:
        checkpoint = utils.load_checkpoint(checkpoint_path)
        if checkpoint:
            stores = checkpoint.get('stores', [])
            completed_urls = set(checkpoint.get('completed_urls', []))
            logging.info(f"Resuming from checkpoint: {len(stores)} stores already collected")
    
    # Discovery phase (skip already completed)
    all_urls = get_store_urls_from_sitemap(session)
    remaining_urls = [url for url in all_urls if url not in completed_urls]
    
    # Process remaining URLs
    for i, url in enumerate(remaining_urls):
        store = extract_store_details(session, url)
        if store:
            stores.append(store.to_dict())
            completed_urls.add(url)
        
        # Save checkpoint periodically
        if (i + 1) % checkpoint_interval == 0:
            utils.save_checkpoint({
                'completed_count': len(stores),
                'completed_urls': list(completed_urls),
                'stores': stores,
                'last_updated': datetime.now().isoformat()
            }, checkpoint_path)
    
    return {
        'stores': stores,
        'count': len(stores),
        'checkpoints_used': resume and checkpoint is not None
    }
```

**Note:** Initial implementation may use basic checkpoint support. Full resume capability can be added in a later enhancement.

### 5. Add Output Handling

**Directory Structure:**
```
data/
  └── {retailer}/
      ├── checkpoints/
      │   └── scrape_progress.json
      ├── output/
      │   ├── stores_latest.json
      │   └── stores_latest.csv
      └── history/
          └── (for future change detection)
```

**Output Files:**
- JSON: `data/{retailer}/output/stores_latest.json`
- CSV: `data/{retailer}/output/stores_latest.csv`

**Implementation in run.py:**
```python
async def run_retailer_async(retailer: str, ...):
    # ... existing session creation ...
    
    # Call scraper
    result = scraper_module.run(session, retailer_config, **kwargs)
    
    # Extract data
    stores = result.get('stores', [])
    count = result.get('count', 0)
    
    # Save outputs
    output_dir = f"data/{retailer}/output"
    json_path = f"{output_dir}/stores_latest.json"
    csv_path = f"{output_dir}/stores_latest.csv"
    
    utils.save_to_json(stores, json_path)
    
    # Get fieldnames from config or use default
    fieldnames = retailer_config.get('output_fields')
    utils.save_to_csv(stores, csv_path, fieldnames=fieldnames)
    
    # Update result dict
    result_dict = {
        'retailer': retailer,
        'status': 'completed',
        'stores': count,
        'error': None
    }
    
    return result_dict
```

**CSV Field Names:**
- Read from `config['output_fields']` in retailers.yaml
- Fall back to all keys if not specified
- Example: `['store_id', 'name', 'street_address', 'city', 'state', 'zip', 'phone', 'url', 'scraped_at']`

**Error Handling:**
```python
try:
    result = scraper_module.run(session, retailer_config, **kwargs)
    # ... save outputs ...
except Exception as e:
    logging.error(f"[{retailer}] Scraper failed: {e}")
    return {
        'retailer': retailer,
        'status': 'error',
        'stores': 0,
        'error': str(e)
    }
```

**Partial Results:**
- If scraper raises exception, return what was saved in checkpoint (if any)
- Log error but don't crash
- Mark status as 'partial' if some stores were collected

## Implementation Details & Clarifications

### Async/Sync Pattern
- **Scraper `run()` functions**: SYNCHRONOUS (regular functions, not async)
- **run_retailer_async()**: Async wrapper that calls synchronous scrapers
- Rationale: All scrapers use `requests` (sync), not `aiohttp`. Converting to async would require major refactor.

### Request Counter Management
Each scraper has a global `_request_counter` that needs proper handling:

```python
def run(session, config, **kwargs):
    # IMPORTANT: Reset counter at start of run
    reset_request_counter()
    
    # ... scraping logic ...
    
    # Counter is automatically incremented in helper functions
    # (get_store_urls_from_sitemap, extract_store_details, etc.)
```

**Why reset?**
- Prevents counter from carrying over between runs
- Ensures pause logic works correctly (e.g., pause after 50 requests)

### kwargs Handling

**Supported in initial implementation:**
- `limit`: int - Limit number of stores to process
- `resume`: bool - Resume from checkpoint (basic support)

**Deferred to later:**
- `incremental`: bool - Only process changes (requires change detection system)
- `render_js`: bool - Handled by ProxyClient, transparent to scrapers
- `proxy_country`: str - Handled by ProxyClient, transparent to scrapers

**Access pattern:**
```python
def run(session, config, **kwargs):
    limit = kwargs.get('limit')
    resume = kwargs.get('resume', False)
    # incremental = kwargs.get('incremental', False)  # Deferred
```

### Retailer Name Extraction

Scrapers need to know their own name for checkpoint paths:

```python
def run(session, config, **kwargs):
    retailer_name = config.get('name', 'unknown').lower()
    checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
```

**Note:** `config['name']` comes from retailers.yaml (e.g., "Walmart", "AT&T")

## Source Code Changes

### Files to Modify

1. **run.py:195-234** - `run_retailer_async()` _(corrected line number)_
   - Call `scraper_module.run(session, retailer_config, **kwargs)`
   - Save outputs using `utils.save_to_json()` and `utils.save_to_csv()`
   - Update result dict with actual counts
   - Add try/except error handling
   - Handle partial results

2. **src/scrapers/walmart.py** - Add `run()` function (Pattern A)
   - Integrate `get_store_urls_from_sitemap()` and `extract_store_details()`
   - Reset request counter
   - Support limit parameter
   - Basic checkpoint support (optional in v1)

3. **src/scrapers/att.py** - Add `run()` function (Pattern A)
4. **src/scrapers/tmobile.py** - Add `run()` function (Pattern A)
5. **src/scrapers/target.py** - Add `run()` function (Pattern B)
6. **src/scrapers/verizon.py** - Add `run()` function (Pattern C)
7. **src/scrapers/bestbuy.py** - Add `run()` function (Pattern B, may need extraction fixes)

### No New Files
All changes are additions/modifications to existing files.

## Data Model Changes

### Interface Contract (Informal)

No formal interface class needed, but all scrapers follow:
- Function name: `run`
- Parameters: `(session, config, **kwargs)`
- Return type: `dict` with `stores`, `count`, `checkpoints_used`

### Return Value Schema

```python
{
    'stores': List[dict],        # Store data in dict format
    'count': int,                # Number of stores scraped
    'checkpoints_used': bool     # Whether resumed from checkpoint
}
```

## Addressed Review Feedback

### ✅ Scraper Implementation Diversity
- Documented 3 distinct patterns (A: sitemap, B: API, C: multi-phase)
- Created pattern-specific implementation templates
- Verified each scraper's discovery method and return type

### ✅ Data Model Compatibility
- Verified all scrapers except verizon use dataclasses with `to_dict()`
- Verizon returns `Dict[str, Any]` directly - handled in Pattern C
- Documented return type for each scraper in comparison table

### ✅ Checkpoint Integration Details
- Specified checkpoint timing (every N stores from config)
- Defined checkpoint file location and format
- Provided complete resume logic example
- Noted as "optional in v1" to allow basic implementation first

### ✅ Error Handling Patterns
- Added try/except in run.py integration
- Defined partial results handling
- Specified error status codes ('error', 'partial', 'completed')

### ✅ Request Counter State Management
- Explicitly documented `reset_request_counter()` at start of `run()`
- Explained why reset is necessary (prevent carry-over between runs)

### ✅ kwargs Handling
- Documented supported kwargs (limit, resume)
- Explicitly deferred incremental mode (requires change detection)
- Clarified that render_js and proxy_country are handled by ProxyClient

### ✅ Async/Sync Pattern
- Clarified scrapers are SYNCHRONOUS (regular functions)
- Explained run_retailer_async is async wrapper
- Rationale: all scrapers use `requests`, not `aiohttp`

### ✅ Output File Paths and Directory Structure
- Specified exact paths: `data/{retailer}/output/stores_latest.json`
- Documented directory structure (checkpoints/, output/, history/)
- Noted data/ directory doesn't exist yet (will be created by utils functions)
- Confirmed CSV fieldnames come from `config['output_fields']`

### ✅ Testing Infrastructure
- Verified pytest exists in requirements.txt
- Provided specific test commands
- Noted syntax check as minimum verification

## Verification Approach

### Testing Strategy

**Prerequisites:**
```bash
# Verify pytest is available
grep pytest requirements.txt
# Output: pytest>=7.4.0

# Install dependencies if needed
pip install -r requirements.txt
```

**Phase 1: Syntax Verification**
```bash
# Verify all Python files compile
python -m py_compile run.py
python -m py_compile src/scrapers/walmart.py
python -m py_compile src/scrapers/att.py
python -m py_compile src/scrapers/tmobile.py
python -m py_compile src/scrapers/target.py
python -m py_compile src/scrapers/verizon.py
python -m py_compile src/scrapers/bestbuy.py
```

**Phase 2: Basic Integration Test**
```bash
# Test single retailer with small limit
python run.py --retailer walmart --limit 5 --verbose

# Verify output files were created
ls -lh data/walmart/output/
# Expected: stores_latest.json, stores_latest.csv

# Verify JSON structure
head -20 data/walmart/output/stores_latest.json
```

**Phase 3: Multi-Retailer Test**
```bash
# Test mode (10 stores each)
python run.py --all --test

# Check all output directories
ls -d data/*/output/
```

**Phase 4: Proxy Testing** (if credentials available)
```bash
# Direct mode (default)
python run.py --retailer target --limit 10 --verbose

# Residential proxy mode
python run.py --retailer att --proxy residential --limit 5
```

**Phase 5: Resume Testing**
```bash
# Start a longer scrape
python run.py --retailer walmart --limit 50 &
SCRAPER_PID=$!

# Wait a bit then interrupt
sleep 10
kill -INT $SCRAPER_PID

# Verify checkpoint exists
ls -lh data/walmart/checkpoints/

# Resume
python run.py --retailer walmart --resume --limit 50
```

### Success Criteria

**Must Have:**
- ✅ All 7 Python files compile without syntax errors
- ✅ All 6 scrapers have `run(session, config, **kwargs)` function
- ✅ Sessions are passed from run.py to scrapers
- ✅ Output files created: `data/{retailer}/output/stores_latest.{json,csv}`
- ✅ `--limit` parameter works (stops after N stores)
- ✅ `--test` mode runs without errors
- ✅ No crashes in `--all` mode

**Should Have:**
- ✅ Logs show session type (ProxyClient vs Session based on mode)
- ✅ CSV files have proper headers from config
- ✅ JSON files contain valid store data
- ✅ Request counters reset between runs

**Nice to Have:**
- ✅ Checkpoint files created when enabled
- ✅ Resume functionality works
- ✅ Proxy modes are utilized correctly

## Implementation Complexity

**Estimated Lines of Code:**
- `run.py`: ~40 lines modified/added
- Each scraper: ~30-50 lines per `run()` function
- Total: ~250-350 lines across 7 files

**Key Challenges:**
1. Maintaining backward compatibility with existing helper functions
2. Handling different discovery methods (sitemap vs HTML crawl vs API)
3. Async wrapper around synchronous scrapers
4. Error handling and partial results

**Risk Mitigation:**
- Start with simplest scraper (walmart or att)
- Test incrementally
- Keep existing functions unchanged
- Add defensive error handling
