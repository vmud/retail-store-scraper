# ScrapeRunner Migration Guide

This guide explains how to migrate existing scrapers to use the new shared `ScrapeRunner` orchestration framework.

## Problem Statement

Prior to Issue #150, scrapers like AT&T, Target, T-Mobile, Best Buy, and Verizon duplicated ~200 lines of orchestration logic for:
- URL caching (7-day cache to skip sitemap fetches)
- Checkpoint/resume (atomic saves with completed URL tracking)
- Parallel extraction (ThreadPoolExecutor with configurable workers)
- Progress logging
- Request tracking and rate limiting
- Store validation

This duplication caused:
- **Regression risk**: Bug fixes had to be applied to 5+ files
- **Inconsistent behavior**: Scrapers diverged over time
- **Maintenance burden**: Code reviews had to check all scrapers

## Solution: Unified ScrapeRunner

The `ScrapeRunner` class in `src/shared/scrape_runner.py` consolidates all orchestration logic into a single, well-tested component.

## Migration Pattern

### Before (Original AT&T scraper)

```python
def run(session, config: dict, **kwargs) -> dict:
    # ~200 lines of orchestration logic
    url_cache = URLCache(retailer)
    store_urls = url_cache.get()
    if not store_urls:
        store_urls = get_store_urls_from_sitemap(...)
        url_cache.set(store_urls)

    if resume:
        checkpoint = utils.load_checkpoint(...)
        stores = checkpoint['stores']
        completed_urls = checkpoint['completed_urls']

    if parallel_workers > 1:
        with ThreadPoolExecutor(...) as executor:
            # parallel extraction logic
    else:
        # sequential extraction logic

    # validation, final checkpoint, etc.
```

### After (Migrated AT&T scraper)

```python
def run(session, config: dict, **kwargs) -> dict:
    """Standard scraper entry point with unified orchestration."""
    retailer_name = kwargs.get('retailer', 'att')

    # Reset global counter for backwards compatibility
    reset_request_counter()

    # Create scraper context
    context = ScraperContext(
        retailer=retailer_name,
        session=session,
        config=config,
        resume=kwargs.get('resume', False),
        limit=kwargs.get('limit'),
        refresh_urls=kwargs.get('refresh_urls', False),
        use_rich_cache=False  # AT&T uses simple URL cache
    )

    # Create and run scraper with unified orchestration
    runner = ScrapeRunner(context)

    return runner.run_with_checkpoints(
        url_discovery_func=get_store_urls_from_sitemap,
        extraction_func=extract_store_details,
        item_key_func=lambda url: url  # Use URL as unique key
    )
```

**Result**: 38 lines of orchestration reduced to ~20 lines of configuration.

## Step-by-Step Migration

### 1. Identify Discovery and Extraction Functions

Every scraper has two core operations:
- **URL Discovery**: Fetches list of store URLs/IDs (usually from sitemap)
- **Store Extraction**: Fetches details for a single store

Example from AT&T:
```python
def get_store_urls_from_sitemap(session, retailer, yaml_config, request_counter) -> List[str]:
    """Discovery function"""
    # Returns list of URLs

def extract_store_details(session, url, retailer, yaml_config, request_counter) -> Optional[ATTStore]:
    """Extraction function"""
    # Returns store data or None
```

### 2. Update Function Signatures (if needed)

Ensure functions accept these parameters:
```python
def discovery_func(
    session,
    retailer: str,
    yaml_config: dict,
    request_counter: RequestCounter,
    **kwargs
) -> List[Any]:
    pass

def extraction_func(
    session,
    item: Any,  # URL or store info dict
    retailer: str,
    yaml_config: dict,
    request_counter: RequestCounter,
    **kwargs
) -> Optional[StoreDataClass]:
    pass
```

### 3. Replace `run()` Function

```python
from src.shared.scrape_runner import ScrapeRunner, ScraperContext

def run(session, config: dict, **kwargs) -> dict:
    retailer_name = kwargs.get('retailer', 'your_retailer')

    # Reset any global state (for backward compatibility)
    reset_request_counter()

    # Create context
    context = ScraperContext(
        retailer=retailer_name,
        session=session,
        config=config,
        resume=kwargs.get('resume', False),
        limit=kwargs.get('limit'),
        refresh_urls=kwargs.get('refresh_urls', False),
        use_rich_cache=False  # Change to True if using RichURLCache
    )

    # Run with ScrapeRunner
    runner = ScrapeRunner(context)
    return runner.run_with_checkpoints(
        url_discovery_func=get_store_urls_from_sitemap,
        extraction_func=extract_store_details,
        item_key_func=lambda url: url  # Or extract store_id from dict
    )
```

