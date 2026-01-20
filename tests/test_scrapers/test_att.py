"""Unit tests for AT&T scraper."""

import pytest
from unittest.mock import Mock, patch

from src.scrapers.att import (
    ATTStore,
    _extract_store_type_and_dealer,
    get_store_urls_from_sitemap,
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
