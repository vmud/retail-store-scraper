"""Unified caching interface for URL and response caches - Issue #154.

This module provides an abstract cache interface with consistent TTL and refresh
semantics across all cache types. It enables:
- Consistent --refresh flag behavior for all scrapers
- Unified TTL handling
- Type-safe cache implementations
- Easy extension for new cache types

Usage:
    # URL list caching
    url_cache = URLListCache('target')
    urls = url_cache.get(force_refresh=args.refresh_urls)
    if urls is None:
        urls = discover_urls(session)
        url_cache.set(urls)

    # Response caching (e.g., Walmart Web Scraper API)
    response_cache = ResponseCache('walmart')
    html = response_cache.get(store_url, force_refresh=args.refresh)
    if html is None:
        html = fetch_store_page(session, store_url)
        response_cache.set(store_url, html)

    # Rich URL caching (with metadata)
    rich_cache = RichURLCache('target')
    store_infos = rich_cache.get(force_refresh=args.refresh_urls)
    if store_infos is None:
        store_infos = discover_stores_with_metadata(session)
        rich_cache.set(store_infos)
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, TypeVar

from src.shared.constants import CACHE

__all__ = [
    'CacheInterface',
    'ResponseCache',
    'RichURLCache',
    'URLListCache',
]

T = TypeVar('T')


class CacheInterface(ABC, Generic[T]):
    """Abstract cache interface with TTL and refresh support.

    Provides a consistent caching API across different cache types with:
    - Time-based expiry (TTL)
    - Force refresh capability (bypass cache)
    - Metadata tracking (cache time, age)
    - Type-safe serialization

    Subclasses must implement:
    - get_cache_key(): Convert identifier to cache file key
    - serialize(): Convert data to string for storage
    - deserialize(): Convert stored string back to data

    Args:
        cache_dir: Directory for cache files
        ttl_days: Cache time-to-live in days (default: 7)
    """

    def __init__(self, cache_dir: Path, ttl_days: int = CACHE.URL_CACHE_EXPIRY_DAYS):
        """Initialize cache interface.

        Args:
            cache_dir: Directory path for cache storage
            ttl_days: Time-to-live in days before cache expires
        """
        self.cache_dir = cache_dir
        self.ttl = timedelta(days=ttl_days)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def get_cache_key(self, identifier: str) -> str:
        """Generate cache key from identifier.

        Args:
            identifier: Unique identifier for cached data (e.g., retailer name, URL)

        Returns:
            Cache key string used for filename
        """

    @abstractmethod
    def serialize(self, data: T) -> str:
        """Serialize data for storage.

        Args:
            data: Data to serialize

        Returns:
            Serialized string representation
        """

    @abstractmethod
    def deserialize(self, raw: str) -> T:
        """Deserialize stored data.

        Args:
            raw: Serialized string from storage

        Returns:
            Deserialized data
        """

    def get(self, identifier: str, force_refresh: bool = False) -> Optional[T]:
        """Get cached data if valid.

        Args:
            identifier: Unique identifier for cached data
            force_refresh: If True, bypass cache and return None

        Returns:
            Cached data if valid and not expired, None otherwise
        """
        if force_refresh:
            return None

        cache_file = self._get_cache_file(identifier)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check expiry based on internal 'cached_at' timestamp for consistency
            cached_at_str = cache_data.get('cached_at')
            if not cached_at_str:
                logging.warning(f"Cache for {identifier} missing 'cached_at' timestamp")
                return None

            cache_time = datetime.fromisoformat(cached_at_str)
            if datetime.now() - cache_time > self.ttl:
                logging.debug(f"Cache for {identifier} has expired")
                return None

            # Extract the actual data (excluding metadata)
            data_str = cache_data.get('data')
            if data_str is None:
                return None

            return self.deserialize(data_str)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.warning(f"Error reading cache for {identifier}: {e}")
            return None

    def set(self, identifier: str, data: T) -> None:
        """Store data in cache with metadata.

        Args:
            identifier: Unique identifier for cached data
            data: Data to cache
        """
        cache_file = self._get_cache_file(identifier)

        cache_data = {
            'cached_at': datetime.now().isoformat(),
            'identifier': identifier,
            'data': self.serialize(data)
        }

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except IOError as e:
            logging.warning(f"Failed to save cache for {identifier}: {e}")

    def clear(self, identifier: str) -> None:
        """Remove cached data for identifier.

        Args:
            identifier: Unique identifier for cached data
        """
        cache_file = self._get_cache_file(identifier)
        if cache_file.exists():
            cache_file.unlink()

    def is_valid(self, identifier: str) -> bool:
        """Check if cache exists and is not expired.

        Args:
            identifier: Unique identifier for cached data

        Returns:
            True if cache is valid, False otherwise
        """
        cache_file = self._get_cache_file(identifier)
        if not cache_file.exists():
            return False

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            cached_at_str = cache_data.get('cached_at')
            if not cached_at_str:
                return False

            cache_time = datetime.fromisoformat(cached_at_str)
            return datetime.now() - cache_time <= self.ttl

        except (json.JSONDecodeError, KeyError, ValueError):
            return False

    def get_metadata(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get cache metadata without loading data.

        Args:
            identifier: Unique identifier for cached data

        Returns:
            Dict with 'cached_at', 'age_days', 'expired' or None if no cache
        """
        cache_file = self._get_cache_file(identifier)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            cached_at = cache_data.get('cached_at')
            if not cached_at:
                return None

            cache_time = datetime.fromisoformat(cached_at)
            age = datetime.now() - cache_time

            return {
                'cached_at': cached_at,
                'age_days': age.days,
                'expired': age > self.ttl
            }

        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _get_cache_file(self, identifier: str) -> Path:
        """Get path to cache file for identifier.

        Args:
            identifier: Unique identifier for cached data

        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{self.get_cache_key(identifier)}.cache"


class URLListCache(CacheInterface[List[str]]):
    """Cache for URL lists (sitemap URLs, store URLs).

    Stores lists of URLs with TTL-based expiry. Useful for caching
    discovered store URLs from sitemaps or API responses.

    Usage:
        cache = URLListCache('target')
        urls = cache.get('target', force_refresh=args.refresh_urls)
        if urls is None:
            urls = discover_store_urls(session)
            cache.set('target', urls)
    """

    def __init__(self, retailer: str, cache_dir: Optional[Path] = None,
                 ttl_days: int = CACHE.URL_CACHE_EXPIRY_DAYS):
        """Initialize URL list cache for a retailer.

        Args:
            retailer: Retailer name (e.g., 'target', 'walmart')
            cache_dir: Optional custom cache directory. Defaults to data/{retailer}/
            ttl_days: Cache expiry in days (default: 7)
        """
        if cache_dir is None:
            cache_dir = Path(f"data/{retailer}")
        super().__init__(cache_dir, ttl_days)

    def get_cache_key(self, identifier: str) -> str:
        """Generate cache key for URL list.

        Args:
            identifier: Retailer name or identifier

        Returns:
            Cache key string
        """
        return f"{identifier}_urls"

    def serialize(self, urls: List[str]) -> str:
        """Serialize URL list to JSON.

        Args:
            urls: List of URLs

        Returns:
            JSON string
        """
        return json.dumps(urls)

    def deserialize(self, raw: str) -> List[str]:
        """Deserialize JSON to URL list.

        Args:
            raw: JSON string

        Returns:
            List of URLs
        """
        return json.loads(raw)


class RichURLCache(CacheInterface[List[Dict[str, Any]]]):
    """Cache for URL lists with metadata (rich URLs).

    Stores lists of dictionaries containing URLs plus additional metadata
    (e.g., store_id, slug). Used by scrapers like Target that need to cache
    extra info alongside URLs to avoid re-parsing later.

    Usage:
        cache = RichURLCache('target')
        store_infos = cache.get('target', force_refresh=args.refresh_urls)
        if store_infos is None:
            store_infos = discover_stores_with_metadata(session)
            cache.set('target', store_infos)
    """

    def __init__(self, retailer: str, cache_dir: Optional[Path] = None,
                 ttl_days: int = CACHE.URL_CACHE_EXPIRY_DAYS):
        """Initialize rich URL cache for a retailer.

        Args:
            retailer: Retailer name (e.g., 'target', 'walmart')
            cache_dir: Optional custom cache directory. Defaults to data/{retailer}/
            ttl_days: Cache expiry in days (default: 7)
        """
        if cache_dir is None:
            cache_dir = Path(f"data/{retailer}")
        super().__init__(cache_dir, ttl_days)

    def get_cache_key(self, identifier: str) -> str:
        """Generate cache key for rich URL list.

        Args:
            identifier: Retailer name or identifier

        Returns:
            Cache key string
        """
        return f"{identifier}_rich_urls"

    def serialize(self, store_infos: List[Dict[str, Any]]) -> str:
        """Serialize store info dicts to JSON.

        Args:
            store_infos: List of store info dictionaries

        Returns:
            JSON string
        """
        return json.dumps(store_infos)

    def deserialize(self, raw: str) -> List[Dict[str, Any]]:
        """Deserialize JSON to store info dicts.

        Args:
            raw: JSON string

        Returns:
            List of store info dictionaries
        """
        return json.loads(raw)


class ResponseCache(CacheInterface[str]):
    """Cache for HTTP responses.

    Stores raw HTTP response bodies (HTML, JSON) with URL-based keys.
    Useful for expensive API calls or Web Scraper API responses.

    Usage:
        cache = ResponseCache('walmart', ttl_days=30)
        html = cache.get(store_url, force_refresh=args.refresh)
        if html is None:
            html = fetch_store_page(session, store_url)
            cache.set(store_url, html)
    """

    def __init__(self, retailer: str, cache_dir: Optional[Path] = None,
                 ttl_days: int = CACHE.RESPONSE_CACHE_EXPIRY_DAYS):
        """Initialize response cache for a retailer.

        Args:
            retailer: Retailer name (e.g., 'walmart')
            cache_dir: Optional custom cache directory. Defaults to data/{retailer}/response_cache/
            ttl_days: Cache expiry in days (default: 30)
        """
        if cache_dir is None:
            cache_dir = Path(f"data/{retailer}/response_cache")
        super().__init__(cache_dir, ttl_days)

    def get_cache_key(self, url: str) -> str:
        """Generate cache key from URL hash.

        Args:
            url: Full URL to cache

        Returns:
            Full SHA256 hash (64 chars) to avoid collisions
        """
        return hashlib.sha256(url.encode()).hexdigest()

    def serialize(self, response: str) -> str:
        """Serialize response (identity function for strings).

        Args:
            response: Raw response body

        Returns:
            Same response string
        """
        return response

    def deserialize(self, raw: str) -> str:
        """Deserialize response (identity function for strings).

        Args:
            raw: Stored response string

        Returns:
            Same response string
        """
        return raw
