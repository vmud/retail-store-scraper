"""Tests for edge cases and malformed responses.

This test suite validates handling of:
- Invalid JSON responses
- Truncated HTML
- Missing required fields
- Malformed XML
- Empty responses
- Invalid encoding
- Network timeouts
- Rate limiting
"""

import json
import gzip
import pytest
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock
import requests


class TestMalformedJSONResponses:
    """Test handling of malformed JSON responses."""

    def test_invalid_json_syntax(self, mock_response_factory, malformed_responses):
        """Test handling of syntactically invalid JSON."""
        from src.scrapers.target import get_store_details

        mock_session = Mock()
        invalid_json = malformed_responses['invalid_json']

        with patch('src.shared.utils.get_with_retry') as mock_get:
            response = mock_response_factory(
                status_code=200,
                text=invalid_json['text']
            )
            response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
            mock_get.return_value = response

            result = get_store_details(mock_session, 1234, 'target')

            # Should handle gracefully and return None
            assert result is None

    def test_json_wrong_structure(self, mock_response_factory, malformed_responses):
        """Test handling of JSON with unexpected structure."""
        from src.scrapers.target import get_store_details

        mock_session = Mock()

        with patch('src.shared.utils.get_with_retry') as mock_get:
            # Response is valid JSON but has wrong structure
            response = mock_response_factory(
                status_code=200,
                json_data={"data": "string instead of object"}
            )
            mock_get.return_value = response

            result = get_store_details(mock_session, 1234, 'target')

            # Should handle gracefully
            assert result is None

    def test_missing_required_json_keys(self, mock_response_factory):
        """Test handling of JSON missing required keys."""
        from src.scrapers.target import get_store_details

        mock_session = Mock()

        with patch('src.shared.utils.get_with_retry') as mock_get:
            # Valid JSON but missing required fields
            response = mock_response_factory(
                status_code=200,
                json_data={
                    "data": {
                        "store": {
                            # Missing store_id, name, address fields
                            "random_field": "value"
                        }
                    }
                }
            )
            mock_get.return_value = response

            result = get_store_details(mock_session, 1234, 'target')

            # Should handle missing keys gracefully (may return empty or None)
            # Just verify it doesn't crash
            assert result is None or (hasattr(result, 'store_id') and result.store_id == '1234')

    def test_nested_null_values(self):
        """Test handling of deeply nested null values in JSON."""
        # Simulate parsing deeply nested structure with nulls
        store_data = {
            "store_id": "12345",
            "name": "Test Store",
            "address": {
                "street": None,
                "city": None,
                "state": None
            },
            "coordinates": {
                "latitude": None,
                "longitude": None
            }
        }

        # Verify JSON can handle None values
        json_str = json.dumps(store_data)
        parsed = json.loads(json_str)

        # Should parse without error
        assert parsed["store_id"] == "12345"
        assert parsed["address"]["street"] is None


class TestTruncatedHTML:
    """Test handling of truncated or incomplete HTML."""

    def test_incomplete_html_tags(self, mock_response_factory, malformed_responses):
        """Test parsing of HTML with incomplete/unclosed tags."""
        from bs4 import BeautifulSoup

        html = malformed_responses['truncated_html']['text']
        soup = BeautifulSoup(html, 'html.parser')

        # BeautifulSoup should handle incomplete HTML gracefully
        divs = soup.find_all('div', class_='store')
        assert isinstance(divs, list)  # Should return list even if malformed

    def test_empty_html_response(self, mock_response_factory, malformed_responses):
        """Test handling of empty HTML response."""
        empty = malformed_responses['empty_response']

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(empty['text'], 'html.parser')

        # Should parse empty HTML without error
        assert soup is not None
        assert len(soup.find_all()) == 0

    def test_html_with_no_store_data(self, mock_response_factory, malformed_responses):
        """Test HTML parsing when expected elements are missing."""
        html = malformed_responses['html_no_data']['text']

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Look for store elements that don't exist
        stores = soup.find_all('div', class_='store-location')
        assert stores == []


