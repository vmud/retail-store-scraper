"""Unit tests for Bell scraper."""
# pylint: disable=no-member

import json
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.scrapers.bell import (
    BellStore,
    _format_schema_hours,
    _extract_store_type,
    _extract_services,
    _has_curbside_pickup,
    get_store_urls_from_sitemap,
    extract_store_details,
    run,
    reset_request_counter,
)


class TestBellStore:
    """Tests for BellStore dataclass."""

    def test_to_dict(self):
        """Test dict conversion."""
        store = BellStore(
            store_id='BE516',
            name='Bell',
            street_address='316 Queen St W',
            city='Toronto',
            state='ON',
            postal_code='M5V2A2',
            country='CA',
            phone='416-977-6969',
            hours='[{"day": "Monday", "open": "10:00", "close": "18:00"}]',
            services='["Mobile devices"]',
            store_type='corporate',
            has_curbside=True,
            url='https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell-Queen-St-W/BE516',
            scraped_at='2026-02-02T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == 'BE516'
        assert result['city'] == 'Toronto'
        assert result['state'] == 'ON'
        assert result['has_curbside'] is True


class TestFormatSchemaHours:
    """Tests for _format_schema_hours function."""

    def test_valid_hours(self):
        """Test formatting valid hours."""
        hours = ["Mo 1000-1800", "Tu 1000-1800", "Su 1200-1700"]
        result = _format_schema_hours(hours)
        parsed = json.loads(result)

        assert len(parsed) == 3
        assert parsed[0]['day'] == 'Monday'
        assert parsed[0]['open'] == '10:00'
        assert parsed[0]['close'] == '18:00'

    def test_empty_hours(self):
        """Test empty hours returns None."""
        assert _format_schema_hours([]) is None
        assert _format_schema_hours(None) is None

    def test_invalid_format_skipped(self):
        """Test invalid hour format is skipped."""
        hours = ["Mo 1000-1800", "invalid", "Tu 0900-1700"]
        result = _format_schema_hours(hours)
        parsed = json.loads(result)

        assert len(parsed) == 2

    def test_single_string_hours(self):
        """Test schema.org single string format is handled."""
        # schema.org allows openingHours as single string, not just array
        hours = "Mo 1000-1800"
        result = _format_schema_hours(hours)
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]['day'] == 'Monday'
        assert parsed[0]['open'] == '10:00'
        assert parsed[0]['close'] == '18:00'


class TestExtractStoreType:
    """Tests for _extract_store_type function."""

    def test_corporate_store(self):
        """Test corporate store detection."""
        assert _extract_store_type('Bell') == 'corporate'
        assert _extract_store_type('bell') == 'corporate'
        assert _extract_store_type(' Bell ') == 'corporate'

    def test_authorized_dealer(self):
        """Test authorized dealer detection."""
        assert _extract_store_type('RWireless') == 'authorized_dealer'
        assert _extract_store_type('TNT Digital') == 'authorized_dealer'
        assert _extract_store_type('Go West Wireless') == 'authorized_dealer'


class TestGetStoreUrlsFromSitemap:
    """Tests for get_store_urls_from_sitemap function."""

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_parse_sitemap(self, mock_counter, mock_get):
        """Test parsing sitemap XML."""
        # Note: URLs must match bell_config.STORE_URL_PATTERN: r'/en/[a-z]{2}/[^/]+/[^/]+'
        # This requires lowercase province codes like /en/on/ (not /en/ON/)
        sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://storelocator.bell.ca/en/on/toronto/bell-queen-st-w</loc></url>
    <url><loc>https://storelocator.bell.ca/en/ab/calgary/bell</loc></url>
    <url><loc>https://storelocator.bell.ca/bellca/en/Ontario.html</loc></url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = sitemap_xml.encode('utf-8')
        mock_get.return_value = mock_response
        mock_session = Mock()

        urls = get_store_urls_from_sitemap(mock_session)

        # Should only include URLs matching the store URL pattern
        assert len(urls) == 2
        assert 'toronto' in urls[0]
        assert 'calgary' in urls[1]

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_failed_fetch(self, mock_counter, mock_get):
        """Test failed fetch returns empty list."""
        mock_get.return_value = None
        mock_session = Mock()

        urls = get_store_urls_from_sitemap(mock_session)

        assert urls == []


