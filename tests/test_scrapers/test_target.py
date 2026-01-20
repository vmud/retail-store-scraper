"""Unit tests for Target scraper."""

import gzip
import json
import pytest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.target import (
    TargetStore,
    get_all_store_ids,
    get_store_details,
    run,
    get_request_count,
    reset_request_counter,
    _check_pause_logic,
)


class TestTargetStore:
    """Tests for TargetStore dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        store = TargetStore(
            store_id='1234',
            name='Test Target',
            status='Open',
            street_address='123 Main St',
            city='Los Angeles',
            state='CA',
            postal_code='90001',
            country='USA',
            latitude=34.0522,
            longitude=-118.2437,
            phone='(555) 123-4567',
            capabilities=['Drive Up', 'Order Pickup'],
            format='SuperTarget',
            building_area=180000,
            url='https://www.target.com/sl/test-target/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == '1234'
        assert result['name'] == 'Test Target'
        assert result['latitude'] == '34.0522'
        assert result['longitude'] == '-118.2437'
        assert json.loads(result['capabilities']) == ['Drive Up', 'Order Pickup']

    def test_to_dict_none_latitude_longitude(self):
        """Test dict conversion with None coordinates."""
        store = TargetStore(
            store_id='1234',
            name='Test Target',
            status='Open',
            street_address='123 Main St',
            city='Los Angeles',
            state='CA',
            postal_code='90001',
            country='USA',
            latitude=None,
            longitude=None,
            phone='(555) 123-4567',
            capabilities=None,
            format=None,
            building_area=None,
            url='https://www.target.com/sl/test-target/1234',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['latitude'] == ''
        assert result['longitude'] == ''
        assert result['capabilities'] == ''
        assert result['building_area'] == ''


class TestGetAllStoreIds:
    """Tests for get_all_store_ids function."""

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_parse_sitemap_plain_xml(self, mock_counter, mock_get, mock_session):
        """Test parsing plain XML sitemap."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.target.com/sl/los-angeles-downtown/1234</loc>
        <lastmod>2025-01-19</lastmod>
    </url>
    <url>
        <loc>https://www.target.com/sl/san-francisco-central/5678</loc>
        <lastmod>2025-01-18</lastmod>
    </url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = xml_content.encode('utf-8')
        mock_get.return_value = mock_response

        stores = get_all_store_ids(mock_session)

        assert len(stores) == 2
        assert stores[0]['store_id'] == 1234
        assert stores[0]['slug'] == 'los-angeles-downtown'
        assert stores[1]['store_id'] == 5678
        assert stores[1]['slug'] == 'san-francisco-central'

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_parse_sitemap_gzipped(self, mock_counter, mock_get, mock_session):
        """Test parsing gzipped sitemap."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.target.com/sl/test-store/9999</loc>
    </url>
</urlset>'''
        # Compress the content
        buffer = BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='wb') as f:
            f.write(xml_content.encode('utf-8'))
        gzipped_content = buffer.getvalue()

        mock_response = Mock()
        mock_response.content = gzipped_content
        mock_get.return_value = mock_response

        stores = get_all_store_ids(mock_session)

        assert len(stores) == 1
        assert stores[0]['store_id'] == 9999

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_deduplicate_store_ids(self, mock_counter, mock_get, mock_session):
        """Test that duplicate store IDs are deduplicated."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.target.com/sl/store-a/1234</loc></url>
    <url><loc>https://www.target.com/sl/store-b/1234</loc></url>
    <url><loc>https://www.target.com/sl/store-c/5678</loc></url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = xml_content.encode('utf-8')
        mock_get.return_value = mock_response

        stores = get_all_store_ids(mock_session)

        # Should only have 2 unique store IDs
        assert len(stores) == 2
        store_ids = {s['store_id'] for s in stores}
        assert store_ids == {1234, 5678}

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_failed_fetch_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that failed fetch returns empty list."""
        mock_get.return_value = None

        stores = get_all_store_ids(mock_session)

        assert stores == []


class TestGetStoreDetails:
    """Tests for get_store_details function."""

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_parse_api_response(self, mock_counter, mock_get, mock_session):
        """Test parsing API response."""
        api_response = {
            "data": {
                "store": {
                    "store_id": 1234,
                    "location_name": "Los Angeles Downtown",
                    "status": "Open",
                    "mailing_address": {
                        "address_line1": "123 Main St",
                        "city": "Los Angeles",
                        "region": "CA",
                        "postal_code": "90001",
                        "country": "United States of America"
                    },
                    "geographic_specifications": {
                        "latitude": 34.0522,
                        "longitude": -118.2437
                    },
                    "physical_specifications": {
                        "format": "SuperTarget"
                    },
                    "main_voice_phone_number": "(555) 123-4567",
                    "capabilities": [
                        {"capability_name": "Drive Up"},
                        {"capability_name": "Order Pickup"}
                    ]
                }
            }
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response
        mock_get.return_value = mock_response

        store = get_store_details(mock_session, 1234)

        assert store is not None
        assert store.store_id == '1234'
        assert store.name == 'Los Angeles Downtown'
        assert store.city == 'Los Angeles'
        assert store.state == 'CA'
        assert store.latitude == 34.0522
        assert store.longitude == -118.2437
        assert store.capabilities == ['Drive Up', 'Order Pickup']

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_missing_store_data_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that missing store data returns None."""
        api_response = {"data": {"store": None}}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response
        mock_get.return_value = mock_response

        store = get_store_details(mock_session, 1234)

        assert store is None

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_failed_request_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that failed request returns None."""
        mock_get.return_value = None

        store = get_store_details(mock_session, 1234)

        assert store is None

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_handles_missing_optional_fields(self, mock_counter, mock_get, mock_session):
        """Test handling of missing optional fields."""
        api_response = {
            "data": {
                "store": {
                    "store_id": 1234,
                    "location_name": "Minimal Store",
                    "status": "Open",
                    "mailing_address": {
                        "address_line1": "123 Test St",
                        "city": "Test City",
                        "region": "TX",
                        "postal_code": "75001"
                    },
                    "geographic_specifications": {},
                    "physical_specifications": {},
                    "capabilities": []
                }
            }
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = api_response
        mock_get.return_value = mock_response

        store = get_store_details(mock_session, 1234)

        assert store is not None
        assert store.latitude is None
        assert store.longitude is None
        assert store.capabilities is None
        assert store.format is None


class TestTargetRun:
    """Tests for Target run() method."""

    def _make_sitemap_response(self, store_ids):
        """Helper to create sitemap response with given store IDs."""
        urls = '\n'.join(
            f'<url><loc>https://www.target.com/sl/store-{sid}/{sid}</loc></url>'
            for sid in store_ids
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_api_response(self, store_id):
        """Helper to create API response for a store."""
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": {
                "store": {
                    "store_id": store_id,
                    "location_name": f"Store {store_id}",
                    "status": "Open",
                    "mailing_address": {
                        "address_line1": f"{store_id} Main St",
                        "city": "Test City",
                        "region": "CA",
                        "postal_code": "90001",
                        "country": "USA"
                    },
                    "geographic_specifications": {"latitude": 34.0, "longitude": -118.0},
                    "physical_specifications": {},
                    "main_voice_phone_number": "(555) 123-4567",
                    "capabilities": []
                }
            }
        }
        return response

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_run_returns_correct_structure(self, mock_counter, mock_get, mock_session):
        """Test that run() returns the expected structure."""
        mock_get.side_effect = [
            self._make_sitemap_response([1001]),
            self._make_api_response(1001)
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_run_with_limit(self, mock_counter, mock_get, mock_session):
        """Test run() respects limit parameter."""
        mock_get.side_effect = [
            self._make_sitemap_response([1001, 1002, 1003, 1004, 1005]),
            self._make_api_response(1001),
            self._make_api_response(1002),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target', limit=2)

        assert result['count'] == 2
        assert len(result['stores']) == 2

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_session):
        """Test run() with empty sitemap returns empty stores."""
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_run_count_matches_stores_length(self, mock_counter, mock_get, mock_session):
        """Test that count matches the actual number of stores."""
        mock_get.side_effect = [
            self._make_sitemap_response([1001, 1002, 1003]),
            self._make_api_response(1001),
            self._make_api_response(1002),
            self._make_api_response(1003),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target')

        assert result['count'] == len(result['stores'])


class TestTargetCheckpoint:
    """Tests for Target checkpoint/resume functionality."""

    @patch('src.scrapers.target.utils.load_checkpoint')
    @patch('src.scrapers.target.utils.save_checkpoint')
    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_resume_loads_checkpoint(self, mock_counter, mock_get, mock_save, mock_load, mock_session):
        """Test that resume=True loads existing checkpoint."""
        mock_load.return_value = {
            'stores': [{'store_id': '1001', 'name': 'Existing Store'}],
            'completed_ids': [1001]
        }
        # Sitemap with URLs (must be non-empty for checkpoints_used to be True)
        xml = '''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.target.com/sl/store/1001</loc></url>
        </urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target', resume=True)

        mock_load.assert_called_once()
        assert result['checkpoints_used'] is True

    @patch('src.scrapers.target.utils.load_checkpoint')
    @patch('src.scrapers.target.utils.save_checkpoint')
    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_resume_skips_completed_stores(self, mock_counter, mock_get, mock_save, mock_load, mock_session):
        """Test that resumed run skips already completed stores."""
        mock_load.return_value = {
            'stores': [{'store_id': '1001', 'name': 'Store 1'}],
            'completed_ids': [1001]
        }

        # Sitemap has stores 1001 (completed) and 1002 (new)
        urls = '''<url><loc>https://www.target.com/sl/store/1001</loc></url>
                  <url><loc>https://www.target.com/sl/store/1002</loc></url>'''
        xml = f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
        sitemap_response = Mock()
        sitemap_response.content = xml.encode('utf-8')

        api_response = Mock()
        api_response.status_code = 200
        api_response.json.return_value = {
            "data": {"store": {"store_id": 1002, "location_name": "Store 2", "status": "Open",
                               "mailing_address": {"address_line1": "2 Main", "city": "City", "region": "CA", "postal_code": "90001"},
                               "geographic_specifications": {}, "physical_specifications": {},
                               "main_voice_phone_number": "", "capabilities": []}}
        }
        mock_get.side_effect = [sitemap_response, api_response]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target', resume=True)

        # Should have 2 stores total (1 from checkpoint + 1 new)
        assert result['count'] == 2

    @patch('src.scrapers.target.utils.load_checkpoint')
    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_no_resume_starts_fresh(self, mock_counter, mock_get, mock_load, mock_session):
        """Test that resume=False does not load checkpoint."""
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target', resume=False)

        mock_load.assert_not_called()
        assert result['checkpoints_used'] is False


class TestTargetRateLimiting:
    """Tests for Target rate limiting and pause logic."""

    def test_request_counter_reset(self):
        """Test that request counter resets properly."""
        reset_request_counter()
        assert get_request_count() == 0

    @patch('src.scrapers.target.time.sleep')
    @patch('src.scrapers.target.random.uniform')
    def test_pause_at_50_requests(self, mock_uniform, mock_sleep):
        """Test that pause triggers at 50 request threshold."""
        mock_uniform.return_value = 1.5
        reset_request_counter()

        # Simulate 50 requests
        from src.scrapers.target import _request_counter
        _request_counter._count = 50

        _check_pause_logic()

        mock_sleep.assert_called_once()
        mock_uniform.assert_called()

    @patch('src.scrapers.target.time.sleep')
    @patch('src.scrapers.target.random.uniform')
    def test_pause_at_200_requests(self, mock_uniform, mock_sleep):
        """Test that longer pause triggers at 200 request threshold."""
        mock_uniform.return_value = 150
        reset_request_counter()

        from src.scrapers.target import _request_counter
        _request_counter._count = 200

        _check_pause_logic()

        mock_sleep.assert_called_once()
        # 200 request pause should use longer delay range
        call_args = mock_uniform.call_args[0]
        assert call_args[0] >= 100  # Min should be at least 100s

    @patch('src.scrapers.target.time.sleep')
    def test_no_pause_between_thresholds(self, mock_sleep):
        """Test that no pause occurs between thresholds."""
        reset_request_counter()

        from src.scrapers.target import _request_counter
        _request_counter._count = 25  # Between 0 and 50

        _check_pause_logic()

        mock_sleep.assert_not_called()


class TestTargetErrorHandling:
    """Tests for Target error handling."""

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_sitemap_fetch_failure_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that sitemap fetch failure returns empty list."""
        mock_get.return_value = None

        stores = get_all_store_ids(mock_session)

        assert stores == []

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_api_error_skips_store(self, mock_counter, mock_get, mock_session):
        """Test that API error for one store doesn't fail entire run."""
        xml = '''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.target.com/sl/store/1001</loc></url>
            <url><loc>https://www.target.com/sl/store/1002</loc></url>
        </urlset>'''
        sitemap_response = Mock()
        sitemap_response.content = xml.encode('utf-8')

        # First store fails, second succeeds
        api_success = Mock()
        api_success.status_code = 200
        api_success.json.return_value = {
            "data": {"store": {"store_id": 1002, "location_name": "Store 2", "status": "Open",
                               "mailing_address": {"address_line1": "2 Main", "city": "City", "region": "CA", "postal_code": "90001"},
                               "geographic_specifications": {}, "physical_specifications": {},
                               "main_voice_phone_number": "", "capabilities": []}}
        }
        mock_get.side_effect = [sitemap_response, None, api_success]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='target')

        # Should have 1 store (second one that succeeded)
        assert result['count'] == 1

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_malformed_xml_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that malformed XML returns empty list."""
        response = Mock()
        response.content = b'<not valid xml'
        mock_get.return_value = response

        stores = get_all_store_ids(mock_session)

        assert stores == []

    @patch('src.scrapers.target.utils.get_with_retry')
    @patch('src.scrapers.target._request_counter')
    def test_json_decode_error_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that JSON decode error returns None for store."""
        response = Mock()
        response.status_code = 200
        response.json.side_effect = json.JSONDecodeError("test", "doc", 0)
        mock_get.return_value = response

        store = get_store_details(mock_session, 1234)

        assert store is None
