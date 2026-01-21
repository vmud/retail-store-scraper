"""Unit tests for Verizon scraper."""

import json
import pytest
from unittest.mock import Mock, patch

from src.scrapers.verizon import (
    StateConfig,
    VALID_STATE_SLUGS,
    STATE_SLUG_TO_NAME,
    STATE_URL_PATTERNS,
    get_state_url,
    _STATES,
    extract_store_details,
    run,
    get_request_count,
    reset_request_counter,
    _check_pause_logic,
)


class TestStateConfiguration:
    """Tests for state configuration data structures."""

    def test_state_config_dataclass(self):
        """Test StateConfig dataclass creation."""
        config = StateConfig(slug='california', name='California')
        assert config.slug == 'california'
        assert config.name == 'California'
        assert config.url_pattern is None

    def test_state_config_with_url_pattern(self):
        """Test StateConfig with custom URL pattern."""
        config = StateConfig(
            slug='north-carolina',
            name='North Carolina',
            url_pattern='/stores/north-carolina/'
        )
        assert config.url_pattern == '/stores/north-carolina/'

    def test_valid_state_slugs_count(self):
        """Test that we have all 51 state slugs (50 states + DC)."""
        assert len(VALID_STATE_SLUGS) == 51

    def test_valid_state_slugs_includes_dc(self):
        """Test that DC is included in valid slugs."""
        assert 'washington-dc' in VALID_STATE_SLUGS

    def test_state_slug_to_name_mapping(self):
        """Test slug to name mapping."""
        assert STATE_SLUG_TO_NAME['california'] == 'California'
        assert STATE_SLUG_TO_NAME['new-york'] == 'New York'
        assert STATE_SLUG_TO_NAME['washington-dc'] == 'District Of Columbia'

    def test_special_url_patterns(self):
        """Test special URL patterns for non-standard states."""
        assert 'north-carolina' in STATE_URL_PATTERNS
        assert STATE_URL_PATTERNS['north-carolina'] == '/stores/north-carolina/'
        assert 'washington-dc' in STATE_URL_PATTERNS
        assert STATE_URL_PATTERNS['washington-dc'] == '/stores/state/washington-dc/'

    def test_states_dict_consistency(self):
        """Test that _STATES dict is consistent with derived views."""
        # All slugs in VALID_STATE_SLUGS should be in _STATES
        for slug in VALID_STATE_SLUGS:
            assert slug in _STATES

        # All states in _STATES should be in VALID_STATE_SLUGS
        for slug in _STATES:
            assert slug in VALID_STATE_SLUGS

        # All slug-to-name mappings should match _STATES
        for slug, name in STATE_SLUG_TO_NAME.items():
            assert _STATES[slug].name == name

    def test_hyphenated_state_names(self):
        """Test hyphenated state names are properly mapped."""
        hyphenated_states = [
            ('new-hampshire', 'New Hampshire'),
            ('new-jersey', 'New Jersey'),
            ('new-mexico', 'New Mexico'),
            ('new-york', 'New York'),
            ('north-carolina', 'North Carolina'),
            ('north-dakota', 'North Dakota'),
            ('rhode-island', 'Rhode Island'),
            ('south-carolina', 'South Carolina'),
            ('south-dakota', 'South Dakota'),
            ('west-virginia', 'West Virginia'),
        ]
        for slug, name in hyphenated_states:
            assert slug in VALID_STATE_SLUGS
            assert STATE_SLUG_TO_NAME[slug] == name


class TestGetStateUrl:
    """Tests for get_state_url function."""

    def test_standard_state_url(self):
        """Test URL for standard state."""
        url = get_state_url('california')
        assert url == '/stores/state/california/'

    def test_north_carolina_special_url(self):
        """Test special URL for North Carolina."""
        url = get_state_url('north-carolina')
        assert url == '/stores/north-carolina/'

    def test_washington_dc_special_url(self):
        """Test special URL for Washington DC."""
        url = get_state_url('washington-dc')
        assert url == '/stores/state/washington-dc/'

    def test_unknown_state_defaults_to_standard(self):
        """Test that unknown state slug uses standard pattern."""
        url = get_state_url('unknown-state')
        assert url == '/stores/state/unknown-state/'

    def test_all_states_have_urls(self):
        """Test that all valid states return a URL."""
        for slug in VALID_STATE_SLUGS:
            url = get_state_url(slug)
            assert url.startswith('/stores/')
            assert url.endswith('/')


