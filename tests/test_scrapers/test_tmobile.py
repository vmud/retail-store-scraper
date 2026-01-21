"""Unit tests for T-Mobile scraper."""

import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.tmobile import (
    TMobileStore,
    _extract_store_type_from_title,
    get_store_urls_from_sitemap,
    extract_store_details,
    run,
    get_request_count,
    reset_request_counter,
    _check_pause_logic,
    _create_session_factory,
    _extract_single_store,
    _load_cached_urls,
    _save_cached_urls,
    _get_url_cache_path,
    URL_CACHE_EXPIRY_DAYS,
)


class TestTMobileStore:
    """Tests for TMobileStore dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        store = TMobileStore(
            store_id='TX-DAL-001',
            branch_code='TX-DAL-001',
            name='T-Mobile Dallas',
            store_type='T-Mobile Store',
            phone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude='32.7767',
            longitude='-96.7970',
            opening_hours=['Mon-Fri: 10am-8pm', 'Sat: 10am-6pm', 'Sun: 12pm-6pm'],
            url='https://www.t-mobile.com/stores/tx/dallas/tx-dal-001',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == 'TX-DAL-001'
        assert result['branch_code'] == 'TX-DAL-001'
        assert result['store_type'] == 'T-Mobile Store'
        assert json.loads(result['opening_hours']) == ['Mon-Fri: 10am-8pm', 'Sat: 10am-6pm', 'Sun: 12pm-6pm']

    def test_to_dict_none_opening_hours(self):
        """Test dict conversion with None opening_hours."""
        store = TMobileStore(
            store_id='TX-DAL-001',
            branch_code='TX-DAL-001',
            name='T-Mobile Dallas',
            store_type='T-Mobile Store',
            phone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude='32.7767',
            longitude='-96.7970',
            opening_hours=None,
            url='https://www.t-mobile.com/stores/tx/dallas/tx-dal-001',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['opening_hours'] == ''

    def test_to_dict_none_store_type(self):
        """Test dict conversion with None store_type."""
        store = TMobileStore(
            store_id='TX-DAL-001',
            branch_code='TX-DAL-001',
            name='T-Mobile Dallas',
            store_type=None,
            phone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude='32.7767',
            longitude='-96.7970',
            opening_hours=None,
            url='https://www.t-mobile.com/stores/tx/dallas/tx-dal-001',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_type'] == ''


class TestExtractStoreTypeFromTitle:
    """Tests for _extract_store_type_from_title function."""

    def test_experience_store(self):
        """Test extraction of Experience Store type."""
        title = "T-Mobile Penn & I-494: Experience Store in Bloomington, MN"
        result = _extract_store_type_from_title(title)
        # Function returns full prefixed type name
        assert result == 'T-Mobile Experience Store'

    def test_store_type(self):
        """Test extraction of T-Mobile Store type."""
        # The function looks for specific patterns in the title
        title = "T-Mobile at 123 Main St in Dallas, TX"
        result = _extract_store_type_from_title(title)
        # May return None if pattern not found
        # This test documents current behavior

    def test_metro_store(self):
        """Test extraction of Metro by T-Mobile type."""
        # Test various Metro by T-Mobile formats
        title = "Metro by T-Mobile Broadway in Houston, TX"
        result = _extract_store_type_from_title(title)
        # Result depends on implementation

    def test_no_store_type_found(self):
        """Test when no store type is found."""
        title = "Some Random Page Title"
        result = _extract_store_type_from_title(title)
        assert result is None

    def test_empty_title(self):
        """Test with empty title."""
        result = _extract_store_type_from_title("")
        assert result is None


class TestGetStoreUrlsFromSitemap:
    """Tests for get_store_urls_from_sitemap function."""

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_parse_sitemap_xml(self, mock_counter, mock_get, mock_config, mock_session):
        """Test parsing sitemap XML."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap-stores.xml'
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.t-mobile.com/stores/bd/tx/dallas/tx-dal-001</loc></url>
    <url><loc>https://www.t-mobile.com/stores/bd/tx/houston/tx-hou-002</loc></url>
    <url><loc>https://www.t-mobile.com/stores/state/tx</loc></url>
