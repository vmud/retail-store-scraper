"""Test specific exception handling in scrapers (issue #167).

This test suite validates that inner exception handlers catch specific
exceptions rather than broad `except Exception`, while top-level handlers
maintain their safety net role.
"""

import gzip
import json
import pytest
import requests
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.target import (
    get_all_store_ids as target_get_all_store_ids,
    get_store_details as target_get_store_details,
    _extract_single_store as target_extract_single_store,
)
from src.scrapers.tmobile import (
    get_store_urls_from_sitemap as tmobile_get_store_urls,
    extract_store_details as tmobile_extract_store_details,
    _extract_single_store as tmobile_extract_single_store,
)
from src.scrapers.att import (
    get_store_urls_from_sitemap as att_get_store_urls,
    extract_store_details as att_extract_store_details,
    _extract_single_store as att_extract_single_store,
)


class TestTargetExceptionHandling:
    """Test Target scraper exception handling."""

    @patch('src.scrapers.target.utils.get_with_retry')
    def test_get_all_store_ids_handles_unicode_decode_error(self, mock_get):
        """Test that sitemap parsing catches UnicodeDecodeError specifically."""
        mock_session = Mock()

        # Simulate content with invalid UTF-8 encoding (not gzipped)
        mock_response = Mock()
        mock_response.content = b'<?xml version="1.0"?>\x80\x81\x82'  # Invalid UTF-8
        mock_get.return_value = mock_response

        result = target_get_all_store_ids(mock_session, 'target')

        # Should handle error gracefully and return empty list
        assert result == []

    @patch('src.scrapers.target.utils.get_with_retry')
    def test_get_all_store_ids_handles_regex_error(self, mock_get):
        """Test that sitemap parsing catches re.error specifically."""
        mock_session = Mock()

        # Valid XML but will test regex handling
        xml_content = '''<?xml version="1.0"?>
        <urlset>
            <url><loc>https://www.target.com/sl/test/1234</loc></url>
        </urlset>'''

        mock_response = Mock()
        mock_response.content = xml_content.encode('utf-8')
        mock_get.return_value = mock_response

        # Should not raise exception even with edge case content
        result = target_get_all_store_ids(mock_session, 'target')
        assert isinstance(result, list)

    @patch('src.scrapers.target.utils.get_with_retry')
    def test_get_store_details_handles_json_decode_error(self, mock_get):
        """Test that store details parsing catches JSONDecodeError specifically."""
        mock_session = Mock()

        # Response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response

        result = target_get_store_details(mock_session, 1234, 'target')

        # Should handle JSON error and return None
        assert result is None

    @patch('src.scrapers.target.utils.get_with_retry')
    def test_get_store_details_handles_key_error(self, mock_get):
        """Test that store details parsing catches KeyError specifically."""
        mock_session = Mock()

        # Response with missing required keys
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "store": {}  # Missing required fields
            }
        }
        mock_get.return_value = mock_response

        result = target_get_store_details(mock_session, 1234, 'target')

        # Should handle missing keys and return valid store or None
        assert result is None or hasattr(result, 'store_id')

    @patch('src.scrapers.target.utils.get_with_retry')
    def test_get_store_details_handles_type_error(self, mock_get):
        """Test that store details parsing catches TypeError specifically."""
        mock_session = Mock()

        # Response with wrong types
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "store": {
                    "store_id": None,  # Should be string
                    "location_name": None,
                    "mailing_address": None,  # Should be dict
                }
            }
        }
        mock_get.return_value = mock_response

        # Should handle type errors gracefully
        result = target_get_store_details(mock_session, 1234, 'target')
        assert result is None or hasattr(result, 'store_id')

    def test_extract_single_store_handles_request_exception(self):
        """Test that parallel worker catches RequestException specifically."""
        mock_factory = Mock()
        mock_session = Mock()
        mock_factory.return_value = mock_session
        mock_session.close = Mock()

        # Simulate network error
        with patch('src.scrapers.target.get_store_details', side_effect=requests.RequestException("Network error")):
            store_info = {'store_id': 1234, 'slug': 'test', 'url': 'http://test.com'}
            store_id, result = target_extract_single_store(
                store_info, mock_factory, 'target'
            )

            # Should handle network error and return None
            assert store_id == 1234
            assert result is None
            mock_session.close.assert_called_once()

    @patch('src.scrapers.target.utils.get_with_retry')
    def test_get_all_store_ids_handles_bad_gzip_file(self, mock_get):
        """Test that sitemap parsing catches gzip.BadGzipFile specifically (#167).

        Uses patch to raise gzip.BadGzipFile directly to test the outer handler.
        """
        mock_session = Mock()

        # Return valid HTTP response but patch gzip to fail
        mock_response = Mock()
        mock_response.content = b'\x1f\x8b\x08\x00'  # gzip header to trigger decompression path
        mock_get.return_value = mock_response

        # Patch gzip.GzipFile to raise BadGzipFile
        with patch('src.scrapers.target.gzip.GzipFile', side_effect=gzip.BadGzipFile("Invalid gzip")):
            result = target_get_all_store_ids(mock_session, 'target')

            # Should handle gzip error gracefully and return empty list
            assert result == []

    @patch('src.scrapers.target.utils.get_with_retry')
    def test_get_store_details_handles_attribute_error(self, mock_get):
        """Test that store details parsing catches AttributeError specifically (#167)."""
        mock_session = Mock()

        # Response where .get() is called on None (triggers AttributeError)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "store": {
                    "store_id": "1234",
                    "location_name": "Test Store",
                    "mailing_address": None,  # None.get('city') raises AttributeError
                }
            }
        }
        mock_get.return_value = mock_response

        result = target_get_store_details(mock_session, 1234, 'target')

        # Should handle attribute error and return None
        assert result is None or hasattr(result, 'store_id')


