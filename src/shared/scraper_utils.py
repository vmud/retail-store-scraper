"""Shared utilities for scraper run() functions to reduce code duplication.

This module provides common patterns used across all scrapers:
- Checkpoint loading/saving
- URL cache handling
- Progress logging
- Validation summary logging
- Request counter initialization
- Delay selection
- Worker configuration

Addresses Issue #169: Reduce code duplication in scraper run() functions
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from src.shared import utils
from src.shared.cache import URLCache, RichURLCache
from src.shared.constants import WORKERS
from src.shared.request_counter import RequestCounter


@dataclass
class ScraperRunContext:
    """Context object holding common scraper run state.

    This encapsulates the common state and configuration that all scrapers need,
    reducing duplication in run() functions.

    Attributes:
        retailer_name: Name of the retailer (e.g., 'att', 'target')
        config: Retailer configuration from retailers.yaml
        stores: List of scraped store dictionaries
        completed_ids: Set of completed store IDs (for resume)
        checkpoints_used: Whether checkpoint resume was used
        request_counter: RequestCounter instance for rate limiting
        checkpoint_path: Path to checkpoint file
        checkpoint_interval: How often to save checkpoints
        min_delay: Minimum delay between requests
        max_delay: Maximum delay between requests
        parallel_workers: Number of parallel worker threads
        proxy_mode: Proxy mode ('direct', 'residential', 'web_scraper_api')
    """
    retailer_name: str
    config: Dict[str, Any]
    stores: List[Dict[str, Any]] = field(default_factory=list)
    completed_ids: Set[Union[str, int]] = field(default_factory=set)
    checkpoints_used: bool = False
    request_counter: RequestCounter = field(default_factory=RequestCounter)
    checkpoint_path: str = ""
    checkpoint_interval: int = 100
    min_delay: float = 2.0
    max_delay: float = 5.0
    parallel_workers: int = 1
    proxy_mode: str = "direct"


def initialize_run_context(
    retailer_name: str,
    config: Dict[str, Any],
    resume: bool = False
) -> ScraperRunContext:
    """Initialize common scraper run context with defaults.

    This handles all the boilerplate setup that every scraper run() needs:
    - Request counter initialization
    - Delay selection based on proxy mode
    - Parallel workers configuration
    - Checkpoint path setup
    - Checkpoint loading if resuming

    Args:
        retailer_name: Name of the retailer
        config: Retailer configuration from retailers.yaml
        resume: Whether to resume from checkpoint

    Returns:
        ScraperRunContext with initialized state
    """
    logging.info(f"[{retailer_name}] Starting scrape run")

    # Create fresh RequestCounter instance for this run
    request_counter = RequestCounter()

    # Auto-select delays based on proxy mode for optimal performance
    proxy_mode = config.get('proxy', {}).get('mode', 'direct')
    min_delay, max_delay = utils.select_delays(config, proxy_mode)
    logging.info(f"[{retailer_name}] Using delays: {min_delay:.1f}-{max_delay:.1f}s (mode: {proxy_mode})")

    # Get parallel workers count (default: WORKERS.PROXIED_WORKERS for residential proxy, WORKERS.DIRECT_WORKERS for direct)
    default_workers = WORKERS.PROXIED_WORKERS if proxy_mode in ('residential', 'web_scraper_api') else WORKERS.DIRECT_WORKERS
    parallel_workers = config.get('parallel_workers', default_workers)
    logging.info(f"[{retailer_name}] Parallel workers: {parallel_workers}")

    # Setup checkpoint configuration
    checkpoint_path = f"data/{retailer_name}/checkpoints/scrape_progress.json"
    base_checkpoint_interval = config.get('checkpoint_interval', 100)
    # Increase checkpoint interval when using parallel workers (less frequent saves)
    checkpoint_interval = base_checkpoint_interval * max(1, parallel_workers) if parallel_workers > 1 else base_checkpoint_interval

    # Initialize context
    context = ScraperRunContext(
        retailer_name=retailer_name,
        config=config,
        request_counter=request_counter,
        checkpoint_path=checkpoint_path,
        checkpoint_interval=checkpoint_interval,
        min_delay=min_delay,
        max_delay=max_delay,
        parallel_workers=parallel_workers,
        proxy_mode=proxy_mode
    )

    # Load checkpoint if resuming
    if resume:
        checkpoint = utils.load_checkpoint(checkpoint_path)
        if checkpoint:
            context.stores = checkpoint.get('stores', [])
            completed_ids_list = checkpoint.get('completed_ids', checkpoint.get('completed_urls', []))
            context.completed_ids = set(completed_ids_list)
            logging.info(f"[{retailer_name}] Resuming from checkpoint: {len(context.stores)} stores already collected")
            context.checkpoints_used = True

    return context


def load_urls_with_cache(
    cache: Union[URLCache, RichURLCache],
    fetch_callback,
    refresh_urls: bool = False
) -> Optional[Union[List[str], List[Dict[str, Any]]]]:
    """Load URLs with cache support.

    Tries to load from cache first, falls back to fetching if cache miss or refresh requested.
    Automatically saves fetched results to cache.

    Args:
        cache: URLCache or RichURLCache instance
        fetch_callback: Callable that fetches URLs when cache miss (should return list)
        refresh_urls: Whether to force URL re-discovery (ignore cache)

    Returns:
        List of URLs (for URLCache) or list of dicts (for RichURLCache), or None if fetch failed
    """
    retailer_name = getattr(cache, 'retailer', 'unknown')
    urls = None

    # Try to load cached URLs
    if not refresh_urls:
        if isinstance(cache, RichURLCache):
            urls = cache.get_rich()
        else:
            urls = cache.get()

    if urls is None:
        # Cache miss or refresh requested - fetch from source
        urls = fetch_callback()

        if urls:
            url_count = len(urls)
            logging.info(f"[{retailer_name}] Found {url_count} URLs from source")
            # Save to cache for future runs
            if isinstance(cache, RichURLCache):
                cache.set_rich(urls)
            else:
                cache.set(urls)
        else:
            logging.warning(f"[{retailer_name}] No URLs found from source")
    elif urls:
        logging.info(f"[{retailer_name}] Using {len(urls)} cached URLs")

    return urls


def filter_remaining_items(
    all_items: List[Union[str, Dict[str, Any]]],
    completed_ids: Set[Union[str, int]],
    limit: Optional[int],
    current_store_count: int,
    retailer_name: str,
    id_extractor=None
) -> List[Union[str, Dict[str, Any]]]:
    """Filter items to process based on completed IDs and limit.

    Handles both URL lists and dict lists (like Target's store_info objects).

    Args:
        all_items: All items (URLs or dicts) from source
        completed_ids: Set of already-completed IDs
        limit: Optional limit on total stores to process
        current_store_count: Number of stores already in results
        retailer_name: Retailer name for logging
        id_extractor: Optional function to extract ID from item (for dict items)

    Returns:
        Filtered list of items to process
    """
    # Filter out already-completed items
    if id_extractor:
        # For dicts (like Target), extract ID with provided function
        remaining = [item for item in all_items if id_extractor(item) not in completed_ids]
    else:
        # For URLs (like AT&T, T-Mobile), use URL itself as ID
        remaining = [item for item in all_items if item not in completed_ids]

    if completed_ids:
        logging.info(f"[{retailer_name}] Skipping {len(all_items) - len(remaining)} already-processed items from checkpoint")

    # Apply limit if specified
    if limit:
        logging.info(f"[{retailer_name}] Limited to {limit} stores")
        total_needed = limit - current_store_count
        if total_needed > 0:
            remaining = remaining[:total_needed]
        else:
            remaining = []

    total_to_process = len(remaining)
    if total_to_process > 0:
        logging.info(f"[{retailer_name}] Extracting details for {total_to_process} items")
    else:
        logging.info(f"[{retailer_name}] No new items to process")

    return remaining


def save_checkpoint_if_needed(
    context: ScraperRunContext,
    current_count: int,
    force: bool = False
) -> None:
    """Save checkpoint at regular intervals or on demand.

    Args:
        context: ScraperRunContext with current state
        current_count: Current number of items processed
        force: Whether to force save regardless of interval
    """
    if force or current_count % context.checkpoint_interval == 0:
        checkpoint_data = {
            'completed_count': len(context.stores),
            'completed_ids': list(context.completed_ids),
            'completed_urls': list(context.completed_ids),  # Backward compatibility
            'stores': context.stores,
            'last_updated': datetime.now().isoformat()
        }
        utils.save_checkpoint(checkpoint_data, context.checkpoint_path)
        logging.info(f"[{context.retailer_name}] Checkpoint saved: {len(context.stores)} stores processed")


def log_progress(
    retailer_name: str,
    current_count: int,
    total_count: int,
    successful_count: Optional[int] = None
) -> None:
    """Log progress at regular intervals.

    Args:
        retailer_name: Name of retailer for logging
        current_count: Current number of items processed
        total_count: Total number of items to process
        successful_count: Optional count of successful extractions (for success rate)
    """
    if current_count % 50 == 0:
        progress_pct = (current_count / total_count * 100) if total_count > 0 else 0

        if successful_count is not None:
            success_rate = (successful_count / current_count * 100) if current_count > 0 else 0
            logging.info(
                f"[{retailer_name}] Progress: {current_count}/{total_count} "
                f"({progress_pct:.1f}%) - "
                f"{successful_count} stores extracted ({success_rate:.0f}% success)"
            )
        else:
            logging.info(
                f"[{retailer_name}] Progress: {current_count}/{total_count} "
                f"({progress_pct:.1f}%) - {current_count} stores extracted"
            )


def log_validation_summary(
    stores: List[Dict[str, Any]],
    retailer_name: str
) -> Dict[str, Any]:
    """Validate stores and log summary.

    Args:
        stores: List of store dictionaries to validate
        retailer_name: Name of retailer for logging

    Returns:
        Validation summary dict
    """
    validation_summary = utils.validate_stores_batch(stores)
    logging.info(
        f"[{retailer_name}] Validation: {validation_summary['valid']}/{validation_summary['total']} valid, "
        f"{validation_summary['warning_count']} warnings"
    )
    return validation_summary


def log_failed_extractions(
    failed_items: List[Union[str, int]],
    retailer_name: str,
    item_type: str = "stores"
) -> None:
    """Log failed extractions with details.

    Args:
        failed_items: List of failed item IDs or URLs
        retailer_name: Name of retailer for logging
        item_type: Type of item (e.g., "stores", "URLs") for logging
    """
    if not failed_items:
        return

    logging.warning(f"[{retailer_name}] Failed to extract {len(failed_items)} {item_type}:")
    for failed_item in failed_items[:10]:  # Log first 10
        logging.warning(f"[{retailer_name}]   - {failed_item}")
    if len(failed_items) > 10:
        logging.warning(f"[{retailer_name}]   ... and {len(failed_items) - 10} more")


def save_failed_items(
    failed_items: List[Union[str, int]],
    retailer_name: str,
    item_key: str = "failed_urls"
) -> None:
    """Save failed item IDs/URLs to file for followup.

    Args:
        failed_items: List of failed item IDs or URLs
        retailer_name: Name of retailer
        item_key: JSON key name for failed items (e.g., "failed_urls", "failed_store_ids")
    """
    if not failed_items:
        return

    failed_path = Path(f"data/{retailer_name}/failed_extractions.json")
    failed_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(failed_path, 'w', encoding='utf-8') as f:
            json.dump({
                'run_date': datetime.now().isoformat(),
                'failed_count': len(failed_items),
                item_key: failed_items
            }, f, indent=2)
        logging.info(f"[{retailer_name}] Saved {len(failed_items)} failed items to {failed_path}")
    except IOError as e:
        logging.warning(f"[{retailer_name}] Failed to save failed items: {e}")


def finalize_scraper_run(
    context: ScraperRunContext,
    failed_items: Optional[List[Union[str, int]]] = None,
    item_key: str = "failed_urls"
) -> Dict[str, Any]:
    """Finalize scraper run with validation, logging, and return dict.

    This handles all the common cleanup that every scraper needs:
    - Final checkpoint save
    - Validation summary
    - Failed items logging
    - Result dict construction

    Args:
        context: ScraperRunContext with final state
        failed_items: Optional list of failed item IDs/URLs
        item_key: JSON key name for failed items

    Returns:
        Standard scraper result dict with 'stores', 'count', 'checkpoints_used'
    """
    retailer_name = context.retailer_name

    # Save final checkpoint
    if context.stores:
        save_checkpoint_if_needed(context, len(context.stores), force=True)

    # Log failed extractions if any
    if failed_items:
        log_failed_extractions(failed_items, retailer_name)
        save_failed_items(failed_items, retailer_name, item_key)

    # Validate store data
    log_validation_summary(context.stores, retailer_name)

    logging.info(f"[{retailer_name}] Completed: {len(context.stores)} stores successfully scraped")

    return {
        'stores': context.stores,
        'count': len(context.stores),
        'checkpoints_used': context.checkpoints_used
    }