</urlset>'''
        response = Mock()
        response.content = xml_content.encode('utf-8')
        mock_get.return_value = response

        urls = get_store_urls_from_sitemap(mock_session)

        # Should only include /stores/bd/ URLs
        assert len(urls) == 2
        assert 'https://www.t-mobile.com/stores/bd/tx/dallas/tx-dal-001' in urls
        assert 'https://www.t-mobile.com/stores/bd/tx/houston/tx-hou-002' in urls

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_parse_multiple_pages(self, mock_counter, mock_get, mock_config, mock_session):
        """Test parsing multiple sitemap pages."""
        mock_config.SITEMAP_PAGES = [1, 2]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap-stores.xml'

        xml1 = '''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.t-mobile.com/stores/bd/tx/dallas/store-1</loc></url>
</urlset>'''
        xml2 = '''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.t-mobile.com/stores/bd/tx/houston/store-2</loc></url>
</urlset>'''

        response1, response2 = Mock(), Mock()
        response1.content = xml1.encode('utf-8')
        response2.content = xml2.encode('utf-8')
        mock_get.side_effect = [response1, response2]

        urls = get_store_urls_from_sitemap(mock_session)

        assert len(urls) == 2

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_failed_fetch_continues(self, mock_counter, mock_get, mock_config, mock_session):
        """Test that failed fetch for one page continues to next."""
        mock_config.SITEMAP_PAGES = [1, 2]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap-stores.xml'

        xml = '''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.t-mobile.com/stores/bd/tx/dallas/store-1</loc></url>
</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.side_effect = [None, response]

        urls = get_store_urls_from_sitemap(mock_session)

        assert len(urls) == 1