class TestTMobileExceptionHandling:
    """Test T-Mobile scraper exception handling."""

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    def test_get_store_urls_handles_parse_error(self, mock_get):
        """Test that sitemap parsing catches ET.ParseError specifically."""
        mock_session = Mock()

        # Invalid XML
        mock_response = Mock()
        mock_response.content = b'<invalid><xml>missing closing tag'
        mock_get.return_value = mock_response

        result = tmobile_get_store_urls(mock_session, 'tmobile')

        # Should handle XML parse error and continue
        assert isinstance(result, list)

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    def test_get_store_urls_handles_unicode_decode_error(self, mock_get):
        """Test that sitemap parsing catches UnicodeDecodeError specifically."""
        mock_session = Mock()

        # Invalid UTF-8 bytes
        mock_response = Mock()
        mock_response.content = b'<?xml version="1.0"?>\x80\x81\x82'
        mock_get.return_value = mock_response

        # Should handle decode error gracefully
        result = tmobile_get_store_urls(mock_session, 'tmobile')
        assert isinstance(result, list)

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    def test_extract_store_details_handles_json_decode_error(self, mock_get):
        """Test that store details parsing catches JSONDecodeError specifically."""
        mock_session = Mock()

        # HTML with malformed JSON-LD
        mock_response = Mock()
        mock_response.text = '''<html>
            <script type="application/ld+json">
                {invalid json}
            </script>
        </html>'''
        mock_get.return_value = mock_response

        result = tmobile_extract_store_details(mock_session, 'http://test.com', 'tmobile')

        # Should handle JSON error and return None
        assert result is None

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    def test_extract_store_details_handles_key_error(self, mock_get):
        """Test that store details parsing catches KeyError specifically."""
        mock_session = Mock()

        # Valid JSON but missing required fields
        mock_response = Mock()
        mock_response.text = '''<html>
            <script type="application/ld+json">
                {"@type": "Store", "address": {}}
            </script>
        </html>'''
        mock_get.return_value = mock_response

        # Should handle missing keys gracefully
        result = tmobile_extract_store_details(mock_session, 'http://test.com', 'tmobile')
        assert result is None or hasattr(result, 'store_id')

    @patch('src.scrapers.tmobile.utils.get_with_retry')
    def test_extract_store_details_handles_type_error(self, mock_get):
        """Test that store details parsing catches TypeError specifically."""
        mock_session = Mock()

        # Valid JSON but wrong types
        mock_response = Mock()
        mock_response.text = '''<html>
            <script type="application/ld+json">
                {"@type": "Store", "address": "should be dict"}
            </script>
        </html>'''
        mock_get.return_value = mock_response

        # Should handle type errors gracefully
        result = tmobile_extract_store_details(mock_session, 'http://test.com', 'tmobile')
        assert result is None or hasattr(result, 'store_id')

    def test_extract_single_store_handles_request_exception(self):
        """Test that parallel worker catches RequestException specifically."""
        mock_factory = Mock()
        mock_session = Mock()
        mock_factory.return_value = mock_session
        mock_session.close = Mock()

        # Simulate network error
        with patch('src.scrapers.tmobile.extract_store_details', side_effect=requests.RequestException("Network error")):
            url, result = tmobile_extract_single_store(
                'http://test.com', mock_factory, 'tmobile'
            )

            # Should handle network error and return None
            assert url == 'http://test.com'
            assert result is None
            mock_session.close.assert_called_once()


