"""Tests for Sam's Club scraper."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.scrapers.samsclub import (
    run,
    _parse_services,
    _format_hours,
    _extract_club_data_from_page,
    get_club_urls_from_sitemap,
    SamsClubStore
)


class TestSamsClubParser:
    """Test Sam's Club data parsing functions."""

    def test_parse_services_all_present(self):
        """Test service parsing with all services present (uppercase format)."""
        # New format: services are objects with 'name' field or uppercase strings
        services = [
            {'name': 'PHARMACY'}, {'name': 'VISION_CENTER'}, {'name': 'HEARING_AID_CENTER'},
            {'name': 'WIRELESS_MOBILE'}, {'name': 'CAFE'}, {'name': 'BAKERY'},
            {'name': 'GAS_SAMS'}, {'name': 'LIQUOR'}, {'name': 'TIRE_AND_LUBE'}
        ]
        names, flags = _parse_services(services)

        assert 'PHARMACY' in names
        assert flags['has_pharmacy'] is True
        assert flags['has_optical'] is True
        assert flags['has_hearing_aid'] is True
        assert flags['has_wireless'] is True
        assert flags['has_cafe'] is True
        assert flags['has_bakery'] is True
        assert flags['has_gas'] is True
        assert flags['has_liquor'] is True
        assert flags['has_tires_batteries'] is True

    def test_parse_services_partial(self):
        """Test service parsing with partial services."""
        services = [{'name': 'PHARMACY'}, {'name': 'CAFE'}]
        names, flags = _parse_services(services)

        assert flags['has_pharmacy'] is True
        assert flags['has_cafe'] is True
        assert flags['has_optical'] is False
        assert flags['has_gas'] is False

    def test_parse_services_empty(self):
        """Test service parsing with empty list."""
        names, flags = _parse_services([])
        assert names == []
        assert all(v is False for v in flags.values())

    def test_parse_services_none(self):
        """Test service parsing with None."""
        names, flags = _parse_services(None)
        assert names == []
        assert all(v is False for v in flags.values())

    def test_format_hours_valid(self):
        """Test hours formatting with valid data."""
        hours = {
            'monToFriHrs': {'startHrs': '09:00', 'endHrs': '20:00'},
            'saturdayHrs': {'startHrs': '09:00', 'endHrs': '18:00'},
        }
        assert _format_hours(hours, 'monToFriHrs') == '09:00-20:00'
        assert _format_hours(hours, 'saturdayHrs') == '09:00-18:00'

    def test_format_hours_missing_key(self):
        """Test hours formatting with missing key."""
        hours = {'monToFriHrs': {'startHrs': '09:00', 'endHrs': '20:00'}}
        assert _format_hours(hours, 'sundayHrs') == ''

    def test_format_hours_empty(self):
        """Test hours formatting with empty data."""
        assert _format_hours({}, 'monToFriHrs') == ''
        assert _format_hours(None, 'monToFriHrs') == ''


class TestSamsClubPageExtraction:
    """Test page data extraction."""

    def test_extract_club_data_from_page_no_next_data(self):
        """Test extraction when __NEXT_DATA__ is missing."""
        html = '<html><body>No data here</body></html>'
        result = _extract_club_data_from_page(html, 'https://www.samsclub.com/club/1234-test', 'samsclub')
        assert result is None

    def test_extract_club_data_from_page_invalid_json(self):
        """Test extraction with invalid JSON in __NEXT_DATA__."""
        html = '<html><script id="__NEXT_DATA__" type="application/json">not valid json</script></html>'
        result = _extract_club_data_from_page(html, 'https://www.samsclub.com/club/1234-test', 'samsclub')
        assert result is None


