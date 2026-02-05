"""Pytest configuration and fixtures for scraper tests"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_config_data():
    """Sample configuration data for testing"""
    return {
        'retailers': {
            'verizon': {
                'name': 'Verizon',
                'enabled': True,
                'base_url': 'https://www.verizon.com',
                'discovery_method': 'html_crawl',
                'min_delay': 1.0,
                'max_delay': 3.0,
                'timeout': 30,
                'checkpoint_interval': 50
            },
            'att': {
                'name': 'AT&T',
                'enabled': True,
                'base_url': 'https://www.att.com',
                'discovery_method': 'sitemap',
                'min_delay': 1.0,
                'max_delay': 3.0,
                'timeout': 30,
                'checkpoint_interval': 50
            }
        }
    }


@pytest.fixture
def mock_response_factory():
    """Factory for creating mock HTTP responses with various scenarios.

    Usage:
        response = mock_response_factory(status_code=200, json_data={"key": "value"})
        response = mock_response_factory(status_code=404, text="Not Found")
        response = mock_response_factory(status_code=500, raise_error=requests.HTTPError())
    """
    def _create_response(
        status_code: int = 200,
        text: str = "",
        json_data: Optional[dict] = None,
        content: Optional[bytes] = None,
        headers: Optional[dict] = None,
        raise_error: Optional[Exception] = None
    ):
        """Create a mock response object.

        Args:
            status_code: HTTP status code
            text: Response text
            json_data: JSON response data (dict)
            content: Raw response content (bytes)
            headers: Response headers
            raise_error: Exception to raise when accessed

        Returns:
            Mock response object
        """
        response = Mock()
        response.status_code = status_code
        response.text = text
        response.headers = headers or {}

        if content is not None:
            response.content = content
        else:
            response.content = text.encode('utf-8') if text else b''

        if json_data is not None:
            response.json.return_value = json_data
        else:
            response.json.side_effect = ValueError("No JSON data")

        if raise_error:
            response.raise_for_status.side_effect = raise_error
        else:
            response.raise_for_status.return_value = None

        return response

    return _create_response


@pytest.fixture
def sample_store_data():
    """Common test data for store objects with various completeness levels.

    Returns:
        Dict with 'valid', 'minimal', 'invalid', and 'partial' store examples
    """
    return {
        'valid': {
            'store_id': 'TEST001',
            'name': 'Test Store',
            'street_address': '123 Main St',
            'city': 'TestCity',
            'state': 'CA',
            'zip_code': '90210',
            'latitude': 34.0522,
            'longitude': -118.2437,
            'phone': '555-1234',
            'url': 'https://example.com/store/TEST001',
            'hours': 'Mon-Fri 9am-5pm'
        },
        'minimal': {
            'store_id': 'MIN001',
            'name': 'Minimal Store',
            'street_address': '456 Oak Ave',
            'city': 'MinCity',
            'state': 'NY'
        },
        'invalid': {
            'store_id': 'INV001',
            'name': 'Invalid Store',
            # Missing required fields: street_address, city, state
            'zip_code': '99999',
            'phone': 'invalid-phone'
        },
        'partial': {
            'store_id': 'PART001',
            'name': 'Partial Store',
            'street_address': '789 Elm St',
            'city': 'PartCity',
            'state': 'TX',
            'zip_code': '12345',
            # Missing coordinates (recommended but not required)
            'latitude': None,
            'longitude': None
        }
    }


@pytest.fixture
def malformed_responses():
    """Collection of malformed response examples for edge case testing.

    Returns:
        Dict with various malformed response scenarios
    """
    return {
        'invalid_json': {
            'text': '{"incomplete": "json"',
            'content': b'{"incomplete": "json"'
        },
        'truncated_html': {
            'text': '<html><body><div class="store">Incomplete',
            'content': b'<html><body><div class="store">Incomplete'
        },
        'invalid_xml': {
            'text': '<?xml version="1.0"?><root><unclosed>',
            'content': b'<?xml version="1.0"?><root><unclosed>'
        },
        'empty_response': {
            'text': '',
            'content': b''
        },
        'invalid_utf8': {
            'text': 'Cannot decode',
            'content': b'\x80\x81\x82\x83\x84'  # Invalid UTF-8
        },
        'json_wrong_structure': {
            'text': '{"data": "not an object"}',
            'content': b'{"data": "not an object"}'
        },
        'html_no_data': {
            'text': '<html><body><p>No store data here</p></body></html>',
            'content': b'<html><body><p>No store data here</p></body></html>'
        },
        'xml_no_urls': {
            'text': '<?xml version="1.0"?><urlset></urlset>',
            'content': b'<?xml version="1.0"?><urlset></urlset>'
        }
    }


@pytest.fixture
def mock_url_cache():
    """Create a properly configured mock URLCache.

    Returns a Mock that behaves like a real URLCache:
    - get() returns None (cache miss)
    - set() accepts a list
    - retailer attribute for logging
    """
    cache = Mock()
    cache.retailer = 'test-retailer'
    cache.get.return_value = None  # Default: cache miss
    cache.set.return_value = None
    return cache


@pytest.fixture
def mock_rich_url_cache():
    """Create a properly configured mock RichURLCache.

    Returns a Mock that behaves like a real RichURLCache:
    - get_rich() returns None (cache miss)
    - set_rich() accepts a list
    - retailer attribute for logging
    - Properly configured for isinstance() checks
    """
    from src.shared.cache import RichURLCache
    cache = Mock(spec=RichURLCache)
    cache.retailer = 'test-retailer'
    cache.get_rich.return_value = None  # Default: cache miss
    cache.set_rich.return_value = None
    return cache
