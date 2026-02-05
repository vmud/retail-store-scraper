"""Tests for get_with_retry functionality."""
import logging
import pytest
from unittest.mock import Mock, patch
import requests

from src.shared.utils import get_with_retry


class TestGetWithRetry403Handling:
    """Tests for 403 error handling in get_with_retry (#144)."""

    def test_403_uses_exponential_backoff_not_fixed_5min(self):
        """403 errors should use exponential backoff starting at 30s, not fixed 5 minutes."""
        session = Mock(spec=requests.Session)
        session.headers = {}

        # Create mock responses: 403, 403, then 200
        mock_responses = [
            Mock(status_code=403),
            Mock(status_code=403),
            Mock(status_code=200),
        ]
        session.get.side_effect = mock_responses

        with patch('src.shared.http.time.sleep') as mock_sleep, \
             patch('src.shared.delays.time.sleep') as mock_delay_sleep, \
             patch('src.shared.delays.random.uniform', return_value=0.1):  # Minimize random delay
            result = get_with_retry(session, "http://example.com", max_retries=3, min_delay=0.1, max_delay=0.1)

        # Verify result is returned (200 after retries)
        assert result is not None
        assert result.status_code == 200

        # Should have called sleep for 403 backoff
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]

        # Verify no 300-second (5 min) sleeps
        assert all(s < 300 for s in sleep_calls), f"Found 5-minute sleep in: {sleep_calls}"

        # Verify exponential backoff pattern (30s base, then 60s, etc)
        # First 403 should wait ~30s (base), second should wait ~60s
        backoff_sleeps = [s for s in sleep_calls if s >= 10]  # Filter out random delays
        if len(backoff_sleeps) >= 1:
            assert backoff_sleeps[0] <= 60, f"First 403 backoff too long: {backoff_sleeps[0]}"

    def test_403_logs_context_with_url(self, caplog):
        """403 errors should log the URL and context for debugging."""
        session = Mock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = Mock(status_code=403)

        with patch('src.shared.http.time.sleep'), \
             patch('src.shared.delays.time.sleep'), \
             patch('src.shared.delays.random.uniform', return_value=0.1), \
             caplog.at_level(logging.WARNING):
            get_with_retry(session, "http://example.com/store/123", max_retries=2, min_delay=0.1, max_delay=0.1)

        # Should log the URL in the 403 warning
        assert any("403" in record.message and "example.com" in record.message for record in caplog.records), \
            f"Expected 403 log with URL, got: {[r.message for r in caplog.records]}"

    def test_403_does_not_silently_return_none_without_logging(self, caplog):
        """403 should not silently return None - must log the failure."""
        session = Mock(spec=requests.Session)
        session.headers = {}
        session.get.return_value = Mock(status_code=403)

        with patch('src.shared.http.time.sleep'), \
             patch('src.shared.delays.time.sleep'), \
             patch('src.shared.delays.random.uniform', return_value=0.1), \
             caplog.at_level(logging.WARNING):
            result = get_with_retry(session, "http://example.com", max_retries=2, min_delay=0.1, max_delay=0.1)

        # Should return None (that's OK) but must have logged
        assert result is None
        assert len(caplog.records) > 0, "403 failure should be logged"

    def test_403_retries_instead_of_immediate_return(self):
        """403 should retry instead of returning immediately."""
        session = Mock(spec=requests.Session)
        session.headers = {}

        # 403 then 200
        mock_responses = [
            Mock(status_code=403),
            Mock(status_code=200),
        ]
        session.get.side_effect = mock_responses

        with patch('src.shared.http.time.sleep'), \
             patch('src.shared.delays.time.sleep'), \
             patch('src.shared.delays.random.uniform', return_value=0.1):
            result = get_with_retry(session, "http://example.com", max_retries=3, min_delay=0.1, max_delay=0.1)

        # Should have retried and got the 200
        assert result is not None
        assert result.status_code == 200
        # Should have made 2 requests
        assert session.get.call_count == 2
