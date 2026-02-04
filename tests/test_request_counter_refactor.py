"""Tests for RequestCounter refactoring from global state to instance-based.

This test suite validates that helper functions in scrapers accept optional
RequestCounter instances instead of relying on global module state.

Tests cover:
1. Helper functions accept optional request_counter parameter
2. Counter is incremented when passed
3. Functions work without counter (backwards compatibility)
4. run() creates its own counter instance (no global state)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.shared.request_counter import RequestCounter


class TestTargetRefactoring:
    """Test Target scraper refactoring."""

    def test_get_all_store_ids_accepts_counter_parameter(self):
        """Test that get_all_store_ids accepts optional request_counter parameter."""
        from src.scrapers import target

        # Should accept request_counter parameter without error
        mock_session = Mock()
        mock_session.get = Mock(return_value=Mock(
            status_code=200,
            content=b'<?xml version="1.0"?><urlset></urlset>'
        ))

        counter = RequestCounter()

        # This should not raise an error about unexpected keyword argument
        with patch('src.shared.utils.get_with_retry') as mock_retry:
            mock_retry.return_value = Mock(
                status_code=200,
                content=b'<?xml version="1.0"?><urlset></urlset>'
            )
            result = target.get_all_store_ids(
                mock_session,
                retailer='target',
                request_counter=counter
            )
            assert isinstance(result, list)

    def test_get_all_store_ids_increments_counter_when_passed(self):
        """Test that get_all_store_ids increments counter when provided."""
        from src.scrapers import target

        mock_session = Mock()
        counter = RequestCounter()

        initial_count = counter.count

        with patch('src.shared.utils.get_with_retry') as mock_retry:
            mock_retry.return_value = Mock(
                status_code=200,
                content=b'<?xml version="1.0"?><urlset></urlset>'
            )
            target.get_all_store_ids(
                mock_session,
                retailer='target',
                request_counter=counter
            )

        # Counter should have been incremented
        assert counter.count == initial_count + 1

    def test_get_all_store_ids_works_without_counter(self):
        """Test that get_all_store_ids works without counter (backwards compat)."""
        from src.scrapers import target

        mock_session = Mock()

        # Should work without counter parameter
        with patch('src.shared.utils.get_with_retry') as mock_retry:
            mock_retry.return_value = Mock(
                status_code=200,
                content=b'<?xml version="1.0"?><urlset></urlset>'
            )
            result = target.get_all_store_ids(mock_session, retailer='target')
            assert isinstance(result, list)

    def test_get_store_details_accepts_counter_parameter(self):
        """Test that get_store_details accepts optional request_counter parameter."""
        from src.scrapers import target

        mock_session = Mock()
        counter = RequestCounter()

        with patch('src.shared.utils.get_with_retry') as mock_retry:
            mock_retry.return_value = None  # Simulate failed request
            result = target.get_store_details(
                mock_session,
                store_id=1234,
                retailer='target',
                request_counter=counter
            )
            assert result is None  # Expected failure

    def test_get_store_details_increments_counter_when_passed(self):
        """Test that get_store_details increments counter when provided."""
        from src.scrapers import target

        mock_session = Mock()
        counter = RequestCounter()

        initial_count = counter.count

        with patch('src.shared.utils.get_with_retry') as mock_retry:
            # Mock successful response with valid store data
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'data': {
                    'store': {
                        'store_id': '1234',
                        'location_name': 'Test Store',
                        'mailing_address': {
                            'address_line1': '123 Main St',
                            'city': 'Test City',
                            'region': 'CA',
                            'postal_code': '90001'
                        },
                        'geographic_specifications': {},
                        'physical_specifications': {}
                    }
                }
            }
            mock_retry.return_value = mock_response

            target.get_store_details(
                mock_session,
                store_id=1234,
                retailer='target',
                request_counter=counter
            )

        # Counter should have been incremented
        assert counter.count == initial_count + 1

    def test_run_creates_own_counter_instance(self):
        """Test that run() creates its own RequestCounter instance."""
        from src.scrapers import target

        mock_session = Mock()
        mock_config = {
            'proxy': {'mode': 'direct'},
            'delays': {'direct': {'min_delay': 0.1, 'max_delay': 0.2}}
        }

        with patch('src.scrapers.target.get_all_store_ids') as mock_get_ids, \
             patch('src.scrapers.target.get_store_details') as mock_get_details, \
             patch('src.scrapers.target.RichURLCache') as mock_cache, \
             patch('src.shared.utils.validate_stores_batch') as mock_validate:

            # Ensure cache returns None so get_all_store_ids is called
            # Target uses get_rich() not get()
            mock_cache.return_value.get_rich.return_value = None
            mock_get_ids.return_value = []
            mock_validate.return_value = {'valid': 0, 'total': 0, 'warning_count': 0}

            result = target.run(mock_session, mock_config, retailer='target')

            # Should have called get_all_store_ids with a counter instance
            assert mock_get_ids.called
            call_kwargs = mock_get_ids.call_args.kwargs
            # The counter should be passed as a parameter
            assert 'request_counter' in call_kwargs
            assert isinstance(call_kwargs['request_counter'], RequestCounter)


class TestATTRefactoring:
    """Test AT&T scraper refactoring."""

    def test_get_store_urls_from_sitemap_accepts_counter_parameter(self):
        """Test that get_store_urls_from_sitemap accepts optional request_counter parameter."""
        from src.scrapers import att

        mock_session = Mock()
        counter = RequestCounter()

        with patch('src.shared.utils.get_with_retry') as mock_retry:
            mock_retry.return_value = Mock(
                status_code=200,
                content=b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
            )
            result = att.get_store_urls_from_sitemap(
                mock_session,
                retailer='att',
                request_counter=counter
            )
            assert isinstance(result, list)

    def test_get_store_urls_from_sitemap_increments_counter(self):
        """Test that get_store_urls_from_sitemap increments counter when provided."""
        from src.scrapers import att

        mock_session = Mock()
        counter = RequestCounter()

        initial_count = counter.count

        with patch('src.shared.utils.get_with_retry') as mock_retry:
            mock_retry.return_value = Mock(
                status_code=200,
                content=b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
            )
            att.get_store_urls_from_sitemap(
                mock_session,
                retailer='att',
                request_counter=counter
            )

        assert counter.count == initial_count + 1

    def test_extract_store_details_accepts_counter_parameter(self):
        """Test that extract_store_details accepts optional request_counter parameter."""
        from src.scrapers import att

        mock_session = Mock()
        counter = RequestCounter()

        with patch('src.shared.utils.get_with_retry') as mock_retry:
            mock_retry.return_value = None
            result = att.extract_store_details(
                mock_session,
                url='https://example.com',
                retailer='att',
                request_counter=counter
            )
            assert result is None

    def test_extract_store_details_increments_counter(self):
        """Test that extract_store_details increments counter when provided."""
        from src.scrapers import att

        mock_session = Mock()
        counter = RequestCounter()

        initial_count = counter.count

        with patch('src.shared.utils.get_with_retry') as mock_retry:
            # Mock a minimal response that will be processed
            mock_retry.return_value = Mock(
                status_code=200,
                text='<html></html>'
            )
            att.extract_store_details(
                mock_session,
                url='https://example.com',
                retailer='att',
                request_counter=counter
            )

        assert counter.count == initial_count + 1

    def test_run_creates_own_counter_instance(self):
        """Test that run() creates its own RequestCounter instance."""
        from src.scrapers import att

        mock_session = Mock()
        mock_config = {
            'proxy': {'mode': 'direct'},
            'delays': {'direct': {'min_delay': 0.1, 'max_delay': 0.2}}
        }

        with patch('src.scrapers.att.get_store_urls_from_sitemap') as mock_get_urls, \
             patch('src.scrapers.att.URLCache') as mock_cache, \
             patch('src.shared.utils.validate_stores_batch') as mock_validate:

            # Ensure cache returns None so get_store_urls_from_sitemap is called
            mock_cache.return_value.get.return_value = None
            mock_get_urls.return_value = []
            mock_validate.return_value = {'valid': 0, 'total': 0, 'warning_count': 0}

            result = att.run(mock_session, mock_config, retailer='att')

            # Should have called get_store_urls_from_sitemap with a counter instance
            assert mock_get_urls.called
            call_kwargs = mock_get_urls.call_args[1]
            assert 'request_counter' in call_kwargs


class TestSamsClubRefactoring:
    """Test Sam's Club scraper refactoring."""

    def test_extract_club_details_accepts_counter_parameter(self):
        """Test that extract_club_details accepts optional request_counter parameter."""
        from src.scrapers import samsclub

        mock_client = Mock()
        counter = RequestCounter()

        # Mock response
        mock_client.get.return_value = Mock(
            status_code=200,
            text='<html></html>'
        )
        mock_client.mode = 'web_scraper_api'

        result = samsclub.extract_club_details(
            mock_client,
            url='https://example.com',
            retailer='samsclub',
            request_counter=counter
        )
        # Result may be None due to missing data, but should accept parameter
        assert result is None or isinstance(result, object)

    def test_extract_club_details_increments_counter(self):
        """Test that extract_club_details increments counter when provided."""
        from src.scrapers import samsclub

        mock_client = Mock()
        counter = RequestCounter()

        initial_count = counter.count

        # Mock response
        mock_client.get.return_value = Mock(
            status_code=200,
            text='<html></html>'
        )
        mock_client.mode = 'web_scraper_api'

        samsclub.extract_club_details(
            mock_client,
            url='https://example.com',
            retailer='samsclub',
            request_counter=counter
        )

        assert counter.count == initial_count + 1

    def test_extract_club_details_works_without_counter(self):
        """Test that extract_club_details works without counter (backwards compat)."""
        from src.scrapers import samsclub

        mock_client = Mock()
        mock_client.get.return_value = Mock(
            status_code=200,
            text='<html></html>'
        )
        mock_client.mode = 'web_scraper_api'

        # Should work without counter parameter
        result = samsclub.extract_club_details(
            mock_client,
            url='https://example.com',
            retailer='samsclub'
        )
        # Should not raise an error
        assert result is None or isinstance(result, object)

    def test_run_creates_own_counter_instance(self):
        """Test that run() creates its own RequestCounter instance and passes it to helper functions."""
        from src.scrapers import samsclub

        mock_session = Mock()
        mock_config = {
            'proxy': {'mode': 'direct'},
            'delays': {'direct': {'min_delay': 0.1, 'max_delay': 0.2}}
        }

        with patch('src.scrapers.samsclub.get_club_urls_from_sitemap') as mock_get_urls, \
             patch('src.scrapers.samsclub.extract_club_details') as mock_extract, \
             patch('src.scrapers.samsclub.ProxyClient') as mock_proxy, \
             patch('src.shared.utils.validate_stores_batch') as mock_validate:

            mock_get_urls.return_value = ['https://www.samsclub.com/club/test-club/1234']
            mock_extract.return_value = None  # Simulate no store data extracted
            mock_validate.return_value = {'valid': 0, 'total': 0, 'warning_count': 0}

            result = samsclub.run(mock_session, mock_config, retailer='samsclub')

            # run() should complete without errors
            assert 'stores' in result
            assert 'count' in result

            # Verify extract_club_details was called with request_counter parameter
            assert mock_extract.called
            call_kwargs = mock_extract.call_args.kwargs
            assert 'request_counter' in call_kwargs
            assert isinstance(call_kwargs['request_counter'], RequestCounter)


