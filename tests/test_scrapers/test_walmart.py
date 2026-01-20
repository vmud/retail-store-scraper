"""Unit tests for Walmart scraper."""

import gzip
import json
import pytest
from io import BytesIO
from unittest.mock import Mock, patch

from src.scrapers.walmart import (
    WalmartStore,
    get_store_urls_from_sitemap,
    extract_store_details,
    run,
    get_request_count,
    reset_request_counter,
    _check_pause_logic,
)


class TestWalmartStore:
    """Tests for WalmartStore dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        store = WalmartStore(
            store_id='1234',
            store_type='Supercenter',
            name='Walmart Supercenter',
            phone_number='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            latitude=32.7767,
            longitude=-96.7970,
            capabilities=['Pharmacy', 'Garden Center', 'Auto Care'],
            is_glass_eligible=True,
            url='https://www.walmart.com/store/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == '1234'
        assert result['store_type'] == 'Supercenter'
        assert result['latitude'] == '32.7767'
        # Float to string conversion may drop trailing zeros
        assert result['longitude'] == '-96.797'
        assert json.loads(result['capabilities']) == ['Pharmacy', 'Garden Center', 'Auto Care']
        assert result['is_glass_eligible'] == 'True'

    def test_to_dict_none_coordinates(self):
        """Test dict conversion with None coordinates."""
        store = WalmartStore(
            store_id='1234',
            store_type='Supercenter',
            name='Walmart Supercenter',
            phone_number='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            latitude=None,
            longitude=None,
            capabilities=None,
            is_glass_eligible=False,
            url='https://www.walmart.com/store/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['latitude'] == ''
        assert result['longitude'] == ''
        assert result['capabilities'] == ''
        assert result['is_glass_eligible'] == 'False'

    def test_to_dict_empty_capabilities(self):
        """Test dict conversion with empty capabilities list."""
        store = WalmartStore(
            store_id='1234',
            store_type='Neighborhood Market',
            name='Walmart Neighborhood Market',
            phone_number='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            latitude=32.7767,
            longitude=-96.7970,
            capabilities=[],
            is_glass_eligible=False,
            url='https://www.walmart.com/store/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        # Empty list is kept as-is (falsy), not JSON encoded
        # This matches the `if result.get('capabilities'):` check
        assert result['capabilities'] == []

    def test_to_dict_single_capability(self):
        """Test dict conversion with single capability."""
        store = WalmartStore(
            store_id='5678',
            store_type='Supercenter',
            name='Walmart Supercenter',
            phone_number='(555) 987-6543',
            street_address='456 Oak Ave',
            city='Houston',
            state='TX',
            postal_code='77001',
            country='US',
            latitude=29.7604,
            longitude=-95.3698,
            capabilities=['Pharmacy'],
            is_glass_eligible=True,
            url='https://www.walmart.com/store/5678',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert json.loads(result['capabilities']) == ['Pharmacy']


class TestWalmartStoreTypes:
    """Tests for Walmart store type handling."""

    def test_supercenter_type(self):
        """Test Supercenter store type."""
        store = WalmartStore(
            store_id='1', store_type='Supercenter', name='Test',
            phone_number='', street_address='', city='', state='',
            postal_code='', country='', latitude=None, longitude=None,
            capabilities=None, is_glass_eligible=False, url='', scraped_at=''
        )
        assert store.store_type == 'Supercenter'

    def test_neighborhood_market_type(self):
        """Test Neighborhood Market store type."""
        store = WalmartStore(
            store_id='2', store_type='Neighborhood Market', name='Test',
            phone_number='', street_address='', city='', state='',
            postal_code='', country='', latitude=None, longitude=None,
            capabilities=None, is_glass_eligible=False, url='', scraped_at=''
        )
        assert store.store_type == 'Neighborhood Market'

    def test_sams_club_type(self):
        """Test Sam's Club store type."""
        store = WalmartStore(
            store_id='3', store_type="Sam's Club", name='Test',
            phone_number='', street_address='', city='', state='',
            postal_code='', country='', latitude=None, longitude=None,
            capabilities=None, is_glass_eligible=False, url='', scraped_at=''
        )
        assert store.store_type == "Sam's Club"


