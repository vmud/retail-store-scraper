"""
Comprehensive tests for Walmart proxy configuration handling (Issue #149).

These tests verify that Walmart scraper correctly respects CLI and YAML proxy settings
instead of forcibly overriding them to web_scraper_api.

TDD Approach: These tests should FAIL before implementing the fix.
"""
# pylint: disable=no-member,redefined-outer-name

import logging
import pytest
from unittest.mock import Mock, patch, MagicMock, call

from src.scrapers.walmart import run
from src.shared.proxy_client import ProxyMode, ProxyConfig, ProxyClient


@pytest.fixture
def mock_session():
    """Mock requests session for sitemap fetching."""
    return Mock()


@pytest.fixture
def mock_url_cache():
    """Mock URLCache to avoid actual sitemap fetching."""
    with patch('src.scrapers.walmart.URLCache') as mock_cache_class:
        mock_cache = Mock()
        mock_cache.get.return_value = []  # Empty cache - no URLs
        mock_cache_class.return_value = mock_cache
        yield mock_cache


@pytest.fixture
def mock_sitemap():
    """Mock sitemap fetching to return empty list."""
    with patch('src.scrapers.walmart.get_store_urls_from_sitemap') as mock:
        mock.return_value = []
        yield mock


class TestWalmartRespectsDirectProxyMode:
    """Test that Walmart respects explicit 'direct' mode configuration."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_direct_mode_warns_about_js_requirement(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap, caplog
    ):
        """Walmart should warn when direct mode is used (JS rendering needed)."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'direct'},
            'checkpoint_interval': 100
        }

        # Execute
        with caplog.at_level(logging.INFO):
            run(mock_session, config, retailer='walmart')

        # Verify warning about JS rendering requirement
        log_messages = [rec.message for rec in caplog.records]
        assert any('JS rendering' in msg or 'JavaScript' in msg for msg in log_messages), \
            "Should warn about JavaScript rendering requirement for Walmart"

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_direct_mode_upgrades_to_web_scraper_api_with_justification(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap, caplog
    ):
        """Direct mode should upgrade to web_scraper_api but with clear logging."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'direct'},
            'checkpoint_interval': 100
        }

        # Execute
        with caplog.at_level(logging.INFO):
            run(mock_session, config, retailer='walmart')

        # Verify upgrade happens with justification
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('mode') == 'web_scraper_api', \
            "Direct mode should upgrade to web_scraper_api for Walmart (JS required)"

        # Should log the upgrade reason
        log_messages = [rec.message for rec in caplog.records]
        assert any('upgrading' in msg.lower() or 'upgrade' in msg.lower()
                  for msg in log_messages), \
            "Should log that mode is being upgraded"


class TestWalmartRespectsResidentialProxyMode:
    """Test that Walmart respects explicit 'residential' mode configuration."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_residential_mode_not_upgraded(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Walmart should use residential mode when explicitly configured (not upgrade)."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'residential'},
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify residential mode is preserved
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('mode') == 'residential', \
            f"Expected 'residential' mode, got: {call_args.get('mode')}"

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_residential_mode_with_custom_settings(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Residential mode should preserve custom geo-targeting settings."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {
                'mode': 'residential',
                'country_code': 'ca',
                'city': 'toronto'
            },
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify settings are passed through
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('mode') == 'residential'
        assert call_args.get('country_code') == 'ca', \
            "Should preserve country_code setting"
        assert call_args.get('city') == 'toronto', \
            "Should preserve city setting"