class TestSamsClubSitemap:
    """Test sitemap parsing."""

    def test_get_club_urls_from_sitemap_success(self):
        """Test successful sitemap parsing."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.samsclub.com/club/1234-test-city</loc></url>
            <url><loc>https://www.samsclub.com/club/5678-other-city</loc></url>
            <url><loc>https://www.samsclub.com/other/page</loc></url>
        </urlset>'''
        mock_session.get.return_value = mock_response

        urls = get_club_urls_from_sitemap(mock_session, 'samsclub')

        assert len(urls) == 2
        assert 'https://www.samsclub.com/club/1234-test-city' in urls
        assert 'https://www.samsclub.com/club/5678-other-city' in urls
        assert 'https://www.samsclub.com/other/page' not in urls

    def test_get_club_urls_from_sitemap_failure(self):
        """Test sitemap parsing on HTTP error."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        urls = get_club_urls_from_sitemap(mock_session, 'samsclub')

        assert urls == []


class TestSamsClubStore:
    """Test SamsClubStore dataclass."""

    def test_to_dict_converts_coordinates(self):
        """Test that to_dict converts coordinates to strings."""
        store = SamsClubStore(
            store_id='1234',
            name='Test Club',
            street_address='123 Main St',
            city='Test City',
            state='TX',
            zip='75001',
            county='Test County',
            country='US',
            latitude=32.123,
            longitude=-96.456,
            phone='555-1234',
            url='https://www.samsclub.com/club/1234',
            time_zone='CST',
            services=['pharmacy', 'cafe'],
            scraped_at='2024-01-01T00:00:00'
        )

        result = store.to_dict()

        assert result['latitude'] == '32.123'
        assert result['longitude'] == '-96.456'
        assert result['services'] == 'pharmacy,cafe'

    def test_to_dict_handles_none_coordinates(self):
        """Test that to_dict handles None coordinates."""
        store = SamsClubStore(
            store_id='1234',
            name='Test Club',
            street_address='123 Main St',
            city='Test City',
            state='TX',
            zip='75001',
            county='',
            country='US',
            latitude=None,
            longitude=None,
            phone='555-1234',
            url='',
            time_zone='',
            scraped_at=''
        )

        result = store.to_dict()

        assert result['latitude'] == ''
        assert result['longitude'] == ''


class TestSamsClubRun:
    """Test the main run function."""

    @patch('src.scrapers.samsclub.get_club_urls_from_sitemap')
    @patch('src.scrapers.samsclub.ProxyClient')
    @patch('src.scrapers.samsclub.ProxyConfig')
    @patch('src.scrapers.samsclub.URLCache')
    def test_run_with_limit(self, mock_cache_class, mock_config, mock_client_class, mock_sitemap):
        """Test run function respects limit parameter."""
        # Setup mocks
        mock_sitemap.return_value = [
            'https://www.samsclub.com/club/1-city1',
            'https://www.samsclub.com/club/2-city2',
            'https://www.samsclub.com/club/3-city3',
        ]

        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>No __NEXT_DATA__</body></html>'
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        mock_proxy_config = Mock()
        mock_config.from_env.return_value = mock_proxy_config

        yaml_config = {'checkpoint_interval': 100}
        session = Mock()

        result = run(session, yaml_config, retailer='samsclub', limit=2)

        # Should have processed at most 2 URLs (limit)
        assert mock_client.get.call_count <= 2

    @patch('src.scrapers.samsclub.get_club_urls_from_sitemap')
    @patch('src.scrapers.samsclub.ProxyClient')
    @patch('src.scrapers.samsclub.ProxyConfig')
    @patch('src.scrapers.samsclub.URLCache')
    def test_run_uses_cached_urls(self, mock_cache_class, mock_config, mock_client_class, mock_sitemap):
        """Test that cached URLs are used when available."""
        cached_urls = ['https://www.samsclub.com/club/cached-1']

        mock_cache = Mock()
        mock_cache.get.return_value = cached_urls
        mock_cache_class.return_value = mock_cache

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html></html>'
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        mock_proxy_config = Mock()
        mock_config.from_env.return_value = mock_proxy_config

        yaml_config = {'checkpoint_interval': 100}
        session = Mock()

        run(session, yaml_config, retailer='samsclub', limit=1)

        # Sitemap should not be called when cache is available
        mock_sitemap.assert_not_called()
