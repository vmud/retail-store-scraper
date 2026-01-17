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

**Pattern for each scraper:**

```python
# In each scraper module (e.g., walmart.py, bestbuy.py)

def run(session, config, **kwargs):
    """Implement standard interface"""
    limit = kwargs.get('limit')
    resume = kwargs.get('resume', False)
    
    # Use existing functions
    store_urls = get_store_urls_from_sitemap(session)
    if limit:
        store_urls = store_urls[:limit]
    
    stores = []
    for url in store_urls:
        store = extract_store_details(session, url)
        if store:
            stores.append(store.to_dict())
    
    return {
        'stores': stores,
        'count': len(stores),
        'checkpoints_used': False
    }
```

**Scrapers to update:**
- `src/scrapers/walmart.py`
- `src/scrapers/bestbuy.py`
- `src/scrapers/target.py`
- `src/scrapers/tmobile.py`
- `src/scrapers/att.py`
- `src/scrapers/verizon.py`

### 4. Add Checkpoint Support

Integrate existing checkpoint utilities:
- Use `utils.save_checkpoint()` and `utils.load_checkpoint()` 
- Checkpoint format: `{'completed_urls': [...], 'stores': [...]}`
- Save every N stores (from config.checkpoint_interval)

### 5. Add Output Handling

After scraper completes:
- Save to `data/{retailer}/output/stores_latest.json`
- Save to `data/{retailer}/output/stores_latest.csv`
- Use `utils.save_to_json()` and `utils.save_to_csv()`

## Source Code Changes

### Files to Modify

1. **run.py:194-234** - `run_retailer_async()`
   - Add scraper function call
   - Add output saving
   - Update result dict with actual counts

2. **src/scrapers/walmart.py** - Add `run()` function
   - Integrate `get_store_urls_from_sitemap()` and `extract_store_details()`
   - Add limit support
   - Add basic checkpoint support

3. **src/scrapers/bestbuy.py** - Add `run()` function
   - Integrate `get_all_store_ids()` and existing extraction logic
   - Add limit support
   
4. **src/scrapers/target.py** - Add `run()` function
5. **src/scrapers/tmobile.py** - Add `run()` function
6. **src/scrapers/att.py** - Add `run()` function
7. **src/scrapers/verizon.py** - Add `run()` function

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

## Verification Approach

### Testing Strategy

1. **Unit Tests** (if test framework exists)
   - Test each scraper's `run()` function with mock session
   - Verify return value structure
   - Test limit parameter

2. **Integration Testing**
   ```bash
   # Test single retailer with limit
   python run.py --retailer walmart --limit 5 --verbose
   
   # Verify output files exist
   ls data/walmart/output/
   
   # Test with test mode
   python run.py --all --test  # 10 stores per retailer
   ```

3. **Proxy Testing**
   ```bash
   # Test with different proxy modes
   python run.py --retailer target --proxy direct --limit 10
   python run.py --retailer walmart --proxy web_scraper_api --limit 5
   ```

4. **Resume Testing**
   ```bash
   # Start scraping
   python run.py --retailer bestbuy --limit 100
   
   # Interrupt (Ctrl+C)
   # Resume
   python run.py --retailer bestbuy --resume
   ```

### Success Criteria

- ✅ All 6 scrapers have `run()` function
- ✅ Sessions are passed and used by scrapers
- ✅ Output files are created in `data/{retailer}/output/`
- ✅ `--limit` parameter works correctly
- ✅ `--test` mode runs 10 stores per retailer
- ✅ No errors in `--all` mode
- ✅ Proxy modes are utilized (check logs for "ProxyClient" vs "Session")

### Lint/Test Commands

Based on project structure:
```bash
# Check if requirements.txt has test dependencies
cat requirements.txt | grep -i pytest

# Run any existing tests
pytest tests/ -v

# Verify Python syntax
python -m py_compile run.py
python -m py_compile src/scrapers/*.py
```

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