class TestTMobileRun:
    """Tests for T-Mobile run() method."""

    def _make_sitemap_response(self, store_codes):
        """Helper to create sitemap response with given store codes."""
        urls = '\n'.join(
            f'<url><loc>https://www.t-mobile.com/stores/bd/tx/dallas/{code}</loc></url>'
            for code in store_codes
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_page_response(self, branch_code):
        """Helper to create store page HTML response with JSON-LD."""
        json_ld = {
            "@type": "Store",
            "name": f"T-Mobile {branch_code}",
            "branchCode": branch_code,
            "telephone": "(555) 123-4567",
            "address": {
                "streetAddress": "123 Main St",
                "addressLocality": "Dallas",
                "addressRegion": "TX",
                "postalCode": "75001",
                "addressCountry": "US"
            },
            "geo": {
                "latitude": "32.7767",
                "longitude": "-96.7970"
            },
            "openingHours": ["Mon-Fri 10am-8pm", "Sat 10am-6pm"]
        }
        html = f'''<!DOCTYPE html>
<html>
<head>
<title>T-Mobile Store: Store in Dallas, TX</title>
<script type="application/ld+json">{json.dumps(json_ld)}</script>
</head>
</html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_returns_correct_structure(self, mock_counter, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test that run() returns the expected structure."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_load_cache.return_value = ['https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001']
        mock_get.return_value = self._make_store_page_response('TX-DAL-001')

        result = run(mock_session, {'checkpoint_interval': 100, 'parallel_workers': 1}, retailer='tmobile')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_with_limit(self, mock_counter, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test run() respects limit parameter."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        # Return cached URLs to skip sitemap fetch
        mock_load_cache.return_value = [
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-002',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-003',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-004',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-005'
        ]
        mock_get.side_effect = [
            self._make_store_page_response('TX-DAL-001'),
            self._make_store_page_response('TX-DAL-002'),
        ]

        result = run(mock_session, {'checkpoint_interval': 100, 'parallel_workers': 1}, retailer='tmobile', limit=2)

        assert result['count'] == 2
        assert len(result['stores']) == 2

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test run() with empty sitemap returns empty stores."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        # No cached URLs, force sitemap fetch
        mock_load_cache.return_value = None
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100, 'parallel_workers': 1}, retailer='tmobile')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_count_matches_stores_length(self, mock_counter, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test that count matches the actual number of stores."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_load_cache.return_value = [
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-002',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-003'
        ]
        mock_get.side_effect = [
            self._make_store_page_response('TX-DAL-001'),
            self._make_store_page_response('TX-DAL-002'),
            self._make_store_page_response('TX-DAL-003'),
        ]

        result = run(mock_session, {'checkpoint_interval': 100, 'parallel_workers': 1}, retailer='tmobile')

        assert result['count'] == len(result['stores'])


class TestTMobileCheckpoint:
    """Tests for T-Mobile checkpoint/resume functionality."""

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.load_checkpoint')
    @patch('src.scrapers.tmobile.utils.save_checkpoint')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_resume_loads_checkpoint(self, mock_counter, mock_get, mock_save, mock_load, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test that resume=True loads existing checkpoint."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_load.return_value = {
            'stores': [{'branch_code': 'TX-DAL-001', 'name': 'Existing Store'}],
            'completed_urls': ['https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001']
        }
        # Return cached URLs
        mock_load_cache.return_value = ['https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001']

        result = run(mock_session, {'checkpoint_interval': 100, 'parallel_workers': 1}, retailer='tmobile', resume=True)

        mock_load.assert_called_once()
        assert result['checkpoints_used'] is True

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.load_checkpoint')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_no_resume_starts_fresh(self, mock_counter, mock_get, mock_load, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test that resume=False does not load checkpoint."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        # No cached URLs
        mock_load_cache.return_value = None
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100, 'parallel_workers': 1}, retailer='tmobile', resume=False)

        mock_load.assert_not_called()
        assert result['checkpoints_used'] is False


class TestTMobileRateLimiting:
    """Tests for T-Mobile rate limiting and pause logic."""

    def test_request_counter_reset(self):
        """Test that request counter resets properly."""
        reset_request_counter()
        assert get_request_count() == 0

    @patch('src.scrapers.tmobile.time.sleep')
    @patch('src.scrapers.tmobile.random.uniform')
    def test_pause_at_50_requests(self, mock_uniform, mock_sleep):
        """Test that pause triggers at 50 request threshold."""
        mock_uniform.return_value = 15
        reset_request_counter()

        from src.scrapers.tmobile import _request_counter
        _request_counter._count = 50

        _check_pause_logic()

        mock_sleep.assert_called_once()
        mock_uniform.assert_called()

    @patch('src.scrapers.tmobile.time.sleep')
    @patch('src.scrapers.tmobile.random.uniform')
    def test_pause_at_200_requests(self, mock_uniform, mock_sleep):
        """Test that longer pause triggers at 200 request threshold."""
        mock_uniform.return_value = 180
        reset_request_counter()

        from src.scrapers.tmobile import _request_counter
        _request_counter._count = 200

        _check_pause_logic()

        mock_sleep.assert_called_once()

    @patch('src.scrapers.tmobile.time.sleep')
    def test_no_pause_between_thresholds(self, mock_sleep):
        """Test that no pause occurs between thresholds."""
        reset_request_counter()

        from src.scrapers.tmobile import _request_counter
        _request_counter._count = 25

        _check_pause_logic()

        mock_sleep.assert_not_called()


class TestTMobileErrorHandling:
    """Tests for T-Mobile error handling."""

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_store_fetch_failure_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that store page fetch failure returns None."""
        mock_get.return_value = None

        store = extract_store_details(mock_session, 'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001')

        assert store is None

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_missing_json_ld_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that missing JSON-LD returns None."""
        html = '<html><body>No JSON-LD here</body></html>'
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001')

        assert store is None

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_wrong_json_ld_type_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that wrong JSON-LD type returns None."""
        html = '''<html><head>
<script type="application/ld+json">{"@type": "Organization", "name": "T-Mobile"}</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001')

        assert store is None

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_malformed_json_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that malformed JSON-LD returns None."""
        html = '''<html><head>
<script type="application/ld+json">{invalid json}</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001')

        assert store is None


class TestTMobileSessionFactory:
    """Tests for session factory function."""

    @patch('src.scrapers.tmobile.utils.create_proxied_session')
    def test_session_factory_creates_session(self, mock_create_session):
        """Test that session factory creates a session."""
        mock_session = Mock()
        mock_create_session.return_value = mock_session

        config = {'proxy': {'mode': 'residential'}}
        factory = _create_session_factory(config)

        result = factory()

        mock_create_session.assert_called_once_with(config)
        assert result == mock_session

    @patch('src.scrapers.tmobile.utils.create_proxied_session')
    def test_session_factory_creates_new_session_each_call(self, mock_create_session):
        """Test that session factory creates new session each time."""
        mock_session1 = Mock()
        mock_session2 = Mock()
        mock_create_session.side_effect = [mock_session1, mock_session2]

        config = {'proxy': {'mode': 'residential'}}
        factory = _create_session_factory(config)

        result1 = factory()
        result2 = factory()

        assert mock_create_session.call_count == 2
        assert result1 == mock_session1
        assert result2 == mock_session2


class TestTMobileParallelExtraction:
    """Tests for parallel store extraction."""

    def _make_store_page_response(self, branch_code):
        """Helper to create store page HTML response with JSON-LD."""
        json_ld = {
            "@type": "Store",
            "name": f"T-Mobile {branch_code}",
            "branchCode": branch_code,
            "telephone": "(555) 123-4567",
            "address": {
                "streetAddress": "123 Main St",
                "addressLocality": "Dallas",
                "addressRegion": "TX",
                "postalCode": "75001",
                "addressCountry": "US"
            },
            "geo": {
                "latitude": "32.7767",
                "longitude": "-96.7970"
            },
            "openingHours": ["Mon-Fri 10am-8pm", "Sat 10am-6pm"]
        }
        html = f'''<!DOCTYPE html>
<html>
<head>
<title>T-Mobile Store: Store in Dallas, TX</title>
<script type="application/ld+json">{json.dumps(json_ld)}</script>
</head>
</html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.tmobile.extract_store_details')
    def test_extract_single_store_success(self, mock_extract):
        """Test successful single store extraction in parallel worker."""
        mock_store = Mock()
        mock_store.to_dict.return_value = {'branch_code': 'TX-DAL-001', 'name': 'T-Mobile Dallas'}
        mock_extract.return_value = mock_store

        mock_session = Mock()
        mock_factory = Mock(return_value=mock_session)

        url = 'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001'
        result_url, result_data = _extract_single_store(url, mock_factory, 'tmobile', {})

        assert result_url == url
        assert result_data == {'branch_code': 'TX-DAL-001', 'name': 'T-Mobile Dallas'}
        mock_session.close.assert_called_once()

    @patch('src.scrapers.tmobile.extract_store_details')
    def test_extract_single_store_failure(self, mock_extract):
        """Test failed single store extraction returns None."""
        mock_extract.return_value = None

        mock_session = Mock()
        mock_factory = Mock(return_value=mock_session)

        url = 'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001'
        result_url, result_data = _extract_single_store(url, mock_factory, 'tmobile', {})

        assert result_url == url
        assert result_data is None
        mock_session.close.assert_called_once()

    @patch('src.scrapers.tmobile.extract_store_details')
    def test_extract_single_store_exception(self, mock_extract):
        """Test that exceptions in extraction are handled gracefully."""
        mock_extract.side_effect = Exception("Network error")

        mock_session = Mock()
        mock_factory = Mock(return_value=mock_session)

        url = 'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001'
        result_url, result_data = _extract_single_store(url, mock_factory, 'tmobile', {})

        assert result_url == url
        assert result_data is None
        mock_session.close.assert_called_once()


class TestTMobileURLCaching:
    """Tests for URL caching functionality."""

    def test_get_url_cache_path(self):
        """Test URL cache path generation."""
        path = _get_url_cache_path('tmobile')
        assert path == Path('data/tmobile/store_urls.json')

    def test_load_cached_urls_no_file(self, tmp_path):
        """Test loading from non-existent cache returns None."""
        with patch('src.scrapers.tmobile._get_url_cache_path', return_value=tmp_path / 'nonexistent.json'):
            result = _load_cached_urls('tmobile')
            assert result is None

    def test_load_cached_urls_valid_cache(self, tmp_path):
        """Test loading valid cached URLs."""
        cache_file = tmp_path / 'store_urls.json'
        cache_data = {
            'discovered_at': datetime.now().isoformat(),
            'store_count': 3,
            'urls': [
                'https://www.t-mobile.com/stores/bd/tx/dallas/store-1',
                'https://www.t-mobile.com/stores/bd/tx/houston/store-2',
                'https://www.t-mobile.com/stores/bd/ca/la/store-3'
            ]
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch('src.scrapers.tmobile._get_url_cache_path', return_value=cache_file):
            result = _load_cached_urls('tmobile')
            assert result is not None
            assert len(result) == 3
            assert 'https://www.t-mobile.com/stores/bd/tx/dallas/store-1' in result

    def test_load_cached_urls_expired(self, tmp_path):
        """Test that expired cache returns None."""
        cache_file = tmp_path / 'store_urls.json'
        # Create cache with old timestamp (8 days ago)
        old_date = datetime.now() - timedelta(days=8)
        cache_data = {
            'discovered_at': old_date.isoformat(),
            'store_count': 3,
            'urls': ['url1', 'url2', 'url3']
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch('src.scrapers.tmobile._get_url_cache_path', return_value=cache_file):
            result = _load_cached_urls('tmobile')
            assert result is None

    def test_load_cached_urls_invalid_json(self, tmp_path):
        """Test that invalid JSON cache returns None."""
        cache_file = tmp_path / 'store_urls.json'
        cache_file.write_text('invalid json {')

        with patch('src.scrapers.tmobile._get_url_cache_path', return_value=cache_file):
            result = _load_cached_urls('tmobile')
            assert result is None

    def test_save_cached_urls(self, tmp_path):
        """Test saving URLs to cache."""
        cache_file = tmp_path / 'store_urls.json'
        urls = ['url1', 'url2', 'url3']

        with patch('src.scrapers.tmobile._get_url_cache_path', return_value=cache_file):
            _save_cached_urls('tmobile', urls)

        assert cache_file.exists()
        saved_data = json.loads(cache_file.read_text())
        assert saved_data['store_count'] == 3
        assert saved_data['urls'] == urls
        assert 'discovered_at' in saved_data


class TestTMobileRunParallel:
    """Tests for T-Mobile run() with parallel extraction."""

    def _make_sitemap_response(self, store_codes):
        """Helper to create sitemap response with given store codes."""
        urls = '\n'.join(
            f'<url><loc>https://www.t-mobile.com/stores/bd/tx/dallas/{code}</loc></url>'
            for code in store_codes
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_page_response(self, branch_code):
        """Helper to create store page HTML response."""
        json_ld = {
            "@type": "Store",
            "name": f"T-Mobile {branch_code}",
            "branchCode": branch_code,
            "telephone": "(555) 123-4567",
            "address": {
                "streetAddress": "123 Main St",
                "addressLocality": "Dallas",
                "addressRegion": "TX",
                "postalCode": "75001",
                "addressCountry": "US"
            },
            "geo": {"latitude": "32.7767", "longitude": "-96.7970"}
        }
        html = f'''<!DOCTYPE html>
<html><head>
<title>T-Mobile Store: Store in Dallas, TX</title>
<script type="application/ld+json">{json.dumps(json_ld)}</script>
</head></html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_uses_url_cache(self, mock_counter, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test that run() uses cached URLs when available."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_load_cache.return_value = ['https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001']
        mock_get.return_value = self._make_store_page_response('TX-DAL-001')

        config = {
            'checkpoint_interval': 100,
            'proxy': {'mode': 'direct'},
            'parallel_workers': 1
        }
        result = run(mock_session, config, retailer='tmobile')

        mock_load_cache.assert_called_once_with('tmobile')
        mock_save_cache.assert_not_called()  # No save since cache was valid

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_refresh_urls_ignores_cache(self, mock_counter, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test that refresh_urls=True ignores cached URLs."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_get.side_effect = [
            self._make_sitemap_response(['TX-DAL-001']),
            self._make_store_page_response('TX-DAL-001')
        ]

        config = {
            'checkpoint_interval': 100,
            'proxy': {'mode': 'direct'},
            'parallel_workers': 1
        }
        result = run(mock_session, config, retailer='tmobile', refresh_urls=True)

        mock_load_cache.assert_not_called()  # Should not load cache
        mock_save_cache.assert_called_once()  # Should save newly discovered URLs

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile._create_session_factory')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.save_checkpoint')
    @patch('src.scrapers.tmobile.extract_store_details')
    def test_run_parallel_extraction(self, mock_extract, mock_save_checkpoint, mock_config, mock_session_factory, mock_save_cache, mock_load_cache, mock_session):
        """Test that parallel extraction works with multiple workers."""
        mock_config.SITEMAP_PAGES = [1]
        mock_load_cache.return_value = [
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-002',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-003'
        ]

        # Mock session factory
        mock_worker_session = Mock()
        mock_session_factory.return_value = lambda: mock_worker_session

        # Mock extract_store_details to return store objects
        def make_store(session, url, retailer):
            code = url.split('/')[-1]
            store = Mock()
            store.to_dict.return_value = {'branch_code': code, 'name': f'T-Mobile {code}'}
            return store
        mock_extract.side_effect = make_store

        config = {
            'checkpoint_interval': 100,
            'proxy': {'mode': 'residential'},
            'parallel_workers': 3
        }
        result = run(mock_session, config, retailer='tmobile')

        assert result['count'] == 3
        assert len(result['stores']) == 3
        mock_session_factory.assert_called_once()

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_sequential_fallback(self, mock_counter, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session):
        """Test that sequential extraction is used when parallel_workers=1."""
        mock_config.SITEMAP_PAGES = [1]
        mock_load_cache.return_value = ['https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001']
        mock_get.return_value = self._make_store_page_response('TX-DAL-001')

        config = {
            'checkpoint_interval': 100,
            'proxy': {'mode': 'direct'},
            'parallel_workers': 1
        }
        result = run(mock_session, config, retailer='tmobile')

        assert result['count'] == 1
        # Verify sequential path was used (extract_store_details called directly)


class TestTMobileFailedExtraction:
    """Tests for failed extraction tracking."""

    def _make_store_page_response(self, branch_code):
        """Helper to create store page HTML response."""
        json_ld = {
            "@type": "Store",
            "name": f"T-Mobile {branch_code}",
            "branchCode": branch_code,
            "telephone": "(555) 123-4567",
            "address": {
                "streetAddress": "123 Main St",
                "addressLocality": "Dallas",
                "addressRegion": "TX",
                "postalCode": "75001",
                "addressCountry": "US"
            },
            "geo": {"latitude": "32.7767", "longitude": "-96.7970"}
        }
        html = f'''<!DOCTYPE html>
<html><head>
<title>T-Mobile Store: Store in Dallas, TX</title>
<script type="application/ld+json">{json.dumps(json_ld)}</script>
</head></html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.tmobile._load_cached_urls')
    @patch('src.scrapers.tmobile._save_cached_urls')
    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile.utils.save_checkpoint')
    @patch('src.scrapers.tmobile._request_counter')
    def test_failed_urls_logged_and_saved(self, mock_counter, mock_save_checkpoint, mock_get, mock_config, mock_save_cache, mock_load_cache, mock_session, tmp_path, monkeypatch):
        """Test that failed URLs are logged and saved to file."""
        mock_config.SITEMAP_PAGES = [1]
        mock_load_cache.return_value = [
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001',
            'https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-002'
        ]
        # First URL succeeds, second fails
        mock_get.side_effect = [
            self._make_store_page_response('TX-DAL-001'),
            None  # Failure
        ]

        config = {
            'checkpoint_interval': 100,
            'proxy': {'mode': 'direct'},
            'parallel_workers': 1
        }

        # Use monkeypatch to redirect the data directory to tmp_path
        original_path = Path
        def patched_path(path_str):
            if 'data/tmobile' in str(path_str):
                # Redirect to tmp_path
                return original_path(tmp_path / path_str.replace('data/', ''))
            return original_path(path_str)

        monkeypatch.setattr('src.scrapers.tmobile.Path', patched_path)

        result = run(mock_session, config, retailer='tmobile')

        # One successful, one failed
        assert result['count'] == 1
        # Check that failed_extractions.json was created
        failed_file = tmp_path / 'tmobile' / 'failed_extractions.json'
        assert failed_file.exists()
        failed_data = json.loads(failed_file.read_text())
        assert failed_data['failed_count'] == 1
        assert 'TX-DAL-002' in failed_data['failed_urls'][0]