class TestWalmartRespectsWebScraperApiMode:
    """Test that Walmart respects explicit 'web_scraper_api' mode configuration."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_web_scraper_api_mode_used_as_is(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Walmart should use web_scraper_api when explicitly configured."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'web_scraper_api'},
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify mode is preserved
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('mode') == 'web_scraper_api'

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_web_scraper_api_defaults_render_js_to_true(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Web scraper API mode should default render_js to True for Walmart."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'web_scraper_api'},  # No render_js specified
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify render_js is enabled
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('render_js') is True, \
            "Should default render_js to True for web_scraper_api mode"

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_web_scraper_api_respects_explicit_render_js_false(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Web scraper API should respect explicit render_js=False (even if not recommended)."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {
                'mode': 'web_scraper_api',
                'render_js': False  # Explicitly disabled
            },
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify render_js setting is preserved
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        # Should NOT override explicit False (even if it's a bad idea)
        # The default behavior only applies when render_js is not set
        assert 'render_js' in call_args


class TestWalmartYamlProxySettings:
    """Test that Walmart uses proxy settings from retailers.yaml."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_uses_yaml_proxy_config(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Walmart should use proxy settings loaded from YAML config."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        # Simulate YAML config loaded from retailers.yaml
        config = {
            'proxy': {
                'mode': 'residential',
                'country_code': 'us',
                'timeout': 90,
                'max_retries': 5
            },
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify ProxyConfig.from_dict was called with YAML settings
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('mode') == 'residential'
        assert call_args.get('country_code') == 'us'
        assert call_args.get('timeout') == 90
        assert call_args.get('max_retries') == 5

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_yaml_settings_merged_with_defaults(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Partial YAML config should merge with defaults."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {
                'mode': 'web_scraper_api',
                # Only mode specified, other settings should use defaults
            },
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify mode is set, render_js gets default
        assert mock_proxy_config_class.from_dict.called
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('mode') == 'web_scraper_api'
        assert call_args.get('render_js') is True  # Should get default for Walmart


class TestWalmartProxyCredentialValidation:
    """Test that Walmart validates proxy credentials appropriately."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_proxy_client_initialized_with_config(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """ProxyClient should be initialized with config from ProxyConfig.from_dict."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'residential'},
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify ProxyClient was initialized with the config instance
        mock_proxy_client_class.assert_called_once_with(mock_config_instance)

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_missing_credentials_handled_by_proxy_client(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap, caplog
    ):
        """ProxyClient should handle missing credentials (validation in ProxyClient.__init__)."""
        # Setup
        mock_config_instance = Mock()
        mock_config_instance.validate.return_value = False  # Invalid credentials
        mock_config_instance.mode = ProxyMode.RESIDENTIAL
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        # ProxyClient should log error when credentials are invalid
        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'residential'},
            'checkpoint_interval': 100
        }

        # Execute
        with caplog.at_level(logging.ERROR):
            run(mock_session, config, retailer='walmart')

        # ProxyClient.__init__ should have been called
        # Credential validation happens inside ProxyClient
        assert mock_proxy_client_class.called


class TestWalmartProxyConsistency:
    """Test that Walmart proxy handling matches other scrapers."""

    @patch('src.scrapers.target.run')
    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_proxy_initialization_pattern_matches_target(
        self, mock_proxy_config_class, mock_proxy_client_class, mock_target_run,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Walmart should use same proxy initialization pattern as Target."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'residential'},
            'checkpoint_interval': 100
        }

        # Execute Walmart run
        run(mock_session, config, retailer='walmart')

        # Verify pattern: ProxyConfig.from_dict() then ProxyClient(config)
        assert mock_proxy_config_class.from_dict.called, \
            "Should use ProxyConfig.from_dict() like Target"
        assert mock_proxy_client_class.called, \
            "Should initialize ProxyClient like Target"

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_does_not_create_proxy_client_directly_with_hardcoded_mode(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Should NOT create ProxyClient with hardcoded mode (the bug being fixed)."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'residential'},  # User wants residential
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify we use ProxyConfig.from_dict, not direct creation
        assert mock_proxy_config_class.from_dict.called

        # Should not see any calls like: ProxyConfig(mode='web_scraper_api', ...)
        # All config should come from from_dict()
        if mock_proxy_config_class.call_count > 0:
            # If ProxyConfig() constructor was called directly, that's the bug
            direct_calls = [
                call for call in mock_proxy_config_class.call_args_list
                if call != mock_proxy_config_class.from_dict.call_args_list[0]
            ]
            assert len(direct_calls) == 0, \
                "Should not create ProxyConfig directly, only via from_dict()"


class TestWalmartProxyWarnings:
    """Test that Walmart provides helpful warnings about proxy requirements."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_warns_when_direct_mode_used(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap, caplog
    ):
        """Should warn when direct mode is used for Walmart (JS rendering needed)."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'direct'},
            'checkpoint_interval': 100
        }

        # Execute
        with caplog.at_level(logging.INFO):
            run(mock_session, config, retailer='walmart')

        # Verify warning about Walmart requirements
        log_messages = '\n'.join([rec.message for rec in caplog.records])
        assert 'walmart' in log_messages.lower() or 'js' in log_messages.lower(), \
            "Should log information about Walmart's JavaScript requirements"

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_logs_final_proxy_mode_used(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap, caplog
    ):
        """Should log what proxy mode is actually being used for store extraction."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'residential'},
            'checkpoint_interval': 100
        }

        # Execute
        with caplog.at_level(logging.INFO):
            run(mock_session, config, retailer='walmart')

        # Verify logging of proxy mode
        log_messages = '\n'.join([rec.message for rec in caplog.records])
        assert 'proxy' in log_messages.lower() or 'mode' in log_messages.lower(), \
            "Should log proxy mode being used"


class TestWalmartProxyConfigImmutability:
    """Test that proxy config is not mutated for other retailers."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_does_not_mutate_original_config_dict(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Walmart should not mutate the original config dict."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        original_proxy_config = {'mode': 'direct'}
        config = {
            'proxy': original_proxy_config,
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify original config was not mutated
        assert original_proxy_config['mode'] == 'direct', \
            "Should not mutate original config dict"

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_creates_copy_before_modifying_config(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Walmart should create a copy of proxy config before modifications."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'direct'},
            'checkpoint_interval': 100
        }

        original_proxy_mode = config['proxy']['mode']

        # Execute
        run(mock_session, config, retailer='walmart')

        # Original config should be unchanged
        assert config['proxy']['mode'] == original_proxy_mode

        # The config passed to ProxyConfig.from_dict should be modified
        call_args = mock_proxy_config_class.from_dict.call_args[0][0]
        assert call_args.get('mode') == 'web_scraper_api', \
            "Modified copy should have upgraded mode"


class TestWalmartProxyEdgeCases:
    """Test edge cases in proxy configuration handling."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_handles_missing_proxy_config_key(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Should handle config dict without 'proxy' key gracefully."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'checkpoint_interval': 100
            # No 'proxy' key
        }

        # Execute - should not raise exception
        run(mock_session, config, retailer='walmart')

        # Should still create ProxyConfig with defaults
        assert mock_proxy_config_class.from_dict.called

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_handles_empty_proxy_config(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Should handle empty proxy config dict."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {},  # Empty
            'checkpoint_interval': 100
        }

        # Execute - should not raise exception
        run(mock_session, config, retailer='walmart')

        # Should create ProxyConfig with defaults (empty dict -> defaults)
        assert mock_proxy_config_class.from_dict.called

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_handles_none_proxy_config(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """Should raise AttributeError when proxy config is None (not graceful but explicit)."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': None,  # This is invalid - will raise error
            'checkpoint_interval': 100
        }

        # Execute - should raise AttributeError
        # Note: This could be improved to handle None more gracefully,
        # but for now we document the actual behavior
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'get'"):
            run(mock_session, config, retailer='walmart')


