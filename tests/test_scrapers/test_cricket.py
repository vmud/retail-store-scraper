"""Unit tests for Cricket Wireless scraper."""
# pylint: disable=no-member  # Mock objects have dynamic attributes

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.cricket import (
    CricketStore,
    _generate_us_grid,
    _format_hours,
    _categorize_store,
    _parse_store,
    _fetch_stores_at_point,
    run,
)
from config import cricket_config as config


class TestCricketStore:
    """Tests for CricketStore dataclass."""

    def test_to_dict_full_data(self):
        """Test dict conversion with all fields populated."""
        store = CricketStore(
            store_id='12345',
            name='Cricket Wireless',
            store_type='authorized_retailer',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude=32.7767,
            longitude=-96.7970,
            phone='(555) 123-4567',
            url='https://www.cricketwireless.com/stores/12345',
            hours_monday='10:00-19:00',
            hours_tuesday='10:00-19:00',
            hours_wednesday='10:00-19:00',
            hours_thursday='10:00-19:00',
            hours_friday='10:00-19:00',
            hours_saturday='10:00-18:00',
            hours_sunday='12:00-17:00',
            closed=False,
            scraped_at='2025-01-26T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == '12345'
        assert result['store_type'] == 'authorized_retailer'
        assert result['latitude'] == '32.7767'
        assert result['longitude'] == '-96.797'
        assert result['closed'] is False

    def test_to_dict_missing_coordinates(self):
        """Test dict conversion with missing coordinates."""
        store = CricketStore(
            store_id='12345',
            name='Cricket Wireless',
            store_type='unknown',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            zip='75001',
            country='US',
            latitude=None,
            longitude=None,
            phone='',
            url=None,
            hours_monday='',
            hours_tuesday='',
            hours_wednesday='',
            hours_thursday='',
            hours_friday='',
            hours_saturday='',
            hours_sunday='',
            closed=False,
            scraped_at='2025-01-26T12:00:00'
        )
        result = store.to_dict()

        assert result['latitude'] == ''
        assert result['longitude'] == ''


class TestGenerateGrid:
    """Tests for _generate_us_grid function."""

    def test_generates_points_within_bounds(self):
        """Test that all generated points are within US bounds."""
        points = _generate_us_grid(spacing_miles=100)

        for lat, lng in points:
            assert config.US_BOUNDS['lat_min'] <= lat <= config.US_BOUNDS['lat_max']
            assert config.US_BOUNDS['lng_min'] <= lng <= config.US_BOUNDS['lng_max']

    def test_grid_count_varies_with_spacing(self):
        """Test that smaller spacing produces more points."""
        points_large = _generate_us_grid(spacing_miles=200)
        points_small = _generate_us_grid(spacing_miles=100)

        # Smaller spacing should produce more points
        assert len(points_small) > len(points_large)

    def test_default_spacing_produces_expected_count(self):
        """Test that 50-mile spacing produces reasonable point count."""
        points = _generate_us_grid(spacing_miles=50)

        # Should be roughly 2,000-3,000 points for continental US
        # (US is ~2,800 miles wide, ~1,600 miles tall)
        assert 1500 <= len(points) <= 3500

    def test_grid_points_are_tuples(self):
        """Test that grid points are (lat, lng) tuples."""
        points = _generate_us_grid(spacing_miles=200)

        for point in points:
            assert isinstance(point, tuple)
            assert len(point) == 2
            lat, lng = point
            assert isinstance(lat, float)
            assert isinstance(lng, float)


class TestFormatHours:
    """Tests for _format_hours function."""

    def test_format_valid_hours(self):
        """Test formatting valid hours data."""
        hours_data = {
            'monday': {
                'openIntervals': [{'start': '10:00', 'end': '19:00'}]
            }
        }
        result = _format_hours(hours_data, 'monday')
        assert result == '10:00-19:00'

    def test_format_empty_hours(self):
        """Test formatting when hours data is empty."""
        assert _format_hours({}, 'monday') == ''
        assert _format_hours(None, 'monday') == ''

    def test_format_missing_day(self):
        """Test formatting when day is not in hours data."""
        hours_data = {
            'monday': {'openIntervals': [{'start': '10:00', 'end': '19:00'}]}
        }
        assert _format_hours(hours_data, 'tuesday') == ''

    def test_format_no_intervals(self):
        """Test formatting when no open intervals exist."""
        hours_data = {
            'monday': {'openIntervals': []}
        }
        assert _format_hours(hours_data, 'monday') == ''


class TestCategorizeStore:
    """Tests for _categorize_store function."""

    def test_categorize_authorized_retailer(self):
        """Test categorization of Cricket authorized retailer."""
        filters = ['Cricket Wireless Authorized Retailer']
        result = _categorize_store(filters)
        assert result == 'authorized_retailer'

    def test_categorize_walmart(self):
        """Test categorization of Walmart location."""
        filters = ['Walmart']
        result = _categorize_store(filters)
        assert result == 'walmart'

    def test_categorize_bestbuy(self):
        """Test categorization of Best Buy location."""
        filters = ['Best Buy']
        result = _categorize_store(filters)
        assert result == 'bestbuy'

    def test_categorize_unknown(self):
        """Test categorization of unknown filter."""
        filters = ['Some Unknown Store Type']
        result = _categorize_store(filters)
        assert result == 'some_unknown_store_type'

    def test_categorize_empty(self):
        """Test categorization with empty filters."""
        assert _categorize_store([]) == 'unknown'
        assert _categorize_store(None) == 'unknown'


class TestParseStore:
    """Tests for _parse_store function."""

    def test_parse_full_store_data(self):
        """Test parsing complete store data."""
        raw_store = {
            'data': {
                'id': '12345',
                'name': 'Cricket Wireless',
                'address': {
                    'line1': '123 Main St',
                    'city': 'Dallas',
                    'region': 'TX',
                    'postalCode': '75001',
                    'countryCode': 'US',
                    'coordinate': {
                        'latitude': 32.7767,
                        'longitude': -96.7970
                    }
                },
                'mainPhone': '(555) 123-4567',
                'c_locatorFilters': ['Cricket Wireless Authorized Retailer'],
                'hours': {
                    'monday': {'openIntervals': [{'start': '10:00', 'end': '19:00'}]}
                },
                'closed': False
            }
        }

        store = _parse_store(raw_store)

        assert store is not None
        assert store.store_id == '12345'
        assert store.name == 'Cricket Wireless'
        assert store.store_type == 'authorized_retailer'
        assert store.street_address == '123 Main St'
        assert store.city == 'Dallas'
        assert store.state == 'TX'
        assert store.latitude == 32.7767
        assert store.hours_monday == '10:00-19:00'

    def test_parse_minimal_store_data(self):
        """Test parsing store with minimal data."""
        raw_store = {
            'data': {
                'id': '99999',
                'name': 'Minimal Store',
                'address': {}
            }
        }

        store = _parse_store(raw_store)

        assert store is not None
        assert store.store_id == '99999'
        assert store.name == 'Minimal Store'
        assert store.latitude is None
        assert store.phone == ''

    def test_parse_unwrapped_data(self):
        """Test parsing store without 'data' wrapper."""
        raw_store = {
            'id': '11111',
            'name': 'Direct Store',
            'address': {
                'city': 'Austin',
                'region': 'TX'
            }
        }

        store = _parse_store(raw_store)

        assert store is not None
        assert store.store_id == '11111'
        assert store.city == 'Austin'


class TestFetchStoresAtPoint:
    """Tests for _fetch_stores_at_point function."""

    @patch('src.scrapers.cricket.utils.get_with_retry')
    def test_fetch_returns_stores(self, mock_get):
        """Test fetching stores returns parsed results."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'response': {
                'modules': [{
                    'results': [
                        {'data': {'id': '1', 'name': 'Store 1', 'address': {}}},
                        {'data': {'id': '2', 'name': 'Store 2', 'address': {}}}
                    ]
                }]
            }
        }
        mock_get.return_value = mock_response

        session = Mock()
        stores = _fetch_stores_at_point(session, 32.7767, -96.7970)

        assert len(stores) == 2
        mock_get.assert_called_once()

    @patch('src.scrapers.cricket.utils.get_with_retry')
    def test_fetch_returns_empty_on_failure(self, mock_get):
        """Test fetching returns empty list on failure."""
        mock_get.return_value = None

        session = Mock()
        stores = _fetch_stores_at_point(session, 32.7767, -96.7970)

        assert stores == []

    @patch('src.scrapers.cricket.utils.get_with_retry')
    def test_fetch_handles_json_error(self, mock_get):
        """Test fetching handles JSON parse errors gracefully."""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        session = Mock()
        stores = _fetch_stores_at_point(session, 32.7767, -96.7970)

        assert stores == []


class TestCricketRun:
    """Tests for Cricket run() method."""

    def _make_api_response(self, store_ids):
        """Helper to create API response with given store IDs."""
        results = [
            {
                'data': {
                    'id': str(sid),
                    'name': f'Store {sid}',
                    'address': {
                        'line1': f'{sid} Main St',
                        'city': 'Dallas',
                        'region': 'TX',
                        'postalCode': '75001',
                        'countryCode': 'US'
                    }
                }
            }
            for sid in store_ids
        ]
        response = Mock()
        response.json.return_value = {'response': {'results': results}}
        return response

    @patch('src.scrapers.cricket.create_session_factory')
    @patch('src.scrapers.cricket._fetch_stores_at_point')
    @patch('src.scrapers.cricket._generate_us_grid')
    def test_run_returns_correct_structure(self, mock_grid, mock_fetch, mock_factory, mock_session):
        """Test that run() returns the expected structure."""
        # Use small grid for test
        mock_grid.return_value = [(32.0, -96.0), (33.0, -97.0)]

        # Return stores from fetch
        mock_fetch.return_value = [
            {'data': {'id': '1', 'name': 'Store 1', 'address': {}}}
        ]

        mock_factory.return_value = lambda: Mock()

        result = run(mock_session, {'parallel_workers': 1}, retailer='cricket')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert result['checkpoints_used'] is False

    @patch('src.scrapers.cricket.create_session_factory')
    @patch('src.scrapers.cricket._fetch_stores_at_point')
    @patch('src.scrapers.cricket._generate_us_grid')
    def test_run_with_limit(self, mock_grid, mock_fetch, mock_factory, mock_session):
        """Test run() respects limit parameter."""
        mock_grid.return_value = [(32.0, -96.0)]
        mock_fetch.return_value = [
            {'data': {'id': str(i), 'name': f'Store {i}', 'address': {}}}
            for i in range(10)
        ]
        mock_factory.return_value = lambda: Mock()

        result = run(mock_session, {'parallel_workers': 1}, retailer='cricket', limit=3)

        assert result['count'] == 3
        assert len(result['stores']) == 3

    @patch('src.scrapers.cricket.create_session_factory')
    @patch('src.scrapers.cricket._fetch_stores_at_point')
    @patch('src.scrapers.cricket._generate_us_grid')
    def test_run_deduplicates_stores(self, mock_grid, mock_fetch, mock_factory, mock_session):
        """Test that run() deduplicates stores by store_id."""
        # Multiple grid points return the same store
        mock_grid.return_value = [(32.0, -96.0), (32.5, -96.5), (33.0, -97.0)]

        # Same store returned from each point
        mock_fetch.return_value = [
            {'data': {'id': 'same-id', 'name': 'Same Store', 'address': {}}}
        ]

        mock_factory.return_value = lambda: Mock()

        result = run(mock_session, {'parallel_workers': 1}, retailer='cricket')

        # Should only have one store despite 3 grid points
        assert result['count'] == 1
        assert result['stores'][0]['store_id'] == 'same-id'

    @patch('src.scrapers.cricket.create_session_factory')
    @patch('src.scrapers.cricket._fetch_stores_at_point')
    @patch('src.scrapers.cricket._generate_us_grid')
    def test_run_test_mode(self, mock_grid, mock_fetch, mock_factory, mock_session):
        """Test run() in test mode uses larger grid spacing."""
        mock_grid.return_value = [(32.0, -96.0)]
        mock_fetch.return_value = []
        mock_factory.return_value = lambda: Mock()

        run(mock_session, {'parallel_workers': 1}, retailer='cricket', test=True)

        # Should have been called with larger spacing
        mock_grid.assert_called_once_with(200)

    @patch('src.scrapers.cricket.create_session_factory')
    @patch('src.scrapers.cricket._fetch_stores_at_point')
    @patch('src.scrapers.cricket._generate_us_grid')
    def test_run_empty_results(self, mock_grid, mock_fetch, mock_factory, mock_session):
        """Test run() with no stores found."""
        mock_grid.return_value = [(32.0, -96.0)]
        mock_fetch.return_value = []
        mock_factory.return_value = lambda: Mock()

        result = run(mock_session, {'parallel_workers': 1}, retailer='cricket')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False


class TestCricketConfig:
    """Tests for Cricket configuration."""

    def test_api_url_builder(self):
        """Test API URL builder creates valid URL."""
        url = config.build_api_url(32.7767, -96.7970)

        assert 'prod-cdn.us.yextapis.com' in url
        assert 'api_key=' in url
        assert 'location=32.7767,-96.797' in url
        assert 'locationRadius=' in url
        # Verify limit is NOT in URL (Yext doesn't support it)
        assert 'limit=' not in url

    def test_api_url_radius_conversion(self):
        """Test API URL converts miles to meters correctly."""
        url = config.build_api_url(32.7767, -96.7970, radius_miles=50)

        # 50 miles = ~80467 meters
        assert 'locationRadius=80467' in url

    def test_headers_function(self):
        """Test headers function returns valid headers."""
        headers = config.get_headers()

        assert 'User-Agent' in headers
        assert 'Accept' in headers
        assert headers['Accept'] == 'application/json'
        assert 'cricketwireless.com' in headers.get('Referer', '')

    def test_store_types_mapping(self):
        """Test store types mapping is complete."""
        assert 'Cricket Wireless Authorized Retailer' in config.STORE_TYPES
        assert 'Walmart' in config.STORE_TYPES
        assert 'Best Buy' in config.STORE_TYPES
        assert config.STORE_TYPES['Walmart'] == 'walmart'
