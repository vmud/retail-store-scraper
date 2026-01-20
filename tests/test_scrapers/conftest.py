"""Shared fixtures for scraper unit tests."""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

import requests


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = Mock(spec=requests.Session)
    return session


@pytest.fixture
def mock_response():
    """Factory for creating mock HTTP responses."""
    def _create(
        status_code: int = 200,
        text: str = '',
        content: bytes = None,
        json_data: dict = None,
        headers: dict = None,
        url: str = 'https://example.com'
    ):
        response = Mock(spec=requests.Response)
        response.status_code = status_code
        response.text = text
        response.content = content if content is not None else text.encode('utf-8')
        response.ok = 200 <= status_code < 400
        response.url = url
        response.headers = headers or {}

        if json_data is not None:
            response.json.return_value = json_data
        else:
            response.json.side_effect = ValueError("No JSON data")

        return response
    return _create


@pytest.fixture
def sample_retailer_config():
    """Sample retailer config for tests."""
    return {
        'name': 'TestRetailer',
        'enabled': True,
        'base_url': 'https://example.com',
        'min_delay': 0,
        'max_delay': 0,
        'timeout': 30,
        'checkpoint_interval': 50,
    }


@pytest.fixture
def fixtures_dir():
    """Get the path to the fixtures directory."""
    return Path(__file__).parent / 'fixtures'


@pytest.fixture
def sample_store_data():
    """Sample store data matching expected scraper output."""
    return {
        'store_id': '12345',
        'name': 'Test Store',
        'street_address': '123 Main St',
        'city': 'Test City',
        'state': 'CA',
        'postal_code': '90210',
        'country': 'US',
        'latitude': 34.0522,
        'longitude': -118.2437,
        'phone': '(555) 123-4567',
        'url': 'https://example.com/store/12345',
        'scraped_at': '2025-01-19T12:00:00',
    }


@pytest.fixture
def sample_sitemap_xml():
    """Sample sitemap XML for testing sitemap parsers."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/stores/store-1</loc>
        <lastmod>2025-01-19</lastmod>
    </url>
    <url>
        <loc>https://example.com/stores/store-2</loc>
        <lastmod>2025-01-18</lastmod>
    </url>
    <url>
        <loc>https://example.com/stores/store-3</loc>
        <lastmod>2025-01-17</lastmod>
    </url>
</urlset>'''


@pytest.fixture
def sample_sitemap_index_xml():
    """Sample sitemap index XML for testing index parsers."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://example.com/sitemap-stores-1.xml</loc>
        <lastmod>2025-01-19</lastmod>
    </sitemap>
    <sitemap>
        <loc>https://example.com/sitemap-stores-2.xml</loc>
        <lastmod>2025-01-18</lastmod>
    </sitemap>
</sitemapindex>'''