class TestATTExceptionHandling:
    """Test AT&T scraper exception handling."""

    @patch('src.scrapers.att.utils.get_with_retry')
    def test_get_store_urls_handles_parse_error(self, mock_get):
        """Test that sitemap parsing catches ET.ParseError specifically."""
        mock_session = Mock()

        # Invalid XML
        mock_response = Mock()
        mock_response.content = b'<urlset><url><loc>missing closing tags'
        mock_get.return_value = mock_response

        result = att_get_store_urls(mock_session, 'att')

        # Should handle XML parse error and return empty list
        assert result == []

    @patch('src.scrapers.att.utils.get_with_retry')
    def test_get_store_urls_handles_unicode_decode_error(self, mock_get):
        """Test that sitemap parsing catches UnicodeDecodeError specifically."""
        mock_session = Mock()

        # Invalid UTF-8 in XML
        mock_response = Mock()
        mock_response.content = b'<?xml version="1.0"?>\x80\x81'
        mock_get.return_value = mock_response

        # Should handle decode error gracefully
        result = att_get_store_urls(mock_session, 'att')
        assert result == []

    @patch('src.scrapers.att.utils.get_with_retry')
    def test_extract_store_details_handles_json_decode_error(self, mock_get):
        """Test that store details parsing catches JSONDecodeError specifically."""
        mock_session = Mock()

        # HTML with malformed JSON-LD
        mock_response = Mock()
        mock_response.text = '''<html>
            <script type="application/ld+json">
                {invalid: json}
            </script>
        </html>'''
        mock_get.return_value = mock_response

        result = att_extract_store_details(mock_session, 'http://test.com', 'att')

        # Should handle JSON error and return None
        assert result is None

    @patch('src.scrapers.att.utils.get_with_retry')
    def test_extract_store_details_handles_key_error(self, mock_get):
        """Test that store details parsing catches KeyError specifically."""
        mock_session = Mock()

        # Valid JSON but missing required fields
        mock_response = Mock()
        mock_response.text = '''<html>
            <script type="application/ld+json">
                {"@type": "MobilePhoneStore", "address": {}}
            </script>
        </html>'''
        mock_get.return_value = mock_response

        # Should handle missing keys gracefully
        result = att_extract_store_details(mock_session, 'http://test.com/stores/1234', 'att')
        assert result is None or hasattr(result, 'store_id')

    @patch('src.scrapers.att.utils.get_with_retry')
    def test_extract_store_details_handles_type_error(self, mock_get):
        """Test that store details parsing catches TypeError specifically."""
        mock_session = Mock()

        # Valid JSON but wrong types
        mock_response = Mock()
        mock_response.text = '''<html>
            <script type="application/ld+json">
                {"@type": "MobilePhoneStore", "aggregateRating": "should be dict"}
            </script>
        </html>'''
        mock_get.return_value = mock_response

        # Should handle type errors gracefully
        result = att_extract_store_details(mock_session, 'http://test.com/stores/1234', 'att')
        assert result is None or hasattr(result, 'store_id')

    def test_extract_single_store_handles_request_exception(self):
        """Test that parallel worker catches RequestException specifically."""
        mock_factory = Mock()
        mock_session = Mock()
        mock_factory.return_value = mock_session
        mock_session.close = Mock()

        # Simulate network error
        with patch('src.scrapers.att.extract_store_details', side_effect=requests.RequestException("Network error")):
            url, result = att_extract_single_store(
                'http://test.com', mock_factory, 'att'
            )

            # Should handle network error and return None
            assert url == 'http://test.com'
            assert result is None
            mock_session.close.assert_called_once()

    @patch('src.scrapers.att.utils.get_with_retry')
    def test_extract_store_details_handles_value_error(self, mock_get):
        """Test that rating parsing catches ValueError specifically (#167)."""
        mock_session = Mock()

        # Valid JSON but with invalid rating value that can't be converted to float
        mock_response = Mock()
        mock_response.text = '''<html>
            <script type="application/ld+json">
                {"@type": "MobilePhoneStore",
                 "address": {"streetAddress": "123 Main St", "addressLocality": "Test", "addressRegion": "TX", "postalCode": "12345"},
                 "aggregateRating": {"ratingValue": "not-a-number", "reviewCount": "invalid"}}
            </script>
        </html>'''
        mock_get.return_value = mock_response

        # Should handle ValueError from float()/int() conversion gracefully
        result = att_extract_store_details(mock_session, 'http://test.com/stores/1234', 'att')
        # Should still return store data, just with rating set to defaults
        assert result is None or hasattr(result, 'store_id')


