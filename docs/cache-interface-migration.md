# Cache Interface Migration Guide

## Overview

Issue #154 introduces a unified caching interface (`cache_interface.py`) that provides consistent TTL and refresh behavior across all cache types. This guide shows how to migrate from legacy caching to the new interface.

## Benefits

- **Consistent API**: All cache types use the same interface
- **Unified refresh semantics**: `force_refresh` parameter works the same across all caches
- **Type safety**: Generic typing for better IDE support
- **Better metadata**: Consistent cache age tracking
- **Extensible**: Easy to add new cache types

## Cache Types

### URLListCache
Cache for simple URL lists (sitemap URLs, store URLs).

**Before (legacy URLCache):**
```python
from src.shared.cache import URLCache

cache = URLCache('target')
urls = cache.get()
if urls is None:
    urls = discover_urls(session)
    cache.set(urls)
```

**After (new URLListCache):**
```python
from src.shared.cache_interface import URLListCache

cache = URLListCache('target')
# Pass force_refresh from CLI args
urls = cache.get('target', force_refresh=kwargs.get('refresh_urls', False))
if urls is None:
    urls = discover_urls(session)
    cache.set('target', urls)
```

**Key differences:**
- `get()` takes identifier and optional `force_refresh` parameter
- `set()` takes identifier as first argument
- Same TTL behavior (7 days default)

### RichURLCache
Cache for URL lists with metadata (e.g., store_id, slug).

**Before (legacy RichURLCache):**
```python
from src.shared.cache import RichURLCache

cache = RichURLCache('target')
stores = cache.get_rich()
if stores is None:
    stores = discover_stores_with_metadata(session)
    cache.set_rich(stores)
```

**After (new RichURLCache):**
```python
from src.shared.cache_interface import RichURLCache

cache = RichURLCache('target')
# Pass force_refresh from CLI args
stores = cache.get('target', force_refresh=kwargs.get('refresh_urls', False))
if stores is None:
    stores = discover_stores_with_metadata(session)
    cache.set('target', stores)
```

**Key differences:**
- Use `get()` instead of `get_rich()`
- Use `set()` instead of `set_rich()`
- Same parameter structure, cleaner API

### ResponseCache
Cache for HTTP responses (NEW - previously only in Walmart scraper).

**Before (Walmart-specific response cache):**
```python
# From walmart.py
def _get_cached_response(url: str, retailer: str) -> Optional[str]:
    cache_dir = _get_response_cache_dir(retailer)
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    cache_file = cache_dir / f"{url_hash}.json"
    # ... manual cache file handling

def _cache_response(url: str, html: str, retailer: str) -> None:
    cache_dir = _get_response_cache_dir(retailer)
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    # ... manual cache file writing
```

**After (unified ResponseCache):**
```python
from src.shared.cache_interface import ResponseCache

# Initialize once (at module or function level)
response_cache = ResponseCache('walmart', ttl_days=30)

# Use throughout scraper
html = response_cache.get(store_url, force_refresh=kwargs.get('refresh', False))
if html is None:
    html = fetch_store_page(session, store_url)
    response_cache.set(store_url, html)
```

**Key benefits:**
- No manual cache directory management
- Automatic TTL handling
- Consistent with other cache types
- Easy to add to any scraper

## Migration Checklist

### For Existing Scrapers Using URLCache

1. **Import the new cache**:
   ```python
   # Old
   from src.shared.cache import URLCache

   # New
   from src.shared.cache_interface import URLListCache
   ```

2. **Update cache initialization** (no change needed):
   ```python
   cache = URLListCache('retailer_name')
   ```

3. **Update cache.get() calls**:
   ```python
   # Old
   urls = cache.get()

   # New
   urls = cache.get('retailer_name', force_refresh=kwargs.get('refresh_urls', False))
   ```

4. **Update cache.set() calls**:
   ```python
   # Old
   cache.set(urls)

   # New
   cache.set('retailer_name', urls)
   ```

### For Existing Scrapers Using RichURLCache

1. **Import the new cache**:
   ```python
   # Old
   from src.shared.cache import RichURLCache

   # New
   from src.shared.cache_interface import RichURLCache
   ```

2. **Update method calls**:
   ```python
   # Old
   stores = cache.get_rich()
   cache.set_rich(stores)

   # New
   stores = cache.get('retailer_name', force_refresh=kwargs.get('refresh_urls', False))
   cache.set('retailer_name', stores)
   ```

