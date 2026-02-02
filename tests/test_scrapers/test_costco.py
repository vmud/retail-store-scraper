"""Unit tests for Costco warehouse scraper."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.costco import (
    CostcoWarehouse,
    _parse_address,
    _normalize_warehouse_json,
    _extract_warehouses_from_page,
    run,
)


class TestCostcoWarehouse:
    """Tests for CostcoWarehouse dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        warehouse = CostcoWarehouse(
            store_id='148',
            name='Marina Del Rey',
            store_type='warehouse',
            street_address='13463 Washington Blvd',
            city='Marina Del Rey',
            state='CA',
            zip='90292',
            country='US',
            latitude=33.9966,
            longitude=-118.4516,
            phone='(310) 754-8100',
            url='https://www.costco.com/w/-/ca/marina-del-rey/148',
            services=['gas_station', 'tire_center', 'optical'],
            hours_weekday='10:00 AM - 8:30 PM',
            hours_saturday='9:30 AM - 6:00 PM',
            hours_sunday='10:00 AM - 6:00 PM',
            scraped_at='2025-01-26T12:00:00Z'
        )
        result = warehouse.to_dict()

        assert result['store_id'] == '148'
        assert result['name'] == 'Marina Del Rey'
        assert result['store_type'] == 'warehouse'
        assert result['latitude'] == '33.9966'
        assert result['longitude'] == '-118.4516'
        assert json.loads(result['services']) == ['gas_station', 'tire_center', 'optical']

    def test_to_dict_none_coordinates(self):
        """Test dict conversion with None coordinates."""
        warehouse = CostcoWarehouse(
            store_id='148',
            name='Marina Del Rey',
            store_type='warehouse',
            street_address='13463 Washington Blvd',
            city='Marina Del Rey',
            state='CA',
            zip='90292',
            country='US',
            latitude=None,
            longitude=None,
            phone='(310) 754-8100',
            url='https://www.costco.com/w/-/ca/marina-del-rey/148',
            services=[],
            hours_weekday='',
            hours_saturday='',
            hours_sunday='',
            scraped_at='2025-01-26T12:00:00Z'
        )
        result = warehouse.to_dict()

        assert result['latitude'] == ''
        assert result['longitude'] == ''
        assert result['services'] == ''

    def test_to_dict_business_center(self):
        """Test dict conversion for business center type."""
        warehouse = CostcoWarehouse(
            store_id='999',
            name='Los Angeles Business Center',
            store_type='business_center',
            street_address='123 Business Blvd',
            city='Los Angeles',
            state='CA',
            zip='90001',
            country='US',
            latitude=34.0522,
            longitude=-118.2437,
            phone='(310) 555-1234',
            url='https://www.costco.com/w/-/ca/los-angeles/999',
            services=['food_court'],
            hours_weekday='7:00 AM - 6:00 PM',
            hours_saturday='7:00 AM - 4:00 PM',
            hours_sunday='Closed',
            scraped_at='2025-01-26T12:00:00Z'
        )
        result = warehouse.to_dict()

        assert result['store_type'] == 'business_center'


class TestParseAddress:
    """Tests for _parse_address function."""

    def test_parse_standard_address(self):
        """Test parsing standard US address format."""
        address_text = """13463 Washington Blvd
Marina Del Rey, CA 90292"""
        result = _parse_address(address_text)

        assert result['street_address'] == '13463 Washington Blvd'
        assert result['city'] == 'Marina Del Rey'
        assert result['state'] == 'CA'
        assert result['zip'] == '90292'

    def test_parse_address_with_zip_plus_four(self):
        """Test parsing address with ZIP+4 format."""
        address_text = """2201 Senter Rd
San Jose, CA 95112-2627"""
        result = _parse_address(address_text)

        assert result['street_address'] == '2201 Senter Rd'
        assert result['city'] == 'San Jose'
        assert result['state'] == 'CA'
        assert result['zip'] == '95112-2627'

    def test_parse_empty_address(self):
        """Test parsing empty address."""
        result = _parse_address('')

        assert result['street_address'] == ''
        assert result['city'] == ''
        assert result['state'] == ''
        assert result['zip'] == ''

    def test_parse_address_single_line(self):
        """Test parsing single line address."""
        address_text = "123 Main St"
        result = _parse_address(address_text)

        assert result['street_address'] == '123 Main St'
        assert result['city'] == ''