class TestGetStoreUrlsFromSitemap:
    """Tests for get_store_urls_from_sitemap function."""

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_parse_plain_xml_sitemap(self, mock_counter, mock_get, mock_config, mock_session):
        """Test parsing plain (non-gzipped) sitemap XML."""
        mock_config.SITEMAP_URLS = ['https://www.walmart.com/sitemap_store.xml']
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.walmart.com/store/1234-dallas-tx</loc></url>
    <url><loc>https://www.walmart.com/store/5678-houston-tx</loc></url>
</urlset>'''
        response = Mock()
        response.content = xml_content.encode('utf-8')
        mock_get.return_value = response

        urls = get_store_urls_from_sitemap(mock_session)

        assert len(urls) == 2
        assert 'https://www.walmart.com/store/1234-dallas-tx' in urls

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_parse_gzipped_sitemap(self, mock_counter, mock_get, mock_config, mock_session):
        """Test parsing gzipped sitemap."""
        mock_config.SITEMAP_URLS = ['https://www.walmart.com/sitemap_store.xml.gz']
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.walmart.com/store/9999-test-ca</loc></url>
</urlset>'''
        buffer = BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb') as f:
            f.write(xml_content.encode('utf-8'))
        gzipped_content = buffer.getvalue()

        response = Mock()
        response.content = gzipped_content
        mock_get.return_value = response

        urls = get_store_urls_from_sitemap(mock_session)

        assert len(urls) == 1
        assert urls[0] == 'https://www.walmart.com/store/9999-test-ca'

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_failed_fetch_continues(self, mock_counter, mock_get, mock_config, mock_session):
        """Test that failed fetch for one sitemap continues to next."""
        mock_config.SITEMAP_URLS = ['https://fail.com/sitemap.xml', 'https://success.com/sitemap.xml']
        xml_content = '''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.walmart.com/store/1234-test-tx</loc></url>
</urlset>'''
        response = Mock()
        response.content = xml_content.encode('utf-8')
        mock_get.side_effect = [None, response]

        urls = get_store_urls_from_sitemap(mock_session)

        assert len(urls) == 1


class TestWalmartRun:
    """Tests for Walmart run() method."""

    def _make_sitemap_response(self, store_ids):
        """Helper to create sitemap response with given store IDs."""
        urls = '\n'.join(
            f'<url><loc>https://www.walmart.com/store/{sid}-test-tx</loc></url>'
            for sid in store_ids
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_page_response(self, store_id):
        """Helper to create store page with __NEXT_DATA__."""
        next_data = {
            "props": {
                "pageProps": {
                    "store": {
                        "id": str(store_id),
                        "name": "Walmart Supercenter",
                        "displayName": f"Walmart Store {store_id}",
                        "phoneNumber": "(555) 123-4567",
                        "address": {
                            "addressLineOne": f"{store_id} Main St",
                            "city": "Test City",
                            "state": "TX",
                            "postalCode": "75001",
                            "country": "US"
                        },
                        "geoPoint": {
                            "latitude": 32.7767,
                            "longitude": -96.7970
                        },
                        "capabilities": ["Pharmacy", "Garden Center"],
                        "isGlassEligible": True
                    }
                }
            }
        }
        html = f'''<html><head>
<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
</head></html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_run_returns_correct_structure(self, mock_counter, mock_get, mock_config, mock_session):
        """Test that run() returns the expected structure."""
        mock_config.SITEMAP_URLS = ['https://test.com/sitemap.xml']
        mock_get.side_effect = [
            self._make_sitemap_response([1234]),
            self._make_store_page_response(1234)
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='walmart')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_run_with_limit(self, mock_counter, mock_get, mock_config, mock_session):
        """Test run() respects limit parameter."""
        mock_config.SITEMAP_URLS = ['https://test.com/sitemap.xml']
        mock_get.side_effect = [
            self._make_sitemap_response([1234, 1235, 1236, 1237, 1238]),
            self._make_store_page_response(1234),
            self._make_store_page_response(1235),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='walmart', limit=2)

        assert result['count'] == 2
        assert len(result['stores']) == 2

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_config, mock_session):
        """Test run() with empty sitemap returns empty stores."""
        mock_config.SITEMAP_URLS = ['https://test.com/sitemap.xml']
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='walmart')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_run_count_matches_stores_length(self, mock_counter, mock_get, mock_config, mock_session):
        """Test that count matches the actual number of stores."""
        mock_config.SITEMAP_URLS = ['https://test.com/sitemap.xml']
        mock_get.side_effect = [
            self._make_sitemap_response([1234, 1235, 1236]),
            self._make_store_page_response(1234),
            self._make_store_page_response(1235),
            self._make_store_page_response(1236),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='walmart')

        assert result['count'] == len(result['stores'])


class TestWalmartCheckpoint:
    """Tests for Walmart checkpoint/resume functionality."""

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.load_checkpoint')
    @patch('src.scrapers.walmart.utils.save_checkpoint')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_resume_loads_checkpoint(self, mock_counter, mock_get, mock_save, mock_load, mock_config, mock_session):
        """Test that resume=True loads existing checkpoint."""
        mock_config.SITEMAP_URLS = ['https://test.com/sitemap.xml']
        mock_load.return_value = {
            'stores': [{'store_id': '1234', 'name': 'Existing Store'}],
            'completed_urls': ['https://www.walmart.com/store/1234-test-tx']
        }
        # Sitemap with URLs (must be non-empty for checkpoints_used to be True)
        xml = '''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.walmart.com/store/1234-test-tx</loc></url>
        </urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='walmart', resume=True)

        mock_load.assert_called_once()
        assert result['checkpoints_used'] is True

    @patch('src.scrapers.walmart.walmart_config')
    @patch('src.scrapers.walmart.utils.load_checkpoint')
    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_no_resume_starts_fresh(self, mock_counter, mock_get, mock_load, mock_config, mock_session):
        """Test that resume=False does not load checkpoint."""
        mock_config.SITEMAP_URLS = ['https://test.com/sitemap.xml']
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='walmart', resume=False)

        mock_load.assert_not_called()
        assert result['checkpoints_used'] is False


