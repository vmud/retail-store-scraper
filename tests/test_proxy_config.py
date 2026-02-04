#!/usr/bin/env python3
"""Test suite for ProxyConfig class - configuration loading and validation"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import pytest
from unittest.mock import patch

from src.shared.proxy_client import ProxyConfig, ProxyMode


class TestProxyConfigFromEnv:
    """Test ProxyConfig.from_env() method"""

    def test_from_env_default_direct_mode(self):
        """Test default mode is DIRECT when no env vars set"""
        with patch.dict(os.environ, {}, clear=True):
            config = ProxyConfig.from_env()
            assert config.mode == ProxyMode.DIRECT
            assert config.residential_username == ""
            assert config.residential_password == ""
            assert config.scraper_api_username == ""
            assert config.scraper_api_password == ""

    def test_from_env_residential_mode_specific_credentials(self):
        """Test residential mode with mode-specific credentials"""
        env_vars = {
            "PROXY_MODE": "residential",
            "OXYLABS_RESIDENTIAL_USERNAME": "res_user",
            "OXYLABS_RESIDENTIAL_PASSWORD": "res_pass",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.mode == ProxyMode.RESIDENTIAL
            assert config.residential_username == "res_user"
            assert config.residential_password == "res_pass"
            assert config.username == "res_user"
            assert config.password == "res_pass"

    def test_from_env_residential_mode_legacy_credentials(self):
        """Test residential mode with legacy fallback credentials"""
        env_vars = {
            "PROXY_MODE": "residential",
            "OXYLABS_USERNAME": "legacy_user",
            "OXYLABS_PASSWORD": "legacy_pass",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.mode == ProxyMode.RESIDENTIAL
            assert config.residential_username == "legacy_user"
            assert config.residential_password == "legacy_pass"
            assert config.username == "legacy_user"
            assert config.password == "legacy_pass"

    def test_from_env_web_scraper_api_mode_specific_credentials(self):
        """Test web_scraper_api mode with mode-specific credentials"""
        env_vars = {
            "PROXY_MODE": "web_scraper_api",
            "OXYLABS_SCRAPER_API_USERNAME": "api_user",
            "OXYLABS_SCRAPER_API_PASSWORD": "api_pass",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.mode == ProxyMode.WEB_SCRAPER_API
            assert config.scraper_api_username == "api_user"
            assert config.scraper_api_password == "api_pass"
            assert config.username == "api_user"
            assert config.password == "api_pass"

    def test_from_env_scraper_api_alias(self):
        """Test 'scraper_api' alias maps to WEB_SCRAPER_API mode"""
        env_vars = {
            "PROXY_MODE": "scraper_api",
            "OXYLABS_USERNAME": "user",
            "OXYLABS_PASSWORD": "pass",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.mode == ProxyMode.WEB_SCRAPER_API

    def test_from_env_invalid_mode_defaults_to_direct(self):
        """Test invalid mode string defaults to DIRECT"""
        env_vars = {
            "PROXY_MODE": "invalid_mode",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.mode == ProxyMode.DIRECT

    def test_from_env_credential_priority_specific_over_legacy(self):
        """Test mode-specific credentials take priority over legacy"""
        env_vars = {
            "PROXY_MODE": "residential",
            "OXYLABS_RESIDENTIAL_USERNAME": "specific_user",
            "OXYLABS_RESIDENTIAL_PASSWORD": "specific_pass",
            "OXYLABS_USERNAME": "legacy_user",
            "OXYLABS_PASSWORD": "legacy_pass",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.residential_username == "specific_user"
            assert config.residential_password == "specific_pass"

    def test_from_env_country_code(self):
        """Test country code loading from env"""
        env_vars = {
            "OXYLABS_COUNTRY": "de",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.country_code == "de"

    def test_from_env_render_js_true(self):
        """Test render_js boolean parsing"""
        env_vars = {
            "OXYLABS_RENDER_JS": "true",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.render_js is True

        env_vars = {
            "OXYLABS_RENDER_JS": "false",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.render_js is False

    def test_from_env_timeout_and_retries(self):
        """Test numeric settings parsing"""
        env_vars = {
            "OXYLABS_TIMEOUT": "120",
            "OXYLABS_MAX_RETRIES": "5",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_env()
            assert config.timeout == 120
            assert config.max_retries == 5


class TestProxyConfigFromDict:
    """Test ProxyConfig.from_dict() method"""

    def test_from_dict_direct_mode(self):
        """Test direct mode from dict"""
        data = {"mode": "direct"}
        config = ProxyConfig.from_dict(data)
        assert config.mode == ProxyMode.DIRECT

    def test_from_dict_residential_with_explicit_credentials(self):
        """Test residential mode with explicit credentials in dict"""
        data = {
            "mode": "residential",
            "residential_username": "dict_user",
            "residential_password": "dict_pass",
            "country_code": "gb",
        }
        with patch.dict(os.environ, {}, clear=True):
            config = ProxyConfig.from_dict(data)
            assert config.mode == ProxyMode.RESIDENTIAL
            assert config.residential_username == "dict_user"
            assert config.residential_password == "dict_pass"
            assert config.country_code == "gb"

    def test_from_dict_web_scraper_api_with_settings(self):
        """Test web_scraper_api with render settings"""
        data = {
            "mode": "web_scraper_api",
            "scraper_api_username": "api_user",
            "scraper_api_password": "api_pass",
            "render_js": True,
            "parse": True,
        }
        with patch.dict(os.environ, {}, clear=True):
            config = ProxyConfig.from_dict(data)
            assert config.mode == ProxyMode.WEB_SCRAPER_API
            assert config.render_js is True
            assert config.parse is True

    def test_from_dict_legacy_username_password_residential(self):
        """Test legacy username/password keys for residential mode"""
        data = {
            "mode": "residential",
            "username": "legacy_user",
            "password": "legacy_pass",
        }
        with patch.dict(os.environ, {}, clear=True):
            config = ProxyConfig.from_dict(data)
            assert config.residential_username == "legacy_user"
            assert config.residential_password == "legacy_pass"

    def test_from_dict_legacy_username_password_web_scraper_api(self):
        """Test legacy username/password keys for web_scraper_api mode"""
        data = {
            "mode": "web_scraper_api",
            "username": "api_user",
            "password": "api_pass",
        }
        with patch.dict(os.environ, {}, clear=True):
            config = ProxyConfig.from_dict(data)
            assert config.scraper_api_username == "api_user"
            assert config.scraper_api_password == "api_pass"

    def test_from_dict_falls_back_to_env_credentials(self):
        """Test dict config falls back to env credentials when not specified"""
        env_vars = {
            "OXYLABS_RESIDENTIAL_USERNAME": "env_user",
            "OXYLABS_RESIDENTIAL_PASSWORD": "env_pass",
        }
        data = {
            "mode": "residential",
            "country_code": "fr",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = ProxyConfig.from_dict(data)
            assert config.residential_username == "env_user"
            assert config.residential_password == "env_pass"
            assert config.country_code == "fr"

    def test_from_dict_all_settings(self):
        """Test loading all possible settings from dict"""
        data = {
            "mode": "residential",
            "residential_username": "user",
            "residential_password": "pass",
            "country_code": "jp",
            "city": "tokyo",
            "state": "kanto",
            "session_type": "sticky",
            "timeout": 90,
            "max_retries": 5,
            "retry_delay": 3.0,
            "min_delay": 1.0,
            "max_delay": 3.0,
        }
        with patch.dict(os.environ, {}, clear=True):
            config = ProxyConfig.from_dict(data)
            assert config.mode == ProxyMode.RESIDENTIAL
            assert config.country_code == "jp"
            assert config.city == "tokyo"
            assert config.state == "kanto"
            assert config.session_type == "sticky"
            assert config.timeout == 90
            assert config.max_retries == 5
            assert config.retry_delay == 3.0
            assert config.min_delay == 1.0
            assert config.max_delay == 3.0


class TestProxyConfigValidation:
    """Test ProxyConfig.validate() method"""

    def test_validate_direct_mode_always_valid(self):
        """Test direct mode is always valid (no credentials needed)"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        assert config.validate() is True

    def test_validate_residential_mode_with_credentials(self):
        """Test residential mode is valid with credentials"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="user",
            residential_password="pass"
        )
        assert config.validate() is True

    def test_validate_residential_mode_missing_username(self):
        """Test residential mode is invalid without username"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="",
            residential_password="pass"
        )
        assert config.validate() is False

    def test_validate_residential_mode_missing_password(self):
        """Test residential mode is invalid without password"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="user",
            residential_password=""
        )
        assert config.validate() is False

    def test_validate_web_scraper_api_mode_with_credentials(self):
        """Test web_scraper_api mode is valid with credentials"""
        config = ProxyConfig(
            mode=ProxyMode.WEB_SCRAPER_API,
            scraper_api_username="user",
            scraper_api_password="pass"
        )
        assert config.validate() is True

    def test_validate_web_scraper_api_mode_missing_credentials(self):
        """Test web_scraper_api mode is invalid without credentials"""
        config = ProxyConfig(
            mode=ProxyMode.WEB_SCRAPER_API,
            scraper_api_username="",
            scraper_api_password=""
        )
        assert config.validate() is False


class TestProxyConfigProperties:
    """Test ProxyConfig username/password properties"""

    def test_username_property_direct_mode(self):
        """Test username property returns empty string for direct mode"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        assert config.username == ""

    def test_username_property_residential_mode(self):
        """Test username property returns residential username"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_username="res_user",
            scraper_api_username="api_user"
        )
        assert config.username == "res_user"

    def test_username_property_web_scraper_api_mode(self):
        """Test username property returns scraper_api username"""
        config = ProxyConfig(
            mode=ProxyMode.WEB_SCRAPER_API,
            residential_username="res_user",
            scraper_api_username="api_user"
        )
        assert config.username == "api_user"

    def test_password_property_residential_mode(self):
        """Test password property returns residential password"""
        config = ProxyConfig(
            mode=ProxyMode.RESIDENTIAL,
            residential_password="res_pass",
            scraper_api_password="api_pass"
        )
        assert config.password == "res_pass"

    def test_password_property_web_scraper_api_mode(self):
        """Test password property returns scraper_api password"""
        config = ProxyConfig(
            mode=ProxyMode.WEB_SCRAPER_API,
            residential_password="res_pass",
            scraper_api_password="api_pass"
        )
        assert config.password == "api_pass"

    def test_is_enabled_direct_mode(self):
        """Test is_enabled returns False for direct mode"""
        config = ProxyConfig(mode=ProxyMode.DIRECT)
        assert config.is_enabled() is False

    def test_is_enabled_residential_mode(self):
        """Test is_enabled returns True for residential mode"""
        config = ProxyConfig(mode=ProxyMode.RESIDENTIAL)
        assert config.is_enabled() is True

    def test_is_enabled_web_scraper_api_mode(self):
        """Test is_enabled returns True for web_scraper_api mode"""
        config = ProxyConfig(mode=ProxyMode.WEB_SCRAPER_API)
        assert config.is_enabled() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
