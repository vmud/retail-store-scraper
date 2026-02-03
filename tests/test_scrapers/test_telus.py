"""Tests for Telus scraper functionality."""
import pytest
from unittest.mock import Mock, patch

from src.scrapers import telus
from src.shared import utils


@pytest.fixture
def mock_session():
    """Create a mock session for testing."""
    session = Mock()
    session.headers = {}
    return session


class TestTelusExplicitFailure:
    """Tests for explicit failure on persistent errors (#147)."""

    def test_empty_response_after_retries_raises_exception(self, mock_session):
        """Should raise exception on persistent failure, not return empty success."""
        # Mock get_with_retry to return None (simulating all retries failed)
        with patch.object(utils, 'get_with_retry', return_value=None):
            with pytest.raises(RuntimeError, match="API request failed"):
                telus.fetch_all_stores(mock_session, 'telus')

    def test_api_error_status_raises_exception(self, mock_session):
        """Should raise exception when API returns error status."""
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'ERROR', 'response': {}}

        with patch.object(utils, 'get_with_retry', return_value=mock_response):
            with pytest.raises(RuntimeError, match="API returned error"):
                telus.fetch_all_stores(mock_session, 'telus')

    def test_run_raises_on_persistent_failure(self, mock_session):
        """run() should propagate exception, not return empty success."""
        with patch.object(telus, 'fetch_all_stores', side_effect=RuntimeError("API failed")):
            with pytest.raises(RuntimeError):
                telus.run(mock_session, {}, retailer='telus')


class TestTelusSuccessfulFetch:
    """Tests for successful store fetching."""

    def test_successful_api_response_returns_stores(self, mock_session):
        """Should return stores when API succeeds."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'SUCCESS',
            'response': {
                'locations': [
                    {
                        'id': '123',
                        'identifier': 'TELUS-123',
                        'name': 'Test Store',
                        'streetAndNumber': '123 Main St',
                        'city': 'Vancouver',
                        'province': 'British Columbia',
                        'zip': 'V6B 1A1',
                        'country': 'CA',
                        'lat': 49.2827,
                        'lng': -123.1207,
                        'phone': '604-555-1234',
                    }
                ]
            }
        }

        with patch.object(utils, 'get_with_retry', return_value=mock_response):
            stores = telus.fetch_all_stores(mock_session, 'telus')

        assert len(stores) == 1
        assert stores[0].name == 'Test Store'
        assert stores[0].city == 'Vancouver'