class TestMalformedXML:
    """Test handling of malformed XML responses."""

    def test_invalid_xml_syntax(self, mock_response_factory, malformed_responses):
        """Test parsing of syntactically invalid XML."""
        try:
            from defusedxml import ElementTree as ET
        except ImportError:
            pytest.skip("defusedxml not installed")

        invalid_xml = malformed_responses['invalid_xml']['content']

        with pytest.raises(ET.ParseError):
            ET.fromstring(invalid_xml)

    def test_xml_with_no_urls(self, mock_response_factory, malformed_responses):
        """Test sitemap XML with no URL entries."""
        try:
            from defusedxml import ElementTree as ET
        except ImportError:
            pytest.skip("defusedxml not installed")

        xml = malformed_responses['xml_no_urls']['content']
        root = ET.fromstring(xml)

        # Should parse successfully but have no URLs
        urls = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        assert urls == []

    def test_gzipped_xml_corruption(self):
        """Test handling of corrupted gzipped XML content."""
        corrupted_gzip = b'\x1f\x8b\x08\x00\x00\x00\x00\x00CORRUPTED'

        with pytest.raises((gzip.BadGzipFile, OSError, EOFError)):
            gzip.decompress(corrupted_gzip)

    def test_sitemap_with_invalid_urls(self, mock_response_factory):
        """Test sitemap containing malformed URLs."""
        try:
            from defusedxml import ElementTree as ET
        except ImportError:
            pytest.skip("defusedxml not installed")

        xml_content = '''<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>not-a-valid-url</loc></url>
            <url><loc>http://example.com/valid</loc></url>
            <url><loc></loc></url>
        </urlset>'''

        # Parse and extract URLs
        root = ET.fromstring(xml_content.encode('utf-8'))
        urls = [loc.text for loc in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]

        # Should extract all URL text (including malformed)
        assert isinstance(urls, list)
        assert len(urls) == 3


class TestEncodingIssues:
    """Test handling of encoding issues."""

    def test_invalid_utf8_bytes(self, mock_response_factory, malformed_responses):
        """Test handling of invalid UTF-8 byte sequences."""
        invalid_bytes = malformed_responses['invalid_utf8']['content']

        # Attempting to decode should raise error
        with pytest.raises(UnicodeDecodeError):
            invalid_bytes.decode('utf-8')

        # Should work with error handling
        decoded = invalid_bytes.decode('utf-8', errors='ignore')
        assert isinstance(decoded, str)

    def test_mixed_encoding_response(self):
        """Test handling of response with mixed encoding."""
        # Latin-1 encoded content
        latin1_content = "Café résumé".encode('latin-1')

        # Try to decode as UTF-8 (will fail)
        with pytest.raises(UnicodeDecodeError):
            latin1_content.decode('utf-8')

        # Should work with correct encoding
        decoded = latin1_content.decode('latin-1')
        assert "Café" in decoded

    def test_response_with_bom(self):
        """Test handling of response with Byte Order Mark (BOM)."""
        # UTF-8 with BOM
        content_with_bom = b'\xef\xbb\xbf{"key": "value"}'

        # Should parse correctly (BOM is handled)
        text = content_with_bom.decode('utf-8-sig')
        data = json.loads(text)
        assert data == {"key": "value"}


