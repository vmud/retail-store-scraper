"""Shared fixtures for scraper unit tests."""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile
import shutil

import requests


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = Mock(spec=requests.Session)
    return session


@pytest.fixture
def mock_session_with_errors():
    """Create a mock session that returns HTTP errors."""
    def _create(error_code: int = 429, error_after: int = 0):
        """
        Args:
            error_code: HTTP status code to return
            error_after: Number of successful requests before error
        """
        session = Mock(spec=requests.Session)
        call_count = [0]

        def mock_get(*args, **kwargs):
            call_count[0] += 1
            response = Mock(spec=requests.Response)
            if call_count[0] > error_after:
                response.status_code = error_code
                response.ok = False
                response.text = f"Error {error_code}"
            else:
                response.status_code = 200
                response.ok = True
                response.text = "<html></html>"
            return response

        session.get = mock_get
        return session
    return _create


@pytest.fixture
def mock_session_with_timeout():
    """Create a mock session that raises timeout errors."""
    session = Mock(spec=requests.Session)
    session.get.side_effect = requests.exceptions.Timeout("Connection timed out")
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


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for checkpoint tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_checkpoint_data(sample_store_data):
    """Sample checkpoint data for resume tests."""
    return {
        'completed_count': 2,
        'completed_ids': ['12345', '12346'],
        'stores': [
            sample_store_data,
            {**sample_store_data, 'store_id': '12346', 'name': 'Test Store 2'}
        ],
        'last_updated': '2025-01-19T12:00:00'
    }


@pytest.fixture
def mock_get_with_retry():
    """Patch utils.get_with_retry for controlled responses."""
    def _create(responses: list):
        """
        Args:
            responses: List of response objects to return in order
        """
        response_iter = iter(responses)

        def mock_func(*args, **kwargs):
            try:
                return next(response_iter)
            except StopIteration:
                return None

        return patch('src.shared.utils.get_with_retry', side_effect=mock_func)
    return _create


@pytest.fixture
def assert_run_result():
    """Helper to validate run() return structure."""
    def _assert(result: dict):
        assert isinstance(result, dict), "run() must return a dict"
        assert 'stores' in result, "Result must contain 'stores' key"
        assert 'count' in result, "Result must contain 'count' key"
        assert 'checkpoints_used' in result, "Result must contain 'checkpoints_used' key"
        assert isinstance(result['stores'], list), "'stores' must be a list"
        assert isinstance(result['count'], int), "'count' must be an int"
        assert isinstance(result['checkpoints_used'], bool), "'checkpoints_used' must be a bool"
        assert result['count'] == len(result['stores']), "count must match stores length"
    return _assert