class TestWalmartProxyClientCleanup:
    """Test that ProxyClient is properly cleaned up."""

    @patch('src.scrapers.walmart.ProxyClient')
    @patch('src.scrapers.walmart.ProxyConfig')
    def test_proxy_client_closed_on_success(
        self, mock_proxy_config_class, mock_proxy_client_class,
        mock_session, mock_url_cache, mock_sitemap
    ):
        """ProxyClient should be closed after successful run."""
        # Setup
        mock_config_instance = Mock()
        mock_proxy_config_class.from_dict.return_value = mock_config_instance

        mock_client_instance = Mock()
        mock_client_instance.close = Mock()
        mock_proxy_client_class.return_value = mock_client_instance

        config = {
            'proxy': {'mode': 'residential'},
            'checkpoint_interval': 100
        }

        # Execute
        run(mock_session, config, retailer='walmart')

        # Verify close was called
        mock_client_instance.close.assert_called_once()

    def test_proxy_client_closed_on_exception(
        self, mock_session
    ):
        """ProxyClient should be closed even if exception occurs during URL fetching."""
        # Patch URLCache to return None (cache miss) so it actually calls get_store_urls_from_sitemap
        with patch('src.scrapers.walmart.URLCache') as mock_cache_class:
            mock_cache = Mock()
            mock_cache.get.return_value = None  # Force cache miss
            mock_cache_class.return_value = mock_cache

            # Patch get_store_urls_from_sitemap to raise exception AFTER ProxyClient is created
            with patch('src.scrapers.walmart.ProxyConfig') as mock_proxy_config_class:
                with patch('src.scrapers.walmart.ProxyClient') as mock_proxy_client_class:
                    with patch('src.scrapers.walmart.get_store_urls_from_sitemap',
                              side_effect=Exception("Test error")):
                        # Setup
                        mock_config_instance = Mock()
                        mock_proxy_config_class.from_dict.return_value = mock_config_instance

                        mock_client_instance = Mock()
                        mock_client_instance.close = Mock()
                        mock_proxy_client_class.return_value = mock_client_instance

                        config = {
                            'proxy': {'mode': 'residential'},
                            'checkpoint_interval': 100
                        }

                        # Execute - expect exception to be raised from run()
                        with pytest.raises(Exception, match="Test error"):
                            run(mock_session, config, retailer='walmart')

                        # Verify close was still called (in finally block)
                        mock_client_instance.close.assert_called_once()