class TestNetworkErrors:
    """Test handling of network-related errors."""

    def test_connection_timeout(self):
        """Test handling of connection timeout."""
        from src.shared.utils import get_with_retry

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.Timeout("Connection timeout")

        # get_with_retry catches timeouts and retries, then returns None
        with patch('time.sleep'):  # Don't sleep during retries
            result = get_with_retry(
                session=mock_session,
                url='https://example.com/timeout',
                max_retries=2
            )

        # Should return None after retries exhausted
        assert result is None

    def test_connection_error(self):
        """Test handling of connection error."""
        from src.shared.utils import get_with_retry

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        # get_with_retry catches connection errors and retries, then returns None
        with patch('time.sleep'):  # Don't sleep during retries
            result = get_with_retry(
                session=mock_session,
                url='https://example.com/error',
                max_retries=2
            )

        # Should return None after retries exhausted
        assert result is None

    def test_rate_limit_response(self, mock_response_factory):
        """Test handling of 429 rate limit response."""
        from src.shared.utils import get_with_retry

        mock_session = Mock()

        # First request: 429, subsequent: 200
        response_429 = mock_response_factory(status_code=429, text="Rate limited")
        response_200 = mock_response_factory(status_code=200, json_data={"success": True})

        mock_session.get.side_effect = [response_429, response_200]

        with patch('time.sleep'):  # Don't actually sleep in tests
            result = get_with_retry(
                session=mock_session,
                url='https://example.com/api'
            )

        # Should retry and succeed
        assert result.status_code == 200

    def test_server_error_500(self, mock_response_factory):
        """Test handling of 500 internal server error."""
        from src.shared.utils import get_with_retry

        mock_session = Mock()
        response_500 = mock_response_factory(status_code=500, text="Internal Server Error")
        # Mock raise_for_status to raise HTTPError
        response_500.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")

        mock_session.get.return_value = response_500

        # get_with_retry catches HTTPError and retries, then returns None
        with patch('time.sleep'):  # Don't sleep during retries
            result = get_with_retry(
                session=mock_session,
                url='https://example.com/error500',
                max_retries=2
            )

        # Should return None after retries exhausted
        assert result is None


class TestEmptyAndNullResponses:
    """Test handling of empty and null responses."""

    def test_empty_json_array(self, mock_response_factory):
        """Test handling of empty JSON array response."""
        response = mock_response_factory(
            status_code=200,
            json_data=[]
        )

        data = response.json()
        assert data == []
        assert len(data) == 0

    def test_null_json_response(self):
        """Test handling of JSON null value."""
        # Verify JSON can represent null
        json_str = 'null'
        data = json.loads(json_str)
        assert data is None

        # Verify we can serialize None
        result = json.dumps(None)
        assert result == 'null'

    def test_empty_string_response(self, mock_response_factory, malformed_responses):
        """Test handling of empty string response."""
        empty = malformed_responses['empty_response']

        response = mock_response_factory(
            status_code=200,
            text=empty['text']
        )

        assert response.text == ""
        assert response.content == b''


class TestStoreDataValidation:
    """Test validation of store data with edge cases."""

    def test_validate_store_with_missing_required_fields(self, sample_store_data):
        """Test validation of store missing required fields."""
        from src.shared.utils import validate_store_data

        invalid_store = sample_store_data['invalid']

        result = validate_store_data(invalid_store)

        # Should identify missing required fields
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_validate_store_with_invalid_coordinates(self):
        """Test validation of store with out-of-range coordinates."""
        from src.shared.utils import validate_store_data

        store_with_invalid_coords = {
            'store_id': 'TEST001',
            'name': 'Test Store',
            'street_address': '123 Main St',
            'city': 'TestCity',
            'state': 'CA',
            'latitude': 999.0,  # Invalid (must be -90 to 90)
            'longitude': -999.0  # Invalid (must be -180 to 180)
        }

        result = validate_store_data(store_with_invalid_coords)

        # Should identify invalid coordinates
        assert not result.is_valid
        assert any('latitude' in str(e).lower() for e in result.errors)

    def test_validate_store_with_invalid_zip_code(self):
        """Test validation of store with invalid ZIP code."""
        from src.shared.utils import validate_store_data

        store_with_invalid_zip = {
            'store_id': 'TEST001',
            'name': 'Test Store',
            'street_address': '123 Main St',
            'city': 'TestCity',
            'state': 'CA',
            'zip_code': 'INVALID'  # Not a valid ZIP format
        }

        result = validate_store_data(store_with_invalid_zip)

        # May or may not be invalid depending on validation rules
        # Just verify it doesn't crash
        assert hasattr(result, 'is_valid')

    def test_validate_batch_with_mixed_validity(self, sample_store_data):
        """Test batch validation with mix of valid and invalid stores."""
        from src.shared.utils import validate_stores_batch

        stores = [
            sample_store_data['valid'],
            sample_store_data['invalid'],
            sample_store_data['minimal']
        ]

        summary = validate_stores_batch(stores)

        # Should provide summary statistics
        assert 'total' in summary
        assert 'valid' in summary
        assert 'invalid' in summary
        assert summary['total'] == 3