class TestWalmartRateLimiting:
    """Tests for Walmart rate limiting and pause logic."""

    def test_request_counter_reset(self):
        """Test that request counter resets properly."""
        reset_request_counter()
        assert get_request_count() == 0

    @patch('src.scrapers.walmart.time.sleep')
    @patch('src.scrapers.walmart.random.uniform')
    def test_pause_at_50_requests(self, mock_uniform, mock_sleep):
        """Test that pause triggers at 50 request threshold."""
        mock_uniform.return_value = 15
        reset_request_counter()

        from src.scrapers.walmart import _request_counter
        _request_counter._count = 50

        _check_pause_logic()

        mock_sleep.assert_called_once()
        mock_uniform.assert_called()

    @patch('src.scrapers.walmart.time.sleep')
    @patch('src.scrapers.walmart.random.uniform')
    def test_pause_at_200_requests(self, mock_uniform, mock_sleep):
        """Test that longer pause triggers at 200 request threshold."""
        mock_uniform.return_value = 180
        reset_request_counter()

        from src.scrapers.walmart import _request_counter
        _request_counter._count = 200

        _check_pause_logic()

        mock_sleep.assert_called_once()

    @patch('src.scrapers.walmart.time.sleep')
    def test_no_pause_between_thresholds(self, mock_sleep):
        """Test that no pause occurs between thresholds."""
        reset_request_counter()

        from src.scrapers.walmart import _request_counter
        _request_counter._count = 25

        _check_pause_logic()

        mock_sleep.assert_not_called()


class TestWalmartErrorHandling:
    """Tests for Walmart error handling."""

    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_store_fetch_failure_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that store page fetch failure returns None."""
        mock_get.return_value = None

        store = extract_store_details(mock_session, 'https://www.walmart.com/store/1234-test-tx')

        assert store is None

    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_missing_next_data_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that missing __NEXT_DATA__ returns None."""
        html = '<html><body>No NEXT_DATA here</body></html>'
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.walmart.com/store/1234-test-tx')

        assert store is None

    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_missing_store_in_props_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that missing store in props returns None."""
        next_data = {"props": {"pageProps": {}}}
        html = f'''<html><head>
<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.walmart.com/store/1234-test-tx')

        assert store is None

    @patch('src.scrapers.walmart.utils.get_with_retry')
    @patch('src.scrapers.walmart._request_counter')
    def test_invalid_json_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that invalid JSON in __NEXT_DATA__ returns None."""
        html = '''<html><head>
<script id="__NEXT_DATA__" type="application/json">{invalid json}</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.walmart.com/store/1234-test-tx')

        assert store is None