### For Adding Response Caching (Walmart Example)

1. **Remove manual cache functions**:
   - Delete `_get_response_cache_dir()`
   - Delete `_get_cached_response()`
   - Delete `_cache_response()`

2. **Initialize ResponseCache at module level**:
   ```python
   from src.shared.cache_interface import ResponseCache
   from src.shared.constants import CACHE

   # Initialize once
   _response_cache = None

   def get_response_cache(retailer: str) -> ResponseCache:
       global _response_cache
       if _response_cache is None:
           _response_cache = ResponseCache(retailer, ttl_days=CACHE.RESPONSE_CACHE_EXPIRY_DAYS)
       return _response_cache
   ```

3. **Use in scraping functions**:
   ```python
   def scrape_store(session, url: str, retailer: str, **kwargs):
       cache = get_response_cache(retailer)

       # Try cache first
       html = cache.get(url, force_refresh=kwargs.get('refresh', False))

       if html is None:
           # Fetch from API/web
           html = fetch_store_page(session, url)
           cache.set(url, html)

       # Parse cached or fresh HTML
       store_data = parse_html(html)
       return store_data
   ```

## CLI Flag Behavior

The new interface standardizes flag behavior:

| Flag | Purpose | Cache Type | Effect |
|------|---------|-----------|--------|
| `--refresh-urls` | Re-discover store URLs | URLListCache, RichURLCache | Bypasses URL discovery cache |
| `--refresh` | Re-fetch responses | ResponseCache | Bypasses response cache |

**Implementation pattern:**
```python
def run(session, retailer_config, retailer: str, **kwargs):
    # URL discovery phase
    url_cache = URLListCache(retailer)
    urls = url_cache.get(retailer, force_refresh=kwargs.get('refresh_urls', False))

    if urls is None:
        urls = discover_urls(session)
        url_cache.set(retailer, urls)

    # Store scraping phase
    response_cache = ResponseCache(retailer)
    stores = []

    for url in urls:
        html = response_cache.get(url, force_refresh=kwargs.get('refresh', False))

        if html is None:
            html = fetch_page(session, url)
            response_cache.set(url, html)

        store = parse_html(html)
        stores.append(store)

    return {'stores': stores, 'count': len(stores)}
```

## Testing Migration

After migrating, ensure:

1. **Cache files are compatible**:
   - Legacy cache files should still work (backward compatible)
   - New cache files use updated format with metadata wrapper

2. **Force refresh works**:
   ```bash
   # Should bypass URL cache
   python run.py --retailer target --refresh-urls

   # Should bypass response cache
   python run.py --retailer walmart --refresh
   ```

3. **TTL expiry works**:
   - Check that old cache files expire correctly
   - Verify metadata shows correct age

4. **Unit tests pass**:
   ```bash
   pytest tests/test_cache_interface.py -v
   ```

## Example: Complete Migration (Target Scraper)

**Before:**
```python
from src.shared.cache import RichURLCache

def run(session, retailer_config, retailer: str, **kwargs):
    cache = RichURLCache(retailer)

    # Check cache
    stores = cache.get_rich()

    if stores is None:
        # Discover stores
        stores = discover_stores(session)
        cache.set_rich(stores)

    return {'stores': stores, 'count': len(stores)}
```

**After:**
```python
from src.shared.cache_interface import RichURLCache

def run(session, retailer_config, retailer: str, **kwargs):
    cache = RichURLCache(retailer)

    # Check cache with refresh support
    stores = cache.get(retailer, force_refresh=kwargs.get('refresh_urls', False))

    if stores is None:
        # Discover stores
        stores = discover_stores(session)
        cache.set(retailer, stores)

    return {'stores': stores, 'count': len(stores)}
```

## Backward Compatibility

The legacy `URLCache` and `RichURLCache` classes in `src/shared/cache.py` remain available for backward compatibility. They will continue to work but should be migrated to the new interface over time.

## Future Enhancements

The unified interface makes it easy to add new cache types:

- **StateCache**: Cache state-specific data for targeted scraping
- **APIResponseCache**: Cache API responses with request parameters
- **SitemapCache**: Cache sitemap XML with compression
- **StoreDataCache**: Cache parsed store data between runs

All would share the same consistent API and TTL behavior.