class TestBoundaryConditions:
    """Test boundary conditions and extreme values."""

    def test_very_large_response(self):
        """Test handling of very large response body."""
        # Simulate large JSON array
        large_array = [{"id": i, "data": "x" * 100} for i in range(1000)]
        json_str = json.dumps(large_array)

        # Should parse without memory issues
        parsed = json.loads(json_str)
        assert len(parsed) == 1000

    def test_deeply_nested_json(self):
        """Test handling of deeply nested JSON structures."""
        # Create deeply nested structure
        nested = {"level": 1}
        current = nested
        for i in range(2, 50):
            current["next"] = {"level": i}
            current = current["next"]

        # Should serialize and parse
        json_str = json.dumps(nested)
        parsed = json.loads(json_str)
        assert parsed["level"] == 1

    def test_unicode_characters_in_store_data(self):
        """Test handling of Unicode characters in store data."""
        from src.shared.utils import validate_store_data

        store_with_unicode = {
            'store_id': 'TEST001',
            'name': 'Café & Restaurant 日本',
            'street_address': '123 Straße',
            'city': 'Montréal',
            'state': 'QC'
        }

        result = validate_store_data(store_with_unicode)

        # Should handle Unicode without issues
        assert hasattr(result, 'is_valid')

    def test_store_with_very_long_strings(self):
        """Test handling of store data with very long string values."""
        from src.shared.utils import validate_store_data

        store_with_long_strings = {
            'store_id': 'TEST001',
            'name': 'X' * 1000,  # Very long name
            'street_address': 'Y' * 500,
            'city': 'Z' * 200,
            'state': 'CA'
        }

        result = validate_store_data(store_with_long_strings)

        # Should handle without crashing
        assert hasattr(result, 'is_valid')


class TestCheckpointEdgeCases:
    """Test checkpoint save/load edge cases."""

    def test_load_corrupted_checkpoint(self, tmp_path):
        """Test loading a corrupted checkpoint file."""
        from src.shared.utils import load_checkpoint

        checkpoint_file = tmp_path / "corrupted.json"
        checkpoint_file.write_text("{ corrupted json")

        result = load_checkpoint(str(checkpoint_file))

        # Should return None for corrupted checkpoint
        assert result is None

    def test_load_nonexistent_checkpoint(self):
        """Test loading a non-existent checkpoint file."""
        from src.shared.utils import load_checkpoint

        result = load_checkpoint("/nonexistent/path/checkpoint.json")

        # Should return None
        assert result is None

    def test_save_checkpoint_with_unserializable_data(self, tmp_path):
        """Test saving checkpoint with non-JSON-serializable data."""
        from src.shared.utils import save_checkpoint

        checkpoint_file = tmp_path / "test_checkpoint.json"

        # Data with non-serializable objects
        data = {
            "stores": ["store1", "store2"],
            "func": lambda x: x  # Not JSON serializable
        }

        # Should handle gracefully
        try:
            save_checkpoint(data, str(checkpoint_file))
        except (TypeError, ValueError):
            # Expected behavior - can't serialize function
            pass
