"""Tests for scraper registry functions."""

import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from src.scrapers import (
    get_available_retailers,
    get_enabled_retailers,
    get_scraper_module,
    SCRAPER_REGISTRY
)


class TestGetAvailableRetailers:
    """Tests for get_available_retailers function."""

    def test_returns_all_registered_retailers(self):
        """Test that all registered retailers are returned."""
        retailers = get_available_retailers()
        assert isinstance(retailers, list)
        assert len(retailers) == len(SCRAPER_REGISTRY)
        assert 'verizon' in retailers
        assert 'att' in retailers
        assert 'target' in retailers
        assert 'tmobile' in retailers
        assert 'walmart' in retailers
        assert 'bestbuy' in retailers


class TestGetEnabledRetailers:
    """Tests for get_enabled_retailers function."""

    def test_returns_enabled_retailers_from_config(self):
        """Test that only enabled retailers are returned."""
        config_yaml = """
retailers:
  verizon:
    enabled: true
  att:
    enabled: false
  target:
    enabled: true
  tmobile:
    enabled: true
  walmart:
    enabled: false
  bestbuy:
    enabled: true
"""
        with patch('builtins.open', mock_open(read_data=config_yaml)):
            retailers = get_enabled_retailers()
            assert 'verizon' in retailers
            assert 'att' not in retailers
            assert 'target' in retailers
            assert 'tmobile' in retailers
            assert 'walmart' not in retailers
            assert 'bestbuy' in retailers

    def test_defaults_to_enabled_when_not_specified(self):
        """Test that retailers default to enabled when not explicitly set."""
        config_yaml = """
retailers:
  verizon:
    base_url: https://example.com
  att:
    enabled: false
"""
        with patch('builtins.open', mock_open(read_data=config_yaml)):
            retailers = get_enabled_retailers()
            # verizon should default to enabled
            assert 'verizon' in retailers
            # att is explicitly disabled
            assert 'att' not in retailers

    def test_handles_empty_yaml_file(self):
        """Test that empty YAML file (returns None) doesn't crash."""
        # Empty YAML file causes yaml.safe_load() to return None
        with patch('builtins.open', mock_open(read_data='')):
            retailers = get_enabled_retailers()
            # Should return all retailers (default to enabled)
            assert len(retailers) == len(SCRAPER_REGISTRY)
            assert 'verizon' in retailers

    def test_handles_yaml_with_no_retailers_key(self):
        """Test that YAML without 'retailers' key doesn't crash."""
        config_yaml = """
proxy:
  mode: direct
"""
        with patch('builtins.open', mock_open(read_data=config_yaml)):
            retailers = get_enabled_retailers()
            # Should return all retailers (default to enabled)
            assert len(retailers) == len(SCRAPER_REGISTRY)

    def test_handles_missing_config_file(self):
        """Test that missing config file returns all retailers."""
        with patch('builtins.open', side_effect=FileNotFoundError):
            retailers = get_enabled_retailers()
            assert len(retailers) == len(SCRAPER_REGISTRY)

    def test_handles_invalid_yaml(self):
        """Test that invalid YAML returns all retailers."""
        invalid_yaml = "{ this is: [not: valid yaml"
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            retailers = get_enabled_retailers()
            assert len(retailers) == len(SCRAPER_REGISTRY)


class TestGetScraperModule:
    """Tests for get_scraper_module function."""

    def test_returns_module_for_valid_retailer(self):
        """Test that valid retailer returns a module."""
        module = get_scraper_module('verizon')
        assert module is not None
        assert hasattr(module, 'run')

    def test_raises_for_invalid_retailer(self):
        """Test that invalid retailer raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_scraper_module('invalid_retailer')
        assert 'Unknown retailer' in str(exc_info.value)
        assert 'invalid_retailer' in str(exc_info.value)

    def test_all_registered_retailers_can_be_loaded(self):
        """Test that all registered retailers can be loaded."""
        for retailer in SCRAPER_REGISTRY:
            module = get_scraper_module(retailer)
            assert module is not None
            assert hasattr(module, 'run'), f"{retailer} module missing run() function"
