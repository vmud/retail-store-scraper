"""Unit tests for unified cache interface - Issue #154."""

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from src.shared.cache_interface import (
    CacheInterface,
    ResponseCache,
    RichURLCache,
    URLListCache,
)


class TestURLListCache:
    """Test URLListCache implementation."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "data" / "target"

    @pytest.fixture
    def url_cache(self, cache_dir):
        """Create URLListCache instance."""
        return URLListCache('target', cache_dir=cache_dir)

    def test_init_creates_cache_dir(self, url_cache, cache_dir):
        """Test that cache initialization creates directory."""
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_get_returns_none_when_no_cache(self, url_cache):
        """Test get returns None when cache file doesn't exist."""
        result = url_cache.get('target')
        assert result is None

    def test_set_and_get_urls(self, url_cache):
        """Test setting and retrieving URL list."""
        urls = [
            'https://target.com/store/1',
            'https://target.com/store/2',
            'https://target.com/store/3'
        ]

        url_cache.set('target', urls)
        retrieved = url_cache.get('target')

        assert retrieved == urls

    def test_get_with_force_refresh_returns_none(self, url_cache):
        """Test force_refresh bypasses cache."""
        urls = ['https://target.com/store/1']
        url_cache.set('target', urls)

        # Normal get works
        assert url_cache.get('target') is not None

        # Force refresh returns None
        assert url_cache.get('target', force_refresh=True) is None

    def test_cache_expiry(self, url_cache, cache_dir):
        """Test cache expires after TTL."""
        # Create cache with 0-day TTL (instant expiry)
        url_cache_instant = URLListCache('target', cache_dir=cache_dir, ttl_days=0)

        urls = ['https://target.com/store/1']
        url_cache_instant.set('target', urls)

        # Sleep briefly to ensure expiry
        time.sleep(0.1)

        # Should be expired
        assert url_cache_instant.get('target') is None

    def test_is_valid_returns_false_for_missing_cache(self, url_cache):
        """Test is_valid returns False when cache doesn't exist."""
        assert url_cache.is_valid('target') is False

    def test_is_valid_returns_true_for_valid_cache(self, url_cache):
        """Test is_valid returns True for unexpired cache."""
        urls = ['https://target.com/store/1']
        url_cache.set('target', urls)

        assert url_cache.is_valid('target') is True

    def test_clear_removes_cache(self, url_cache):
        """Test clear removes cached data."""
        urls = ['https://target.com/store/1']
        url_cache.set('target', urls)

        assert url_cache.is_valid('target') is True

        url_cache.clear('target')

        assert url_cache.is_valid('target') is False
        assert url_cache.get('target') is None

    def test_get_metadata(self, url_cache):
        """Test get_metadata returns cache info."""
        urls = ['https://target.com/store/1']
        url_cache.set('target', urls)

        metadata = url_cache.get_metadata('target')

        assert metadata is not None
        assert 'cached_at' in metadata
        assert 'age_days' in metadata
        assert 'expired' in metadata
        assert metadata['age_days'] == 0
        assert metadata['expired'] is False

    def test_get_metadata_returns_none_for_missing_cache(self, url_cache):
        """Test get_metadata returns None when cache doesn't exist."""
        metadata = url_cache.get_metadata('target')
        assert metadata is None

    def test_cache_key_format(self, url_cache):
        """Test cache key generation."""
        cache_key = url_cache.get_cache_key('target')
        assert cache_key == 'target_urls'

    def test_serialization_roundtrip(self, url_cache):
        """Test serialize/deserialize roundtrip."""
        urls = [
            'https://target.com/store/1',
            'https://target.com/store/2'
        ]

        serialized = url_cache.serialize(urls)
        assert isinstance(serialized, str)

        deserialized = url_cache.deserialize(serialized)
        assert deserialized == urls

    def test_corrupted_cache_returns_none(self, url_cache, cache_dir):
        """Test that corrupted cache file returns None."""
        cache_file = cache_dir / 'target_urls.cache'
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON
        cache_file.write_text('{ invalid json }')

        result = url_cache.get('target')
        assert result is None