class TestExtractStoreDetails:
    """Tests for extract_store_details function."""

    def _make_store_page_html(self, store_id='BE516', name='Bell', has_curbside=True):
        """Helper to create store page HTML."""
        curbside_html = '<img src="/bellca/Icon/curbside.png"> Curbside pickup' if has_curbside else ''
        return f'''<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{{
    "@type": "LocalBusiness",
    "name": "{name}",
    "telephone": "416 977-6969",
    "address": {{
        "streetAddress": "316 Queen St W",
        "addressLocality": "Toronto",
        "addressRegion": "ON",
        "postalCode": "M5V2A2"
    }},
    "openingHours": ["Mo 1000-1800", "Tu 1000-1800"]
}}
</script>
</head>
<body>
<ul class="rsx-list">
    <li>Mobile devices for business + consumer</li>
    <li>Residential: Internet + TV + Phone</li>
</ul>
{curbside_html}
</body>
</html>'''

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_extract_valid_store(self, mock_counter, mock_get):
        """Test extracting valid store data."""
        mock_response = Mock()
        mock_response.text = self._make_store_page_html()
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell-Queen-St-W/BE516'
        store = extract_store_details(mock_session, url)

        assert store is not None
        assert store.store_id == 'BE516'
        assert store.name == 'Bell'
        assert store.city == 'Toronto'
        assert store.state == 'ON'
        assert store.store_type == 'corporate'
        assert store.has_curbside is True

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_extract_dealer_store(self, mock_counter, mock_get):
        """Test extracting dealer store."""
        mock_response = Mock()
        mock_response.text = self._make_store_page_html(name='RWireless')
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/AB/Calgary/RWireless/BE725'
        store = extract_store_details(mock_session, url)

        assert store is not None
        assert store.store_type == 'authorized_dealer'

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_no_curbside(self, mock_counter, mock_get):
        """Test store without curbside pickup."""
        mock_response = Mock()
        mock_response.text = self._make_store_page_html(has_curbside=False)
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell/BE516'
        store = extract_store_details(mock_session, url)

        assert store is not None
        assert store.has_curbside is False

    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_missing_json_ld(self, mock_counter, mock_get):
        """Test handling missing JSON-LD."""
        mock_response = Mock()
        mock_response.text = '<html><body>No schema</body></html>'
        mock_get.return_value = mock_response
        mock_session = Mock()

        url = 'https://storelocator.bell.ca/bellca/en/ON/Toronto/Bell/BE516'
        store = extract_store_details(mock_session, url)

        assert store is None


class TestBellRun:
    """Tests for Bell run() function."""

    def _make_sitemap_response(self, store_ids):
        """Helper to create sitemap response."""
        # URLs must match bell_config.STORE_URL_PATTERN: r'/en/[a-z]{2}/[^/]+/[^/]+'
        urls = '\n'.join(
            f'<url><loc>https://storelocator.bell.ca/en/on/toronto/bell-{sid}</loc></url>'
            for sid in store_ids
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_response(self):
        """Helper to create store page response."""
        html = '''<!DOCTYPE html>
<html><head>
<script type="application/ld+json">
{
    "@type": "LocalBusiness",
    "name": "Bell",
    "telephone": "416 977-6969",
    "address": {
        "streetAddress": "316 Queen St W",
        "addressLocality": "Toronto",
        "addressRegion": "ON",
        "postalCode": "M5V2A2"
    }
}
</script>
</head><body></body></html>'''
        response = Mock()
        response.text = html
        return response

    @patch('src.scrapers.bell.URLCache')
    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell.utils.random_delay')
    @patch('src.scrapers.bell._request_counter')
    def test_run_returns_structure(self, mock_counter, mock_delay, mock_get, mock_cache_class):
        """Test run() returns expected structure."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache
        mock_get.side_effect = [
            self._make_sitemap_response([516]),
            self._make_store_response()
        ]
        mock_session = Mock()

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='bell')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result

    @patch('src.scrapers.bell.URLCache')
    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell.utils.random_delay')
    @patch('src.scrapers.bell._request_counter')
    def test_run_with_limit(self, mock_counter, mock_delay, mock_get, mock_cache_class):
        """Test run() respects limit parameter."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache
        mock_get.side_effect = [
            self._make_sitemap_response([516, 517, 518, 519, 520]),
            self._make_store_response(),
            self._make_store_response(),
        ]
        mock_session = Mock()

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='bell', limit=2)

        assert result['count'] == 2

    @patch('src.scrapers.bell.URLCache')
    @patch('src.scrapers.bell.utils.get_with_retry')
    @patch('src.scrapers.bell._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_cache_class):
        """Test run() with empty sitemap."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response
        mock_session = Mock()

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='bell')

        assert result['stores'] == []
        assert result['count'] == 0


@pytest.fixture
def mock_session():
    """Fixture for mock session."""
    return Mock()
