"""URL caching abstraction for retail store scrapers.

This module provides a unified URLCache class that replaces the duplicate
caching implementations across individual scrapers.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.shared.constants import CACHE


# Default cache expiry: 7 days (stores don't change location frequently)
DEFAULT_CACHE_EXPIRY_DAYS = CACHE.URL_CACHE_EXPIRY_DAYS


class URLCache:
    """Cache for discovered store URLs to skip re-discovery on subsequent runs.

    Provides a standardized caching interface for all scrapers, replacing
    the ~80 lines of duplicate code that existed in each scraper module.

    Usage:
        cache = URLCache('target')

        # Try to load from cache
        urls = cache.get()
        if urls is None:
            # Cache miss - discover URLs
            urls = discover_store_urls(session)
            cache.set(urls)
    """

    def __init__(
        self,
        retailer: str,
        cache_dir: Optional[Path] = None,
        expiry_days: int = DEFAULT_CACHE_EXPIRY_DAYS
    ):
        """Initialize URL cache for a retailer.

        Args:
            retailer: Retailer name (e.g., 'target', 'walmart')
            cache_dir: Optional custom cache directory. Defaults to data/{retailer}/
            expiry_days: Cache expiry in days (default: 7)
        """
        self.retailer = retailer
        self.expiry_days = expiry_days

        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path(f"data/{retailer}")

        self.cache_path = self.cache_dir / "store_urls.json"

    def get(self) -> Optional[List[str]]:
        """Load cached store URLs if cache is valid.

        Returns:
            List of cached URLs if cache exists and is not expired, None otherwise
        """
        if not self.cache_path.exists():
            logging.info(f"[{self.retailer}] No URL cache found at {self.cache_path}")
            return None

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check cache freshness
            discovered_at = cache_data.get('discovered_at')
            if discovered_at:
                cache_time = datetime.fromisoformat(discovered_at)
                age_days = (datetime.now() - cache_time).days

                if age_days > self.expiry_days:
                    logging.info(
                        f"[{self.retailer}] URL cache expired "
                        f"({age_days} days old, max: {self.expiry_days})"
                    )
                    return None

                urls = cache_data.get('urls', [])
                if urls:
                    logging.info(
                        f"[{self.retailer}] Loaded {len(urls)} URLs from cache "
                        f"({age_days} days old)"
                    )
                    return urls

            logging.warning(f"[{self.retailer}] URL cache is invalid or empty")
            return None

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.warning(f"[{self.retailer}] Error loading URL cache: {e}")
            return None

    def set(self, urls: List[str]) -> None:
        """Save store URLs to cache.

        Args:
            urls: List of store URLs to cache
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        cache_data = {
            'discovered_at': datetime.now().isoformat(),
            'store_count': len(urls),
            'urls': urls
        }

        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            logging.info(f"[{self.retailer}] Saved {len(urls)} URLs to cache: {self.cache_path}")
        except IOError as e:
            logging.warning(f"[{self.retailer}] Failed to save URL cache: {e}")

    def is_valid(self) -> bool:
        """Check if cache exists and is not expired.

        Returns:
            True if cache is valid, False otherwise
        """
        if not self.cache_path.exists():
            return False

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            discovered_at = cache_data.get('discovered_at')
            if not discovered_at:
                return False

            cache_time = datetime.fromisoformat(discovered_at)
            age_days = (datetime.now() - cache_time).days

            return age_days <= self.expiry_days and bool(cache_data.get('urls'))

        except (json.JSONDecodeError, KeyError, ValueError):
            return False

    def clear(self) -> None:
        """Remove cached data."""
        if self.cache_path.exists():
            self.cache_path.unlink()
            logging.info(f"[{self.retailer}] Cleared URL cache")

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """Get cache metadata without loading all URLs.

        Returns:
            Dict with 'discovered_at', 'store_count', 'age_days' or None if no cache
        """
        if not self.cache_path.exists():
            return None

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            discovered_at = cache_data.get('discovered_at')
            if discovered_at:
                cache_time = datetime.fromisoformat(discovered_at)
                age_days = (datetime.now() - cache_time).days

                return {
                    'discovered_at': discovered_at,
                    'store_count': cache_data.get('store_count', 0),
                    'age_days': age_days,
                    'expired': age_days > self.expiry_days
                }
            return None

        except (json.JSONDecodeError, KeyError, ValueError):
            return None


class RichURLCache(URLCache):
    """Extended URL cache that stores additional metadata per URL.

    Used by scrapers like Target that need to cache extra info alongside URLs
    (e.g., store_id, slug) to avoid re-parsing later.

    Usage:
        cache = RichURLCache('target')

        # Try to load from cache
        store_infos = cache.get_rich()  # Returns List[Dict] instead of List[str]
        if store_infos is None:
            store_infos = discover_stores(session)  # Returns [{'store_id': ..., 'url': ...}]
            cache.set_rich(store_infos)
    """

    def get_rich(self) -> Optional[List[Dict[str, Any]]]:
        """Load cached store info dicts if cache is valid.

        Returns:
            List of store info dicts if cache is valid, None otherwise
        """
        if not self.cache_path.exists():
            logging.info(f"[{self.retailer}] No URL cache found at {self.cache_path}")
            return None

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            discovered_at = cache_data.get('discovered_at')
            if discovered_at:
                cache_time = datetime.fromisoformat(discovered_at)
                age_days = (datetime.now() - cache_time).days

                if age_days > self.expiry_days:
                    logging.info(
                        f"[{self.retailer}] URL cache expired "
                        f"({age_days} days old, max: {self.expiry_days})"
                    )
                    return None

                # Support both 'stores' (legacy Target) and 'urls' keys
                stores = cache_data.get('stores') or cache_data.get('urls', [])
                if stores:
                    logging.info(
                        f"[{self.retailer}] Loaded {len(stores)} store URLs from cache "
                        f"({age_days} days old)"
                    )
                    return stores

            logging.warning(f"[{self.retailer}] URL cache is invalid or empty")
            return None

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.warning(f"[{self.retailer}] Error loading URL cache: {e}")
            return None

    def set_rich(self, store_infos: List[Dict[str, Any]]) -> None:
        """Save store info dicts to cache.

        Args:
            store_infos: List of store info dicts (must contain at least 'url' key)
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        cache_data = {
            'discovered_at': datetime.now().isoformat(),
            'store_count': len(store_infos),
            'urls': store_infos  # Use 'urls' key for consistency
        }

        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            logging.info(
                f"[{self.retailer}] Saved {len(store_infos)} store URLs to cache: {self.cache_path}"
            )
        except IOError as e:
            logging.warning(f"[{self.retailer}] Failed to save URL cache: {e}")