class TestRichURLCache:
    """Test RichURLCache implementation."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "data" / "target"

    @pytest.fixture
    def rich_cache(self, cache_dir):
        """Create RichURLCache instance."""
        return RichURLCache('target', cache_dir=cache_dir)

    def test_set_and_get_rich_urls(self, rich_cache):
        """Test setting and retrieving rich URL list."""
        store_infos = [
            {'store_id': '1', 'url': 'https://target.com/store/1', 'slug': 'store-1'},
            {'store_id': '2', 'url': 'https://target.com/store/2', 'slug': 'store-2'},
        ]

        rich_cache.set('target', store_infos)
        retrieved = rich_cache.get('target')

        assert retrieved == store_infos

    def test_cache_key_format(self, rich_cache):
        """Test rich cache key generation."""
        cache_key = rich_cache.get_cache_key('target')
        assert cache_key == 'target_rich_urls'

    def test_force_refresh_bypasses_cache(self, rich_cache):
        """Test force_refresh returns None even with valid cache."""
        store_infos = [
            {'store_id': '1', 'url': 'https://target.com/store/1'}
        ]

        rich_cache.set('target', store_infos)

        # Normal get works
        assert rich_cache.get('target') is not None

        # Force refresh returns None
        assert rich_cache.get('target', force_refresh=True) is None

    def test_serialization_preserves_metadata(self, rich_cache):
        """Test that serialization preserves all metadata fields."""
        store_infos = [
            {
                'store_id': '1',
                'url': 'https://target.com/store/1',
                'slug': 'store-1',
                'name': 'Target Store 1',
                'extra_field': 'extra_value'
            }
        ]

        rich_cache.set('target', store_infos)
        retrieved = rich_cache.get('target')

        assert retrieved == store_infos
        assert retrieved[0]['extra_field'] == 'extra_value'


class TestResponseCache:
    """Test ResponseCache implementation."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "data" / "walmart" / "response_cache"

    @pytest.fixture
    def response_cache(self, cache_dir):
        """Create ResponseCache instance."""
        return ResponseCache('walmart', cache_dir=cache_dir, ttl_days=30)

    def test_set_and_get_response(self, response_cache):
        """Test setting and retrieving HTTP response."""
        url = 'https://walmart.com/store/12345'
        html = '<html><body>Store data</body></html>'

        response_cache.set(url, html)
        retrieved = response_cache.get(url)

        assert retrieved == html

    def test_cache_key_is_url_hash(self, response_cache):
        """Test cache key is full SHA256 hash of URL."""
        url = 'https://walmart.com/store/12345'
        cache_key = response_cache.get_cache_key(url)

        # Should be 64-char hex string (full SHA256)
        assert len(cache_key) == 64
        assert all(c in '0123456789abcdef' for c in cache_key)

    def test_different_urls_have_different_keys(self, response_cache):
        """Test different URLs produce different cache keys."""
        url1 = 'https://walmart.com/store/12345'
        url2 = 'https://walmart.com/store/67890'

        key1 = response_cache.get_cache_key(url1)
        key2 = response_cache.get_cache_key(url2)

        assert key1 != key2

    def test_same_url_has_same_key(self, response_cache):
        """Test same URL always produces same cache key."""
        url = 'https://walmart.com/store/12345'

        key1 = response_cache.get_cache_key(url)
        key2 = response_cache.get_cache_key(url)

        assert key1 == key2

    def test_force_refresh_bypasses_cache(self, response_cache):
        """Test force_refresh returns None even with valid cache."""
        url = 'https://walmart.com/store/12345'
        html = '<html><body>Store data</body></html>'

        response_cache.set(url, html)

        # Normal get works
        assert response_cache.get(url) is not None

        # Force refresh returns None
        assert response_cache.get(url, force_refresh=True) is None

    def test_ttl_days_default(self, tmp_path):
        """Test default TTL for response cache is 30 days."""
        cache_dir = tmp_path / "walmart" / "response_cache"
        response_cache = ResponseCache('walmart', cache_dir=cache_dir)

        # TTL should be 30 days
        assert response_cache.ttl.days == 30


