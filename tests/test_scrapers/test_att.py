"""Unit tests for AT&T scraper."""

import json
import pytest
from unittest.mock import Mock, patch

from src.scrapers.att import (
    ATTStore,
    _extract_store_type_and_dealer,
    get_store_urls_from_sitemap,
    extract_store_details,
    run,
    get_request_count,
    reset_request_counter,
    _check_pause_logic,
)


class TestATTStore:
    """Tests for ATTStore dataclass."""

    def test_to_dict_cor_store(self):
        """Test dict conversion for corporate store."""
        store = ATTStore(
            store_id='ATT-12345',
            name='AT&T Store',
            telephone='(555) 123-4567',
            street_address='123 Main St',
            city='Dallas',
            state='TX',
            postal_code='75001',
            country='US',
            rating_value=4.5,
            rating_count=120,
            url='https://www.att.com/stores/texas/dallas/12345',
            sub_channel='COR',
            dealer_name=None,
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == 'ATT-12345'
        assert result['sub_channel'] == 'COR'
        assert result['dealer_name'] is None

    def test_to_dict_dealer_store(self):
        """Test dict conversion for dealer store."""
        store = ATTStore(
            store_id='ATT-67890',
            name='Prime Wireless',
            telephone='(555) 987-6543',
            street_address='456 Oak Ave',
            city='Houston',
            state='TX',
            postal_code='77001',
            country='US',
            rating_value=3.8,
            rating_count=45,
            url='https://www.att.com/stores/texas/houston/67890',
            sub_channel='Dealer',
            dealer_name='PRIME COMMUNICATIONS',
            scraped_at='2025-01-19T12:00:00'
        )
        result = store.to_dict()

        assert result['store_id'] == 'ATT-67890'
        assert result['sub_channel'] == 'Dealer'
        assert result['dealer_name'] == 'PRIME COMMUNICATIONS'


class TestExtractStoreTypeAndDealer:
    """Tests for _extract_store_type_and_dealer function."""

    def test_cor_store_detection(self):
        """Test detection of corporate retail store."""
        html = '''
        <script>
            let topDisplayType = "AT&T Retail";
            let storeMasterDealer = "";
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None

    def test_dealer_store_detection(self):
        """Test detection of dealer store with dealer name."""
        html = '''
        <script>
            let topDisplayType = "Authorized Retail";
            storeMasterDealer: "PRIME COMMUNICATIONS - 58"
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'Dealer'
        assert dealer_name == 'PRIME COMMUNICATIONS'

    def test_dealer_name_suffix_removal(self):
        """Test that dealer name suffix is properly removed."""
        html = '''
        <script>
            let topDisplayType = "Authorized Retail";
            storeMasterDealer: 'WIRELESS VISION - 123'
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'Dealer'
        assert dealer_name == 'WIRELESS VISION'

    def test_single_quotes_handling(self):
        """Test that single quotes are handled correctly."""
        html = '''
        <script>
            let topDisplayType = 'AT&T Retail';
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None

    def test_unknown_display_type_defaults_to_cor(self):
        """Test that unknown display type defaults to COR."""
        html = '''
        <script>
            let topDisplayType = "Unknown Type";
        </script>
        '''
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None

    def test_missing_display_type_defaults_to_cor(self):
        """Test that missing display type defaults to COR."""
        html = '<html><body>No JavaScript here</body></html>'
        sub_channel, dealer_name = _extract_store_type_and_dealer(html)

        assert sub_channel == 'COR'
        assert dealer_name is None


class TestGetStoreUrlsFromSitemap:
    """Tests for get_store_urls_from_sitemap function."""

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_parse_sitemap_xml(self, mock_counter, mock_get, mock_session):
        """Test parsing sitemap XML."""
        sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://www.att.com/stores/texas/dallas/12345</loc>
    </url>
    <url>
        <loc>https://www.att.com/stores/texas/houston/67890</loc>
    </url>
    <url>
        <loc>https://www.att.com/stores/texas</loc>
    </url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = sitemap_xml.encode('utf-8')
        mock_get.return_value = mock_response

        urls = get_store_urls_from_sitemap(mock_session)

        # Should only include URLs ending in numeric IDs
        assert len(urls) == 2
        assert 'https://www.att.com/stores/texas/dallas/12345' in urls
        assert 'https://www.att.com/stores/texas/houston/67890' in urls

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_failed_fetch_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that failed fetch returns empty list."""
        mock_get.return_value = None

        urls = get_store_urls_from_sitemap(mock_session)

        assert urls == []

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_filters_non_store_urls(self, mock_counter, mock_get, mock_session):
        """Test that non-store URLs are filtered out."""
        sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://www.att.com/stores/texas/dallas/12345</loc></url>
    <url><loc>https://www.att.com/stores/texas</loc></url>
    <url><loc>https://www.att.com/stores</loc></url>
    <url><loc>https://www.att.com/about</loc></url>
</urlset>'''
        mock_response = Mock()
        mock_response.content = sitemap_xml.encode('utf-8')
        mock_get.return_value = mock_response

        urls = get_store_urls_from_sitemap(mock_session)

        # Only the URL ending in numeric ID should be included
        assert len(urls) == 1
        assert urls[0] == 'https://www.att.com/stores/texas/dallas/12345'


class TestATTRun:
    """Tests for AT&T run() method."""

    def _make_sitemap_response(self, store_ids):
        """Helper to create sitemap response with given store IDs."""
        urls = '\n'.join(
            f'<url><loc>https://www.att.com/stores/texas/dallas/{sid}</loc></url>'
            for sid in store_ids
        )
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        return response

    def _make_store_page_response(self, store_id, sub_channel='COR'):
        """Helper to create store page HTML response."""
        display_type = 'AT&T Retail' if sub_channel == 'COR' else 'Authorized Retail'
        dealer_line = '' if sub_channel == 'COR' else 'storeMasterDealer: "TEST DEALER - 1"'
        html = f'''<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{{
    "@type": "MobilePhoneStore",
    "name": "AT&T Store {store_id}",
    "telephone": "(555) 123-4567",
    "address": {{
        "streetAddress": "{store_id} Main St",
        "addressLocality": "Dallas",
        "addressRegion": "TX",
        "postalCode": "75001",
        "addressCountry": {{"name": "US"}}
    }},
    "aggregateRating": {{"ratingValue": "4.5", "ratingCount": "120"}}
}}
</script>
</head>
<body>
<script>
let topDisplayType = "{display_type}";
{dealer_line}
</script>
</body>
</html>'''
        response = Mock()
        response.text = html
        response.content = html.encode('utf-8')
        return response

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_returns_correct_structure(self, mock_counter, mock_get, mock_session):
        """Test that run() returns the expected structure."""
        mock_get.side_effect = [
            self._make_sitemap_response([12345]),
            self._make_store_page_response(12345)
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att')

        assert isinstance(result, dict)
        assert 'stores' in result
        assert 'count' in result
        assert 'checkpoints_used' in result
        assert isinstance(result['stores'], list)
        assert isinstance(result['count'], int)
        assert isinstance(result['checkpoints_used'], bool)

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_with_limit(self, mock_counter, mock_get, mock_session):
        """Test run() respects limit parameter."""
        mock_get.side_effect = [
            self._make_sitemap_response([12345, 12346, 12347, 12348, 12349]),
            self._make_store_page_response(12345),
            self._make_store_page_response(12346),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att', limit=2)

        assert result['count'] == 2
        assert len(result['stores']) == 2

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_empty_sitemap(self, mock_counter, mock_get, mock_session):
        """Test run() with empty sitemap returns empty stores."""
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att')

        assert result['stores'] == []
        assert result['count'] == 0
        assert result['checkpoints_used'] is False

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_run_count_matches_stores_length(self, mock_counter, mock_get, mock_session):
        """Test that count matches the actual number of stores."""
        mock_get.side_effect = [
            self._make_sitemap_response([12345, 12346, 12347]),
            self._make_store_page_response(12345),
            self._make_store_page_response(12346),
            self._make_store_page_response(12347),
        ]

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att')

        assert result['count'] == len(result['stores'])


class TestATTCheckpoint:
    """Tests for AT&T checkpoint/resume functionality."""

    @patch('src.scrapers.att.utils.load_checkpoint')
    @patch('src.scrapers.att.utils.save_checkpoint')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_resume_loads_checkpoint(self, mock_counter, mock_get, mock_save, mock_load, mock_session):
        """Test that resume=True loads existing checkpoint."""
        mock_load.return_value = {
            'stores': [{'store_id': '12345', 'name': 'Existing Store'}],
            'completed_urls': ['https://www.att.com/stores/texas/dallas/12345']
        }
        # Sitemap with URLs (must be non-empty for checkpoints_used to be True)
        xml = '''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.att.com/stores/texas/dallas/12345</loc></url>
        </urlset>'''
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att', resume=True)

        mock_load.assert_called_once()
        assert result['checkpoints_used'] is True

    @patch('src.scrapers.att.utils.load_checkpoint')
    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_no_resume_starts_fresh(self, mock_counter, mock_get, mock_load, mock_session):
        """Test that resume=False does not load checkpoint."""
        xml = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        response = Mock()
        response.content = xml.encode('utf-8')
        mock_get.return_value = response

        result = run(mock_session, {'checkpoint_interval': 100}, retailer='att', resume=False)

        mock_load.assert_not_called()
        assert result['checkpoints_used'] is False


class TestATTRateLimiting:
    """Tests for AT&T rate limiting and pause logic."""

    def test_request_counter_reset(self):
        """Test that request counter resets properly."""
        reset_request_counter()
        assert get_request_count() == 0

    @patch('src.scrapers.att.time.sleep')
    @patch('src.scrapers.att.random.uniform')
    def test_pause_at_50_requests(self, mock_uniform, mock_sleep):
        """Test that pause triggers at 50 request threshold."""
        mock_uniform.return_value = 15
        reset_request_counter()

        from src.scrapers.att import _request_counter
        _request_counter._count = 50

        _check_pause_logic()

        mock_sleep.assert_called_once()
        mock_uniform.assert_called()

    @patch('src.scrapers.att.time.sleep')
    @patch('src.scrapers.att.random.uniform')
    def test_pause_at_200_requests(self, mock_uniform, mock_sleep):
        """Test that longer pause triggers at 200 request threshold."""
        mock_uniform.return_value = 180
        reset_request_counter()

        from src.scrapers.att import _request_counter
        _request_counter._count = 200

        _check_pause_logic()

        mock_sleep.assert_called_once()

    @patch('src.scrapers.att.time.sleep')
    def test_no_pause_between_thresholds(self, mock_sleep):
        """Test that no pause occurs between thresholds."""
        reset_request_counter()

        from src.scrapers.att import _request_counter
        _request_counter._count = 25

        _check_pause_logic()

        mock_sleep.assert_not_called()


class TestATTErrorHandling:
    """Tests for AT&T error handling."""

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_sitemap_fetch_failure_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that sitemap fetch failure returns empty list."""
        mock_get.return_value = None

        urls = get_store_urls_from_sitemap(mock_session)

        assert urls == []

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_store_fetch_failure_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that store page fetch failure returns None."""
        mock_get.return_value = None

        store = extract_store_details(mock_session, 'https://www.att.com/stores/texas/dallas/12345')

        assert store is None

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_malformed_xml_returns_empty(self, mock_counter, mock_get, mock_session):
        """Test that malformed XML returns empty list."""
        response = Mock()
        response.content = b'<not valid xml'
        mock_get.return_value = response

        urls = get_store_urls_from_sitemap(mock_session)

        assert urls == []

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_missing_json_ld_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that missing JSON-LD returns None."""
        html = '<html><body>No JSON-LD here</body></html>'
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.att.com/stores/texas/dallas/12345')

        assert store is None

    @patch('src.scrapers.att.utils.get_with_retry')
    @patch('src.scrapers.att._request_counter')
    def test_wrong_json_ld_type_returns_none(self, mock_counter, mock_get, mock_session):
        """Test that wrong JSON-LD type returns None."""
        html = '''<html><head>
<script type="application/ld+json">{"@type": "Organization", "name": "AT&T"}</script>
</head></html>'''
        response = Mock()
        response.text = html
        mock_get.return_value = response

        store = extract_store_details(mock_session, 'https://www.att.com/stores/texas/dallas/12345')

        assert store is None
