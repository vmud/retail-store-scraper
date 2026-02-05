"""Tests for refactored helper functions in run.py."""
import argparse
import logging
import os
import tempfile
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

import pytest
import yaml

from run import (
    _validate_and_load_config,
    _initialize_proxy,
    _validate_proxy_credentials,
    _prepare_scraper_options,
    _setup_cloud_storage,
    _log_scraper_options,
    _get_yaml_proxy_mode,
    _get_target_retailers,
    validate_cli_options,
)


class TestValidateAndLoadConfig:
    """Tests for _validate_and_load_config helper."""

    def test_valid_config_loads_successfully(self, tmp_path):
        """Valid config should load without errors."""
        config_content = """
retailers:
  verizon:
    enabled: true
    base_url: https://example.com
    min_delay: 2.0
    max_delay: 5.0
"""
        config_file = tmp_path / "retailers.yaml"
        config_file.write_text(config_content)

        args = Mock()
        args.proxy = None
        args.render_js = False

        with patch('run.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = config_content
            with patch('yaml.safe_load', return_value=yaml.safe_load(config_content)):
                config = _validate_and_load_config(args)

        assert isinstance(config, dict)
        assert 'retailers' in config

    def test_invalid_config_raises_system_exit(self):
        """Invalid config should raise SystemExit."""
        args = Mock()
        args.proxy = None
        args.render_js = False

        with patch('run.validate_config_on_startup', return_value=['Configuration error']):
            with pytest.raises(SystemExit) as exc_info:
                _validate_and_load_config(args)
            assert exc_info.value.code == 1

    def test_conflicting_cli_options_raises_system_exit(self):
        """Conflicting CLI options should raise SystemExit."""
        args = Mock()
        args.proxy = None
        args.render_js = False
        args.test = True
        args.limit = 50

        with patch('run.validate_config_on_startup', return_value=[]):
            with patch('yaml.safe_load', return_value={'retailers': {}}):
                with patch('run.validate_cli_options', return_value=['CLI error']):
                    with pytest.raises(SystemExit) as exc_info:
                        _validate_and_load_config(args)
                    assert exc_info.value.code == 1


class TestInitializeProxy:
    """Tests for _initialize_proxy helper."""

    def test_residential_proxy_without_credentials_exits(self):
        """Residential proxy without credentials should exit."""
        args = Mock()
        args.proxy = 'residential'
        args.render_js = False
        args.proxy_country = 'us'

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                _initialize_proxy(args)
            assert exc_info.value.code == 1

    def test_web_scraper_api_without_credentials_exits(self):
        """Web Scraper API without credentials should exit."""
        args = Mock()
        args.proxy = 'web_scraper_api'
        args.render_js = True
        args.proxy_country = 'us'

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                _initialize_proxy(args)
            assert exc_info.value.code == 1

    def test_direct_proxy_succeeds(self):
        """Direct proxy mode should not require credentials."""
        args = Mock()
        args.proxy = 'direct'
        args.render_js = False
        args.proxy_country = None

        with patch('run.get_proxy_client'):
            _initialize_proxy(args)  # Should not raise

    def test_no_proxy_loads_from_yaml(self):
        """No CLI proxy should attempt to load from YAML."""
        args = Mock()
        args.proxy = None

        with patch('run.init_proxy_from_yaml') as mock_init:
            _initialize_proxy(args)
            mock_init.assert_called_once()


class TestValidateProxyCredentials:
    """Tests for _validate_proxy_credentials helper."""

    def test_validate_proxy_success(self, capfd):
        """Successful proxy validation should print success message."""
        args = Mock()
        args.validate_proxy = True

        mock_client = Mock()
        mock_client.validate_credentials.return_value = (True, "Credentials valid")

        with patch('run.get_proxy_client', return_value=mock_client):
            _validate_proxy_credentials(args)

        captured = capfd.readouterr()
        assert "✓" in captured.out
        assert "Credentials valid" in captured.out

    def test_validate_proxy_failure_exits(self):
        """Failed proxy validation should exit."""
        args = Mock()
        args.validate_proxy = True

        mock_client = Mock()
        mock_client.validate_credentials.return_value = (False, "Invalid credentials")

        with patch('run.get_proxy_client', return_value=mock_client):
            with pytest.raises(SystemExit) as exc_info:
                _validate_proxy_credentials(args)
            assert exc_info.value.code == 1

    def test_no_validation_skipped(self):
        """No validation flag should skip validation."""
        args = Mock()
        args.validate_proxy = False

        _validate_proxy_credentials(args)  # Should not raise


class TestPrepareScraperOptions:
    """Tests for _prepare_scraper_options helper."""

    def test_test_mode_sets_limit(self):
        """Test mode should set limit to 10."""
        args = Mock()
        args.test = True
        args.limit = None
        args.proxy = None
        args.proxy_country = None
        args.render_js = False
        args.refresh_urls = False
        args.states = None

        options = _prepare_scraper_options(args)

        assert options['limit'] == 10

    def test_explicit_limit_used(self):
        """Explicit limit should be used."""
        args = Mock()
        args.test = False
        args.limit = 100
        args.proxy = None
        args.proxy_country = None
        args.render_js = False
        args.refresh_urls = False
        args.states = None

        options = _prepare_scraper_options(args)

        assert options['limit'] == 100

    def test_proxy_settings_included(self):
        """Proxy settings should be included in options."""
        args = Mock()
        args.test = False
        args.limit = None
        args.proxy = 'residential'
        args.proxy_country = 'ca'
        args.render_js = True
        args.refresh_urls = True
        args.states = ['MD', 'PA']

        options = _prepare_scraper_options(args)

        assert options['cli_proxy_override'] == 'residential'
        assert options['cli_proxy_settings']['country_code'] == 'ca'
        assert options['cli_proxy_settings']['render_js'] is True
        assert options['refresh_urls'] is True
        assert options['target_states'] == ['MD', 'PA']


class TestSetupCloudStorage:
    """Tests for _setup_cloud_storage helper."""

    def test_no_cloud_flag_disables_cloud(self, caplog):
        """--no-cloud should disable cloud storage."""
        args = Mock()
        args.no_cloud = True
        args.cloud = False
        args.gcs_bucket = None
        args.gcs_history = False

        config = {}

        with caplog.at_level(logging.DEBUG):
            result = _setup_cloud_storage(args, config)

        assert result is None
        assert "Cloud storage disabled" in caplog.text

    def test_cloud_flag_enables_cloud(self):
        """--cloud should enable cloud storage."""
        args = Mock()
        args.no_cloud = False
        args.cloud = True
        args.gcs_bucket = None
        args.gcs_history = False

        config = {}

        mock_manager = Mock()
        mock_manager.provider_name = "GCS"

        with patch('run.get_cloud_storage', return_value=mock_manager):
            result = _setup_cloud_storage(args, config)

        assert result == mock_manager

    def test_config_enables_cloud(self):
        """Config with cloud_storage.enabled should enable cloud."""
        args = Mock()
        args.no_cloud = False
        args.cloud = False
        args.gcs_bucket = None
        args.gcs_history = False

        config = {'cloud_storage': {'enabled': True}}

        mock_manager = Mock()
        mock_manager.provider_name = "GCS"

        with patch('run.get_cloud_storage', return_value=mock_manager):
            result = _setup_cloud_storage(args, config)

        assert result == mock_manager


class TestLogScraperOptions:
    """Tests for _log_scraper_options helper."""

    def test_basic_options_logged(self, caplog):
        """Basic scraper options should be logged."""
        retailers = ['verizon', 'att']
        export_formats = [Mock(value='json'), Mock(value='csv')]
        args = Mock()
        args.resume = False
        args.incremental = False
        options = {
            'limit': None,
            'refresh_urls': False,
            'target_states': None
        }

        with caplog.at_level(logging.INFO):
            _log_scraper_options(retailers, export_formats, args, options)

        assert "verizon" in caplog.text
        assert "att" in caplog.text
        assert "json" in caplog.text
        assert "csv" in caplog.text

    def test_all_options_logged(self, caplog):
        """All scraper options should be logged when present."""
        retailers = ['verizon']
        export_formats = [Mock(value='json')]
        args = Mock()
        args.resume = True
        args.incremental = True
        options = {
            'limit': 100,
            'refresh_urls': True,
            'target_states': ['MD', 'PA']
        }

        with caplog.at_level(logging.INFO):
            _log_scraper_options(retailers, export_formats, args, options)

        assert "Limit: 100" in caplog.text
        assert "Resume mode enabled" in caplog.text
        assert "Incremental mode enabled" in caplog.text
        assert "Refresh URLs mode enabled" in caplog.text
        assert "Targeted states mode" in caplog.text


class TestGetYamlProxyMode:
    """Tests for _get_yaml_proxy_mode helper."""

    def test_global_proxy_mode(self):
        """Should return global proxy mode."""
        config = {
            'proxy': {'mode': 'residential'}
        }

        mode = _get_yaml_proxy_mode(config)

        assert mode == 'residential'

    def test_retailer_specific_proxy_mode(self):
        """Should return retailer-specific proxy mode."""
        config = {
            'proxy': {'mode': 'direct'},
            'retailers': {
                'verizon': {
                    'proxy': {'mode': 'web_scraper_api'}
                }
            }
        }

        mode = _get_yaml_proxy_mode(config, 'verizon')

        assert mode == 'web_scraper_api'

    def test_retailer_inherits_global_mode(self):
        """Retailer without specific mode should inherit global."""
        config = {
            'proxy': {'mode': 'residential'},
            'retailers': {
                'verizon': {}
            }
        }

        mode = _get_yaml_proxy_mode(config, 'verizon')

        assert mode == 'residential'

    def test_no_proxy_config_returns_none(self):
        """No proxy config should return None."""
        config = {}

        mode = _get_yaml_proxy_mode(config)

        assert mode is None


class TestGetTargetRetailers:
    """Tests for _get_target_retailers helper."""

    def test_single_retailer(self):
        """Should return single retailer."""
        args = Mock()
        args.retailer = 'verizon'
        args.all = False
        args.exclude = []

        retailers = _get_target_retailers(args)

        assert retailers == ['verizon']

    def test_all_retailers(self):
        """Should return all enabled retailers."""
        args = Mock()
        args.retailer = None
        args.all = True
        args.exclude = []

        with patch('run.get_enabled_retailers', return_value=['verizon', 'att', 'target']):
            retailers = _get_target_retailers(args)

        assert len(retailers) == 3
        assert 'verizon' in retailers

    def test_all_with_exclusions(self):
        """Should exclude specified retailers."""
        args = Mock()
        args.retailer = None
        args.all = True
        args.exclude = ['att']

        with patch('run.get_enabled_retailers', return_value=['verizon', 'att', 'target']):
            retailers = _get_target_retailers(args)

        assert 'att' not in retailers
        assert 'verizon' in retailers
        assert 'target' in retailers

    def test_no_selection_returns_empty(self):
        """No retailer selection should return empty list."""
        args = Mock()
        args.retailer = None
        args.all = False
        args.exclude = []

        retailers = _get_target_retailers(args)

        assert retailers == []


class TestValidateCliOptions:
    """Tests for validate_cli_options function."""

    def test_test_and_limit_conflict(self):
        """--test and --limit should conflict."""
        args = Mock()
        args.test = True
        args.limit = 50
        args.render_js = False
        args.proxy = None
        args.exclude = None
        args.all = False

        errors = validate_cli_options(args, {})

        assert len(errors) > 0
        assert any('--test' in err and '--limit' in err for err in errors)

    def test_render_js_without_web_scraper_api(self):
        """--render-js without web_scraper_api should error."""
        args = Mock()
        args.test = False
        args.limit = None
        args.render_js = True
        args.proxy = 'residential'
        args.exclude = None
        args.all = False

        errors = validate_cli_options(args, {})

        assert len(errors) > 0
        assert any('render-js' in err.lower() for err in errors)

    def test_negative_limit(self):
        """Negative limit should error."""
        args = Mock()
        args.test = False
        args.limit = -1
        args.render_js = False
        args.proxy = None
        args.exclude = None
        args.all = False

        errors = validate_cli_options(args, {})

        assert len(errors) > 0
        assert any('positive integer' in err for err in errors)

    def test_exclude_without_all(self):
        """--exclude without --all should error."""
        args = Mock()
        args.test = False
        args.limit = None
        args.render_js = False
        args.proxy = None
        args.exclude = ['att']
        args.all = False
        args.retailer = None

        errors = validate_cli_options(args, {})

        assert len(errors) > 0
        assert any('exclude' in err.lower() and '--all' in err for err in errors)

    def test_valid_options(self):
        """Valid options should return no errors."""
        args = Mock()
        args.test = False
        args.limit = 100
        args.render_js = False
        args.proxy = None
        args.exclude = None
        args.all = False

        errors = validate_cli_options(args, {})

        assert len(errors) == 0
