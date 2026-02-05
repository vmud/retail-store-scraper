#!/usr/bin/env python3
"""Test suite for ProxiedSession wrapper and create_proxied_session()"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from src.shared.utils import ProxiedSession, create_proxied_session
from src.shared.proxy_client import ProxyMode, ProxyConfig


class TestProxiedSessionInitialization:
    """Test ProxiedSession initialization"""

    def test_init_with_direct_mode_config(self):
        """Test ProxiedSession with direct mode"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)
            assert session._client.config.mode == ProxyMode.DIRECT
            assert hasattr(session, 'headers')
            assert isinstance(session.headers, dict)

    def test_init_with_residential_mode_config(self):
        """Test ProxiedSession with residential mode"""
        config = {
            "mode": "residential",
            "residential_username": "user",
            "residential_password": "pass"
        }
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)
            assert session._client.config.mode == ProxyMode.RESIDENTIAL

    def test_init_creates_headers_attribute(self):
        """Test ProxiedSession has headers attribute (critical for scrapers)"""
        session = ProxiedSession({"mode": "direct"})
        assert hasattr(session, 'headers')
        assert 'User-Agent' in session.headers
        assert 'Accept' in session.headers


class TestProxiedSessionGetMethod:
    """Test ProxiedSession.get() method compatibility"""

    def test_get_with_direct_mode_uses_session(self):
        """Test direct mode uses standard requests.Session"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "success"

            with patch.object(session._session, 'get', return_value=mock_response) as mock_get:
                response = session.get("https://example.com")

            assert response is not None
            mock_get.assert_called_once()

    def test_get_with_proxy_mode_uses_client(self):
        """Test proxy modes use ProxyClient"""
        config = {
            "mode": "residential",
            "residential_username": "user",
            "residential_password": "pass"
        }
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "success"

            with patch.object(session._client, 'get', return_value=mock_response) as mock_get:
                response = session.get("https://example.com")

            assert response is not None
            mock_get.assert_called_once()

    def test_get_with_params(self):
        """Test get() passes query parameters correctly"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)

            mock_response = Mock()
            mock_response.status_code = 200

            with patch.object(session._session, 'get', return_value=mock_response) as mock_get:
                session.get("https://example.com", params={"key": "value"})

            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['params'] == {"key": "value"}

    def test_get_with_custom_headers(self):
        """Test get() merges custom headers with instance headers"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)
            session.headers = {"X-Custom": "base"}

            mock_response = Mock()
            mock_response.status_code = 200

            with patch.object(session._session, 'get', return_value=mock_response) as mock_get:
                session.get("https://example.com", headers={"X-Override": "value"})

            # Should merge base headers + custom headers
            call_kwargs = mock_get.call_args[0]
            # Headers are updated on session before call
            assert session._session.headers.get('X-Custom') == 'base'

    def test_get_with_timeout(self):
        """Test get() passes timeout parameter"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)

            mock_response = Mock()
            mock_response.status_code = 200

            with patch.object(session._session, 'get', return_value=mock_response) as mock_get:
                session.get("https://example.com", timeout=60)

            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['timeout'] == 60

    def test_get_handles_request_exception(self):
        """Test get() handles request exceptions gracefully"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)

            with patch.object(session._session, 'get', side_effect=requests.exceptions.RequestException("Error")):
                response = session.get("https://example.com")

            assert response is None


class TestProxiedSessionContextManager:
    """Test ProxiedSession context manager support"""

    def test_context_manager_enter_exit(self):
        """Test ProxiedSession works as context manager"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            with ProxiedSession(config) as session:
                assert session is not None
                assert hasattr(session, 'headers')

    def test_context_manager_closes_session(self):
        """Test context manager closes underlying session"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)
            _ = session._session  # Create direct session

            with session:
                pass

            # After context, session should be None
            assert session._direct_session is None


class TestCreateProxiedSession:
    """Test create_proxied_session() function - CRITICAL GIT CHANGE VALIDATION"""

    def test_returns_session_for_direct_mode(self):
        """Test returns standard requests.Session for direct mode"""
        config = {"proxy": {"mode": "direct"}}
        with patch.dict('os.environ', {}, clear=True):
            session = create_proxied_session(config)

        assert isinstance(session, requests.Session)
        assert hasattr(session, 'headers')

    def test_returns_proxied_session_for_residential_mode(self):
        """Test returns ProxiedSession for residential mode (GIT CHANGE FIX)"""
        config = {
            "name": "test_retailer",
            "proxy": {
                "mode": "residential",
                "residential_username": "user",
                "residential_password": "pass"
            }
        }
        with patch.dict('os.environ', {}, clear=True):
            session = create_proxied_session(config)

        # CRITICAL: Should return ProxiedSession, not ProxyClient
        assert isinstance(session, ProxiedSession)
        assert hasattr(session, 'headers')  # Must have headers attribute
        assert hasattr(session, 'get')  # Must have get method

    def test_returns_proxied_session_for_web_scraper_api_mode(self):
        """Test returns ProxiedSession for web_scraper_api mode (GIT CHANGE FIX)"""
        config = {
            "name": "test_retailer",
            "proxy": {
                "mode": "web_scraper_api",
                "scraper_api_username": "user",
                "scraper_api_password": "pass"
            }
        }
        with patch.dict('os.environ', {}, clear=True):
            session = create_proxied_session(config)

        # CRITICAL: Should return ProxiedSession, not ProxyClient
        assert isinstance(session, ProxiedSession)
        assert hasattr(session, 'headers')  # Must have headers attribute

    def test_falls_back_to_direct_on_missing_credentials(self):
        """Test falls back to direct mode when credentials missing"""
        config = {
            "name": "test_retailer",
            "proxy": {
                "mode": "residential"
                # Missing username/password
            }
        }
        with patch.dict('os.environ', {}, clear=True):
            session = create_proxied_session(config)

        # Should fall back to standard requests.Session
        assert isinstance(session, requests.Session)

    def test_handles_none_config(self):
        """Test handles None retailer_config gracefully"""
        with patch.dict('os.environ', {}, clear=True):
            session = create_proxied_session(None)

        # Should return standard session for direct mode
        assert isinstance(session, requests.Session)

    def test_handles_missing_proxy_section(self):
        """Test handles config without proxy section"""
        config = {"name": "test_retailer"}
        with patch.dict('os.environ', {}, clear=True):
            session = create_proxied_session(config)

        # Should default to direct mode
        assert isinstance(session, requests.Session)


class TestProxiedSessionCompatibility:
    """Test ProxiedSession is compatible with requests.Session interface"""

    def test_has_required_attributes(self):
        """Test ProxiedSession has required attributes for scraper compatibility"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)

        # Required attributes for scrapers
        assert hasattr(session, 'headers')
        assert hasattr(session, 'get')
        assert hasattr(session, 'close')
        assert hasattr(session, '__enter__')
        assert hasattr(session, '__exit__')

    def test_headers_attribute_is_mutable_dict(self):
        """Test headers attribute can be modified like requests.Session"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            session = ProxiedSession(config)

        # Should be able to update headers
        session.headers['X-Custom'] = 'value'
        assert session.headers['X-Custom'] == 'value'

        # Should be able to update existing headers
        session.headers.update({'X-Another': 'test'})
        assert session.headers['X-Another'] == 'test'

    def test_can_replace_requests_session_in_scrapers(self):
        """Test ProxiedSession can replace requests.Session in existing code"""
        config = {"mode": "direct"}
        with patch.dict('os.environ', {}, clear=True):
            # Simulating scraper code:
            # session = requests.Session()  # OLD
            # session = ProxiedSession(config)  # NEW

            session = ProxiedSession(config)
            session.headers.update({'User-Agent': 'Custom/1.0'})

            mock_response = Mock()
            mock_response.status_code = 200

            with patch.object(session._session, 'get', return_value=mock_response):
                response = session.get("https://example.com")

            assert response is not None
            assert response.status_code == 200


class TestGitChangeFix:
    """Test the specific git change that fixes the headers attribute issue"""

    def test_git_change_returns_proxied_session_not_proxy_client(self):
        """
        CRITICAL TEST: Validates the git diff change on line 593 of utils.py

        OLD CODE (broken):
            client = get_proxy_client(proxy_config_dict, retailer=retailer_name)
            return client  # Returns ProxyClient (no headers attribute)

        NEW CODE (fixed):
            proxied_session = ProxiedSession(proxy_config_dict)
            return proxied_session  # Returns ProxiedSession (has headers attribute)
        """
        config = {
            "name": "verizon",
            "proxy": {
                "mode": "residential",
                "residential_username": "user",
                "residential_password": "pass"
            }
        }

        with patch.dict('os.environ', {}, clear=True):
            result = create_proxied_session(config)

        # Before fix: result would be ProxyClient (no headers attribute)
        # After fix: result is ProxiedSession (has headers attribute)
        assert isinstance(result, ProxiedSession), \
            "create_proxied_session should return ProxiedSession for proxy modes"

        assert hasattr(result, 'headers'), \
            "ProxiedSession must have headers attribute for scraper compatibility"

        # Verify headers attribute is accessible (this would fail with old ProxyClient)
        result.headers['X-Test'] = 'value'
        assert result.headers['X-Test'] == 'value'

    def test_git_change_logging_message(self):
        """Test logging message reflects the change from ProxyClient to ProxiedSession"""
        config = {
            "name": "walmart",
            "proxy": {
                "mode": "web_scraper_api",
                "scraper_api_username": "user",
                "scraper_api_password": "pass"
            }
        }

        with patch.dict('os.environ', {}, clear=True):
            with patch('src.shared.utils.logging') as mock_logging:
                result = create_proxied_session(config)

        # Should log "Created ProxiedSession", not "Created ProxyClient"
        assert any('ProxiedSession' in str(call) for call in mock_logging.info.call_args_list), \
            "Logging should mention ProxiedSession"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