class TestVerizonRun:
    """Tests for Verizon run() method."""

    def _make_store_page_response(self, store_id, city='dallas'):
        """Helper to create store page HTML response with JSON-LD."""
        html = f'''<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{{
    "@type": "Store",
    "name": "Verizon Store {store_id}",
    "telephone": "(555) 123-4567",
    "address": {{
        "streetAddress": "{store_id} Main St",
        "addressLocality": "{city}",
        "addressRegion": "TX",
        "postalCode": "75001",
        "addressCountry": "US"
    }},
    "geo": {{
        "latitude": "32.7767",
        "longitude": "-96.7970"
    }}
}}
</script>
</head>
</html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.verizon._load_cached_urls')
    @patch('src.scrapers.verizon.get_stores_for_city')
    @patch('src.scrapers.verizon.get_cities_for_state')
    @patch('src.scrapers.verizon.get_all_states')
    @patch('src.scrapers.verizon.extract_store_details')
    @patch('src.scrapers.verizon.reset_request_counter')
    def test_run_returns_correct_structure(self, mock_reset, mock_extract, mock_states,
                                           mock_cities, mock_stores, mock_cache, mock_session):
        """Test that run() returns the expected structure."""
        mock_cache.return_value = None  # Force discovery (no URL cache)
        mock_states.return_value = [{'name': 'Texas', 'url': 'https://www.verizon.com/stores/state/texas/'}]
        mock_cities.return_value = [{'city': 'Dallas', 'state': 'Texas', 'url': 'https://www.verizon.com/stores/texas/dallas/'}]
        mock_stores.return_value = [{'city': 'Dallas', 'state': 'Texas', 'url': 'https://www.verizon.com/stores/texas/dallas/store-123/'}]
        mock_extract.return_value = {
            'name': 'Test Store',
            'street_address': '123 Main St',
            'city': 'Dallas',
            'state': 'TX',
            'zip': '75001',
            'country': 'US',
            'latitude': '32.77',
            'longitude': '-96.79',
            'phone': '(555) 123-4567',
            'url': 'https://www.verizon.com/stores/texas/dallas/store-123/',
            'sub_channel': 'COR',
            'dealer_name': None,
            'store_location': 'dallas',
            'retailer_store_number': None,
            'verizon_uid': '123',
            'scraped_at': '2025-01-19T12:00:00'
        }

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='verizon')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.verizon._load_cached_urls')
    @patch('src.scrapers.verizon.get_stores_for_city')
    @patch('src.scrapers.verizon.get_cities_for_state')
    @patch('src.scrapers.verizon.get_all_states')
    @patch('src.scrapers.verizon.extract_store_details')
    @patch('src.scrapers.verizon.reset_request_counter')
    def test_run_with_limit(self, mock_reset, mock_extract, mock_states,
                            mock_cities, mock_stores, mock_cache, mock_session):
        """Test run() respects limit parameter."""
        mock_cache.return_value = None  # Force discovery (no URL cache)
        mock_states.return_value = [{'name': 'Texas', 'url': 'https://www.verizon.com/stores/state/texas/'}]
        mock_cities.return_value = [{'city': 'Dallas', 'state': 'Texas', 'url': 'https://www.verizon.com/stores/texas/dallas/'}]
        mock_stores.return_value = [
            {'city': 'Dallas', 'state': 'Texas', 'url': f'https://www.verizon.com/stores/texas/dallas/store-{i}/'}
            for i in range(5)
        ]
        mock_extract.return_value = {
            'name': 'Test Store',
            'street_address': '123 Main St',
            'city': 'Dallas',
            'state': 'TX',
            'zip': '75001',
            'country': 'US',
            'latitude': '32.77',
            'longitude': '-96.79',
            'phone': '(555) 123-4567',
            'url': 'https://www.verizon.com/stores/test/',
            'sub_channel': 'COR',
            'dealer_name': None,
            'store_location': 'dallas',
            'retailer_store_number': None,
            'verizon_uid': '123',
            'scraped_at': '2025-01-19T12:00:00'
        }

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='verizon', limit=2)

        assert result['count'] == 2
        assert len(result['stores']) == 2

    @patch('src.scrapers.verizon._load_cached_urls')
    @patch('src.scrapers.verizon.get_stores_for_city')
    @patch('src.scrapers.verizon.get_cities_for_state')
    @patch('src.scrapers.verizon.get_all_states')
    @patch('src.scrapers.verizon.reset_request_counter')
    def test_run_empty_stores(self, mock_reset, mock_states, mock_cities, mock_stores, mock_cache, mock_session):
        """Test run() with no store URLs returns empty stores."""
        mock_cache.return_value = None  # Force discovery (no URL cache)
        mock_states.return_value = [{'name': 'Texas', 'url': 'https://www.verizon.com/stores/state/texas/'}]
        mock_cities.return_value = []
        mock_stores.return_value = []

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='verizon')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False


class TestVerizonCheckpoint:
    """Tests for Verizon checkpoint/resume functionality."""

    @patch('src.scrapers.verizon._load_cached_urls')
    @patch('src.scrapers.verizon.utils.load_checkpoint')
    @patch('src.scrapers.verizon.utils.save_checkpoint')
    @patch('src.scrapers.verizon.get_stores_for_city')
    @patch('src.scrapers.verizon.get_cities_for_state')
    @patch('src.scrapers.verizon.get_all_states')
    @patch('src.scrapers.verizon.reset_request_counter')
    def test_resume_loads_checkpoint(self, mock_reset, mock_states, mock_cities,
                                      mock_stores, mock_save, mock_load, mock_cache, mock_session):
        """Test that resume=True loads existing checkpoint."""
        mock_cache.return_value = None  # Force discovery (no URL cache)
        mock_load.return_value = {
            'stores': [{'store_id': '123', 'name': 'Existing Store'}],
            'completed_urls': ['https://www.verizon.com/stores/texas/dallas/store-123/']
        }
        # Must have non-empty stores for checkpoints_used to be True
        mock_states.return_value = [{'name': 'Texas', 'url': 'https://www.verizon.com/stores/state/texas/'}]
        mock_cities.return_value = [{'city': 'Dallas', 'state': 'Texas', 'url': 'https://www.verizon.com/stores/texas/dallas/'}]
        mock_stores.return_value = [{'city': 'Dallas', 'state': 'Texas', 'url': 'https://www.verizon.com/stores/texas/dallas/store-123/'}]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='verizon', resume=True)

        mock_load.assert_called_once()
        assert result['checkpoints_used'] is True

    @patch('src.scrapers.verizon._load_cached_urls')
    @patch('src.scrapers.verizon.utils.load_checkpoint')
    @patch('src.scrapers.verizon.get_stores_for_city')
    @patch('src.scrapers.verizon.get_cities_for_state')
    @patch('src.scrapers.verizon.get_all_states')
    @patch('src.scrapers.verizon.reset_request_counter')
    def test_no_resume_starts_fresh(self, mock_reset, mock_states, mock_cities,
                                     mock_stores, mock_load, mock_cache, mock_session):
        """Test that resume=False does not load checkpoint."""
        mock_cache.return_value = None  # Force discovery (no URL cache)
        mock_states.return_value = []
        mock_cities.return_value = []
        mock_stores.return_value = []

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='verizon', resume=False)

        mock_load.assert_not_called()
        assert result['checkpoints_used'] is False


class TestVerizonRateLimiting:
    """Tests for Verizon rate limiting and pause logic."""

    def test_request_counter_reset(self):
        """Test that request counter resets properly."""
        reset_request_counter()
        assert get_request_count() == 0

    @patch('src.scrapers.verizon.time.sleep')
    @patch('src.scrapers.verizon.random.uniform')
    def test_pause_at_50_requests(self, mock_uniform, mock_sleep):
        """Test that pause triggers at 50 request threshold."""
        mock_uniform.return_value = 15
        reset_request_counter()

        from src.scrapers.verizon import _request_counter
        _request_counter._count = 50

        _check_pause_logic()

        mock_sleep.assert_called_once()
        mock_uniform.assert_called()

    @patch('src.scrapers.verizon.time.sleep')
    @patch('src.scrapers.verizon.random.uniform')
    def test_pause_at_200_requests(self, mock_uniform, mock_sleep):
        """Test that longer pause triggers at 200 request threshold."""
        mock_uniform.return_value = 180
        reset_request_counter()

        from src.scrapers.verizon import _request_counter
        _request_counter._count = 200

        _check_pause_logic()

        mock_sleep.assert_called_once()

    @patch('src.scrapers.verizon.time.sleep')
    def test_no_pause_between_thresholds(self, mock_sleep):
        """Test that no pause occurs between thresholds."""
        reset_request_counter()

        from src.scrapers.verizon import _request_counter
        _request_counter._count = 25

        _check_pause_logic()

        mock_sleep.assert_not_called()


class TestVerizonErrorHandling:
    """Tests for Verizon error handling."""

    @patch('src.scrapers.verizon.utils.get_with_retry')
    @patch('src.scrapers.verizon._request_counter')
    def test_store_fetch_failure_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that store page fetch failure returns None."""
        mock_get.return_value = None

        store = extract_store_details(mock_session, 'https://www.verizon.com/stores/texas/dallas/store-123/')

        assert store is None

    @patch('src.scrapers.verizon.utils.get_with_retry')
    @patch('src.scrapers.verizon._request_counter')
    def test_missing_json_ld_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that missing JSON-LD returns None."""
        html = '<html><body>No JSON-LD here</body></html>'
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.verizon.com/stores/texas/dallas/store-123/')

        assert store is None

    @patch('src.scrapers.verizon.utils.get_with_retry')
    @patch('src.scrapers.verizon._request_counter')
    def test_wrong_json_ld_type_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that wrong JSON-LD type returns None."""
        html = '''<html><head>
