"""Unit tests for Target scraper."""

import gzip
import json
import pytest
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.target import (
    TargetStore,
    get_all_store_ids,
    get_store_details,
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
