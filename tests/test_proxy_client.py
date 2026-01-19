#!/usr/bin/env python3
"""Test suite for ProxyClient class - core proxy functionality"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.shared.proxy_client import (
    ProxyClient, ProxyConfig, ProxyMode, ProxyResponse
)


class TestProxyClientInitialization:
    """Test ProxyClient initialization and validation"""
    
    def test_init_with_valid_direct_config(self):
        """Test initialization with direct mode config"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        assert client.config.mode == ProxyMode.DIRECT
        assert client._request_count == 0
    
    def test_init_with_valid_residential_config(self):
        """Test initialization with valid residential config"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="user",
            residential_password="pass"
        )
        client = ProxyClient(config)
        assert client.config.mode == ProxyMode.RESIDENTIAL
    
    def test_init_with_invalid_config_falls_back_to_direct(self):
        """Test invalid config falls back to direct mode"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="",  # Missing credentials
            residential_password=""
        )
        client = ProxyClient(config)
        assert client.config.mode == ProxyMode.DIRECT
    
    def test_init_from_env_with_no_config(self):
        """Test initialization without config loads from env"""
        with patch.dict('os.environ', {}, clear=True):
            client = ProxyClient()
            assert client.config.mode == ProxyMode.DIRECT


class TestProxyClientSessionManagement:
    """Test session property and configuration"""
    
    def test_session_lazy_creation(self):
        """Test session is created lazily"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        assert client._session is None
        session = client.session
        assert session is not None
        assert client._session is session
    
    def test_session_configuration_for_residential(self):
        """Test session is configured with proxy for residential mode"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="user",
            residential_password="pass",
            country_code="us"
        )
        client = ProxyClient(config)
        session = client.session
        assert 'http' in session.proxies
        assert 'https' in session.proxies
        assert 'user' in session.proxies['http']
        assert 'pr.oxylabs.io:7777' in session.proxies['http']


class TestProxyClientResidentialProxyURL:
    """Test residential proxy URL building"""
    
    def test_build_proxy_url_basic(self):
        """Test basic proxy URL with username and password"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="customer_test",
            residential_password="testpass",
            residential_endpoint="pr.oxylabs.io:7777",
            country_code=""  # No country targeting for basic test
        )
        client = ProxyClient(config)
        url = client._build_residential_proxy_url()
        # Oxylabs format adds customer- prefix to username
        assert url == "http://customer-customer_test:testpass@pr.oxylabs.io:7777"
    
    def test_build_proxy_url_with_country(self):
        """Test proxy URL with country targeting"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="customer_test",
            residential_password="testpass",
            country_code="de"
        )
        client = ProxyClient(config)
        url = client._build_residential_proxy_url()
        # Oxylabs uses cc-{COUNTRY} format with uppercase country code
        assert "cc-DE" in url
    
    def test_build_proxy_url_with_city(self):
        """Test proxy URL with city targeting"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="customer_test",
            residential_password="testpass",
            country_code="us",
            city="newyork"
        )
        client = ProxyClient(config)
        url = client._build_residential_proxy_url()
        # Oxylabs uses cc-{COUNTRY} and city-{city} format
        assert "cc-US" in url
        assert "city-newyork" in url
    
    def test_build_proxy_url_with_state(self):
        """Test proxy URL with state targeting"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="customer_test",
            residential_password="testpass",
            state="california"
        )
        client = ProxyClient(config)
        url = client._build_residential_proxy_url()
        # Oxylabs uses st-{state} format for US states
        assert "st-california" in url
    
    def test_build_proxy_url_with_sticky_session(self):
        """Test proxy URL with sticky session"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="customer_test",
            residential_password="testpass",
            session_type="sticky",
            session_id="session123"
        )
        client = ProxyClient(config)
        url = client._build_residential_proxy_url()
        # Oxylabs uses sessid-{session_id} format for sticky sessions
        assert "sessid-session123" in url


class TestProxyClientGetHeaders:
    """Test header generation"""
    
    def test_get_headers_default(self):
        """Test default headers include user agent and accept headers"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        headers = client._get_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers
    
    def test_get_headers_with_custom_headers(self):
        """Test custom headers are merged"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        custom = {"X-Custom": "value", "Authorization": "Bearer token"}
        headers = client._get_headers(custom)
        assert headers["X-Custom"] == "value"
        assert headers["Authorization"] == "Bearer token"
        assert "User-Agent" in headers  # Default headers still present
    
    def test_get_headers_user_agent_rotation(self):
        """Test user agent is randomly selected"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        user_agents = set()
        for _ in range(20):
            headers = client._get_headers()
            user_agents.add(headers["User-Agent"])
        # Should have multiple different user agents
        assert len(user_agents) > 1


