"""Unit tests for AT&T scraper."""

import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.att import (
    ATTStore,
    _extract_store_type_and_dealer,
    get_store_urls_from_sitemap,
    extract_store_details,
    run,
    get_request_count,
    reset_request_counter,
    _check_pause_logic,
    _create_session_factory,
    _extract_single_store,
    _get_url_cache_path,
    _load_cached_urls,
    _save_cached_urls,
    URL_CACHE_EXPIRY_DAYS,
)


class TestATTStore:
    """Tests for ATTStore dataclass."""

    def test_to_dict_cor_store(self):
        """Test dict conversion for corporate store."""
        store = ATTStore(
            store_id='ATT-12345',
            name='AT&T Store',
            telephone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            rating_value=4.5,
            rating_count=120,
            url='https://www.att.com/stores/texas/dallas/12345',
            sub_channel='COR',
            dealer_name=None,
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == 'ATT-12345'
        assert result['sub_channel'] == 'COR'
        assert result['dealer_name'] is None

    def test_to_dict_dealer_store(self):
        """Test dict conversion for dealer store."""
        store = ATTStore(
            store_id='ATT-67890',
            name='Prime Wireless',
            telephone='(555) 987-6543',
            street_address='456 Oak Ave',
            city='Houston',
            state='TX',
            postal_code='77001',
            country='US',
            rating_value=3.8,
            rating_count=45,
            url='https://www.att.com/stores/texas/houston/67890',
            sub_channel='Dealer',
            dealer_name='PRIME COMMUNICATIONS',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == 'ATT-67890'
        assert result['sub_channel'] == 'Dealer'
        assert result['dealer_name'] == 'PRIME COMMUNICATIONS'


class TestExtractStoreTypeAndDealer:
    """Tests for _extract_store_type_and_dealer function."""

    def test_cor_store_detection(self):
        """Test detection of corporate retail store."""
        html = '''
        <script>
            let topDisplayType = "AT&T Retail";
            let storeMasterDealer = "";
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None

    def test_dealer_store_detection(self):
        """Test detection of dealer store with dealer name."""
        html = '''
        <script>
            let topDisplayType = "Authorized Retail";
            storeMasterDealer: "PRIME COMMUNICATIONS - 58"
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'Dealer'
        assert dealer_name == 'PRIME COMMUNICATIONS'

    def test_dealer_name_suffix_removal(self):
        """Test that dealer name suffix is properly removed."""
        html = '''
        <script>
            let topDisplayType = "Authorized Retail";
            storeMasterDealer: 'WIRELESS VISION - 123'
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'Dealer'
        assert dealer_name == 'WIRELESS VISION'

    def test_single_quotes_handling(self):
        """Test that single quotes are handled correctly."""
        html = '''
        <script>
            let topDisplayType = 'AT&T Retail';
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None

    def test_unknown_display_type_defaults_to_cor(self):
        """Test that unknown display type defaults to COR."""
        html = '''
        <script>
            let topDisplayType = "Unknown Type";
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None

    def test_missing_display_type_defaults_to_cor(self):
        """Test that missing display type defaults to COR."""
        html = '<html><body>No JavaScript here</body></html>'
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None


class TestGetStoreUrlsFromSitemap:
    """Tests for get_store_urls_from_sitemap function."""

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_parse_sitemap_xml(self, mock_counter, mock_get, mock_session):
        """Test parsing sitemap XML."""
        sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.att.com/stores/texas/dallas/12345</loc>
    </url>
    <url>
        <loc>https://www.att.com/stores/texas/houston/67890</loc>
    </url>
    <url>
        <loc>https://www.att.com/stores/texas</loc>
    </url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = sitemap_xml.encode('utf-8')
        mock_get.return_value = mock_response

        urls = get_store_urls_from_sitemap(mock_session)

        # Should only include URLs ending in numeric IDs
        assert len(urls) == 2
        assert 'https://www.att.com/stores/texas/dallas/12345' in urls
        assert 'https://www.att.com/stores/texas/houston/67890' in urls

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_failed_fetch_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that failed fetch returns empty list."""
        mock_get.return_value = None

        urls = get_store_urls_from_sitemap(mock_session)

        assert not urls

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_filters_non_store_urls(self, mock_counter, mock_get, mock_session):
        """Test that non-store URLs are filtered out."""
        sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.att.com/stores/texas/dallas/12345</loc></url>
    <url><loc>https://www.att.com/stores/texas</loc></url>
    <url><loc>https://www.att.com/stores</loc></url>
    <url><loc>https://www.att.com/about</loc></url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = sitemap_xml.encode('utf-8')
        mock_get.return_value = mock_response

        urls = get_store_urls_from_sitemap(mock_session)

        # Only the URL ending in numeric ID should be included
        assert len(urls) == 1
        assert urls[0] == 'https://www.att.com/stores/texas/dallas/12345'


class TestATTRun:
    """Tests for AT&T run() method."""

    def _make_sitemap_response(self, store_ids):
        """Helper to create sitemap response with given store IDs."""
        urls = '\n'.join(
            f'<url><loc>https://www.att.com/stores/texas/dallas/{sid}</loc></url>'
            for sid in store_ids
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_page_response(self, store_id, sub_channel='COR'):
        """Helper to create store page HTML response."""
        display_type = 'AT&T Retail' if sub_channel == 'COR' else 'Authorized Retail'
        dealer_line = '' if sub_channel == 'COR' else 'storeMasterDealer: "TEST DEALER - 1"'
        html = f'''<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{{
    "@type": "MobilePhoneStore",
    "name": "AT&T Store {store_id}",
    "telephone": "(555) 123-4567",
    "address": {{
        "streetAddress": "{store_id} Main St",
        "addressLocality": "Dallas",
        "addressRegion": "TX",
        "postalCode": "75001",
        "addressCountry": {{"name": "US"}}
    }},
    "aggregateRating": {{"ratingValue": "4.5", "ratingCount": "120"}}
}}
</script>
</head>
<body>
<script>
let topDisplayType = "{display_type}";
{dealer_line}
</script>
</body>
</html>'''
        response = Mock()
        response.text = html
        response.content = html.encode('utf-8')
        return response

    @patch('src.scrapers.att._save_cached_urls')
    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_returns_correct_structure(self, mock_counter, mock_get, mock_load_cache, mock_save_cache, mock_session):
        """Test that run() returns the expected structure."""
        mock_load_cache.return_value = None
        mock_get.side_effect = [
            self._make_sitemap_response([12345]),
            self._make_store_page_response(12345)
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.att._save_cached_urls')
    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_with_limit(self, mock_counter, mock_get, mock_load_cache, mock_save_cache, mock_session):
        """Test run() respects limit parameter."""
        mock_load_cache.return_value = None
        mock_get.side_effect = [
            self._make_sitemap_response([12345, 12346, 12347, 12348, 12349]),
            self._make_store_page_response(12345),
            self._make_store_page_response(12346),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att', limit=2)

        assert result['count'] == 2
        assert len(result['stores']) == 2

    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_load_cache, mock_session):
        """Test run() with empty sitemap returns empty stores."""
        mock_load_cache.return_value = None
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False

    @patch('src.scrapers.att._save_cached_urls')
    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_count_matches_stores_length(self, mock_counter, mock_get, mock_load_cache, mock_save_cache, mock_session):
        """Test that count matches the actual number of stores."""
        mock_load_cache.return_value = None
        mock_get.side_effect = [
            self._make_sitemap_response([12345, 12346, 12347]),
            self._make_store_page_response(12345),
            self._make_store_page_response(12346),
            self._make_store_page_response(12347),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att')

        assert result['count'] == len(result['stores'])


class TestATTCheckpoint:
    """Tests for AT&T checkpoint/resume functionality."""

    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.load_checkpoint')
    @patch('src.scrapers.att.utils.save_checkpoint')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_resume_loads_checkpoint(self, mock_counter, mock_get, mock_save, mock_load, mock_load_cache, mock_session):
        """Test that resume=True loads existing checkpoint."""
        mock_load_cache.return_value = None
        mock_load.return_value = {
            'stores': [{'store_id': '12345', 'name': 'Existing Store'}],
            'completed_urls': ['https://www.att.com/stores/texas/dallas/12345']
        }
        # Sitemap with URLs (must be non-empty for checkpoints_used to be True)
        xml = '''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.att.com/stores/texas/dallas/12345</loc></url>
        </urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att', resume=True)

        mock_load.assert_called_once()
        assert result['checkpoints_used'] is True

    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.load_checkpoint')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_no_resume_starts_fresh(self, mock_counter, mock_get, mock_load, mock_load_cache, mock_session):
        """Test that resume=False does not load checkpoint."""
        mock_load_cache.return_value = None
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att', resume=False)

        mock_load.assert_not_called()
        assert result['checkpoints_used'] is False


class TestATTRateLimiting:
    """Tests for AT&T rate limiting and pause logic."""

    def test_request_counter_reset(self):
        """Test that request counter resets properly."""
        reset_request_counter()
        assert get_request_count() == 0

    @patch('src.scrapers.att.time.sleep')
    @patch('src.scrapers.att.random.uniform')
    def test_pause_at_50_requests(self, mock_uniform, mock_sleep):
        """Test that pause triggers at 50 request threshold."""
        mock_uniform.return_value = 15
        reset_request_counter()

        from src.scrapers.att import _request_counter
        _request_counter._count = 50

        _check_pause_logic()

        mock_sleep.assert_called_once()
        mock_uniform.assert_called()

    @patch('src.scrapers.att.time.sleep')
    @patch('src.scrapers.att.random.uniform')
    def test_pause_at_200_requests(self, mock_uniform, mock_sleep):
        """Test that longer pause triggers at 200 request threshold."""
        mock_uniform.return_value = 180
        reset_request_counter()

        from src.scrapers.att import _request_counter
        _request_counter._count = 200

        _check_pause_logic()

        mock_sleep.assert_called_once()

    @patch('src.scrapers.att.time.sleep')
    def test_no_pause_between_thresholds(self, mock_sleep):
        """Test that no pause occurs between thresholds."""
        reset_request_counter()

        from src.scrapers.att import _request_counter
        _request_counter._count = 25

        _check_pause_logic()

        mock_sleep.assert_not_called()


class TestATTErrorHandling:
    """Tests for AT&T error handling."""

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_sitemap_fetch_failure_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that sitemap fetch failure returns empty list."""
        mock_get.return_value = None

        urls = get_store_urls_from_sitemap(mock_session)

        assert not urls

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_store_fetch_failure_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that store page fetch failure returns None."""
        mock_get.return_value = None

        store = extract_store_details(mock_session, 'https://www.att.com/stores/texas/dallas/12345')

        assert store is None

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_malformed_xml_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that malformed XML returns empty list."""
        response = Mock()
        response.content = b'<not valid xml'
        mock_get.return_value = response

        urls = get_store_urls_from_sitemap(mock_session)

        assert not urls

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_missing_json_ld_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that missing JSON-LD returns None."""
        html = '<html><body>No JSON-LD here</body></html>'
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.att.com/stores/texas/dallas/12345')

        assert store is None

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_wrong_json_ld_type_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that wrong JSON-LD type returns None."""
        html = '''<html><head>
<script type="application/ld+json">{"@type": "Organization", "name": "AT&T"}</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.att.com/stores/texas/dallas/12345')

        assert store is None


class TestATTParallelExtraction:
    """Tests for AT&T parallel extraction infrastructure."""

    def test_create_session_factory_returns_callable(self):
        """Test that session factory returns a callable."""
        config = {'proxy': {'mode': 'direct'}}

        with patch('src.scrapers.att.utils.create_proxied_session') as mock_create:
            mock_session = Mock()
            mock_create.return_value = mock_session

            factory = _create_session_factory(config)

            assert callable(factory)
            # Call the factory to verify it works
            session = factory()
            mock_create.assert_called_once_with(config)
            assert session == mock_session

    def test_create_session_factory_creates_new_session_each_call(self):
        """Test that factory creates a new session each time it's called."""
        config = {'proxy': {'mode': 'residential'}}

        with patch('src.scrapers.att.utils.create_proxied_session') as mock_create:
            session1 = Mock()
            session2 = Mock()
            mock_create.side_effect = [session1, session2]

            factory = _create_session_factory(config)

            result1 = factory()
            result2 = factory()

            assert result1 == session1
            assert result2 == session2
            assert mock_create.call_count == 2

    @patch('src.scrapers.att.extract_store_details')
    def test_extract_single_store_success(self, mock_extract):
        """Test worker function returns store data on success."""
        mock_store = Mock()
        mock_store.to_dict.return_value = {'store_id': '12345', 'name': 'Test Store'}
        mock_extract.return_value = mock_store

        mock_session = Mock()
        session_factory = Mock(return_value=mock_session)
        yaml_config = {'proxy': {'mode': 'residential'}}

        url = 'https://www.att.com/stores/texas/dallas/12345'
        result_url, result_data = _extract_single_store(url, session_factory, 'att', yaml_config)

        assert result_url == url
        assert result_data == {'store_id': '12345', 'name': 'Test Store'}
        mock_extract.assert_called_once_with(mock_session, url, 'att', yaml_config)

    @patch('src.scrapers.att.extract_store_details')
    def test_extract_single_store_failure(self, mock_extract):
        """Test worker function returns None on extraction failure."""
        mock_extract.return_value = None

        mock_session = Mock()
        session_factory = Mock(return_value=mock_session)

        url = 'https://www.att.com/stores/texas/dallas/12345'
        result_url, result_data = _extract_single_store(url, session_factory, 'att')

        assert result_url == url
        assert result_data is None

    @patch('src.scrapers.att.extract_store_details')
    def test_extract_single_store_exception(self, mock_extract):
        """Test worker function handles exceptions gracefully."""
        mock_extract.side_effect = Exception("Network error")

        mock_session = Mock()
        session_factory = Mock(return_value=mock_session)

        url = 'https://www.att.com/stores/texas/dallas/12345'
        result_url, result_data = _extract_single_store(url, session_factory, 'att')

        assert result_url == url
        assert result_data is None

    @patch('src.scrapers.att.extract_store_details')
    def test_extract_single_store_closes_session(self, mock_extract):
        """Test worker function closes session after use."""
        mock_store = Mock()
        mock_store.to_dict.return_value = {'store_id': '12345'}
        mock_extract.return_value = mock_store

        mock_session = Mock()
        session_factory = Mock(return_value=mock_session)

        url = 'https://www.att.com/stores/texas/dallas/12345'
        _extract_single_store(url, session_factory, 'att')

        mock_session.close.assert_called_once()


class TestATTURLCaching:
    """Tests for AT&T URL caching functionality."""

    def test_get_url_cache_path(self):
        """Test cache path generation."""
        path = _get_url_cache_path('att')

        assert path == Path('data/att/store_urls.json')

    def test_load_cached_urls_no_cache_file(self):
        """Test loading when cache file doesn't exist."""
        with patch.object(Path, 'exists', return_value=False):
            result = _load_cached_urls('att')

        assert result is None

    def test_load_cached_urls_valid_cache(self):
        """Test loading valid, fresh cache."""
        cache_data = {
            'discovered_at': datetime.now().isoformat(),
            'store_count': 3,
            'urls': [
                'https://www.att.com/stores/texas/dallas/1',
                'https://www.att.com/stores/texas/dallas/2',
                'https://www.att.com/stores/texas/dallas/3'
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cache_data, f)
            temp_path = Path(f.name)

        try:
            with patch('src.scrapers.att._get_url_cache_path', return_value=temp_path):
                result = _load_cached_urls('att')

            assert result is not None
            assert len(result) == 3
            assert 'https://www.att.com/stores/texas/dallas/1' in result
        finally:
            temp_path.unlink()

    def test_load_cached_urls_expired_cache(self):
        """Test loading expired cache returns None."""
        old_date = datetime.now() - timedelta(days=URL_CACHE_EXPIRY_DAYS + 1)
        cache_data = {
            'discovered_at': old_date.isoformat(),
            'store_count': 3,
            'urls': ['url1', 'url2', 'url3']
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(cache_data, f)
            temp_path = Path(f.name)

        try:
            with patch('src.scrapers.att._get_url_cache_path', return_value=temp_path):
                result = _load_cached_urls('att')

            assert result is None
        finally:
            temp_path.unlink()

    def test_load_cached_urls_invalid_json(self):
        """Test loading invalid JSON returns None."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('not valid json')
            temp_path = Path(f.name)

        try:
            with patch('src.scrapers.att._get_url_cache_path', return_value=temp_path):
                result = _load_cached_urls('att')

            assert result is None
        finally:
            temp_path.unlink()

    def test_save_cached_urls(self):
        """Test saving URLs to cache."""
        urls = [
            'https://www.att.com/stores/texas/dallas/1',
            'https://www.att.com/stores/texas/dallas/2'
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / 'data' / 'att' / 'store_urls.json'

            with patch('src.scrapers.att._get_url_cache_path', return_value=cache_path):
                _save_cached_urls('att', urls)

            assert cache_path.exists()

            with open(cache_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)

            assert saved_data['store_count'] == 2
            assert saved_data['urls'] == urls
            assert 'discovered_at' in saved_data

    def test_save_cached_urls_creates_parent_dirs(self):
        """Test that save creates parent directories if needed."""
        urls = ['https://www.att.com/stores/texas/dallas/1']

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / 'nested' / 'dir' / 'store_urls.json'

            with patch('src.scrapers.att._get_url_cache_path', return_value=cache_path):
                _save_cached_urls('att', urls)

            assert cache_path.exists()


class TestATTRunParallel:
    """Tests for AT&T run() with parallel extraction."""

    def _make_sitemap_response(self, store_ids):
        """Helper to create sitemap response with given store IDs."""
        urls = '\n'.join(
            f'<url><loc>https://www.att.com/stores/texas/dallas/{sid}</loc></url>'
            for sid in store_ids
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_page_response(self, store_id, sub_channel='COR'):
        """Helper to create store page HTML response."""
        display_type = 'AT&T Retail' if sub_channel == 'COR' else 'Authorized Retail'
        dealer_line = '' if sub_channel == 'COR' else 'storeMasterDealer: "TEST DEALER - 1"'
        html = f'''<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{{
    "@type": "MobilePhoneStore",
    "name": "AT&T Store {store_id}",
    "telephone": "(555) 123-4567",
    "address": {{
        "streetAddress": "{store_id} Main St",
        "addressLocality": "Dallas",
        "addressRegion": "TX",
        "postalCode": "75001",
        "addressCountry": {{"name": "US"}}
    }},
    "aggregateRating": {{"ratingValue": "4.5", "ratingCount": "120"}}
}}
</script>
</head>
<body>
<script>
let topDisplayType = "{display_type}";
{dealer_line}
</script>
</body>
</html>'''
        response = Mock()
        response.text = html
        response.content = html.encode('utf-8')
        return response

    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_uses_cached_urls(self, mock_counter, mock_get, mock_load_cache, mock_session):
        """Test that run() uses cached URLs when available."""
        mock_load_cache.return_value = [
            'https://www.att.com/stores/texas/dallas/12345'
        ]
        mock_get.return_value = self._make_store_page_response(12345)

        result = run(
            mock_session,
            {'checkpoint_interval': 100, 'proxy': {'mode': 'direct'}},
            retailer='att'
        )

        mock_load_cache.assert_called_once_with('att')
        assert result['count'] == 1

    @patch('src.scrapers.att._save_cached_urls')
    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_saves_urls_on_cache_miss(self, mock_counter, mock_get, mock_load_cache, mock_save_cache, mock_session):
        """Test that run() saves URLs after sitemap fetch on cache miss."""
        mock_load_cache.return_value = None
        mock_get.side_effect = [
            self._make_sitemap_response([12345]),
            self._make_store_page_response(12345)
        ]

        result = run(
            mock_session,
            {'checkpoint_interval': 100, 'proxy': {'mode': 'direct'}},
            retailer='att'
        )

        mock_save_cache.assert_called_once()
        call_args = mock_save_cache.call_args
        assert call_args[0][0] == 'att'
        assert len(call_args[0][1]) == 1

    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_refresh_urls_ignores_cache(self, mock_counter, mock_get, mock_load_cache, mock_session):
        """Test that refresh_urls=True forces sitemap fetch."""
        mock_get.side_effect = [
            self._make_sitemap_response([12345]),
            self._make_store_page_response(12345)
        ]

        result = run(
            mock_session,
            {'checkpoint_interval': 100, 'proxy': {'mode': 'direct'}},
            retailer='att',
            refresh_urls=True
        )

        # Cache should not be loaded when refresh_urls=True
        mock_load_cache.assert_not_called()

    @patch('src.scrapers.att._load_cached_urls')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_respects_parallel_workers_config(self, mock_counter, mock_get, mock_load_cache, mock_session):
        """Test that run() uses parallel_workers from config."""
        mock_load_cache.return_value = [
            'https://www.att.com/stores/texas/dallas/12345'
        ]
        mock_get.return_value = self._make_store_page_response(12345)

        # Test with residential proxy - should default to 5 workers
        config = {'checkpoint_interval': 100, 'proxy': {'mode': 'residential'}}
        result = run(mock_session, config, retailer='att')
        assert result['count'] == 1

        # Test with explicit parallel_workers
        config_explicit = {'checkpoint_interval': 100, 'proxy': {'mode': 'residential'}, 'parallel_workers': 3}
        result2 = run(mock_session, config_explicit, retailer='att')
        assert result2['count'] == 1
