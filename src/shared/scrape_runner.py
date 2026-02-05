"""Unified scraper orchestration framework.

This module provides a shared ScrapeRunner class that consolidates the
cache→checkpoint→threadpool orchestration logic that was duplicated across
AT&T, Target, T-Mobile, Best Buy, and Verizon scrapers.

Addresses Issue #150: Reduce code duplication and regression risk by providing
a single source of truth for scraper execution patterns.
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional, Tuple, Union

from src.shared import utils
from src.shared.cache import URLCache, RichURLCache
from src.shared.constants import WORKERS
from src.shared.request_counter import RequestCounter
from src.shared.session_factory import create_session_factory


__all__ = [
    'ScraperContext',
    'ScrapeRunner',
]


@dataclass
class ScraperContext:
    """Configuration and state for a scraper run.

    Args:
        retailer: Retailer name (e.g., 'att', 'target')
        session: Configured session (requests.Session or ProxyClient)
        config: Retailer configuration from retailers.yaml
        resume: Whether to resume from checkpoint
        limit: Maximum number of stores to process
        refresh_urls: Force URL re-discovery (ignore cache)
        use_rich_cache: Use RichURLCache instead of URLCache
    """
    retailer: str
    session: Any
    config: Dict[str, Any]
    resume: bool = False
    limit: Optional[int] = None
    refresh_urls: bool = False
    use_rich_cache: bool = False


class ScrapeRunner:
    """Unified orchestration for scraper execution.

    Provides standardized:
    - URL caching (7-day cache to skip sitemap fetches)
    - Checkpoint/resume (atomic saves with completed URL tracking)
    - Parallel extraction (ThreadPoolExecutor with configurable workers)
    - Progress logging (consistent reporting across scrapers)
    - Request tracking (rate limiting and pause logic)
    - Validation (batch validation at end of run)

    Usage:
        context = ScraperContext(
            retailer='att',
            session=session,
            config=config,
            resume=kwargs.get('resume', False),
            limit=kwargs.get('limit')
        )

        runner = ScrapeRunner(context)

        return runner.run_with_checkpoints(
            url_discovery_func=get_store_urls_from_sitemap,
            extraction_func=extract_store_details
        )
    """

    def __init__(self, context: ScraperContext):
        """Initialize scrape runner.

        Args:
            context: ScraperContext with configuration and state
        """
        self.context = context
        self.retailer = context.retailer
        self.session = context.session
        self.config = context.config

        # Initialize request counter for this run
        self.request_counter = RequestCounter()

        # Determine proxy mode and select delays
        self.proxy_mode = self.config.get('proxy', {}).get('mode', 'direct')
        self.min_delay, self.max_delay = utils.select_delays(self.config, self.proxy_mode)

        # Determine parallel workers count
        default_workers = (
            WORKERS.PROXIED_WORKERS if self.proxy_mode in ('residential', 'web_scraper_api')
            else WORKERS.DIRECT_WORKERS
        )
        self.parallel_workers = self.config.get('parallel_workers', default_workers)

        # Checkpoint configuration
        self.checkpoint_path = f"data/{self.retailer}/checkpoints/scrape_progress.json"
        base_checkpoint_interval = self.config.get('checkpoint_interval', 100)
        self.checkpoint_interval = (
            base_checkpoint_interval * max(1, self.parallel_workers)
            if self.parallel_workers > 1
            else base_checkpoint_interval
        )

        # Initialize state
        self.stores: List[Dict[str, Any]] = []
        self.completed_items: set = set()  # Can be URLs or IDs
        self.checkpoints_used = False

        # URL cache
        if context.use_rich_cache:
            self.url_cache: Union[URLCache, RichURLCache] = RichURLCache(self.retailer)
        else:
            self.url_cache = URLCache(self.retailer)

        logging.info(f"[{self.retailer}] Using delays: {self.min_delay:.1f}-{self.max_delay:.1f}s (mode: {self.proxy_mode})")
        logging.info(f"[{self.retailer}] Parallel workers: {self.parallel_workers}")

    def _load_checkpoint(self) -> None:
        """Load checkpoint if resume is enabled."""
        if not self.context.resume:
            return

        checkpoint = utils.load_checkpoint(self.checkpoint_path)
        if checkpoint:
            self.stores = checkpoint.get('stores', [])
            # Support both 'completed_urls' and 'completed_ids' keys
            self.completed_items = set(
                checkpoint.get('completed_urls', []) or checkpoint.get('completed_ids', [])
            )
            logging.info(f"[{self.retailer}] Resuming from checkpoint: {len(self.stores)} stores already collected")
            self.checkpoints_used = True

    def _save_checkpoint(self) -> None:
        """Save current progress to checkpoint."""
        utils.save_checkpoint({
            'completed_count': len(self.stores),
            'completed_urls': list(self.completed_items),  # Keep 'completed_urls' for backward compatibility
            'completed_ids': list(self.completed_items),    # Alternative key for ID-based scrapers
            'stores': self.stores,
            'last_updated': datetime.now().isoformat()
        }, self.checkpoint_path)

    def _load_or_discover_urls(
        self,
        discovery_func: Callable,
        **discovery_kwargs
    ) -> List[Any]:
        """Load URLs from cache or discover them.

        Args:
            discovery_func: Function to discover URLs (sitemap fetch, etc.)
            **discovery_kwargs: Additional kwargs to pass to discovery function

        Returns:
            List of URLs or store info dicts (if using RichURLCache)
        """
        urls = None

        if not self.context.refresh_urls:
            if isinstance(self.url_cache, RichURLCache):
                urls = self.url_cache.get_rich()
            else:
                urls = self.url_cache.get()

        if urls is None:
            # Cache miss or refresh requested - call discovery function
            urls = discovery_func(
                self.session,
                self.retailer,
                yaml_config=self.config,
                request_counter=self.request_counter,
                **discovery_kwargs
            )
            logging.info(f"[{self.retailer}] Found {len(urls)} items from discovery")

            # Save to cache
            if urls:
                if isinstance(self.url_cache, RichURLCache):
                    self.url_cache.set_rich(urls)
                else:
                    self.url_cache.set(urls)
        else:
            logging.info(f"[{self.retailer}] Using {len(urls)} cached items")

        return urls

    def _extract_item_parallel(
        self,
        items: List[Any],
        extraction_func: Callable,
        item_key_func: Callable[[Any], Any],
        **extraction_kwargs
    ) -> List[Dict[str, Any]]:
        """Extract items in parallel using ThreadPoolExecutor.

        Args:
            items: List of items to process (URLs or info dicts)
            extraction_func: Function to extract single item data
            item_key_func: Function to extract unique key from item
            **extraction_kwargs: Additional kwargs to pass to extraction function

        Returns:
            List of extracted store dictionaries
        """
        session_factory = create_session_factory(self.config)

        # Thread-safe counters
        processed_count = [0]
        successful_count = [0]
        processed_lock = threading.Lock()
        failed_items = []

        total_to_process = len(items)

        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            # Submit all extraction tasks
            futures = {
                executor.submit(
                    self._extract_single_item,
                    item,
                    session_factory,
                    extraction_func,
                    item_key_func,
                    **extraction_kwargs
                ): item
                for item in items
            }

            for future in as_completed(futures):
                item_key, store_data = future.result()

                with processed_lock:
                    processed_count[0] += 1
                    current_count = processed_count[0]

                    if store_data:
                        self.stores.append(store_data)
                        self.completed_items.add(item_key)
                        successful_count[0] += 1
                    else:
                        failed_items.append(item_key)

                    # Progress logging every 50 items
                    if current_count % 50 == 0:
                        success_rate = (successful_count[0] / current_count * 100) if current_count > 0 else 0
                        logging.info(
                            f"[{self.retailer}] Progress: {current_count}/{total_to_process} "
                            f"({current_count/total_to_process*100:.1f}%) - "
                            f"{successful_count[0]} stores extracted ({success_rate:.0f}% success)"
                        )

                    # Checkpoint at intervals
                    if current_count % self.checkpoint_interval == 0:
                        self._save_checkpoint()
                        logging.info(f"[{self.retailer}] Checkpoint saved: {len(self.stores)} stores processed")

        # Log failed extractions
        if failed_items:
            logging.warning(f"[{self.retailer}] Failed to extract {len(failed_items)} items:")
            for failed_item in failed_items[:10]:
                logging.warning(f"[{self.retailer}]   - {failed_item}")
            if len(failed_items) > 10:
                logging.warning(f"[{self.retailer}]   ... and {len(failed_items) - 10} more")

            # Save failed items to file
            self._save_failed_items(failed_items)

        return self.stores

    def _extract_single_item(
        self,
        item: Any,
        session_factory: Callable,
        extraction_func: Callable,
        item_key_func: Callable[[Any], Any],
        **extraction_kwargs
    ) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """Worker function for parallel extraction.

        Args:
            item: Item to extract (URL or info dict)
            session_factory: Factory to create new session instances
            extraction_func: Function to extract store details
            item_key_func: Function to extract unique key from item
            **extraction_kwargs: Additional kwargs to pass to extraction function

        Returns:
            Tuple of (item_key, store_data_dict) where store_data_dict is None on failure
        """
        session = session_factory()

        try:
            # Extract key inside try block to catch key extraction errors
            item_key = item_key_func(item)

            store_obj = extraction_func(
                session,
                item,
                self.retailer,
                yaml_config=self.config,
                request_counter=self.request_counter,
                **extraction_kwargs
            )
            if store_obj:
                # Handle both dataclass objects and dicts
                if hasattr(store_obj, 'to_dict'):
                    return (item_key, store_obj.to_dict())
                return (item_key, store_obj)
            return (item_key, None)
        except Exception as e:
            # Safe fallback for item_key if extraction failed before key was set
            try:
                item_key = item_key_func(item)
            except Exception:
                item_key = str(item)
            logging.warning(f"[{self.retailer}] Error extracting {item_key}: {e}")
            return (item_key, None)
        finally:
            if hasattr(session, 'close'):
                session.close()

    def _extract_item_sequential(
        self,
        items: List[Any],
        extraction_func: Callable,
        item_key_func: Callable[[Any], Any],
        **extraction_kwargs
    ) -> List[Dict[str, Any]]:
        """Extract items sequentially (fallback for direct mode).

        Args:
            items: List of items to process
            extraction_func: Function to extract single item data
            item_key_func: Function to extract unique key from item
            **extraction_kwargs: Additional kwargs to pass to extraction function

        Returns:
            List of extracted store dictionaries
        """
        total_to_process = len(items)
        failed_items = []

        for i, item in enumerate(items, 1):
            try:
                # Extract key inside try block to catch key extraction errors
                item_key = item_key_func(item)

                store_obj = extraction_func(
                    self.session,
                    item,
                    self.retailer,
                    yaml_config=self.config,
                    request_counter=self.request_counter,
                    **extraction_kwargs
                )

                if store_obj:
                    # Handle both dataclass objects and dicts
                    if hasattr(store_obj, 'to_dict'):
                        self.stores.append(store_obj.to_dict())
                    else:
                        self.stores.append(store_obj)
                    self.completed_items.add(item_key)

                    # Log successful extraction every 10 stores
                    if i % 10 == 0:
                        logging.info(f"[{self.retailer}] Extracted {len(self.stores)} stores so far ({i}/{total_to_process})")
                else:
                    failed_items.append(item_key)
            except Exception as e:
                # Safe fallback for item_key if extraction failed before key was set
                try:
                    item_key = item_key_func(item)
                except Exception:
                    item_key = str(item)
                logging.warning(f"[{self.retailer}] Error extracting {item_key}: {e}")
                failed_items.append(item_key)

            # Progress logging every 100 items
            if i % 100 == 0:
                logging.info(f"[{self.retailer}] Progress: {i}/{total_to_process} ({i/total_to_process*100:.1f}%)")

            if i % self.checkpoint_interval == 0:
                self._save_checkpoint()
                logging.info(f"[{self.retailer}] Checkpoint saved: {len(self.stores)} stores processed")

        # Log failed extractions
        if failed_items:
            logging.warning(f"[{self.retailer}] Failed to extract {len(failed_items)} items:")
            for failed_item in failed_items[:10]:
                logging.warning(f"[{self.retailer}]   - {failed_item}")
            if len(failed_items) > 10:
                logging.warning(f"[{self.retailer}]   ... and {len(failed_items) - 10} more")

            # Save failed items to file
            self._save_failed_items(failed_items)

        return self.stores

    def _save_failed_items(self, failed_items: List[Any]) -> None:
        """Save failed items for followup.

        Args:
            failed_items: List of items that failed extraction
        """
        failed_path = Path(f"data/{self.retailer}/failed_extractions.json")
        failed_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(failed_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'run_date': datetime.now().isoformat(),
                    'failed_count': len(failed_items),
                    'failed_items': [str(item) for item in failed_items]
                }, f, indent=2)
            logging.info(f"[{self.retailer}] Saved {len(failed_items)} failed items to {failed_path}")
        except IOError as e:
            logging.warning(f"[{self.retailer}] Failed to save failed items: {e}")

    def run_with_checkpoints(
        self,
        url_discovery_func: Callable,
        extraction_func: Callable,
        item_key_func: Optional[Callable[[Any], Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Run scraper with unified orchestration.

        Handles:
        - URL caching (load from cache or call discovery function)
        - Checkpoint loading (resume from previous run)
        - Parallel or sequential extraction
        - Progress logging and checkpointing
        - Validation at end

        Args:
            url_discovery_func: Function to discover URLs (e.g., get_store_urls_from_sitemap)
                Signature: func(session, retailer, yaml_config, request_counter, **kwargs) -> List[Any]
            extraction_func: Function to extract single store details
                Signature: func(session, item, retailer, yaml_config, request_counter, **kwargs) -> Optional[StoreData]
            item_key_func: Optional function to extract unique key from item (defaults to identity)
            **kwargs: Additional kwargs to pass to discovery and extraction functions

        Returns:
            dict with keys:
                - stores: List[dict] - Scraped store data
                - count: int - Number of stores processed
                - checkpoints_used: bool - Whether resume was used
        """
        logging.info(f"[{self.retailer}] Starting scrape run")

        try:
            # Default item key function: use item as-is (for URL strings)
            if item_key_func is None:
                if self.context.use_rich_cache:
                    # RichURLCache returns dicts, need a smarter default
                    # Try common ID fields, fall back to URL
                    item_key_func = lambda x: (
                        x.get('store_id') or x.get('id') or x.get('url') or str(x)
                        if isinstance(x, dict) else x
                    )
                else:
                    # URLCache returns strings, use as-is
                    item_key_func = lambda x: x

            # Load checkpoint if resuming
            self._load_checkpoint()

            # Load or discover URLs
            items = self._load_or_discover_urls(url_discovery_func, **kwargs)

            if not items:
                logging.warning(f"[{self.retailer}] No items found")
                return {'stores': [], 'count': 0, 'checkpoints_used': False}

            # Filter out already-completed items
            remaining_items = [item for item in items if item_key_func(item) not in self.completed_items]

            if self.context.resume and self.completed_items:
                logging.info(
                    f"[{self.retailer}] Skipping {len(items) - len(remaining_items)} "
                    f"already-processed items from checkpoint"
                )

            # Apply limit if specified
            if self.context.limit:
                logging.info(f"[{self.retailer}] Limited to {self.context.limit} stores")
                total_needed = self.context.limit - len(self.stores)
                if total_needed > 0:
                    remaining_items = remaining_items[:total_needed]
                else:
                    remaining_items = []

            total_to_process = len(remaining_items)
            if total_to_process > 0:
                logging.info(f"[{self.retailer}] Extracting details for {total_to_process} items")
            else:
                logging.info(f"[{self.retailer}] No new items to process")

            # Extract items (parallel or sequential)
            if self.parallel_workers > 1 and total_to_process > 0:
                logging.info(f"[{self.retailer}] Using parallel extraction with {self.parallel_workers} workers")
                self._extract_item_parallel(remaining_items, extraction_func, item_key_func, **kwargs)
            elif total_to_process > 0:
                self._extract_item_sequential(remaining_items, extraction_func, item_key_func, **kwargs)

            # Final checkpoint save
            if self.stores:
                self._save_checkpoint()
                logging.info(f"[{self.retailer}] Final checkpoint saved: {len(self.stores)} stores total")

            # Validate store data
            validation_summary = utils.validate_stores_batch(self.stores)
            logging.info(
                f"[{self.retailer}] Validation: {validation_summary['valid']}/{validation_summary['total']} valid, "
                f"{validation_summary['warning_count']} warnings"
            )

            logging.info(f"[{self.retailer}] Completed: {len(self.stores)} stores successfully scraped")

            return {
                'stores': self.stores,
                'count': len(self.stores),
                'checkpoints_used': self.checkpoints_used
            }

        except Exception as e:
            logging.error(f"[{self.retailer}] Fatal error: {e}", exc_info=True)
            raise