class TestProxyClientDirectMode:
    """Test direct mode requests"""
    
    def test_request_direct_success(self):
        """Test successful direct mode request"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>test</html>"
        mock_response.content = b"<html>test</html>"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.url = "https://example.com"
        
        with patch.object(client.session, 'get', return_value=mock_response):
            response = client.get("https://example.com")
            
        assert response is not None
        assert response.status_code == 200
        assert response.text == "<html>test</html>"
        assert response.proxy_mode == ProxyMode.DIRECT
    
    def test_request_direct_with_params(self):
        """Test direct mode request with query parameters"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "response"
        mock_response.content = b"response"
        mock_response.headers = {}
        mock_response.url = "https://example.com?key=value"
        
        with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
            response = client.get("https://example.com", params={"key": "value"})
            
        assert response is not None
        mock_get.assert_called_once()


class TestProxyClientRetryLogic:
    """Test retry and error handling logic"""
    
    def test_retry_on_429_rate_limit(self):
        """Test exponential backoff on 429 errors"""
        config = ProxyConfig(mode=ProxyMode.DIRECT, max_retries=3, retry_delay=0.1)
        client = ProxyClient(config)
        
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.ok = False
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.ok = True
        mock_response_200.text = "success"
        mock_response_200.content = b"success"
        mock_response_200.headers = {}
        mock_response_200.url = "https://example.com"
        
        with patch.object(client.session, 'get', side_effect=[mock_response_429, mock_response_200]):
            response = client.get("https://example.com")
            
        assert response is not None
        assert response.status_code == 200
    
    def test_retry_on_500_server_error(self):
        """Test retry on 5xx server errors"""
        config = ProxyConfig(mode=ProxyMode.DIRECT, max_retries=2, retry_delay=0.1)
        client = ProxyClient(config)
        
        mock_response_500 = Mock()
        mock_response_500.status_code = 500
        mock_response_500.ok = False
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.ok = True
        mock_response_200.text = "success"
        mock_response_200.content = b"success"
        mock_response_200.headers = {}
        mock_response_200.url = "https://example.com"
        
        with patch.object(client.session, 'get', side_effect=[mock_response_500, mock_response_200]):
            response = client.get("https://example.com")
            
        assert response is not None
        assert response.status_code == 200
    
    def test_no_retry_on_404(self):
        """Test 404 errors return immediately without retry"""
        config = ProxyConfig(mode=ProxyMode.DIRECT, max_retries=3)
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.ok = False
        mock_response.text = "Not Found"
        mock_response.content = b"Not Found"
        mock_response.headers = {}
        mock_response.url = "https://example.com"
        
        with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
            response = client.get("https://example.com")
            
        # Should only call once (no retries)
        assert mock_get.call_count == 1
        assert response.status_code == 404
    
    def test_max_retries_exhausted(self):
        """Test returns None after max retries exhausted"""
        config = ProxyConfig(mode=ProxyMode.DIRECT, max_retries=2, retry_delay=0.1)
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.ok = False
        
        with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
            response = client.get("https://example.com")
            
        assert response is None
        assert mock_get.call_count == 2  # Initial + 1 retry
    
    def test_timeout_exception_retry(self):
        """Test timeout exceptions trigger retry"""
        import requests
        config = ProxyConfig(mode=ProxyMode.DIRECT, max_retries=2, retry_delay=0.1)
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.text = "success"
        mock_response.content = b"success"
        mock_response.headers = {}
        mock_response.url = "https://example.com"
        
        with patch.object(client.session, 'get', side_effect=[
            requests.exceptions.Timeout("Timeout"),
            mock_response
        ]):
            response = client.get("https://example.com")
            
        assert response is not None
        assert response.status_code == 200