### 4. Choose Cache Type

- **URLCache**: For simple URL lists (AT&T, T-Mobile, Best Buy)
  ```python
  use_rich_cache=False
  ```

- **RichURLCache**: For URLs with metadata (Target stores store_id + slug)
  ```python
  use_rich_cache=True
  ```

### 5. Define Item Key Function

The `item_key_func` extracts a unique identifier from each item for checkpoint tracking.

**Simple URL strings:**
```python
item_key_func=lambda url: url
```

**Store info dicts:**
```python
item_key_func=lambda info: info['store_id']  # Target
```

## What Gets Handled Automatically

The `ScrapeRunner` handles:

1. **URL Caching**
   - Checks cache first (7-day expiry by default)
   - Calls discovery function on cache miss
   - Saves discovered URLs to cache

2. **Checkpoint/Resume**
   - Loads checkpoint if `resume=True`
   - Filters already-completed items
   - Saves checkpoints at intervals

3. **Parallel vs Sequential**
   - Auto-selects based on `parallel_workers` config
   - Creates session factory for parallel mode
   - Handles thread-safe progress tracking

4. **Progress Logging**
   - Logs every 50 items processed
   - Shows success rate in parallel mode
   - Reports final validation summary

5. **Error Handling**
   - Captures failed items
   - Saves failed items to JSON
   - Prevents worker thread crashes

6. **Validation**
   - Runs batch validation at end
   - Logs validation summary

## Backward Compatibility

### Deprecated Internal Functions

For test compatibility, keep deprecated functions with docstring warnings:

```python
def _extract_single_store(...):
    """Worker function for parallel store extraction.

    DEPRECATED: This function is kept for backward compatibility with tests.
    New code should use ScrapeRunner instead.
    """
    # Original implementation
```

### Global Request Counter

If scraper uses a global `_request_counter`, reset it for backward compatibility:

```python
def run(session, config: dict, **kwargs) -> dict:
    reset_request_counter()  # Reset global counter
    # ... rest of ScrapeRunner code
```

## Testing

### Unit Tests for ScrapeRunner

See `tests/test_scrape_runner.py` for comprehensive tests:
- ScraperContext creation
- Checkpoint load/save
- URL caching
- Orchestration flow
- Limit handling

### Integration Tests

Existing scraper tests should continue to pass. If tests patch internal functions, consider:
1. Keeping deprecated stubs (as done with `_extract_single_store`)
2. Updating tests to patch `src.shared.scrape_runner` components
3. Creating new integration tests that test the full `run()` flow

## Migration Checklist

- [ ] Identify discovery and extraction functions
- [ ] Ensure function signatures match expected pattern
- [ ] Replace `run()` function with ScrapeRunner pattern
- [ ] Choose URLCache or RichURLCache
- [ ] Define item_key_func
- [ ] Keep deprecated functions if needed for tests
- [ ] Run existing tests
- [ ] Verify scraper works with test mode: `python run.py --retailer X --test`
- [ ] Update any scraper-specific documentation

## Benefits

1. **Single source of truth**: Bug fixes apply to all scrapers
2. **Consistent behavior**: All scrapers work identically
3. **Less code**: ~200 lines reduced to ~20 lines per scraper
4. **Better tested**: ScrapeRunner has dedicated unit tests
5. **Easier to maintain**: Changes happen in one place
6. **Easier to understand**: Clear separation of concerns

## Next Steps

Migrate scrapers in order of complexity:

1. ✅ **AT&T** (pilot - COMPLETE)
2. **T-Mobile** (similar pattern to AT&T)
3. **Best Buy** (similar pattern to AT&T)
4. **Target** (uses RichURLCache)
5. **Verizon** (multi-phase, most complex)

## Questions?

See `src/shared/scrape_runner.py` docstrings for detailed API documentation.