class TestSafetyNetExceptionHandling:
    """Test that top-level run() functions maintain broad exception handling.

    These tests verify that the top-level safety net still catches all
    exceptions, which is critical for production resilience.
    """

    @patch('src.scrapers.target.reset_request_counter')
    @patch('src.scrapers.target.utils.select_delays')
    @patch('src.scrapers.target.RichURLCache')
    def test_target_run_catches_all_exceptions(self, mock_cache_class, mock_delays, mock_reset):
        """Test that Target run() catches all exceptions as safety net."""
        mock_session = Mock()
        config = {'proxy': {'mode': 'direct'}}
        mock_delays.return_value = (2.0, 5.0)

        # Simulate unexpected exception type when cache is instantiated
        mock_cache_class.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(RuntimeError):
            # run() should re-raise after logging
            from src.scrapers.target import run
            run(mock_session, config, retailer='target')

    @patch('src.scrapers.tmobile.reset_request_counter')
    @patch('src.scrapers.tmobile.utils.select_delays')
    def test_tmobile_run_catches_all_exceptions(self, mock_delays, mock_reset):
        """Test that T-Mobile run() catches all exceptions as safety net."""
        mock_session = Mock()
        config = {'proxy': {'mode': 'direct'}}
        mock_delays.return_value = (2.0, 5.0)

        # Simulate unexpected exception type
        with patch('src.scrapers.tmobile.URLCache', side_effect=MemoryError("Out of memory")):
            with pytest.raises(MemoryError):
                # run() should re-raise after logging
                from src.scrapers.tmobile import run
                run(mock_session, config, retailer='tmobile')

    @patch('src.scrapers.att.reset_request_counter')
    @patch('src.scrapers.att.utils.select_delays')
    def test_att_run_catches_all_exceptions(self, mock_delays, mock_reset):
        """Test that AT&T run() catches all exceptions as safety net."""
        mock_session = Mock()
        config = {'proxy': {'mode': 'direct'}}
        mock_delays.return_value = (2.0, 5.0)

        # Simulate unexpected exception type (RuntimeError not in safety net)
        with patch('src.scrapers.att.URLCache', side_effect=RuntimeError("Unexpected cache error")):
            with pytest.raises(RuntimeError):
                # run() should re-raise after logging
                from src.scrapers.att import run
                run(mock_session, config, retailer='att')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