class TestProxyClientWebScraperAPI:
    """Test Web Scraper API mode"""
    
    def test_web_scraper_api_payload_basic(self):
        """Test basic Web Scraper API payload construction"""
        config = ProxyConfig(
            mode=ProxyMode.WEB_SCRAPER_API,
            scraper_api_username="api_user",
            scraper_api_password="api_pass",
            country_code="us"
        )
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{
                "content": "<html>test</html>",
                "status_code": 200
            }],
            "job_id": "job123",
            "credits_used": 1.5
        }
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            response = client.get("https://example.com")
            
        assert response is not None
        assert response.text == "<html>test</html>"
        assert response.job_id == "job123"
        assert response.credits_used == 1.5
        
        # Verify payload
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs['json']
        assert payload['source'] == 'universal'
        assert payload['url'] == 'https://example.com'
        assert payload['geo_location'] == 'US'
    
    def test_web_scraper_api_with_render_js(self):
        """Test Web Scraper API with JavaScript rendering"""
        config = ProxyConfig(
            mode=ProxyMode.WEB_SCRAPER_API,
            scraper_api_username="api_user",
            scraper_api_password="api_pass",
            render_js=True
        )
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{
                "content": "<html>rendered</html>",
                "status_code": 200
            }]
        }
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            response = client.get("https://example.com")
            
        payload = mock_post.call_args[1]['json']
        assert payload['render'] == 'html'
    
    def test_web_scraper_api_with_parse(self):
        """Test Web Scraper API with parsing enabled"""
        config = ProxyConfig(
            mode=ProxyMode.WEB_SCRAPER_API,
            scraper_api_username="api_user",
            scraper_api_password="api_pass",
            parse=True
        )
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{
                "content": {"parsed": "data"},
                "status_code": 200
            }]
        }
        
        with patch('requests.post', return_value=mock_response) as mock_post:
            response = client.get("https://example.com")
            
        payload = mock_post.call_args[1]['json']
        assert payload['parse'] is True


class TestProxyResponse:
    """Test ProxyResponse object"""
    
    def test_proxy_response_ok_property(self):
        """Test ok property for 2xx status codes"""
        response = ProxyResponse(
            status_code=200,
            text="success",
            content=b"success",
            headers={},
            url="https://example.com",
            elapsed_seconds=1.0,
            proxy_mode=ProxyMode.DIRECT
        )
        assert response.ok is True
        
        response_404 = ProxyResponse(
            status_code=404,
            text="not found",
            content=b"not found",
            headers={},
            url="https://example.com",
            elapsed_seconds=1.0,
            proxy_mode=ProxyMode.DIRECT
        )
        assert response_404.ok is False
    
    def test_proxy_response_json_method(self):
        """Test json() method parses JSON content"""
        json_data = {"key": "value", "number": 123}
        response = ProxyResponse(
            status_code=200,
            text=json.dumps(json_data),
            content=json.dumps(json_data).encode(),
            headers={"Content-Type": "application/json"},
            url="https://api.example.com",
            elapsed_seconds=0.5,
            proxy_mode=ProxyMode.DIRECT
        )
        parsed = response.json()
        assert parsed == json_data
    
    def test_proxy_response_raise_for_status_success(self):
        """Test raise_for_status doesn't raise for successful responses"""
        response = ProxyResponse(
            status_code=200,
            text="success",
            content=b"success",
            headers={},
            url="https://example.com",
            elapsed_seconds=1.0,
            proxy_mode=ProxyMode.DIRECT
        )
        # Should not raise
        response.raise_for_status()
    
    def test_proxy_response_raise_for_status_error(self):
        """Test raise_for_status raises for error responses"""
        import requests
        response = ProxyResponse(
            status_code=404,
            text="not found",
            content=b"not found",
            headers={},
            url="https://example.com",
            elapsed_seconds=1.0,
            proxy_mode=ProxyMode.DIRECT
        )
        with pytest.raises(requests.HTTPError):
            response.raise_for_status()


class TestProxyClientStats:
    """Test client statistics"""
    
    def test_get_stats(self):
        """Test get_stats returns client statistics"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="user",
            residential_password="pass",
            country_code="de",
            render_js=False
        )
        client = ProxyClient(config)
        
        stats = client.get_stats()
        assert stats['mode'] == 'residential'
        assert stats['country'] == 'de'
        assert stats['render_js'] is False
        assert stats['request_count'] == 0
    
    def test_request_count_increments(self):
        """Test request count increments with each request"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        client = ProxyClient(config)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.text = "test"
        mock_response.content = b"test"
        mock_response.headers = {}
        mock_response.url = "https://example.com"
        
        with patch.object(client.session, 'get', return_value=mock_response):
            client.get("https://example.com")
            client.get("https://example.com")
            client.get("https://example.com")
        
        stats = client.get_stats()
        assert stats['request_count'] == 3


class TestProxyClientContextManager:
    """Test context manager support"""
    
    def test_context_manager_closes_session(self):
        """Test context manager properly closes session"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        
        with ProxyClient(config) as client:
            _ = client.session  # Create session
            assert client._session is not None
        
        # After context, session should be closed (session set to None)
        assert client._session is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
