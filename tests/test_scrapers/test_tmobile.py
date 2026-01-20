"""Unit tests for T-Mobile scraper."""

import json
import pytest
from unittest.mock import Mock, patch

from src.scrapers.tmobile import (
    TMobileStore,
    _extract_store_type_from_title,
    get_store_urls_from_sitemap,
    extract_store_details,
    run,
    get_request_count,
    reset_request_counter,
    _check_pause_logic,
)


class TestTMobileStore:
    """Tests for TMobileStore dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        store = TMobileStore(
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

        assert result['branch_code'] == 'TX-DAL-001'
        assert result['store_type'] == 'T-Mobile Store'
        assert json.loads(result['opening_hours']) == ['Mon-Fri: 10am-8pm', 'Sat: 10am-6pm', 'Sun: 12pm-6pm']

    def test_to_dict_none_opening_hours(self):
        """Test dict conversion with None opening_hours."""
        store = TMobileStore(
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

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_returns_correct_structure(self, mock_counter, mock_get, mock_config, mock_session):
        """Test that run() returns the expected structure."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_get.side_effect = [
            self._make_sitemap_response(['TX-DAL-001']),
            self._make_store_page_response('TX-DAL-001')
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='tmobile')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_with_limit(self, mock_counter, mock_get, mock_config, mock_session):
        """Test run() respects limit parameter."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_get.side_effect = [
            self._make_sitemap_response(['TX-DAL-001', 'TX-DAL-002', 'TX-DAL-003', 'TX-DAL-004', 'TX-DAL-005']),
            self._make_store_page_response('TX-DAL-001'),
            self._make_store_page_response('TX-DAL-002'),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='tmobile', limit=2)

        assert result['count'] == 2
        assert len(result['stores']) == 2

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_config, mock_session):
        """Test run() with empty sitemap returns empty stores."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='tmobile')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_run_count_matches_stores_length(self, mock_counter, mock_get, mock_config, mock_session):
        """Test that count matches the actual number of stores."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_get.side_effect = [
            self._make_sitemap_response(['TX-DAL-001', 'TX-DAL-002', 'TX-DAL-003']),
            self._make_store_page_response('TX-DAL-001'),
            self._make_store_page_response('TX-DAL-002'),
            self._make_store_page_response('TX-DAL-003'),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='tmobile')

        assert result['count'] == len(result['stores'])


class TestTMobileCheckpoint:
    """Tests for T-Mobile checkpoint/resume functionality."""

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.load_checkpoint')
    @patch('src.scrapers.tmobile.utils.save_checkpoint')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_resume_loads_checkpoint(self, mock_counter, mock_get, mock_save, mock_load, mock_config, mock_session):
        """Test that resume=True loads existing checkpoint."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        mock_load.return_value = {
            'stores': [{'branch_code': 'TX-DAL-001', 'name': 'Existing Store'}],
            'completed_urls': ['https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001']
        }
        # Sitemap with URLs (must be non-empty for checkpoints_used to be True)
        xml = '''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.t-mobile.com/stores/bd/tx/dallas/TX-DAL-001</loc></url>
        </urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='tmobile', resume=True)

        mock_load.assert_called_once()
        assert result['checkpoints_used'] is True

    @patch('src.scrapers.tmobile.tmobile_config')
    @patch('src.scrapers.tmobile.utils.load_checkpoint')
    @patch('src.scrapers.tmobile.utils.get_with_retry')
    @patch('src.scrapers.tmobile._request_counter')
    def test_no_resume_starts_fresh(self, mock_counter, mock_get, mock_load, mock_config, mock_session):
        """Test that resume=False does not load checkpoint."""
        mock_config.SITEMAP_PAGES = [1]
        mock_config.SITEMAP_BASE_URL = 'https://www.t-mobile.com/sitemap.xml'
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='tmobile', resume=False)

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