class TestNormalizeWarehouseJson:
    """Tests for _normalize_warehouse_json function."""

    def test_normalize_standard_json(self):
        """Test normalizing standard warehouse JSON."""
        data = {
            'storeNumber': '148',
            'name': 'Marina Del Rey',
            'address': '13463 Washington Blvd',
            'city': 'Marina Del Rey',
            'state': 'CA',
            'zip': '90292',
            'country': 'US',
            'latitude': 33.9966,
            'longitude': -118.4516,
            'phone': '(310) 754-8100',
            'url': 'https://www.costco.com/w/-/ca/marina-del-rey/148',
        }
        result = _normalize_warehouse_json(data)

        assert result['store_id'] == '148'
        assert result['name'] == 'Marina Del Rey'
        assert result['latitude'] == 33.9966
        assert result['longitude'] == -118.4516

    def test_normalize_alternative_field_names(self):
        """Test normalizing JSON with alternative field names."""
        data = {
            'locationId': '148',
            'displayName': 'Marina Del Rey Warehouse',
            'streetAddress': '13463 Washington Blvd',
            'city': 'Marina Del Rey',
            'stateCode': 'CA',
            'postalCode': '90292',
            'countryCode': 'US',
            'lat': 33.9966,
            'lng': -118.4516,
            'phoneNumber': '(310) 754-8100',
            'detailsUrl': '/w/-/ca/marina-del-rey/148',
        }
        result = _normalize_warehouse_json(data)

        assert result['store_id'] == '148'
        assert result['name'] == 'Marina Del Rey Warehouse'
        assert result['state'] == 'CA'
        assert result['zip'] == '90292'
        assert result['latitude'] == 33.9966
        assert result['longitude'] == -118.4516

    def test_normalize_business_center(self):
        """Test normalizing business center warehouse."""
        data = {
            'storeNumber': '999',
            'name': 'Los Angeles Business Center',
            'city': 'Los Angeles',
            'state': 'CA',
        }
        result = _normalize_warehouse_json(data)

        assert result['store_type'] == 'business_center'

    def test_normalize_missing_fields(self):
        """Test normalizing JSON with missing fields."""
        data = {
            'id': '148',
        }
        result = _normalize_warehouse_json(data)

        assert result['store_id'] == '148'
        assert result['name'] == ''
        assert result['city'] == ''


class TestExtractWarehousesFromPage:
    """Tests for _extract_warehouses_from_page function."""

    def test_extract_empty_html(self):
        """Test extraction from empty HTML."""
        result = _extract_warehouses_from_page('<html><body></body></html>')
        assert result == []

    def test_extract_minimal_warehouse_html(self):
        """Test extraction from minimal warehouse HTML."""
        html = """
        <html>
        <body>
            <div class="warehouse-item">
                <a href="/w/-/ca/marina-del-rey/148">Marina Del Rey</a>
            </div>
        </body>
        </html>
        """
        result = _extract_warehouses_from_page(html)
        # Should find something (even if incomplete)
        assert isinstance(result, list)


class TestRun:
    """Tests for main run function."""

    @patch('src.scrapers.costco.ProxyClient')
    @patch('src.scrapers.costco.ProxyConfig')
    def test_run_returns_valid_structure(self, mock_config, mock_client):
        """Test that run returns expected structure."""
        # Mock response with minimal data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body></body></html>'

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        mock_config.from_env.return_value = Mock()

        result = run(
            session=Mock(),
            retailer_config={},
            retailer='costco',
            test_mode=True
        )

        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.costco.ProxyClient')
    @patch('src.scrapers.costco.ProxyConfig')
    def test_run_with_limit(self, mock_config, mock_client):
        """Test that limit parameter is respected."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body></body></html>'

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        mock_config.from_env.return_value = Mock()

        result = run(
            session=Mock(),
            retailer_config={},
            retailer='costco',
            limit=5
        )

        # With empty HTML, should return 0 stores (but structure is valid)
        assert result['count'] <= 5

    @patch('src.scrapers.costco.ProxyClient')
    @patch('src.scrapers.costco.ProxyConfig')
    def test_run_handles_error_response(self, mock_config, mock_client):
        """Test that run handles error responses gracefully."""
        mock_response = Mock()
        mock_response.status_code = 403  # Forbidden (bot protection)
        mock_response.text = ''

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        mock_config.from_env.return_value = Mock()

        # Should not raise exception
        result = run(
            session=Mock(),
            retailer_config={},
            retailer='costco',
            test_mode=True
        )

        assert 'stores' in result
        assert result['count'] == 0  # No stores found due to error

    @patch('src.scrapers.costco.ProxyClient')
    @patch('src.scrapers.costco.ProxyConfig')
    def test_run_uses_web_scraper_api_by_default(self, mock_config, mock_client):
        """Test that Costco defaults to web_scraper_api proxy mode."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body></body></html>'

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        mock_config_instance = Mock()
        mock_config.from_env.return_value = mock_config_instance

        run(
            session=Mock(),
            retailer_config={},
            retailer='costco'
        )

        # Verify render_js was set (Web Scraper API mode)
        mock_client_instance.get.assert_called()
        call_kwargs = mock_client_instance.get.call_args[1]
        assert call_kwargs.get('render_js') is True
