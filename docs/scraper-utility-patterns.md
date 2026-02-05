# Scraper Utility Patterns and Anti-Duplication Guide

This document provides guidance on using shared utilities in scrapers and avoiding common code duplication patterns identified during PR #225 code review.

## Table of Contents

1. [Overview](#overview)
2. [Core Principles](#core-principles)
3. [Common Patterns](#common-patterns)
4. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
5. [Reference Implementation](#reference-implementation)

## Overview

The `src/shared/scraper_utils.py` module provides reusable utilities for scraper `run()` functions to eliminate code duplication across all retailer scrapers. These utilities handle common concerns like checkpoint management, failed item tracking, validation, and progress logging.

**Key Benefits:**
- Reduces code duplication by 40-60% in scraper run() functions
- Standardizes error handling and logging patterns
- Centralizes checkpoint and resume logic
- Simplifies scraper implementation to focus on retailer-specific extraction

## Core Principles

### 1. Use Shared Utilities for Common Operations

Always prefer shared utilities over local implementations for:
- Checkpoint loading/saving
- Failed item tracking
- URL caching
- Progress logging
- Validation summaries

### 2. Avoid Function Duplication

Before writing a helper function in a scraper:
1. Check if equivalent functionality exists in `scraper_utils.py`
2. Check if it exists in `src/shared/utils.py`
3. If needed in multiple scrapers, add to shared utilities instead

### 3. Proper Attribute Access

When accessing object attributes, verify the correct attribute name:
- URLCache and RichURLCache use `.retailer` (not `.retailer_name`)
- Use `getattr()` with proper defaults for optional attributes
- Check class definitions when unsure

### 4. Follow Python Conventions

- Import statements at module level (not inside functions)
- Use Google-style docstrings with Args, Returns, Raises sections
- Follow PEP 8 style guidelines

## Common Patterns

### Pattern 1: Initialize Run Context

Use `initialize_run_context()` to set up all common scraper state:

```python
from src.shared.scraper_utils import initialize_run_context

def run(session, config: dict, **kwargs) -> dict:
    # Initialize context with checkpoint loading, config parsing, etc.
    context = initialize_run_context(
        retailer_name='target',
        config=config,
        resume=kwargs.get('resume', False)
    )

    # Access context fields
    checkpoint_path = context.checkpoint_path
    completed_ids = context.completed_ids
    stores = context.stores
    # ... etc
```

**What it provides:**
- Checkpoint path configuration
- Checkpoint loading with resume support
- Checkpoint interval and parallel workers from config
- Initialized stores list and completed IDs set
- Request counter initialization

### Pattern 2: Load URLs with Caching

Use `load_urls_with_cache()` for URL discovery with automatic caching:

```python
from src.shared.cache import RichURLCache
from src.shared.scraper_utils import load_urls_with_cache

def run(session, config: dict, **kwargs) -> dict:
    context = initialize_run_context('target', config, kwargs.get('resume'))

    # Set up cache
    cache = RichURLCache('target')

    # Load URLs with caching (automatically fetches if cache expired)
    store_urls = load_urls_with_cache(
        cache=cache,
        fetch_callback=lambda: discover_store_urls(session),
        refresh_urls=kwargs.get('refresh_urls', False)
    )
```

**Features:**
- Automatic cache expiry checking
- Fallback to fetch function if cache invalid
- Logging with correct retailer name
- Support for both URLCache and RichURLCache

### Pattern 3: Filter Remaining Items

Use `filter_remaining_items()` to handle resume logic and limits:

```python
from src.shared.scraper_utils import filter_remaining_items

def run(session, config: dict, **kwargs) -> dict:
    context = initialize_run_context('target', config, kwargs.get('resume'))
    all_urls = load_urls_with_cache(...)

    # Filter out completed items and apply limits
    remaining_urls = filter_remaining_items(
        all_items=all_urls,
        completed_ids=context.completed_ids,
        limit=kwargs.get('limit'),
        current_store_count=len(context.stores),
        retailer_name=context.retailer_name
    )
```

**What it does:**
- Filters out already completed items (for resume)
- Applies CLI --limit if specified
- Logs remaining item count
- Returns only items that need processing

### Pattern 4: Save Checkpoints

Use `save_checkpoint_if_needed()` for automatic checkpointing:

```python
from src.shared.scraper_utils import save_checkpoint_if_needed

def run(session, config: dict, **kwargs) -> dict:
    context = initialize_run_context('target', config, kwargs.get('resume'))
    # ... processing loop

    for i, url in enumerate(remaining_urls, start=1):
        store_data = extract_store(url)
        context.stores.append(store_data)
        context.completed_ids.add(store_id)

        # Automatically saves checkpoint at configured intervals
        save_checkpoint_if_needed(context, i)
```

**Features:**
- Only saves at configured intervals (default: every 100 items)
- Includes stores and completed_ids
- Logs checkpoint saves
- Use `force=True` for final checkpoint

### Pattern 5: Finalize Run

Use `finalize_scraper_run()` to wrap up scraper execution:

```python
from src.shared.scraper_utils import finalize_scraper_run

def run(session, config: dict, **kwargs) -> dict:
    context = initialize_run_context('target', config, kwargs.get('resume'))
    failed_store_ids = []

    # ... extraction loop, populate failed_store_ids

    # Finalize handles: validation, final checkpoint, failed items logging/saving
    return finalize_scraper_run(
        context,
        failed_items=failed_store_ids,
        item_key="failed_store_ids"
    )
```

**What it handles:**
- Final checkpoint save (force=True)
- Validation summary logging
- Failed items logging
- Failed items file save (failed_extractions.json)
- Returns standard result dict

## Anti-Patterns to Avoid

### Anti-Pattern 1: Duplicate Failed Item Saving

**DON'T DO THIS:**
```python
def run(session, config: dict, **kwargs) -> dict:
    # ... extraction

    # Manual save (redundant)
    if failed_store_ids:
        _save_failed_extractions(retailer_name, failed_store_ids)

    # finalize_scraper_run also saves failed items!
    return finalize_scraper_run(context, failed_items=failed_store_ids)
```

**Issue:** Failed items saved twice to the same file.

**DO THIS INSTEAD:**
```python
def run(session, config: dict, **kwargs) -> dict:
    # ... extraction

    # Only use finalize_scraper_run - it handles failed items
    return finalize_scraper_run(context, failed_items=failed_store_ids, item_key="failed_store_ids")
```

### Anti-Pattern 2: Local Helper Functions for Common Operations

**DON'T DO THIS:**
```python
def _save_failed_extractions(retailer: str, failed_store_ids: List[int]) -> None:
    """Local function that duplicates shared utility."""
    failed_path = Path(f"data/{retailer}/failed_extractions.json")
    failed_path.parent.mkdir(parents=True, exist_ok=True)

    with open(failed_path, 'w', encoding='utf-8') as f:
        json.dump({
            'run_date': datetime.now().isoformat(),
            'failed_count': len(failed_store_ids),
            'failed_store_ids': failed_store_ids
        }, f, indent=2)
```

**Issue:** Duplicates `save_failed_items()` from scraper_utils.py.

**DO THIS INSTEAD:**
```python
# No local function needed - use shared utility
from src.shared.scraper_utils import finalize_scraper_run

# finalize_scraper_run() internally calls save_failed_items()
```

### Anti-Pattern 3: Wrong Attribute Names

**DON'T DO THIS:**
```python
retailer_name = getattr(cache, 'retailer_name', 'unknown')  # Wrong attribute!
```

**Issue:** URLCache/RichURLCache use `.retailer`, not `.retailer_name`. This causes logs to show `[unknown]` instead of actual retailer name.

**DO THIS INSTEAD:**
```python
retailer_name = getattr(cache, 'retailer', 'unknown')  # Correct attribute
```

### Anti-Pattern 4: Late Imports

**DON'T DO THIS:**
```python
def save_failed_items(...):
    import json  # PEP 8 violation
    # ... use json
```

**Issue:** Violates PEP 8 - imports should be at module level.

**DO THIS INSTEAD:**
```python
# At top of file
import json

def save_failed_items(...):
    # ... use json
```

### Anti-Pattern 5: Redundant Logging

**DON'T DO THIS:**
```python
def finalize_scraper_run(context, ...):
    if context.stores:
        save_checkpoint_if_needed(context, len(context.stores), force=True)
        # Redundant - save_checkpoint_if_needed already logs!
        logging.info(f"Final checkpoint saved: {len(context.stores)} stores total")
```

**Issue:** Produces duplicate log messages back-to-back.

**DO THIS INSTEAD:**
```python
def finalize_scraper_run(context, ...):
    if context.stores:
        # save_checkpoint_if_needed logs automatically
        save_checkpoint_if_needed(context, len(context.stores), force=True)
```

## Reference Implementation

Here's a complete example using all patterns correctly (based on target.py):

```python
"""Target scraper using shared utilities."""

import logging
from typing import List
import requests

from src.shared.cache import RichURLCache
from src.shared.scraper_utils import (
    initialize_run_context,
    load_urls_with_cache,
    filter_remaining_items,
    save_checkpoint_if_needed,
    log_progress,
    finalize_scraper_run,
)


def run(session: requests.Session, config: dict, **kwargs) -> dict:
    """Main scraper run function.

    Args:
        session: HTTP session for requests
        config: Retailer configuration dict
        **kwargs: CLI arguments (resume, limit, refresh_urls, etc.)

    Returns:
        Dict with 'stores', 'count', 'checkpoints_used' keys
    """
    # 1. Initialize context (checkpoint loading, config parsing)
    context = initialize_run_context(
        retailer_name='target',
        config=config,
        resume=kwargs.get('resume', False)
    )

    try:
        # 2. Load URLs with caching
        cache = RichURLCache('target')
        store_urls = load_urls_with_cache(
            cache=cache,
            fetch_callback=lambda: discover_all_store_urls(session),
            refresh_urls=kwargs.get('refresh_urls', False)
        )

        if not store_urls:
            logging.warning("[target] No store URLs discovered")
            return finalize_scraper_run(context)

        # 3. Filter remaining items (resume logic + limits)
        remaining_urls = filter_remaining_items(
            all_items=store_urls,
            completed_ids=context.completed_ids,
            limit=kwargs.get('limit'),
            current_store_count=len(context.stores),
            retailer_name=context.retailer_name
        )

        # 4. Extract stores with progress logging and checkpointing
        failed_store_ids = []

        for i, store_url in enumerate(remaining_urls, start=1):
            try:
                store_data = extract_store_details(session, store_url)
                context.stores.append(store_data)
                context.completed_ids.add(store_data['store_id'])
            except Exception as e:
                logging.warning(f"[target] Failed to extract {store_url}: {e}")
                failed_store_ids.append(store_url)

            # Progress logging
            log_progress(context.retailer_name, i, len(remaining_urls))

            # Automatic checkpointing
            save_checkpoint_if_needed(context, i)

        # 5. Finalize run (validation, failed items, final checkpoint)
        return finalize_scraper_run(
            context,
            failed_items=failed_store_ids,
            item_key="failed_store_ids"
        )

    except Exception as e:
        logging.error(f"[target] Fatal error: {e}", exc_info=True)
        raise


def discover_all_store_urls(session: requests.Session) -> List[dict]:
    """Retailer-specific URL discovery logic."""
    # Implementation specific to Target
    pass


def extract_store_details(session: requests.Session, url: str) -> dict:
    """Retailer-specific extraction logic."""
    # Implementation specific to Target
    pass
```

## Summary Checklist

When implementing or reviewing scraper code:

- [ ] Use `initialize_run_context()` instead of manual checkpoint loading
- [ ] Use `load_urls_with_cache()` instead of manual cache handling
- [ ] Use `filter_remaining_items()` for resume logic and limits
- [ ] Use `save_checkpoint_if_needed()` instead of manual checkpoint saves
- [ ] Use `finalize_scraper_run()` instead of manual validation/cleanup
- [ ] Verify correct attribute names (`.retailer` not `.retailer_name`)
- [ ] Import statements at module level (not inside functions)
- [ ] No duplicate functions that exist in shared utilities
- [ ] No duplicate operations (e.g., saving failed items twice)
- [ ] No redundant logging (utilities already log)

Following these patterns ensures consistent, maintainable scraper code with minimal duplication.

## Related Documentation

- `src/shared/scraper_utils.py` - Full API documentation
- `CLAUDE.md` - Project architecture and scraper interface
- PR #225 - Refactoring that established these patterns