class TestCacheInterface:
    """Test abstract CacheInterface functionality."""

    class MockCache(CacheInterface[str]):
        """Concrete implementation for testing."""

        def get_cache_key(self, identifier: str) -> str:
            return f"mock_{identifier}"

        def serialize(self, data: str) -> str:
            return data

        def deserialize(self, raw: str) -> str:
            return raw

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "mock_cache"

    @pytest.fixture
    def mock_cache(self, cache_dir):
        """Create mock cache instance."""
        return self.MockCache(cache_dir, ttl_days=7)

    def test_cache_dir_creation(self, mock_cache, cache_dir):
        """Test cache directory is created on init."""
        assert cache_dir.exists()

    def test_get_cache_file_path(self, mock_cache, cache_dir):
        """Test _get_cache_file returns correct path."""
        cache_file = mock_cache._get_cache_file('test')
        expected_path = cache_dir / 'mock_test.cache'
        assert cache_file == expected_path

    def test_metadata_includes_identifier(self, mock_cache):
        """Test cache file includes identifier in metadata."""
        mock_cache.set('test', 'test_data')

        cache_file = mock_cache._get_cache_file('test')
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        assert cache_data['identifier'] == 'test'

    def test_metadata_includes_cached_at(self, mock_cache):
        """Test cache file includes cached_at timestamp."""
        mock_cache.set('test', 'test_data')

        cache_file = mock_cache._get_cache_file('test')
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        assert 'cached_at' in cache_data
        # Should be valid ISO format timestamp
        datetime.fromisoformat(cache_data['cached_at'])

    def test_io_error_during_set_is_logged(self, mock_cache, cache_dir, caplog):
        """Test IOError during set is logged as warning."""
        # Make cache directory read-only to trigger IOError
        cache_dir.chmod(0o444)

        try:
            mock_cache.set('test', 'test_data')
            # Should have logged warning
            assert any('Failed to save cache' in record.message for record in caplog.records)
        finally:
            # Restore permissions
            cache_dir.chmod(0o755)

    def test_default_cache_dir_none_allowed(self):
        """Test that cache_dir can be created with default."""
        # Should not raise
        cache = URLListCache('test_retailer')
        assert cache.cache_dir == Path('data/test_retailer')


class TestCacheIntegration:
    """Integration tests for cache interface usage patterns."""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "integration"

    def test_url_cache_workflow(self, temp_cache_dir):
        """Test typical URL cache workflow."""
        cache = URLListCache('verizon', cache_dir=temp_cache_dir)

        # First run - no cache
        urls = cache.get('verizon')
        assert urls is None

        # Discover URLs
        discovered_urls = [
            'https://verizon.com/store/1',
            'https://verizon.com/store/2'
        ]
        cache.set('verizon', discovered_urls)

        # Second run - cache hit
        urls = cache.get('verizon')
        assert urls == discovered_urls

        # Third run - force refresh
        urls = cache.get('verizon', force_refresh=True)
        assert urls is None

    def test_response_cache_workflow(self, temp_cache_dir):
        """Test typical response cache workflow."""
        cache = ResponseCache('walmart', cache_dir=temp_cache_dir)

        url = 'https://walmart.com/store/12345'

        # First fetch - no cache
        html = cache.get(url)
        assert html is None

        # Fetch and cache
        fetched_html = '<html><body>Store 12345</body></html>'
        cache.set(url, fetched_html)

        # Second fetch - cache hit
        html = cache.get(url)
        assert html == fetched_html

        # Force refresh
        html = cache.get(url, force_refresh=True)
        assert html is None

    def test_rich_cache_workflow(self, temp_cache_dir):
        """Test typical rich URL cache workflow."""
        cache = RichURLCache('target', cache_dir=temp_cache_dir)

        # First run - no cache
        stores = cache.get('target')
        assert stores is None

        # Discover with metadata
        discovered_stores = [
            {'store_id': '1', 'url': 'https://target.com/1', 'slug': 's1'},
            {'store_id': '2', 'url': 'https://target.com/2', 'slug': 's2'}
        ]
        cache.set('target', discovered_stores)

        # Second run - cache hit
        stores = cache.get('target')
        assert stores == discovered_stores

    def test_multiple_caches_isolated(self, temp_cache_dir):
        """Test multiple cache types don't interfere."""
        url_cache = URLListCache('target', cache_dir=temp_cache_dir)
        rich_cache = RichURLCache('target', cache_dir=temp_cache_dir)

        # Set different data in each
        url_cache.set('target', ['url1', 'url2'])
        rich_cache.set('target', [{'store_id': '1', 'url': 'url1'}])

        # Each retrieves its own data
        urls = url_cache.get('target')
        stores = rich_cache.get('target')

        assert urls == ['url1', 'url2']
        assert stores == [{'store_id': '1', 'url': 'url1'}]