<script type="application/ld+json">{"@type": "Organization", "name": "Verizon"}</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.verizon.com/stores/texas/dallas/store-123/')

        assert store is None

    @patch('src.scrapers.verizon.utils.get_with_retry')
    @patch('src.scrapers.verizon._request_counter')
    def test_invalid_store_data_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that invalid store data (missing required fields) returns None."""
        # Store with missing city and state fails validation
        html = '''<html><head>
<script type="application/ld+json">
{
    "@type": "Store",
    "name": "Test Store",
    "address": {}
}
</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.verizon.com/stores/texas/dallas/store-123/')

        assert store is None


class TestParallelDiscovery:
    """Tests for parallel discovery worker functions."""

    @patch('src.scrapers.verizon.get_cities_for_state')
    @patch('src.scrapers.verizon.utils.create_proxied_session')
    def test_fetch_cities_worker_success(self, mock_create_session, mock_get_cities):
        """Test city worker successfully fetches cities for a state."""
        from src.scrapers.verizon import _fetch_cities_for_state_worker, _create_session_factory

        mock_session = Mock()
        mock_session.close = Mock()
        mock_create_session.return_value = mock_session
        mock_get_cities.return_value = [
            {'city': 'Dallas', 'state': 'Texas', 'url': 'https://verizon.com/stores/texas/dallas/'},
            {'city': 'Houston', 'state': 'Texas', 'url': 'https://verizon.com/stores/texas/houston/'}
        ]

        state = {'name': 'Texas', 'url': 'https://verizon.com/stores/state/texas/'}
        config = {'proxy': {'mode': 'direct'}}
        factory = _create_session_factory(config)

        state_name, cities = _fetch_cities_for_state_worker(state, factory, config, 'verizon')

        assert state_name == 'Texas'
        assert len(cities) == 2
        assert cities[0]['city'] == 'Dallas'
        mock_session.close.assert_called_once()

    @patch('src.scrapers.verizon.get_cities_for_state')
    @patch('src.scrapers.verizon.utils.create_proxied_session')
    def test_fetch_cities_worker_handles_error(self, mock_create_session, mock_get_cities):
        """Test city worker handles errors gracefully."""
        from src.scrapers.verizon import _fetch_cities_for_state_worker, _create_session_factory

        mock_session = Mock()
        mock_session.close = Mock()
        mock_create_session.return_value = mock_session
        mock_get_cities.side_effect = Exception("Network error")

        state = {'name': 'Texas', 'url': 'https://verizon.com/stores/state/texas/'}
        config = {'proxy': {'mode': 'direct'}}
        factory = _create_session_factory(config)

        state_name, cities = _fetch_cities_for_state_worker(state, factory, config, 'verizon')

        assert state_name == 'Texas'
        assert cities == []  # Empty list on error
        mock_session.close.assert_called_once()

    @patch('src.scrapers.verizon.get_stores_for_city')
    @patch('src.scrapers.verizon.utils.create_proxied_session')
    def test_fetch_stores_worker_success(self, mock_create_session, mock_get_stores):
        """Test store URL worker successfully fetches store URLs for a city."""
        from src.scrapers.verizon import _fetch_stores_for_city_worker, _create_session_factory

        mock_session = Mock()
        mock_session.close = Mock()
        mock_create_session.return_value = mock_session
        mock_get_stores.return_value = [
            {'city': 'Dallas', 'state': 'Texas', 'url': 'https://verizon.com/stores/texas/dallas/store-1/'},
            {'city': 'Dallas', 'state': 'Texas', 'url': 'https://verizon.com/stores/texas/dallas/store-2/'}
        ]

        city = {'city': 'Dallas', 'state': 'Texas', 'url': 'https://verizon.com/stores/texas/dallas/'}
        config = {'proxy': {'mode': 'direct'}}
        factory = _create_session_factory(config)

        city_name, state_name, store_urls = _fetch_stores_for_city_worker(city, factory, config, 'verizon')

        assert city_name == 'Dallas'
        assert state_name == 'Texas'
        assert len(store_urls) == 2
        assert 'store-1' in store_urls[0]
        mock_session.close.assert_called_once()

    @patch('src.scrapers.verizon.get_stores_for_city')
    @patch('src.scrapers.verizon.utils.create_proxied_session')
    def test_fetch_stores_worker_handles_error(self, mock_create_session, mock_get_stores):
        """Test store URL worker handles errors gracefully."""
        from src.scrapers.verizon import _fetch_stores_for_city_worker, _create_session_factory

        mock_session = Mock()
        mock_session.close = Mock()
        mock_create_session.return_value = mock_session
        mock_get_stores.side_effect = Exception("Connection timeout")

        city = {'city': 'Dallas', 'state': 'Texas', 'url': 'https://verizon.com/stores/texas/dallas/'}
        config = {'proxy': {'mode': 'direct'}}
        factory = _create_session_factory(config)

        city_name, state_name, store_urls = _fetch_stores_for_city_worker(city, factory, config, 'verizon')

        assert city_name == 'Dallas'
        assert state_name == 'Texas'
        assert store_urls == []  # Empty list on error
        mock_session.close.assert_called_once()

    @patch('src.scrapers.verizon.utils.create_proxied_session')
    def test_session_factory_creates_sessions(self, mock_create_session):
        """Test session factory creates new sessions on each call."""
        from src.scrapers.verizon import _create_session_factory

        session1 = Mock()
        session2 = Mock()
        mock_create_session.side_effect = [session1, session2]

        config = {'proxy': {'mode': 'direct'}}
        factory = _create_session_factory(config)

        result1 = factory()
        result2 = factory()

        assert result1 is session1
        assert result2 is session2
        assert mock_create_session.call_count == 2