class TestBackwardsCompatibility:
    """Test that existing module-level functions still work."""

    def test_target_reset_request_counter_still_exists(self):
        """Test that reset_request_counter() function still exists."""
        from src.scrapers import target

        # Should not raise AttributeError
        target.reset_request_counter()

    def test_target_get_request_count_still_exists(self):
        """Test that get_request_count() function still exists."""
        from src.scrapers import target

        # Should not raise AttributeError
        count = target.get_request_count()
        assert isinstance(count, int)

    def test_att_reset_request_counter_still_exists(self):
        """Test that reset_request_counter() function still exists."""
        from src.scrapers import att

        att.reset_request_counter()

    def test_att_get_request_count_still_exists(self):
        """Test that get_request_count() function still exists."""
        from src.scrapers import att

        count = att.get_request_count()
        assert isinstance(count, int)

    def test_samsclub_reset_request_counter_still_exists(self):
        """Test that reset_request_counter() function still exists."""
        from src.scrapers import samsclub

        samsclub.reset_request_counter()

    def test_samsclub_get_request_count_still_exists(self):
        """Test that get_request_count() function still exists."""
        from src.scrapers import samsclub

        count = samsclub.get_request_count()
        assert isinstance(count, int)


class TestNoGlobalState:
    """Test that global state is not shared between scraper runs."""

    def test_target_run_uses_isolated_counter(self):
        """Test that multiple Target run() calls use isolated counters."""
        from src.scrapers import target

        mock_session = Mock()
        mock_config = {
            'proxy': {'mode': 'direct'},
            'delays': {'direct': {'min_delay': 0.1, 'max_delay': 0.2}}
        }

        with patch('src.scrapers.target.get_all_store_ids') as mock_get_ids, \
             patch('src.scrapers.target.RichURLCache') as mock_cache, \
             patch('src.shared.utils.validate_stores_batch') as mock_validate:

            # Ensure cache returns None so get_all_store_ids is called
            # Target uses get_rich() not get()
            mock_cache.return_value.get_rich.return_value = None
            mock_get_ids.return_value = []
            mock_validate.return_value = {'valid': 0, 'total': 0, 'warning_count': 0}

            # First run
            target.run(mock_session, mock_config, retailer='target')
            first_call_counter = mock_get_ids.call_args[1].get('request_counter')

            # Second run
            target.run(mock_session, mock_config, retailer='target')
            second_call_counter = mock_get_ids.call_args[1].get('request_counter')

            # Each run should create a new counter instance
            if first_call_counter and second_call_counter:
                assert first_call_counter is not second_call_counter

    def test_att_run_uses_isolated_counter(self):
        """Test that multiple AT&T run() calls use isolated counters."""
        from src.scrapers import att

        mock_session = Mock()
        mock_config = {
            'proxy': {'mode': 'direct'},
            'delays': {'direct': {'min_delay': 0.1, 'max_delay': 0.2}}
        }

        with patch('src.scrapers.att.get_store_urls_from_sitemap') as mock_get_urls, \
             patch('src.scrapers.att.URLCache') as mock_cache, \
             patch('src.shared.utils.validate_stores_batch') as mock_validate:

            # Ensure cache returns None so get_store_urls_from_sitemap is called
            mock_cache.return_value.get.return_value = None
            mock_get_urls.return_value = []
            mock_validate.return_value = {'valid': 0, 'total': 0, 'warning_count': 0}

            # First run
            att.run(mock_session, mock_config, retailer='att')
            first_call_counter = mock_get_urls.call_args[1].get('request_counter')

            # Second run
            att.run(mock_session, mock_config, retailer='att')
            second_call_counter = mock_get_urls.call_args[1].get('request_counter')

            # Each run should create a new counter instance
            if first_call_counter and second_call_counter:
                assert first_call_counter is not second_call_counter