class TestCacheExpiryEdgeCases:
    """Test edge cases for TTL expiry calculation - Issue #154 bug fixes."""

    @pytest.fixture
    def cache_dir(self, tmp_path):
        """Create temporary cache directory."""
        return tmp_path / "cache"

    def test_zero_ttl_expires_immediately(self, cache_dir):
        """Test that cache with 0-day TTL expires after any time passes.

        This was a bug where integer truncation of .days caused 0-day TTL
        caches to never appear expired until a full day passed.
        """
        cache = URLListCache('test', cache_dir=cache_dir, ttl_days=0)

        urls = ['https://example.com/store/1']
        cache.set('test', urls)

        # Sleep briefly - cache should expire
        time.sleep(0.1)

        # get() should return None (expired)
        assert cache.get('test') is None

        # is_valid() should return False
        assert cache.is_valid('test') is False

        # get_metadata() should show expired=True
        metadata = cache.get_metadata('test')
        assert metadata is not None
        assert metadata['expired'] is True

    def test_metadata_expired_consistent_with_get(self, cache_dir):
        """Test that get_metadata().expired matches get() behavior.

        This was a bug where get_metadata() used truncated integer days
        while get() used precise timedelta comparison.
        """
        cache = URLListCache('test', cache_dir=cache_dir, ttl_days=0)

        urls = ['https://example.com/store/1']
        cache.set('test', urls)

        time.sleep(0.1)

        # Both should agree on expiry
        get_result = cache.get('test')
        metadata = cache.get_metadata('test')

        # If get() returns None (expired), metadata should show expired=True
        if get_result is None:
            assert metadata['expired'] is True
        else:
            assert metadata['expired'] is False

    def test_fractional_day_expiry(self, cache_dir):
        """Test cache expiry with sub-day precision.

        Uses 0-day TTL to test that fractional seconds are considered.
        """
        cache = URLListCache('test', cache_dir=cache_dir, ttl_days=0)

        urls = ['https://example.com/store/1']
        cache.set('test', urls)

        # Immediately after set, cache might still be valid (within same moment)
        # After a small delay, it should be expired
        time.sleep(0.05)

        # Should be expired
        assert cache.get('test') is None

    def test_cache_missing_cached_at_returns_none(self, cache_dir):
        """Test that cache without cached_at timestamp returns None."""
        cache = URLListCache('test', cache_dir=cache_dir)

        # Manually create malformed cache file
        cache_file = cache_dir / 'test_urls.cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({'data': '["url1"]'}))  # No cached_at

        # get() should return None and log warning
        assert cache.get('test') is None

        # is_valid() should return False
        assert cache.is_valid('test') is False

        # get_metadata() should return None
        assert cache.get_metadata('test') is None

    def test_is_valid_matches_get_behavior(self, cache_dir):
        """Test that is_valid() and get() return consistent results."""
        cache = URLListCache('test', cache_dir=cache_dir, ttl_days=0)

        urls = ['https://example.com/store/1']
        cache.set('test', urls)

        time.sleep(0.1)

        # Both should indicate cache is expired
        get_result = cache.get('test')
        is_valid_result = cache.is_valid('test')

        # If get() returns None, is_valid() should return False
        assert (get_result is None) == (not is_valid_result)
